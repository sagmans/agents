"""Low-level JSON loading, manifest persistence, and atomic filesystem helpers."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, cast

from .constants import (
    DIR_MODE,
    MANIFEST_FILENAME,
    MANIFEST_VERSION,
    REG_FILE_MODE,
)
from .errors import AgentsError, DeploymentError, DestinationConflictError


def read_json_object(
    path: Path,
    operation: str,
    error_factory: Callable[[str, Path, str], AgentsError],
) -> dict[str, Any]:
    """Load and validate a UTF-8 JSON object file using the caller's domain error."""
    try:
        loaded: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise error_factory(operation, path, f"unreadable or invalid JSON: {exc}") from exc
    if not isinstance(loaded, dict):
        raise error_factory(operation, path, "expected top-level JSON object")
    raw_map = cast(dict[object, Any], loaded)
    result: dict[str, Any] = {}
    for key, value in raw_map.items():
        if not isinstance(key, str):
            raise error_factory(operation, path, "all JSON keys must be strings")
        result[key] = value
    return result


def validate_target_path(repo_root: Path, candidate: Path) -> Path:
    """Reject destinations inside `repo_root` so installs never pollute source trees."""
    resolved_root = repo_root.resolve()
    try:
        resolved = candidate.expanduser().resolve()
    except OSError as exc:
        raise DeploymentError("validate destination", candidate, f"cannot resolve path: {exc}") from exc
    if resolved == resolved_root or resolved_root in resolved.parents:
        raise DestinationConflictError(
            "validate destination",
            resolved,
            "destination directory cannot reside inside repository root",
        )
    return resolved


def _validate_manifest_entry_name(name: str, manifest_path: Path) -> None:
    if not name or "\x00" in name or "/" in name or "\\" in name or name in {".", ".."}:
        raise DeploymentError(
            "read manifest",
            manifest_path,
            f"unsafe manifest entry name: {name!r}",
        )


def read_manifest(dest_dir: Path) -> dict[str, dict[str, str]]:
    """Load `.agents-manifest.json` fail-closed on symlinks, corruption, or bad keys."""
    manifest_path = dest_dir / MANIFEST_FILENAME
    if not manifest_path.exists() and not manifest_path.is_symlink():
        return {}
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise DestinationConflictError(
            "read manifest", manifest_path, "manifest path must be a regular file"
        )
    raw = read_json_object(
        manifest_path, "read manifest", lambda op, p, msg: DeploymentError(op, p, msg)
    )
    version = raw.get("version")
    if type(version) is not int or version != MANIFEST_VERSION:
        raise DeploymentError("read manifest", manifest_path, "unsupported manifest version")
    raw_entries: Any = raw.get("entries", {})
    if not isinstance(raw_entries, dict):
        raise DeploymentError("read manifest", manifest_path, "manifest entries must be an object")
    clean: dict[str, dict[str, str]] = {}
    for k, v in cast(dict[object, object], raw_entries).items():
        if not isinstance(k, str) or not isinstance(v, dict):
            raise DeploymentError("read manifest", manifest_path, "invalid manifest entry shape")
        _validate_manifest_entry_name(k, manifest_path)
        meta_dict = cast(dict[object, object], v)
        clean[k] = {str(sk): str(sv) for sk, sv in meta_dict.items()}
    return clean


def atomic_write_text(path: Path, text: str, mode: int) -> None:
    """Write text via a sibling temporary file so interrupted writes never corrupt targets."""
    tmp_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, mode=DIR_MODE, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
    except OSError as exc:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise DeploymentError("write file", path, f"atomic write failed: {exc}") from exc


def write_manifest(dest_dir: Path, entries: dict[str, dict[str, str]]) -> None:
    """Persist manifest entries and unlink empty manifests to avoid empty config clutter."""
    manifest_path = dest_dir / MANIFEST_FILENAME
    if not entries:
        try:
            manifest_path.unlink(missing_ok=True)
        except OSError as exc:
            raise DeploymentError("write manifest", manifest_path, f"cannot remove empty manifest: {exc}") from exc
        return
    payload = {"version": MANIFEST_VERSION, "entries": entries}
    atomic_write_text(
        manifest_path, json.dumps(payload, indent=2, sort_keys=True) + "\n", REG_FILE_MODE
    )


def remove_path(target: Path) -> None:
    """Remove symlinks, directories, files, or special sockets/FIFOs safely."""
    try:
        if target.is_symlink() or not target.is_dir():
            target.unlink(missing_ok=True)
        else:
            shutil.rmtree(target)
    except OSError as exc:
        raise DeploymentError("remove target", target, f"failed to remove path: {exc}") from exc


def is_repo_owned_symlink(target: Path, repo_root: Path) -> bool:
    """True when `target` is a symlink resolving strictly inside this repository."""
    if not target.is_symlink():
        return False
    try:
        resolved = target.resolve(strict=False)
    except (OSError, RuntimeError):
        return False
    return resolved == repo_root or repo_root in resolved.parents


def _snapshot_tree_bytes(root: Path) -> dict[Path, bytes] | None:
    try:
        if root.is_symlink() or not root.is_dir():
            return None
        snapshot: dict[Path, bytes] = {}
        for entry in sorted(root.rglob("*")):
            rel = entry.relative_to(root)
            if "__pycache__" in rel.parts or entry.suffix == ".pyc":
                continue
            if entry.is_symlink():
                return None
            if entry.is_file():
                snapshot[rel] = entry.read_bytes()
        return snapshot
    except OSError:
        return None


def is_dir_copy_current(source_dir: Path, target_dir: Path) -> bool:
    """Compare non-cache regular files recursively so `--copy` detects drift cleanly."""
    src_snap = _snapshot_tree_bytes(source_dir)
    dst_snap = _snapshot_tree_bytes(target_dir)
    if src_snap is None or dst_snap is None:
        return False
    return src_snap == dst_snap


def copy_directory_atomic(source_dir: Path, target: Path) -> None:
    """Stage copied trees beside `target` so failed copies leave old installs intact."""
    staging: Path | None = None
    try:
        staging = Path(tempfile.mkdtemp(prefix=".tmp-dir-", dir=str(target.parent)))
        copied = staging / "payload"
        shutil.copytree(
            source_dir,
            copied,
            symlinks=False,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        if target.exists() or target.is_symlink():
            remove_path(target)
        os.replace(copied, target)
    except OSError as exc:
        raise DeploymentError("copy directory", target, f"atomic directory copy failed: {exc}") from exc
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
