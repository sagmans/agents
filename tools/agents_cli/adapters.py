"""Client adapter metadata validation for Pi and OpenCode role overlays."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from .constants import (
    HEX_COLOR_PATTERN,
    MUTATING_ENGINEER_ROLES,
    OPENCODE_ALLOWED_METADATA_FIELDS,
    PI_ALLOWED_METADATA_FIELDS,
    SAFE_KEY_PATTERN,
    VALID_OPENCODE_MODES,
    VALID_PERMISSION_EFFECTS,
    VALID_PI_ISOLATIONS,
    VALID_PI_MEMORY_SCOPES,
    VALID_PI_PROMPT_MODES,
    VALID_PI_THINKING_LEVELS,
)
from .errors import CatalogValidationError


def _validate_choice(value: Any, allowed: frozenset[str], path: Path, field: str) -> None:
    if value is not None and (not isinstance(value, str) or value not in allowed):
        raise CatalogValidationError(
            "validate adapter metadata",
            path,
            f"{field} must be one of {sorted(allowed)}, got {value!r}",
        )


def _validate_string_list_or_str(
    value: Any, path: Path, field: str, *, allow_bool: bool = False
) -> None:
    if value is None:
        return
    if allow_bool and isinstance(value, bool):
        return
    if isinstance(value, str):
        if not value.strip():
            raise CatalogValidationError("validate metadata", path, f"{field} must not be empty")
        return
    if isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in cast(list[object], value)):
        return
    expected = (
        "must be a boolean, string, or list of strings"
        if allow_bool
        else "must be a string or list of strings"
    )
    raise CatalogValidationError("validate metadata", path, f"{field} {expected}")


def validate_pi_metadata(metadata: dict[str, Any], path: Path) -> None:
    """Enforce allowed Pi role metadata keys and omit hardcoded model bindings."""
    unknown = sorted(set(metadata) - PI_ALLOWED_METADATA_FIELDS)
    if unknown:
        raise CatalogValidationError("validate pi metadata", path, f"disallowed field(s): {', '.join(unknown)}")
    color = metadata.get("color")
    if color is not None and (not isinstance(color, str) or HEX_COLOR_PATTERN.fullmatch(color) is None):
        raise CatalogValidationError("validate pi metadata", path, f"invalid hex color: {color!r}")
    _validate_choice(metadata.get("prompt_mode"), VALID_PI_PROMPT_MODES, path, "prompt_mode")
    _validate_choice(metadata.get("thinking"), VALID_PI_THINKING_LEVELS, path, "thinking")
    _validate_choice(metadata.get("isolation"), VALID_PI_ISOLATIONS, path, "isolation")
    _validate_choice(metadata.get("memory"), VALID_PI_MEMORY_SCOPES, path, "memory")
    _validate_string_list_or_str(metadata.get("skills"), path, "skills", allow_bool=True)
    for field in ("tools", "allowed_subagents", "disallowed_tools"):
        _validate_string_list_or_str(metadata.get(field), path, field)
    session_dir = metadata.get("session_dir")
    if session_dir is not None and (not isinstance(session_dir, str) or not session_dir.strip()):
        raise CatalogValidationError("validate pi metadata", path, "session_dir must be a non-empty string")
    inherit_ctx = metadata.get("inherit_context")
    if inherit_ctx is not None and not isinstance(inherit_ctx, bool):
        raise CatalogValidationError("validate pi metadata", path, "inherit_context must be boolean")
    max_turns = metadata.get("max_turns")
    if max_turns is not None and (isinstance(max_turns, bool) or not isinstance(max_turns, int) or max_turns < 0):
        raise CatalogValidationError("validate pi metadata", path, "max_turns must be >= 0")


def _validate_permission_rule(raw_rule: object, idx: int, path: Path) -> tuple[str, str, str]:
    if not isinstance(raw_rule, dict):
        raise CatalogValidationError("validate opencode metadata", path, f"invalid rule at index {idx}")
    rule = cast(dict[object, object], raw_rule)
    if set(rule) != {"action", "resource", "effect"}:
        raise CatalogValidationError("validate opencode metadata", path, f"invalid rule keys at index {idx}")
    action, resource, effect = rule["action"], rule["resource"], rule["effect"]
    if not isinstance(action, str) or SAFE_KEY_PATTERN.fullmatch(action) is None:
        raise CatalogValidationError("validate opencode metadata", path, f"unsafe permission action at index {idx}")
    if not isinstance(resource, str) or resource != "*":
        raise CatalogValidationError(
            "validate opencode metadata",
            path,
            f"unsupported permission resource {resource!r} at index {idx}; only '*' is supported",
        )
    if not isinstance(effect, str) or effect not in VALID_PERMISSION_EFFECTS:
        raise CatalogValidationError("validate opencode metadata", path, f"invalid effect {effect!r}")
    return action, resource, effect


def _validate_opencode_permissions(role_id: str, permissions: Any, path: Path) -> None:
    if permissions is None:
        if role_id not in MUTATING_ENGINEER_ROLES:
            raise CatalogValidationError("validate opencode metadata", path, "non-mutating role must deny edits")
        return
    if not isinstance(permissions, list) or not permissions:
        raise CatalogValidationError("validate opencode metadata", path, "permissions must be a non-empty list")
    seen_actions: set[str] = set()
    has_wildcard_edit_deny = False
    for idx, raw_rule in enumerate(cast(list[object], permissions)):
        action, resource, effect = _validate_permission_rule(raw_rule, idx, path)
        if action in seen_actions:
            raise CatalogValidationError(
                "validate opencode metadata", path, f"duplicate permission action {action!r}"
            )
        seen_actions.add(action)
        if action == "edit" and resource == "*" and effect == "deny":
            has_wildcard_edit_deny = True
    if role_id not in MUTATING_ENGINEER_ROLES and not has_wildcard_edit_deny:
        raise CatalogValidationError(
            "validate opencode metadata", path, "non-mutating role must deny wildcard edits"
        )


def validate_opencode_metadata(role_id: str, metadata: dict[str, Any], path: Path) -> None:
    """Enforce read-only edit guards on non-mutating roles in OpenCode."""
    unknown = sorted(set(metadata) - OPENCODE_ALLOWED_METADATA_FIELDS)
    if unknown:
        raise CatalogValidationError("validate opencode metadata", path, f"disallowed field(s): {', '.join(unknown)}")
    _validate_choice(metadata.get("mode"), VALID_OPENCODE_MODES, path, "mode")
    _validate_string_list_or_str(metadata.get("tools"), path, "tools")
    temp = metadata.get("temperature")
    if temp is not None and (isinstance(temp, bool) or not isinstance(temp, (int, float))):
        raise CatalogValidationError("validate opencode metadata", path, "temperature must be numeric")
    steps = metadata.get("max_steps")
    if steps is not None and (isinstance(steps, bool) or not isinstance(steps, int) or steps < 1):
        raise CatalogValidationError("validate opencode metadata", path, "max_steps must be >= 1")
    _validate_opencode_permissions(role_id, metadata.get("permissions"), path)


def check_orphan_role_adapters(repo_root: Path, role_ids: set[str]) -> None:
    """Fail closed if an adapter directory exists for a deleted or renamed role."""
    for adapter in ("pi", "opencode"):
        adapter_roles = repo_root / "adapters" / adapter / "roles"
        if not adapter_roles.is_dir():
            continue
        for entry in sorted(adapter_roles.iterdir()):
            if entry.is_dir() and entry.name not in role_ids:
                raise CatalogValidationError(
                    "validate adapter",
                    entry,
                    f"orphan {adapter} role metadata without matching roles/<category>/{entry.name}",
                )
