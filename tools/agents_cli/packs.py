"""Declarative category pack loading, cross-catalog partition checks, and expansion."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .constants import (
    ID_PATTERN,
    MAX_ID_LENGTH,
    PACK_ENTRY_ALLOWED_FIELDS,
    PACKS_FILENAME,
    VALID_CATEGORIES,
)
from .errors import CatalogValidationError
from .fs_ops import read_json_object

_PACKS_ROOT_KEYS: frozenset[str] = frozenset({"packs"})


@dataclass(frozen=True)
class CategoryPack:
    """Curated bundle of related skills, roles, prompts, and commands for one purpose."""

    pack_id: str
    name: str
    summary: str
    skill_ids: tuple[str, ...]
    role_ids: tuple[str, ...]
    prompt_ids: tuple[str, ...]
    command_ids: tuple[str, ...]


def _validate_member_ids(
    raw: Any,
    field: str,
    available: Mapping[str, object],
    seen: set[str],
    path: Path,
) -> tuple[str, ...]:
    """Ensure pack member lists reference real catalog IDs without cross-pack overlap."""
    if not isinstance(raw, list):
        raise CatalogValidationError("validate packs", path, f"{field} must be a JSON list")
    members: list[str] = []
    for item in cast(list[object], raw):
        if (
            not isinstance(item, str)
            or not item
            or len(item) > MAX_ID_LENGTH
            or ID_PATTERN.fullmatch(item) is None
        ):
            raise CatalogValidationError("validate packs", path, f"invalid ID {item!r} in {field}")
        if item not in available:
            raise CatalogValidationError("validate packs", path, f"unknown {field[:-1]} ID {item!r}")
        if item in seen:
            raise CatalogValidationError("validate packs", path, f"duplicate {field[:-1]} ID {item!r} across packs")
        seen.add(item)
        members.append(item)
    return tuple(members)


def _parse_single_pack(
    raw_entry: object,
    path: Path,
    skills_map: Mapping[str, object],
    prompts_map: Mapping[str, object],
    commands_map: Mapping[str, object],
    role_ids_by_cat: Mapping[str, tuple[str, ...]],
    seen_packs: set[str],
    seen_members: dict[str, set[str]],
) -> CategoryPack:
    if not isinstance(raw_entry, dict):
        raise CatalogValidationError("validate packs", path, "each pack entry must be a JSON object")
    entry = cast(dict[str, Any], raw_entry)
    unknown = sorted(set(entry) - PACK_ENTRY_ALLOWED_FIELDS)
    if unknown:
        raise CatalogValidationError("validate packs", path, f"disallowed pack key(s): {', '.join(unknown)}")
    pack_id = entry.get("id")
    if not isinstance(pack_id, str) or pack_id not in VALID_CATEGORIES:
        raise CatalogValidationError(
            "validate packs", path, f"pack id must be one of {list(VALID_CATEGORIES)}, got {pack_id!r}"
        )
    if pack_id in seen_packs:
        raise CatalogValidationError("validate packs", path, f"duplicate pack id {pack_id!r}")
    seen_packs.add(pack_id)

    name, summary = entry.get("name"), entry.get("summary")
    if not isinstance(name, str) or not name.strip():
        raise CatalogValidationError("validate packs", path, f"pack {pack_id!r} name must be non-empty")
    if not isinstance(summary, str) or not summary.strip():
        raise CatalogValidationError("validate packs", path, f"pack {pack_id!r} summary must be non-empty")

    return CategoryPack(
        pack_id=pack_id,
        name=name.strip(),
        summary=summary.strip(),
        skill_ids=_validate_member_ids(entry.get("skills"), "skills", skills_map, seen_members["skills"], path),
        role_ids=role_ids_by_cat.get(pack_id, ()),
        prompt_ids=_validate_member_ids(entry.get("prompts"), "prompts", prompts_map, seen_members["prompts"], path),
        command_ids=_validate_member_ids(
            entry.get("commands"), "commands", commands_map, seen_members["commands"], path
        ),
    )


def _verify_complete_partition(
    path: Path,
    seen_packs: set[str],
    seen_members: dict[str, set[str]],
    skills_map: Mapping[str, object],
    prompts_map: Mapping[str, object],
    commands_map: Mapping[str, object],
) -> None:
    """Guarantee strict mode catches newly added assets omitted from `packs.json`."""
    missing_packs = [cat for cat in VALID_CATEGORIES if cat not in seen_packs]
    if missing_packs:
        raise CatalogValidationError("validate packs", path, f"missing category pack(s): {', '.join(missing_packs)}")
    checks: tuple[tuple[str, Mapping[str, object]], ...] = (
        ("skills", skills_map),
        ("prompts", prompts_map),
        ("commands", commands_map),
    )
    for label, available in checks:
        unpacked = sorted(set(available) - seen_members[label])
        if unpacked:
            raise CatalogValidationError(
                "validate packs", path, f"unassigned {label} missing from packs.json: {', '.join(unpacked)}"
            )


def load_packs(
    repo_root: Path,
    *,
    skills_map: Mapping[str, object],
    role_categories: Mapping[str, str],
    prompts_map: Mapping[str, object],
    commands_map: Mapping[str, object],
    strict_nonempty: bool = False,
) -> dict[str, CategoryPack]:
    """Load `packs.json` and bind category role subdirectories into unified packs."""
    packs_path = repo_root / PACKS_FILENAME
    if not packs_path.exists():
        if strict_nonempty:
            raise CatalogValidationError("validate packs", packs_path, f"missing {PACKS_FILENAME}")
        return {}
    if packs_path.is_symlink() or not packs_path.is_file():
        raise CatalogValidationError("validate packs", packs_path, f"{PACKS_FILENAME} must be a regular file")

    raw = read_json_object(
        packs_path, "validate packs", lambda op, p, msg: CatalogValidationError(op, p, msg)
    )
    if frozenset(raw) != _PACKS_ROOT_KEYS or not isinstance(raw.get("packs"), list) or not raw["packs"]:
        raise CatalogValidationError("validate packs", packs_path, "expected non-empty top-level 'packs' list")

    by_cat: dict[str, list[str]] = {cat: [] for cat in VALID_CATEGORIES}
    for role_id, cat in sorted(role_categories.items()):
        by_cat.setdefault(cat, []).append(role_id)
    role_ids_by_cat = {cat: tuple(ids) for cat, ids in by_cat.items()}

    seen_packs: set[str] = set()
    seen_members: dict[str, set[str]] = {"skills": set(), "prompts": set(), "commands": set()}
    packs: dict[str, CategoryPack] = {}
    for raw_entry in cast(list[object], raw["packs"]):
        pack = _parse_single_pack(
            raw_entry,
            packs_path,
            skills_map,
            prompts_map,
            commands_map,
            role_ids_by_cat,
            seen_packs,
            seen_members,
        )
        packs[pack.pack_id] = pack

    if strict_nonempty:
        _verify_complete_partition(packs_path, seen_packs, seen_members, skills_map, prompts_map, commands_map)
    return packs


def expand_pack_assets(
    packs: Mapping[str, CategoryPack], pack_ids: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Collect deduplicated asset ID tuples across all requested packs."""
    skills: list[str] = []
    roles: list[str] = []
    prompts: list[str] = []
    commands: list[str] = []
    for pid in pack_ids:
        pack = packs[pid]
        skills.extend(pack.skill_ids)
        roles.extend(pack.role_ids)
        prompts.extend(pack.prompt_ids)
        commands.extend(pack.command_ids)
    return (
        tuple(dict.fromkeys(skills)),
        tuple(dict.fromkeys(roles)),
        tuple(dict.fromkeys(prompts)),
        tuple(dict.fromkeys(commands)),
    )
