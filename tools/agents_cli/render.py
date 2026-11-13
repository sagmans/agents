"""Client-specific Markdown frontmatter rendering and optional model mapping."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from .catalog import RolePackage
from .constants import DEFAULT_OPENCODE_DENY_RULE, MUTATING_ENGINEER_ROLES, SUPPORTED_CLIENTS
from .errors import RenderError
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


@dataclass(frozen=True)
class ModelMap:
    """User-supplied role-to-model bindings loaded only when `--model-map` is given."""

    defaults: dict[str, str] = field(default_factory=dict)
    roles: dict[str, str] = field(default_factory=dict)
    source: Path | None = None

    def resolve(self, client: str, role_id: str) -> str | None:
        """Resolve role-specific override first, then client default."""
        role_key = f"{client}:{role_id}"
        if role_key in self.roles:
            return self.roles[role_key]
        if role_id in self.roles:
            return self.roles[role_id]
        return self.defaults.get(client)


def _validate_model_map_section(
    raw: Any, section: str, path: Path, *, check_clients: bool, allow_prefixed: bool
) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise RenderError("load model map", path, f"{section} must be a JSON object")
    out: dict[str, str] = {}
    for k, v in cast(dict[object, object], raw).items():
        if not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip():
            raise RenderError(
                "load model map", path, f"{section} keys and values must be non-empty strings"
            )
        clean_k = k.strip()
        if check_clients and clean_k not in SUPPORTED_CLIENTS:
            raise RenderError("load model map", path, f"unknown client in defaults: {clean_k!r}")
        if allow_prefixed and ":" in clean_k:
            prefix, role_part = clean_k.split(":", 1)
            if prefix not in SUPPORTED_CLIENTS or not role_part.strip():
                raise RenderError("load model map", path, f"invalid scoped role key: {clean_k!r}")
        out[clean_k] = v.strip()
    return out


def load_model_map(path: Path | None) -> ModelMap:
    """Load an optional JSON model mapping file without mutating repository defaults."""
    if path is None:
        return ModelMap()
    expanded = path.expanduser()
    if not expanded.is_file():
        raise RenderError("load model map", expanded, "model-map file does not exist")
    data = read_json_object(
        expanded, "load model map", lambda op, p, msg: RenderError(op, p, msg)
    )
    allowed = {"defaults", "roles", "$schema", "description"}
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise RenderError(
            "load model map", expanded, f"unsupported top-level key(s): {', '.join(unknown)}"
        )
    return ModelMap(
        defaults=_validate_model_map_section(
            data.get("defaults"), "defaults", expanded, check_clients=True, allow_prefixed=False
        ),
        roles=_validate_model_map_section(
            data.get("roles"), "roles", expanded, check_clients=False, allow_prefixed=True
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
    raise RenderError("render role", None, f"unsupported scalar metadata type: {type(value).__name__}")


def _format_yaml_value(value: Any) -> str:
    if isinstance(value, list):
        items = ", ".join(_format_scalar(item) for item in cast(list[object], value))
        return f"[{items}]"
    return _format_scalar(value)


def _emit_frontmatter(
    pairs: list[tuple[str, Any]], nested: dict[str, dict[str, str]] | None = None
) -> str:
    lines: list[str] = ["---"]
    for key, val in pairs:
        if val is not None:
            lines.append(f"{key}: {_format_yaml_value(val)}")
    if nested:
        for block_key, mapping in nested.items():
            if not mapping:
                continue
            lines.append(f"{block_key}:")
            for sub_key, sub_val in mapping.items():
                lines.append(f"  {_yaml_quote(sub_key)}: {_yaml_quote(sub_val)}")
    lines.append("---")
    return "\n".join(lines)


def _render_from_ordered_meta(
    pairs: list[tuple[str, Any]],
    meta: dict[str, Any],
    ordered_keys: tuple[str, ...],
    body: str,
    *,
    nested: dict[str, dict[str, str]] | None = None,
) -> str:
    full_pairs = list(pairs)
    for key in ordered_keys:
        if key in meta:
            full_pairs.append((key, meta[key]))
    return f"{_emit_frontmatter(full_pairs, nested=nested)}\n\n{body}"


def _render_pi(role: RolePackage, model: str | None) -> str:
    ordered_keys = (
        "tools",
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
    pairs: list[tuple[str, Any]] = [("name", role.role_id), ("description", role.summary)]
    if model is not None:
        pairs.append(("model", model))
    return _render_from_ordered_meta(pairs, role.pi_metadata, ordered_keys, role.definition_body)


def _render_opencode(role: RolePackage, model: str | None) -> str:
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
    perm_map: dict[str, str] = {}
    if isinstance(raw_perms, list):
        for raw_rule in cast(list[object], raw_perms):
            if isinstance(raw_rule, dict):
                rule = cast(dict[str, object], raw_rule)
                perm_map[str(rule["action"])] = str(rule["effect"])
    nested = {"permission": perm_map} if perm_map else None
    return _render_from_ordered_meta(
        pairs, meta, ("tools", "temperature", "max_steps"), role.definition_body, nested=nested
    )


def _render_generic(role: RolePackage, model: str | None) -> str:
    pairs: list[tuple[str, Any]] = [("name", role.role_id), ("description", role.summary)]
    if model is not None:
        pairs.append(("model", model))
    return _render_from_ordered_meta(pairs, {}, (), role.definition_body)


def render_role_for_client(
    role: RolePackage, client: str, model_map: ModelMap | None = None
) -> str:
    """Render a role definition with client-native frontmatter and zero hardcoded models."""
    if client not in SUPPORTED_CLIENTS:
        raise RenderError("render role", client, f"unsupported client {client!r}")
    model = model_map.resolve(client, role.role_id) if model_map else None
    if client == "pi":
        return _render_pi(role, model)
    if client == "opencode":
        return _render_opencode(role, model)
    return _render_generic(role, model)
