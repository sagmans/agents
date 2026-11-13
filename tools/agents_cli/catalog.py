"""Catalog discovery and fail-closed structural validation for repository assets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .constants import (
    HEX_COLOR_PATTERN,
    ID_PATTERN,
    MAX_ID_LENGTH,
    MUTATING_ENGINEER_ROLES,
    OPENCODE_ALLOWED_METADATA_FIELDS,
    PI_ALLOWED_METADATA_FIELDS,
    REQUIRED_ROLE_SECTIONS,
    SAFE_KEY_PATTERN,
    VALID_OPENCODE_MODES,
    VALID_PERMISSION_EFFECTS,
    VALID_PI_ISOLATIONS,
    VALID_PI_MEMORY_SCOPES,
    VALID_PI_PROMPT_MODES,
    VALID_PI_THINKING_LEVELS,
)
from .errors import CatalogValidationError
from .fs_ops import read_json_object


@dataclass(frozen=True)
class SkillPackage:
    """Validated portable skill directory containing SKILL.md."""

    skill_id: str
    description: str
    path: Path


@dataclass(frozen=True)
class RolePackage:
    """Validated client-neutral role merged with optional client adapter metadata."""

    role_id: str
    name: str
    summary: str
    definition_body: str
    manifest_path: Path
    definition_path: Path
    pi_metadata: dict[str, Any]
    opencode_metadata: dict[str, Any]


@dataclass(frozen=True)
class AssetFile:
    """Generic file-based asset (prompt, command, theme, style, or hook)."""

    asset_id: str
    path: Path
    executable: bool = False


@dataclass(frozen=True)
class Catalog:
    """Complete verified asset catalog loaded from a repository root."""

    repo_root: Path
    skills: dict[str, SkillPackage]
    roles: dict[str, RolePackage]
    prompts: dict[str, AssetFile]
    opencode_commands: dict[str, AssetFile]
    themes: dict[str, AssetFile]
    claude_styles: dict[str, AssetFile]
    claude_hooks: dict[str, AssetFile]


@dataclass(frozen=True)
class ValidationReport:
    """Summary counts emitted by `setup validate`."""

    skills_count: int
    roles_count: int
    prompts_count: int
    commands_count: int
    themes_count: int
    styles_count: int
    hooks_count: int


def _read_catalog_json(path: Path, context: str) -> dict[str, Any]:
    return read_json_object(path, context, lambda op, p, msg: CatalogValidationError(op, p, msg))


def _read_utf8_text(path: Path, context: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CatalogValidationError(context, path, f"unreadable UTF-8 file: {exc}") from exc


def _validate_contained_path(path: Path, repo_root: Path, context: str) -> None:
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise CatalogValidationError(context, path, f"unresolvable path: {exc}") from exc
    if resolved != repo_root and repo_root not in resolved.parents:
        raise CatalogValidationError(context, path, "symlink escapes repository root")


def _validate_id(value: Any, path: Path, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_ID_LENGTH
        or ID_PATTERN.fullmatch(value) is None
    ):
        raise CatalogValidationError(
            f"validate {label}",
            path,
            f"invalid identifier {value!r} (must start with lowercase alphanumeric; hyphens and underscores allowed)",
        )
    return value


def _extract_frontmatter(text: str, path: Path) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise CatalogValidationError("validate skill", path, "missing YAML frontmatter")
    end_index: int | None = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_index = idx
            break
    if end_index is None:
        raise CatalogValidationError("validate skill", path, "unterminated YAML frontmatter")
    fields = _parse_simple_frontmatter(lines[1:end_index], path)
    body = "\n".join(lines[end_index + 1 :]).strip() + "\n"
    return fields, body


def _parse_simple_frontmatter(lines: list[str], path: Path) -> dict[str, str]:
    """Avoid runtime PyYAML dependency while extracting folded single-level keys."""
    fields: dict[str, str] = {}
    current_key: str | None = None
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw.startswith((" ", "\t")) and current_key is not None:
            fields[current_key] = f"{fields[current_key]} {stripped}".strip()
            continue
        if ":" not in raw:
            raise CatalogValidationError("validate skill", path, f"malformed header line: {raw!r}")
        key, val = raw.split(":", 1)
        clean_key = key.strip()
        clean_val = val.strip().strip("'\"")
        fields[clean_key] = clean_val
        current_key = clean_key
    return fields


def _validate_skill_dir(skill_dir: Path, repo_root: Path) -> SkillPackage:
    _validate_contained_path(skill_dir, repo_root, "validate skill")
    skill_id = _validate_id(skill_dir.name, skill_dir, "skill")
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise CatalogValidationError("validate skill", skill_md, "missing SKILL.md")
    fields, _ = _extract_frontmatter(_read_utf8_text(skill_md, "validate skill"), skill_md)
    fm_name = fields.get("name", "")
    if fm_name != skill_id:
        raise CatalogValidationError(
            "validate skill",
            skill_md,
            f"frontmatter name {fm_name!r} must match directory {skill_id!r}",
        )
    description = fields.get("description", "").strip()
    if not description:
        raise CatalogValidationError("validate skill", skill_md, "frontmatter description is empty")
    return SkillPackage(skill_id=skill_id, description=description, path=skill_dir)


def _validate_role_definition(definition_path: Path) -> str:
    if not definition_path.is_file():
        raise CatalogValidationError("validate role", definition_path, "missing DEFINITION.md")
    text = _read_utf8_text(definition_path, "validate role")
    headings = {
        m.group(1).strip()
        for m in re.finditer(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE)
    }
    missing = [sec for sec in REQUIRED_ROLE_SECTIONS if sec not in headings]
    if missing:
        raise CatalogValidationError(
            "validate role",
            definition_path,
            f"missing required sections: {', '.join(missing)}",
        )
    return text.strip() + "\n"


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


def _validate_pi_metadata(metadata: dict[str, Any], path: Path) -> None:
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


def _validate_opencode_metadata(role_id: str, metadata: dict[str, Any], path: Path) -> None:
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


def _load_role_dir(repo_root: Path, role_dir: Path) -> RolePackage:
    _validate_contained_path(role_dir, repo_root, "validate role")
    role_id = _validate_id(role_dir.name, role_dir, "role")
    manifest_path = role_dir / "manifest.json"
    definition_path = role_dir / "DEFINITION.md"
    if not manifest_path.is_file():
        raise CatalogValidationError("validate role", manifest_path, "missing manifest.json")
    manifest = _read_catalog_json(manifest_path, "validate role manifest")
    if manifest.get("id") != role_id:
        raise CatalogValidationError("validate role", manifest_path, f"manifest id must match {role_id!r}")
    name, summary = manifest.get("name"), manifest.get("summary")
    if not isinstance(name, str) or not name.strip():
        raise CatalogValidationError("validate role", manifest_path, "manifest name must be non-empty")
    if not isinstance(summary, str) or not summary.strip():
        raise CatalogValidationError("validate role", manifest_path, "manifest summary must be non-empty")
    body = _validate_role_definition(definition_path)

    pi_meta: dict[str, Any] = {}
    pi_path = repo_root / "adapters" / "pi" / "roles" / role_id / "metadata.json"
    if pi_path.exists():
        pi_meta = _read_catalog_json(pi_path, "validate pi metadata")
        _validate_pi_metadata(pi_meta, pi_path)

    oc_meta: dict[str, Any] = {}
    oc_path = repo_root / "adapters" / "opencode" / "roles" / role_id / "metadata.json"
    if oc_path.exists():
        oc_meta = _read_catalog_json(oc_path, "validate opencode metadata")
        _validate_opencode_metadata(role_id, oc_meta, oc_path)

    return RolePackage(
        role_id=role_id,
        name=name.strip(),
        summary=summary.strip(),
        definition_body=body,
        manifest_path=manifest_path,
        definition_path=definition_path,
        pi_metadata=pi_meta,
        opencode_metadata=oc_meta,
    )


def _check_orphan_role_adapters(repo_root: Path, role_ids: set[str]) -> None:
    for adapter in ("pi", "opencode"):
        adapter_roles = repo_root / "adapters" / adapter / "roles"
        if not adapter_roles.is_dir():
            continue
        for entry in sorted(adapter_roles.iterdir()):
            if entry.is_dir() and entry.name not in role_ids:
                raise CatalogValidationError(
                    "validate adapter",
                    entry,
                    f"orphan {adapter} role metadata without matching roles/{entry.name}",
                )


def _load_asset_files(
    directory: Path,
    repo_root: Path,
    suffix: str,
    *,
    executable: bool = False,
    validate_json: bool = False,
) -> dict[str, AssetFile]:
    assets: dict[str, AssetFile] = {}
    if not directory.is_dir():
        return assets
    for entry in sorted(directory.iterdir()):
        if not entry.is_file() or entry.suffix != suffix:
            continue
        _validate_contained_path(entry, repo_root, f"validate {suffix} asset")
        asset_id = _validate_id(entry.stem, entry, f"{suffix} asset")
        if validate_json:
            _read_catalog_json(entry, f"validate {suffix} asset")
        else:
            _read_utf8_text(entry, f"validate {suffix} asset")
        assets[asset_id] = AssetFile(asset_id=asset_id, path=entry, executable=executable)
    return assets


def load_catalog(repo_root: Path, *, strict_nonempty: bool = False) -> Catalog:
    """Load and validate every catalog section under `repo_root`."""
    resolved_root = repo_root.resolve()
    skills: dict[str, SkillPackage] = {}
    skills_dir = resolved_root / "skills"
    if skills_dir.is_dir():
        for entry in sorted(skills_dir.iterdir()):
            if entry.is_dir():
                pkg = _validate_skill_dir(entry, resolved_root)
                skills[pkg.skill_id] = pkg

    roles: dict[str, RolePackage] = {}
    roles_dir = resolved_root / "roles"
    if roles_dir.is_dir():
        for entry in sorted(roles_dir.iterdir()):
            if entry.is_dir():
                role = _load_role_dir(resolved_root, entry)
                roles[role.role_id] = role

    _check_orphan_role_adapters(resolved_root, set(roles))
    if strict_nonempty and (not skills or not roles):
        raise CatalogValidationError(
            "validate catalog",
            resolved_root,
            f"strict mode requires skills and roles (found {len(skills)} skills, {len(roles)} roles)",
        )

    return Catalog(
        repo_root=resolved_root,
        skills=skills,
        roles=roles,
        prompts=_load_asset_files(resolved_root / "prompts", resolved_root, ".md"),
        opencode_commands=_load_asset_files(
            resolved_root / "adapters" / "opencode" / "commands", resolved_root, ".md"
        ),
        themes=_load_asset_files(resolved_root / "themes", resolved_root, ".json", validate_json=True),
        claude_styles=_load_asset_files(
            resolved_root / "adapters" / "claude" / "output-styles", resolved_root, ".md"
        ),
        claude_hooks=_load_asset_files(
            resolved_root / "adapters" / "claude" / "hooks", resolved_root, ".sh", executable=True
        ),
    )


def validate_catalog(repo_root: Path, *, strict_nonempty: bool = False) -> ValidationReport:
    """Validate all catalog assets and return summary counts."""
    catalog = load_catalog(repo_root, strict_nonempty=strict_nonempty)
    return ValidationReport(
        skills_count=len(catalog.skills),
        roles_count=len(catalog.roles),
        prompts_count=len(catalog.prompts),
        commands_count=len(catalog.opencode_commands),
        themes_count=len(catalog.themes),
        styles_count=len(catalog.claude_styles),
        hooks_count=len(catalog.claude_hooks),
    )
