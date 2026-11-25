"""Catalog discovery and fail-closed structural validation for repository assets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters import (
    check_orphan_role_adapters,
    validate_opencode_metadata,
    validate_pi_metadata,
)
from .constants import (
    ID_PATTERN,
    MAX_ID_LENGTH,
    MAX_ROLE_DEFINITION_LINES,
    MAX_ROLE_SUMMARY_CHARS,
    MAX_ROLE_WORKFLOW_STEPS,
    MIN_ROLE_WORKFLOW_STEPS,
    REQUIRED_ROLE_SECTIONS,
    ROLE_MANIFEST_ALLOWED_FIELDS,
    ROLE_SUMMARY_PREFIXES,
    VALID_CATEGORIES,
    role_guardrail,
)
from .errors import CatalogValidationError
from .fs_ops import read_json_object
from .packs import CategoryPack, load_packs


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
    category: str
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
    packs: dict[str, CategoryPack]
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

    packs_count: int
    skills_count: int
    roles_count: int
    prompts_count: int
    commands_count: int
    themes_count: int
    styles_count: int
    hooks_count: int


def _read_catalog_json(path: Path, context: str) -> dict[str, Any]:
    return read_json_object(
        path, context, lambda op, p, msg: CatalogValidationError(op, p, msg)
    )


def _read_utf8_text(path: Path, context: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CatalogValidationError(
            context, path, f"unreadable UTF-8 file: {exc}"
        ) from exc


def _validate_contained_path(path: Path, repo_root: Path, context: str) -> None:
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise CatalogValidationError(
            context, path, f"unresolvable path: {exc}"
        ) from exc
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
        raise CatalogValidationError(
            "validate skill", path, "unterminated YAML frontmatter"
        )
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
            raise CatalogValidationError(
                "validate skill", path, f"malformed header line: {raw!r}"
            )
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
    fields, _ = _extract_frontmatter(
        _read_utf8_text(skill_md, "validate skill"), skill_md
    )
    fm_name = fields.get("name", "")
    if fm_name != skill_id:
        raise CatalogValidationError(
            "validate skill",
            skill_md,
            f"frontmatter name {fm_name!r} must match directory {skill_id!r}",
        )
    description = fields.get("description", "").strip()
    if not description:
        raise CatalogValidationError(
            "validate skill", skill_md, "frontmatter description is empty"
        )
    return SkillPackage(skill_id=skill_id, description=description, path=skill_dir)


# Any bullet that reads as a stance (bold or not, hyphenated or not) counts, so a second
# restatement cannot slip past the one-stance-line rule by changing its markup.
STANCE_LINE_PATTERN = re.compile(
    r"^- (stance:|report[- ]only|read[- ]only)", re.IGNORECASE
)


def _role_sections(text: str) -> list[tuple[str, str]]:
    """Split a definition into (heading, body) pairs, ignoring headings inside fenced templates."""
    unfenced = re.sub(r"^```.*?^```[ \t]*$", "", text, flags=re.MULTILINE | re.DOTALL)
    parts = re.split(r"^##[ \t]+(.+?)[ \t]*$", unfenced, flags=re.MULTILINE)
    return [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]


def _validate_role_definition(definition_path: Path, role_id: str) -> str:
    if not definition_path.is_file():
        raise CatalogValidationError(
            "validate role", definition_path, "missing DEFINITION.md"
        )
    text = _read_utf8_text(definition_path, "validate role")
    if not text.startswith("# "):
        raise CatalogValidationError(
            "validate role", definition_path, "must start with an H1 title"
        )
    sections = _role_sections(text)
    headings = tuple(name for name, _ in sections)
    if headings != REQUIRED_ROLE_SECTIONS:
        raise CatalogValidationError(
            "validate role",
            definition_path,
            f"sections must be exactly {', '.join(REQUIRED_ROLE_SECTIONS)} in order; found {', '.join(headings) or 'none'}",
        )
    bodies = dict(sections)
    steps = len(re.findall(r"^\d+\.\s", bodies["Workflow"], flags=re.MULTILINE))
    if not MIN_ROLE_WORKFLOW_STEPS <= steps <= MAX_ROLE_WORKFLOW_STEPS:
        raise CatalogValidationError(
            "validate role",
            definition_path,
            f"Workflow has {steps} steps; expected {MIN_ROLE_WORKFLOW_STEPS}-{MAX_ROLE_WORKFLOW_STEPS}",
        )
    guardrail = role_guardrail(role_id)
    stance_lines = [
        line
        for line in bodies["Rules"].splitlines()
        if STANCE_LINE_PATTERN.match(line.replace("*", "").replace("_", ""))
    ]
    if stance_lines != [guardrail]:
        raise CatalogValidationError(
            "validate role",
            definition_path,
            f"Rules must state the stance once, verbatim: {guardrail}",
        )
    line_count = len(text.strip().splitlines())
    if line_count > MAX_ROLE_DEFINITION_LINES:
        raise CatalogValidationError(
            "validate role",
            definition_path,
            f"{line_count} lines exceeds the {MAX_ROLE_DEFINITION_LINES}-line limit",
        )
    return text.strip() + "\n"


def _load_role_dir(
    repo_root: Path, role_dir: Path, expected_category: str
) -> RolePackage:
    _validate_contained_path(role_dir, repo_root, "validate role")
    role_id = _validate_id(role_dir.name, role_dir, "role")
    manifest_path = role_dir / "manifest.json"
    definition_path = role_dir / "DEFINITION.md"
    if not manifest_path.is_file():
        raise CatalogValidationError(
            "validate role", manifest_path, "missing manifest.json"
        )
    manifest = _read_catalog_json(manifest_path, "validate role manifest")
    unknown = sorted(set(manifest) - ROLE_MANIFEST_ALLOWED_FIELDS)
    if unknown:
        raise CatalogValidationError(
            "validate role",
            manifest_path,
            f"disallowed manifest field(s): {', '.join(unknown)}",
        )
    if manifest.get("id") != role_id:
        raise CatalogValidationError(
            "validate role", manifest_path, f"manifest id must match {role_id!r}"
        )
    if manifest.get("category") != expected_category:
        raise CatalogValidationError(
            "validate role",
            manifest_path,
            f"manifest category {manifest.get('category')!r} must match directory {expected_category!r}",
        )
    name, summary = manifest.get("name"), manifest.get("summary")
    if not isinstance(name, str) or not name.strip():
        raise CatalogValidationError(
            "validate role", manifest_path, "manifest name must be non-empty"
        )
    if not isinstance(summary, str) or not summary.strip():
        raise CatalogValidationError(
            "validate role", manifest_path, "manifest summary must be non-empty"
        )
    if (
        not summary.startswith(ROLE_SUMMARY_PREFIXES)
        or len(summary) > MAX_ROLE_SUMMARY_CHARS
    ):
        raise CatalogValidationError(
            "validate role",
            manifest_path,
            f"summary must start with one of {ROLE_SUMMARY_PREFIXES} and be at most {MAX_ROLE_SUMMARY_CHARS} characters",
        )
    body = _validate_role_definition(definition_path, role_id)

    pi_meta: dict[str, Any] = {}
    pi_path = repo_root / "adapters" / "pi" / "roles" / role_id / "metadata.json"
    if pi_path.exists():
        pi_meta = _read_catalog_json(pi_path, "validate pi metadata")
        validate_pi_metadata(pi_meta, pi_path)

    oc_meta: dict[str, Any] = {}
    oc_path = repo_root / "adapters" / "opencode" / "roles" / role_id / "metadata.json"
    if oc_path.exists():
        oc_meta = _read_catalog_json(oc_path, "validate opencode metadata")
        validate_opencode_metadata(role_id, oc_meta, oc_path)

    return RolePackage(
        role_id=role_id,
        category=expected_category,
        name=name.strip(),
        summary=summary.strip(),
        definition_body=body,
        manifest_path=manifest_path,
        definition_path=definition_path,
        pi_metadata=pi_meta,
        opencode_metadata=oc_meta,
    )


def _load_roles_tree(resolved_root: Path) -> dict[str, RolePackage]:
    """Enforce `roles/<category>/<id>/` hierarchy and globally unique role IDs."""
    roles: dict[str, RolePackage] = {}
    roles_dir = resolved_root / "roles"
    if not roles_dir.is_dir():
        return roles
    allowed_cats = frozenset(VALID_CATEGORIES)
    for cat_entry in sorted(roles_dir.iterdir()):
        if not cat_entry.is_dir() or cat_entry.name not in allowed_cats:
            raise CatalogValidationError(
                "validate role category",
                cat_entry,
                f"roles must reside under roles/<category>/<id>/ using {list(VALID_CATEGORIES)}",
            )
        _validate_contained_path(cat_entry, resolved_root, "validate role category")
        for role_entry in sorted(cat_entry.iterdir()):
            if not role_entry.is_dir():
                raise CatalogValidationError(
                    "validate role",
                    role_entry,
                    "unexpected file inside role category directory",
                )
            role = _load_role_dir(resolved_root, role_entry, cat_entry.name)
            if role.role_id in roles:
                raise CatalogValidationError(
                    "validate role",
                    role_entry,
                    f"duplicate role ID {role.role_id!r} across categories",
                )
            roles[role.role_id] = role
    return roles


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
        assets[asset_id] = AssetFile(
            asset_id=asset_id, path=entry, executable=executable
        )
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

    roles = _load_roles_tree(resolved_root)
    check_orphan_role_adapters(resolved_root, set(roles))
    if strict_nonempty and (not skills or not roles):
        raise CatalogValidationError(
            "validate catalog",
            resolved_root,
            f"strict mode requires skills and roles (found {len(skills)} skills, {len(roles)} roles)",
        )

    prompts = _load_asset_files(resolved_root / "prompts", resolved_root, ".md")
    opencode_commands = _load_asset_files(
        resolved_root / "adapters" / "opencode" / "commands", resolved_root, ".md"
    )
    packs = load_packs(
        resolved_root,
        skills_map=skills,
        role_categories={rid: r.category for rid, r in roles.items()},
        prompts_map=prompts,
        commands_map=opencode_commands,
        strict_nonempty=strict_nonempty,
    )

    return Catalog(
        repo_root=resolved_root,
        packs=packs,
        skills=skills,
        roles=roles,
        prompts=prompts,
        opencode_commands=opencode_commands,
        themes=_load_asset_files(
            resolved_root / "themes", resolved_root, ".json", validate_json=True
        ),
        claude_styles=_load_asset_files(
            resolved_root / "adapters" / "claude" / "output-styles",
            resolved_root,
            ".md",
        ),
        claude_hooks=_load_asset_files(
            resolved_root / "adapters" / "claude" / "hooks",
            resolved_root,
            ".sh",
            executable=True,
        ),
    )


def validate_catalog(
    repo_root: Path, *, strict_nonempty: bool = False
) -> ValidationReport:
    """Validate all catalog assets and return summary counts."""
    catalog = load_catalog(repo_root, strict_nonempty=strict_nonempty)
    return ValidationReport(
        packs_count=len(catalog.packs),
        skills_count=len(catalog.skills),
        roles_count=len(catalog.roles),
        prompts_count=len(catalog.prompts),
        commands_count=len(catalog.opencode_commands),
        themes_count=len(catalog.themes),
        styles_count=len(catalog.claude_styles),
        hooks_count=len(catalog.claude_hooks),
    )
