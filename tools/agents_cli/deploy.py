"""Preflight-checked installation, uninstall, and status inspection engine."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .catalog import AssetFile, Catalog
from .constants import CLIENT_SUBPATHS, DIR_MODE, EXEC_FILE_MODE, REG_FILE_MODE
from .errors import DeploymentError, DestinationConflictError
from .fs_ops import (
    atomic_write_text,
    copy_directory_atomic,
    is_dir_copy_current,
    is_repo_owned_symlink,
    read_manifest,
    remove_path,
    validate_target_path,
    write_manifest,
)
from .render import ModelMap, render_role_for_client


@dataclass(frozen=True)
class Selection:
    """Resolved deployment choices across clients and asset categories."""

    clients: tuple[str, ...]
    skill_ids: tuple[str, ...]
    role_ids: tuple[str, ...]
    prompt_ids: tuple[str, ...]
    command_ids: tuple[str, ...]
    theme_ids: tuple[str, ...]
    include_styles: bool = False
    copy_skills: bool = False
    model_map: ModelMap = field(default_factory=ModelMap)
    dry_run: bool = False
    sync: bool = False

    @property
    def has_assets(self) -> bool:
        """True when at least one skill, role, prompt, command, theme, or style is selected."""
        return any(
            (
                self.skill_ids,
                self.role_ids,
                self.prompt_ids,
                self.command_ids,
                self.theme_ids,
                self.include_styles,
            )
        )


@dataclass(frozen=True)
class PlannedEntry:
    """One atomic unit of filesystem state managed inside a destination directory."""

    dest_dir: Path
    entry_name: str
    kind: str  # "file" | "symlink" | "dir_copy"
    content: str | None = None
    source_path: Path | None = None
    mode: int = REG_FILE_MODE


@dataclass
class DeploySummary:
    """Aggregated counters returned after apply, dry-run, or uninstall."""

    written: int = 0
    unchanged: int = 0
    removed: int = 0
    dry_run: bool = False
    planned_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClientStatus:
    """Live drift status for one client directory layout."""

    client: str
    installed: int
    stale: int
    missing: int
    unmanaged: int
    details: list[str]


def _client_dest_dirs(
    repo_root: Path, home: Path, clients: tuple[str, ...]
) -> list[Path]:
    dirs: list[Path] = []
    for client in clients:
        for subpath in CLIENT_SUBPATHS[client].values():
            dirs.append(validate_target_path(repo_root, home / subpath))
    return sorted(set(dirs))


def _plan_asset_group(
    repo_root: Path,
    dest_dir: Path,
    assets: dict[str, AssetFile],
    selected_ids: tuple[str, ...],
    suffix: str,
) -> list[PlannedEntry]:
    validated = validate_target_path(repo_root, dest_dir)
    planned: list[PlannedEntry] = []
    for asset_id in selected_ids:
        asset = assets[asset_id]
        mode = EXEC_FILE_MODE if asset.executable else REG_FILE_MODE
        try:
            content = asset.path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise DeploymentError("plan asset", asset.path, f"cannot read UTF-8 asset: {exc}") from exc
        planned.append(
            PlannedEntry(
                dest_dir=validated,
                entry_name=f"{asset_id}{suffix}",
                kind="file",
                content=content,
                mode=mode,
            )
        )
    return planned


def _plan_skills_and_roles(
    catalog: Catalog, client: str, home: Path, sel: Selection
) -> list[PlannedEntry]:
    entries: list[PlannedEntry] = []
    subpaths = CLIENT_SUBPATHS[client]
    if "skills" in subpaths:
        dest_dir = validate_target_path(catalog.repo_root, home / subpaths["skills"])
        kind = "dir_copy" if sel.copy_skills else "symlink"
        for skill_id in sel.skill_ids:
            entries.append(
                PlannedEntry(
                    dest_dir=dest_dir,
                    entry_name=skill_id,
                    kind=kind,
                    source_path=catalog.skills[skill_id].path,
                )
            )
    if "roles" in subpaths:
        dest_dir = validate_target_path(catalog.repo_root, home / subpaths["roles"])
        for role_id in sel.role_ids:
            rendered = render_role_for_client(catalog.roles[role_id], client, sel.model_map)
            entries.append(
                PlannedEntry(
                    dest_dir=dest_dir,
                    entry_name=f"{role_id}.md",
                    kind="file",
                    content=rendered,
                    mode=REG_FILE_MODE,
                )
            )
    return entries


def build_plan(catalog: Catalog, home: Path, sel: Selection) -> list[PlannedEntry]:
    """Build deterministic planned entries across selected clients without touching disk."""
    entries: list[PlannedEntry] = []
    for client in sel.clients:
        subpaths = CLIENT_SUBPATHS[client]
        entries.extend(_plan_skills_and_roles(catalog, client, home, sel))
        asset_specs: tuple[tuple[str, dict[str, AssetFile], tuple[str, ...], str], ...] = (
            ("prompts", catalog.prompts, sel.prompt_ids, ".md"),
            ("commands", catalog.opencode_commands, sel.command_ids, ".md"),
            ("themes", catalog.themes, sel.theme_ids, ".json"),
        )
        for key, source_map, selected_ids, suffix in asset_specs:
            if key in subpaths:
                entries.extend(
                    _plan_asset_group(
                        catalog.repo_root, home / subpaths[key], source_map, selected_ids, suffix
                    )
                )
        if client == "claude" and sel.include_styles:
            entries.extend(
                _plan_asset_group(
                    catalog.repo_root,
                    home / subpaths["styles"],
                    catalog.claude_styles,
                    tuple(sorted(catalog.claude_styles)),
                    ".md",
                )
            )
            entries.extend(
                _plan_asset_group(
                    catalog.repo_root,
                    home / subpaths["hooks"],
                    catalog.claude_hooks,
                    tuple(sorted(catalog.claude_hooks)),
                    ".sh",
                )
            )
    return entries


def _preflight(
    dest_dirs: list[Path], entries: list[PlannedEntry], repo_root: Path
) -> tuple[dict[Path, dict[str, dict[str, str]]], list[str]]:
    manifests: dict[Path, dict[str, dict[str, str]]] = {}
    conflicts: list[str] = []
    for dest_dir in sorted(set(dest_dirs) | {e.dest_dir for e in entries}):
        manifests[dest_dir] = read_manifest(dest_dir)
    for entry in entries:
        target = entry.dest_dir / entry.entry_name
        owned = manifests[entry.dest_dir]
        if entry.entry_name in owned or is_repo_owned_symlink(target, repo_root):
            continue
        if target.exists() or target.is_symlink():
            conflicts.append(f"unmanaged destination exists: {target}")
    return manifests, conflicts


def _is_entry_current(entry: PlannedEntry, target: Path) -> bool:
    try:
        if entry.kind == "symlink":
            return (
                target.is_symlink()
                and entry.source_path is not None
                and target.resolve(strict=False) == entry.source_path.resolve()
            )
        if entry.kind == "dir_copy":
            return entry.source_path is not None and is_dir_copy_current(entry.source_path, target)
        if entry.kind == "file":
            return (
                not target.is_symlink()
                and target.is_file()
                and entry.content is not None
                and target.read_text(encoding="utf-8") == entry.content
                and (target.stat().st_mode & 0o777) == entry.mode
            )
    except (OSError, RuntimeError, UnicodeDecodeError):
        return False
    return False


def _apply_one(entry: PlannedEntry) -> bool:
    target = entry.dest_dir / entry.entry_name
    if _is_entry_current(entry, target):
        return False
    try:
        entry.dest_dir.mkdir(parents=True, mode=DIR_MODE, exist_ok=True)
    except OSError as exc:
        raise DeploymentError("create directory", entry.dest_dir, f"mkdir failed: {exc}") from exc
    if entry.kind == "symlink":
        if entry.source_path is None:
            raise DeploymentError("install entry", target, "missing source_path for symlink")
        if target.exists() or target.is_symlink():
            remove_path(target)
        try:
            os.symlink(entry.source_path, target)
        except OSError as exc:
            raise DeploymentError("create symlink", target, f"symlink failed: {exc}") from exc
        return True
    if entry.kind == "dir_copy":
        if entry.source_path is None:
            raise DeploymentError("install entry", target, "missing source_path for dir_copy")
        copy_directory_atomic(entry.source_path, target)
        return True
    if target.is_symlink() or target.is_dir():
        remove_path(target)
    if entry.content is None:
        raise DeploymentError("install entry", target, "missing content for file")
    atomic_write_text(target, entry.content, entry.mode)
    return True


def _stale_names_by_dir(
    manifests: dict[Path, dict[str, dict[str, str]]],
    by_dir: dict[Path, list[PlannedEntry]],
    sync: bool,
) -> dict[Path, list[str]]:
    if not sync:
        return {}
    removals: dict[Path, list[str]] = {}
    for dest_dir, manifest in manifests.items():
        desired = {entry.entry_name for entry in by_dir.get(dest_dir, ())}
        stale = sorted(set(manifest) - desired)
        if stale:
            removals[dest_dir] = stale
    return removals


def _preview_summary(
    entries: list[PlannedEntry],
    stale_by_dir: dict[Path, list[str]],
    planned_paths: list[str],
) -> DeploySummary:
    summary = DeploySummary(dry_run=True, planned_paths=planned_paths)
    for entry in entries:
        if _is_entry_current(entry, entry.dest_dir / entry.entry_name):
            summary.unchanged += 1
        else:
            summary.written += 1
    summary.removed = sum(len(names) for names in stale_by_dir.values())
    return summary


def _apply_dir_group(
    dest_dir: Path,
    group: list[PlannedEntry],
    stale_names: list[str],
    manifest: dict[str, dict[str, str]],
    summary: DeploySummary,
) -> None:
    # Persist partial progress so interrupted runs do not leave unmanaged orphans behind.
    try:
        for stale_name in stale_names:
            remove_path(dest_dir / stale_name)
            del manifest[stale_name]
            summary.removed += 1
        for entry in group:
            if _apply_one(entry):
                summary.written += 1
            else:
                summary.unchanged += 1
            manifest[entry.entry_name] = {"kind": entry.kind}
    finally:
        if manifest or (dest_dir / ".agents-manifest.json").exists():
            write_manifest(dest_dir, manifest)


def install_selection(catalog: Catalog, home: Path, sel: Selection) -> DeploySummary:
    """Validate preflight across all target directories, then atomically apply or preview."""
    entries = build_plan(catalog, home, sel)
    dest_dirs = _client_dest_dirs(catalog.repo_root, home, sel.clients)
    manifests, conflicts = _preflight(dest_dirs, entries, catalog.repo_root)
    if conflicts:
        raise DestinationConflictError(
            "install preflight",
            home,
            "; ".join(conflicts[:5]) + (" (...)" if len(conflicts) > 5 else ""),
        )
    by_dir: dict[Path, list[PlannedEntry]] = {d: [] for d in dest_dirs}
    for entry in entries:
        by_dir.setdefault(entry.dest_dir, []).append(entry)
    stale_by_dir = _stale_names_by_dir(manifests, by_dir, sel.sync)
    planned_paths = [str(e.dest_dir / e.entry_name) for e in entries] + [
        str(d / name) for d, names in sorted(stale_by_dir.items()) for name in names
    ]
    if sel.dry_run:
        return _preview_summary(entries, stale_by_dir, planned_paths)

    summary = DeploySummary(dry_run=False, planned_paths=planned_paths)
    for dest_dir in sorted(by_dir):
        _apply_dir_group(
            dest_dir,
            by_dir[dest_dir],
            stale_by_dir.get(dest_dir, []),
            manifests[dest_dir],
            summary,
        )
    return summary


def uninstall_selection(
    catalog: Catalog, home: Path, clients: tuple[str, ...], *, dry_run: bool = False
) -> DeploySummary:
    """Remove only manifest-owned entries for `clients`, never user files."""
    summary = DeploySummary(dry_run=dry_run)
    for dest_dir in _client_dest_dirs(catalog.repo_root, home, clients):
        if not dest_dir.is_dir():
            continue
        manifest = read_manifest(dest_dir)
        for name in sorted(list(manifest)):
            target = dest_dir / name
            existed = target.exists() or target.is_symlink()
            if existed:
                summary.planned_paths.append(str(target))
                summary.removed += 1
            if not dry_run:
                if existed:
                    remove_path(target)
                del manifest[name]
        if not dry_run:
            write_manifest(dest_dir, manifest)
    return summary


def _client_status_for_dir(
    client: str,
    catalog: Catalog,
    home: Path,
    sel: Selection,
) -> ClientStatus:
    client_sel = Selection(
        clients=(client,),
        skill_ids=sel.skill_ids,
        role_ids=sel.role_ids,
        prompt_ids=sel.prompt_ids,
        command_ids=sel.command_ids,
        theme_ids=sel.theme_ids,
        include_styles=sel.include_styles,
        copy_skills=sel.copy_skills,
        model_map=sel.model_map,
        dry_run=True,
        sync=sel.sync,
    )
    entries = build_plan(catalog, home, client_sel)
    dest_dirs = _client_dest_dirs(catalog.repo_root, home, (client,))
    manifests, _ = _preflight(dest_dirs, entries, catalog.repo_root)
    desired_by_dir: dict[Path, set[str]] = {d: set() for d in dest_dirs}
    installed = stale = missing = unmanaged = 0
    details: list[str] = []

    for entry in entries:
        desired_by_dir.setdefault(entry.dest_dir, set()).add(entry.entry_name)
        target = entry.dest_dir / entry.entry_name
        owned = manifests.get(entry.dest_dir, {})
        is_owned = entry.entry_name in owned or is_repo_owned_symlink(target, catalog.repo_root)
        if not target.exists() and not target.is_symlink():
            missing += 1
        elif not is_owned:
            unmanaged += 1
            details.append(f"unmanaged: {target}")
        elif _is_entry_current(entry, target):
            installed += 1
        else:
            stale += 1
            details.append(f"stale: {target}")

    for dest_dir, manifest in sorted(manifests.items()):
        for orphan in sorted(set(manifest) - desired_by_dir.get(dest_dir, set())):
            stale += 1
            details.append(f"orphaned: {dest_dir / orphan}")

    return ClientStatus(
        client=client,
        installed=installed,
        stale=stale,
        missing=missing,
        unmanaged=unmanaged,
        details=details,
    )


def inspect_status(catalog: Catalog, home: Path, sel: Selection) -> list[ClientStatus]:
    """Compare desired client plans and manifests against disk without mutating files."""
    return [_client_status_for_dir(client, catalog, home, sel) for client in sel.clients]


def has_managed_claude_styles(repo_root: Path, home: Path) -> bool:
    """Detect whether Claude output styles or hooks are already managed on disk."""
    for key in ("styles", "hooks"):
        dest_dir = validate_target_path(repo_root, home / CLIENT_SUBPATHS["claude"][key])
        if read_manifest(dest_dir):
            return True
    return False
