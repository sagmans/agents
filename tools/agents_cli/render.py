"""Client-specific Markdown frontmatter rendering and optional model/runtime overlays."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from .adapters import validate_pi_metadata
from .catalog import RolePackage
from .constants import (
    DEFAULT_OPENCODE_DENY_RULE,
    MUTATING_ENGINEER_ROLES,
    SUPPORTED_CLIENTS,
)
from .errors import CatalogValidationError, RenderError
from .fs_ops import read_json_object

# Control characters that could split YAML scalar strings across lines or directives.
_YAML_ESCAPES: dict[int, str] = {
    ord("\\"): "\\\\",
    ord('"'): '\\"',
    ord("\n"): "\\n",
    ord("\r"): "\\r",
    ord("\t"): "\\t",
    0x0085: "\\u0085",
    0x2028: "\\u2028",
    0x2029: "\\u2029",
}

_MODEL_MAP_ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "defaults",
        "roles",
        "client_metadata",
        "role_appendices",
        "$schema",
        "description",
    }
)

_PI_ORDERED_KEYS: tuple[str, ...] = (
    "tools",
    "extensions",
    "exclude_extensions",
    "skills",
    "color",
    "prompt_mode",
    "thinking",
    "max_turns",
    "isolation",
    "memory",
    "allowed_subagents",
    "session_dir",
    "disallowed_tools",
    "inherit_context",
)


@dataclass(frozen=True)
class ModelMap:
    """User-supplied role-to-model and local runtime bindings loaded via `--model-map`."""

    defaults: dict[str, str] = field(default_factory=dict[str, str])
    roles: dict[str, str] = field(default_factory=dict[str, str])
    client_metadata: dict[str, dict[str, Any]] = field(
        default_factory=dict[str, dict[str, Any]]
    )
    role_appendices: dict[str, str] = field(default_factory=dict[str, str])
    source: Path | None = None

    def resolve(self, client: str, role_id: str) -> str | None:
        """Resolve role-specific model override first, then client default."""
        role_key = f"{client}:{role_id}"
        if role_key in self.roles:
            return self.roles[role_key]
        if role_id in self.roles:
            return self.roles[role_id]
        return self.defaults.get(client)

    def resolve_appendix(self, client: str, role_id: str) -> str | None:
        """Resolve optional local runtime instructions appended below `DEFINITION.md`."""
        role_key = f"{client}:{role_id}"
        if role_key in self.role_appendices:
            return self.role_appendices[role_key]
        return self.role_appendices.get(role_id)


def _validate_model_map_section(
    raw: Any, section: str, path: Path, *, check_clients: bool, allow_prefixed: bool
) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise RenderError("load model map", path, f"{section} must be a JSON object")
    out: dict[str, str] = {}
    for k, v in cast(dict[object, object], raw).items():
        if (
            not isinstance(k, str)
            or not k.strip()
            or not isinstance(v, str)
            or not v.strip()
        ):
            raise RenderError(
                "load model map",
                path,
                f"{section} keys and values must be non-empty strings",
            )
        clean_k = k.strip()
        if check_clients and clean_k not in SUPPORTED_CLIENTS:
            raise RenderError(
                "load model map", path, f"unknown client in {section}: {clean_k!r}"
            )
        if allow_prefixed and ":" in clean_k:
            prefix, role_part = clean_k.split(":", 1)
            if prefix not in SUPPORTED_CLIENTS or not role_part.strip():
                raise RenderError(
                    "load model map", path, f"invalid scoped role key: {clean_k!r}"
                )
        out[clean_k] = v.strip()
    return out


def _validate_client_metadata(raw: Any, path: Path) -> dict[str, dict[str, Any]]:
    """Validate optional client-wide metadata defaults (such as Pi extension exclusions)."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise RenderError(
            "load model map", path, "client_metadata must be a JSON object"
        )
    out: dict[str, dict[str, Any]] = {}
    for client, meta in cast(dict[object, object], raw).items():
        if (
            not isinstance(client, str)
            or client not in SUPPORTED_CLIENTS
            or not isinstance(meta, dict)
        ):
            raise RenderError(
                "load model map", path, f"invalid client_metadata entry for {client!r}"
            )
        typed_meta = {str(mk): mv for mk, mv in cast(dict[object, Any], meta).items()}
        if client == "pi":
            try:
                validate_pi_metadata(typed_meta, path)
            except CatalogValidationError as exc:
                raise RenderError("load model map", path, exc.reason) from exc
        elif typed_meta:
            raise RenderError(
                "load model map",
                path,
                f"client_metadata is only supported for pi, got {client!r}",
            )
        out[client] = typed_meta
    return out


def _validate_role_appendices(raw: Any, path: Path) -> dict[str, str]:
    """Reject frontmatter injection inside local Markdown appendices."""
    parsed = _validate_model_map_section(
        raw, "role_appendices", path, check_clients=False, allow_prefixed=True
    )
    for key, body in parsed.items():
        if body.lstrip().startswith("---"):
            raise RenderError(
                "load model map",
                path,
                f"role_appendices[{key!r}] must not start with YAML frontmatter",
            )
    return parsed


