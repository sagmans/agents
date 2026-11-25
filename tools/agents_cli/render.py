"""Client-specific Markdown frontmatter rendering with user-chosen models from the local config."""

from __future__ import annotations

import json
from typing import Any, cast

from .catalog import RolePackage
from .constants import (
    DEFAULT_OPENCODE_DENY_RULE,
    SUPPORTED_CLIENTS,
    opencode_denies_edits,
)
from .errors import RenderError
from .local_config import EMPTY_CONFIG, LocalConfig, ModelChoice

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


def _render_pi(role: RolePackage, choice: ModelChoice, config: LocalConfig) -> str:
    merged_meta = dict(config.client_metadata.get("pi", {}))
    merged_meta.update(role.pi_metadata)
    if choice.thinking is not None:
        merged_meta["thinking"] = choice.thinking
    pairs: list[tuple[str, Any]] = [
        ("name", role.role_id),
        ("display_name", role.name),
        ("description", role.summary),
    ]
    if choice.model is not None:
        pairs.append(("model", choice.model))
    body = _compose_body(role.definition_body, role.appendices.get("pi"))
    return _render_from_ordered_meta(pairs, merged_meta, _PI_ORDERED_KEYS, body)


def _render_opencode(role: RolePackage, choice: ModelChoice) -> str:
    meta = role.opencode_metadata
    pairs: list[tuple[str, Any]] = [
        ("description", role.summary),
        ("mode", meta.get("mode", "subagent")),
    ]
    if choice.model is not None:
        pairs.append(("model", choice.model))

    raw_perms: Any = meta.get("permissions")
    if raw_perms is None and opencode_denies_edits(role.role_id):
        raw_perms = [DEFAULT_OPENCODE_DENY_RULE]
    raw_lines: list[tuple[str, str]] = []
    if isinstance(raw_perms, list) and raw_perms:
        # OpenCode V2 requires compact `permissions` rule arrays rather than V1 `permission` maps.
        raw_lines.append(("permissions", json.dumps(raw_perms, separators=(",", ":"))))
    body = _compose_body(role.definition_body, role.appendices.get("opencode"))
    return _render_from_ordered_meta(
        pairs, meta, ("tools", "temperature", "max_steps"), body, raw_lines=raw_lines
    )


def _render_generic(role: RolePackage, choice: ModelChoice) -> str:
    pairs: list[tuple[str, Any]] = [
        ("name", role.role_id),
        ("description", role.summary),
    ]
    if choice.model is not None:
        pairs.append(("model", choice.model))
    return _render_from_ordered_meta(pairs, {}, (), role.definition_body)


def render_role_for_client(
    role: RolePackage, client: str, config: LocalConfig = EMPTY_CONFIG
) -> str:
    """Render client-native frontmatter; a model field appears only when the user chose one."""
    if client not in SUPPORTED_CLIENTS:
        raise RenderError("render role", client, f"unsupported client {client!r}")
    if not role.supports(client):
        raise RenderError(
            "render role", role.role_id, f"role does not install into {client}"
        )
    choice = config.resolve(client, role.category, role.role_id)
    if client == "pi":
        return _render_pi(role, choice, config)
    if client == "opencode":
        return _render_opencode(role, choice)
    return _render_generic(role, choice)