def load_model_map(path: Path | None) -> ModelMap:
    """Load an optional JSON model and runtime overlay without mutating repository defaults."""
    if path is None:
        return ModelMap()
    expanded = path.expanduser()
    if not expanded.is_file():
        raise RenderError("load model map", expanded, "model-map file does not exist")
    data = read_json_object(
        expanded, "load model map", lambda op, p, msg: RenderError(op, p, msg)
    )
    unknown = sorted(set(data) - _MODEL_MAP_ALLOWED_KEYS)
    if unknown:
        raise RenderError(
            "load model map",
            expanded,
            f"unsupported top-level key(s): {', '.join(unknown)}",
        )
    return ModelMap(
        defaults=_validate_model_map_section(
            data.get("defaults"),
            "defaults",
            expanded,
            check_clients=True,
            allow_prefixed=False,
        ),
        roles=_validate_model_map_section(
            data.get("roles"),
            "roles",
            expanded,
            check_clients=False,
            allow_prefixed=True,
        ),
        client_metadata=_validate_client_metadata(
            data.get("client_metadata"), expanded
        ),
        role_appendices=_validate_role_appendices(
            data.get("role_appendices"), expanded
        ),
        source=expanded,
    )


def _yaml_quote(value: str) -> str:
    """Escape control characters and line separators so arbitrary metadata stays single-line."""
    escaped: list[str] = []
    for ch in value:
        code = ord(ch)
        if code in _YAML_ESCAPES:
            escaped.append(_YAML_ESCAPES[code])
        elif code < 0x20 or (0x7F <= code <= 0x9F):
            escaped.append(f"\\u{code:04x}")
        else:
            escaped.append(ch)
    return f'"{"".join(escaped)}"'


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return _yaml_quote(value)
    raise RenderError(
        "render role", None, f"unsupported scalar metadata type: {type(value).__name__}"
    )


def _format_yaml_value(value: Any) -> str:
    if isinstance(value, list):
        items = ", ".join(_format_scalar(item) for item in cast(list[object], value))
        return f"[{items}]"
    return _format_scalar(value)


def _emit_frontmatter(
    pairs: list[tuple[str, Any]], raw_lines: list[tuple[str, str]] | None = None
) -> str:
    lines: list[str] = ["---"]
    for key, val in pairs:
        if val is not None:
            lines.append(f"{key}: {_format_yaml_value(val)}")
    if raw_lines:
        for raw_key, raw_val in raw_lines:
            lines.append(f"{raw_key}: {raw_val}")
    lines.append("---")
    return "\n".join(lines)


def _compose_body(definition_body: str, appendix: str | None) -> str:
    if not appendix:
        return definition_body
    return f"{definition_body.rstrip()}\n\n{appendix.strip()}\n"


def _render_from_ordered_meta(
    pairs: list[tuple[str, Any]],
    meta: dict[str, Any],
    ordered_keys: tuple[str, ...],
    body: str,
    *,
    raw_lines: list[tuple[str, str]] | None = None,
) -> str:
    full_pairs = list(pairs)
    for key in ordered_keys:
        if key in meta:
            full_pairs.append((key, meta[key]))
    return f"{_emit_frontmatter(full_pairs, raw_lines=raw_lines)}\n\n{body}"


def _render_pi(role: RolePackage, model: str | None, overlay: ModelMap | None) -> str:
    merged_meta = dict(overlay.client_metadata.get("pi", {})) if overlay else {}
    merged_meta.update(role.pi_metadata)
    pairs: list[tuple[str, Any]] = [
        ("name", role.role_id),
        ("display_name", role.name),
        ("description", role.summary),
    ]
    if model is not None:
        pairs.append(("model", model))
    body = _compose_body(
        role.definition_body,
        overlay.resolve_appendix("pi", role.role_id) if overlay else None,
    )
    return _render_from_ordered_meta(pairs, merged_meta, _PI_ORDERED_KEYS, body)


def _render_opencode(
    role: RolePackage, model: str | None, overlay: ModelMap | None
) -> str:
    meta = role.opencode_metadata
    pairs: list[tuple[str, Any]] = [
        ("description", role.summary),
        ("mode", meta.get("mode", "subagent")),
    ]
    if model is not None:
        pairs.append(("model", model))

    raw_perms: Any = meta.get("permissions")
    if raw_perms is None and role.role_id not in MUTATING_ENGINEER_ROLES:
        raw_perms = [DEFAULT_OPENCODE_DENY_RULE]
    raw_lines: list[tuple[str, str]] = []
    if isinstance(raw_perms, list) and raw_perms:
        # OpenCode V2 requires compact `permissions` rule arrays rather than V1 `permission` maps.
        raw_lines.append(("permissions", json.dumps(raw_perms, separators=(",", ":"))))
    body = _compose_body(
        role.definition_body,
        overlay.resolve_appendix("opencode", role.role_id) if overlay else None,
    )
    return _render_from_ordered_meta(
        pairs, meta, ("tools", "temperature", "max_steps"), body, raw_lines=raw_lines
    )


def _render_generic(
    role: RolePackage, client: str, model: str | None, overlay: ModelMap | None
) -> str:
    pairs: list[tuple[str, Any]] = [
        ("name", role.role_id),
        ("description", role.summary),
    ]
    if model is not None:
        pairs.append(("model", model))
    body = _compose_body(
        role.definition_body,
        overlay.resolve_appendix(client, role.role_id) if overlay else None,
    )
    return _render_from_ordered_meta(pairs, {}, (), body)


def render_role_for_client(
    role: RolePackage, client: str, model_map: ModelMap | None = None
) -> str:
    """Render a role definition with client-native frontmatter and zero hardcoded models."""
    if client not in SUPPORTED_CLIENTS:
        raise RenderError("render role", client, f"unsupported client {client!r}")
    model = model_map.resolve(client, role.role_id) if model_map else None
    if client == "pi":
        return _render_pi(role, model, model_map)
    if client == "opencode":
        return _render_opencode(role, model, model_map)
    return _render_generic(role, client, model, model_map)
