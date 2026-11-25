"""User-local model choices and client metadata kept outside every repository.

The public catalog carries no provider or model names. Each user picks models per client, per
category, or per role with `./setup models`; install, status, and render read the same file, and a
missing file means no model field is rendered, so each client applies its own default.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from .adapters import validate_pi_metadata
from .catalog import Catalog
from .constants import (
    CLIENT_METADATA_CLIENTS,
    LOCAL_CONFIG_ALLOWED_KEYS,
    LOCAL_CONFIG_DEFAULT_BASE,
    LOCAL_CONFIG_DIR_MODE,
    LOCAL_CONFIG_DIRNAME,
    LOCAL_CONFIG_FILE_MODE,
    LOCAL_CONFIG_FILENAME,
    LOCAL_CONFIG_VERSION,
    LOCAL_CONFIG_XDG_ENV,
    MAX_MODEL_ID_LENGTH,
    MODEL_ENTRY_FIELDS,
    MODEL_ID_PATTERN,
    SUPPORTED_CLIENTS,
    THINKING_CLIENTS,
    VALID_PI_THINKING_LEVELS,
)
from .errors import AgentsError, CatalogValidationError, ConfigError
from .fs_ops import atomic_write_text, read_json_object, validate_target_path


class Scope(StrEnum):
    """Where a choice applies; values are the JSON keys inside one client's block."""

    ALL = "all"
    CATEGORY = "categories"
    ROLE = "roles"

    @property
    def label(self) -> str:
        return _SCOPE_LABELS[self]


_SCOPE_LABELS: dict[Scope, str] = {
    Scope.ALL: "client-wide",
    Scope.CATEGORY: "category",
    Scope.ROLE: "role",
}
# The client-wide scope holds one entry; a fixed key lets every scope share one map shape.
ALL_KEY = "*"
# Narrowest first: the order `resolve` walks and `show` prints.
RESOLUTION_ORDER: tuple[Scope, ...] = (Scope.ROLE, Scope.CATEGORY, Scope.ALL)
# Hint printed when stored IDs no longer exist, so users fix the file with the tool, not by hand.
STALE_ID_HINT = (
    "remove it with `./setup models clear --client <client> --role|--category <id>`"
)


@dataclass(frozen=True)
class ModelChoice:
    """One user choice; either field may be unset so a narrower scope can refine a wider one."""

    model: str | None = None
    thinking: str | None = None

    @property
    def is_empty(self) -> bool:
        return self.model is None and self.thinking is None

    def overlay(self, other: ModelChoice) -> ModelChoice:
        """Fields `other` sets win; unset fields keep this choice, so setting one never drops another."""
        return ModelChoice(
            model=other.model if other.model is not None else self.model,
            thinking=other.thinking if other.thinking is not None else self.thinking,
        )

    def as_json(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if self.model is not None:
            out["model"] = self.model
        if self.thinking is not None:
            out["thinking"] = self.thinking
        return out


def _empty_scopes() -> dict[Scope, dict[str, ModelChoice]]:
    return {scope: {} for scope in Scope}


@dataclass(frozen=True)
class ClientModels:
    """Choices for one client, keyed by scope; the client-wide entry sits under `ALL_KEY`."""

    scopes: Mapping[Scope, Mapping[str, ModelChoice]] = field(
        default_factory=_empty_scopes
    )

    def get(self, scope: Scope, key: str) -> ModelChoice | None:
        return self.scopes.get(scope, {}).get(key)

    def entries(self) -> Iterator[tuple[Scope, str, ModelChoice]]:
        """Every stored choice, client-wide first, then sorted categories and roles."""
        for scope in Scope:
            entries = self.scopes.get(scope, {})
            for key in sorted(entries):
                yield scope, key, entries[key]

    @property
    def is_empty(self) -> bool:
        return not any(self.scopes.get(scope) for scope in Scope)


@dataclass(frozen=True)
class LocalConfig:
    """Parsed local config; the empty default renders every role without a model."""

    models: Mapping[str, ClientModels] = field(default_factory=dict[str, ClientModels])
    client_metadata: Mapping[str, dict[str, Any]] = field(
        default_factory=dict[str, dict[str, Any]]
    )
    source: Path | None = None

    def resolve(self, client: str, category: str, role_id: str) -> ModelChoice:
        """Merge field by field so a role can override only its thinking level, for example."""
        block = self.models.get(client)
        if block is None:
            return ModelChoice()
        keys = {Scope.ROLE: role_id, Scope.CATEGORY: category, Scope.ALL: ALL_KEY}
        merged = ModelChoice()
        for scope in reversed(RESOLUTION_ORDER):
            choice = block.get(scope, keys[scope])
            if choice is not None:
                merged = merged.overlay(choice)
        return merged

    def to_json(self) -> dict[str, Any]:
        models: dict[str, Any] = {}
        for client in SUPPORTED_CLIENTS:
            block = self.models.get(client)
            if block is None or block.is_empty:
                continue
            out: dict[str, Any] = {}
            for scope, key, choice in block.entries():
                if scope is Scope.ALL:
                    out[scope.value] = choice.as_json()
                else:
                    out.setdefault(scope.value, {})[key] = choice.as_json()
            models[client] = out
        data: dict[str, Any] = {"version": LOCAL_CONFIG_VERSION, "models": models}
        if self.client_metadata:
            data["client_metadata"] = dict(self.client_metadata)
        return data

    def with_choice(
        self, client: str, scope: Scope, key: str | None, choice: ModelChoice | None
    ) -> LocalConfig:
        """Return a copy with one scope replaced, or removed when `choice` is None or empty."""
        if client not in SUPPORTED_CLIENTS:
            raise ConfigError(
                "edit local config", self.source, f"unknown client {client!r}"
            )
        slot = _slot_key(scope, key, self.source)
        if choice is not None:
            validate_choice(client, choice, self.source)
        block = self.models.get(client, ClientModels())
        scopes = {s: dict(block.scopes.get(s, {})) for s in Scope}
        if choice is None or choice.is_empty:
            scopes[scope].pop(slot, None)
        else:
            scopes[scope][slot] = choice
        models = dict(self.models)
        models[client] = ClientModels(scopes=scopes)
        return LocalConfig(
            models=models, client_metadata=self.client_metadata, source=self.source
        )

    def with_overlay(
        self, client: str, scope: Scope, key: str | None, choice: ModelChoice
    ) -> LocalConfig:
        """Set only the fields `choice` names, keeping any other field already stored there."""
        block = self.models.get(client)
        current = (
            block.get(scope, _slot_key(scope, key, self.source)) if block else None
        )
        merged = (current or ModelChoice()).overlay(choice)
        return self.with_choice(client, scope, key, merged)

    def merged_with(self, other: LocalConfig) -> LocalConfig:
        """Overlay `other` field by field; its fields win where both set one."""
        result = LocalConfig(
            models=self.models,
            client_metadata={**self.client_metadata, **other.client_metadata},
            source=self.source,
        )
        for client, block in other.models.items():
            for scope, key, choice in block.entries():
                result = result.with_overlay(client, scope, key, choice)
        return result

    def entry_count(self) -> int:
        return sum(sum(1 for _ in block.entries()) for block in self.models.values())


# Shared empty default for callers that render without any user choices.
EMPTY_CONFIG = LocalConfig()


def _slot_key(scope: Scope, key: str | None, path: Path | None) -> str:
    if scope is Scope.ALL:
        return ALL_KEY
    if not key:
        raise ConfigError(
            "edit local config", path, f"missing {scope.label} ID for this scope"
        )
    return key


def default_config_path(home: Path) -> Path:
    """Honor an absolute XDG path for the real home only, so `--home` sandboxes never read it.

    The XDG Base Directory spec says relative values are invalid; using one would make the file
    location depend on the current directory.
    """
    xdg = os.environ.get(LOCAL_CONFIG_XDG_ENV, "").strip()
    real_home = home.expanduser().resolve() == Path.home().resolve()
    if xdg and real_home and Path(xdg).is_absolute():
        base = Path(xdg)
    else:
        base = home / LOCAL_CONFIG_DEFAULT_BASE
    return base / LOCAL_CONFIG_DIRNAME / LOCAL_CONFIG_FILENAME


def validate_choice(client: str, choice: ModelChoice, path: Path | None) -> None:
    """Reject model IDs that could break frontmatter and thinking levels a client ignores."""
    if choice.model is not None and (
        len(choice.model) > MAX_MODEL_ID_LENGTH
        or MODEL_ID_PATTERN.fullmatch(choice.model) is None
    ):
        raise ConfigError(
            "validate local config",
            path,
            f"invalid model ID for {client} (allowed: letters, digits, . _ : / @ + -)",
        )
    if choice.thinking is not None:
        if client not in THINKING_CLIENTS:
            raise ConfigError(
                "validate local config",
                path,
                f"thinking is only supported for {sorted(THINKING_CLIENTS)}, not {client}",
            )
        if choice.thinking not in VALID_PI_THINKING_LEVELS:
            raise ConfigError(
                "validate local config",
                path,
                f"thinking must be one of {sorted(VALID_PI_THINKING_LEVELS)}",
            )


def _parse_choice(raw: Any, client: str, where: str, path: Path) -> ModelChoice:
    if not isinstance(raw, dict):
        raise ConfigError("load local config", path, f"{where} must be an object")
    entry = cast(dict[str, Any], raw)
    unknown = sorted(set(entry) - MODEL_ENTRY_FIELDS)
    if unknown or not entry:
        raise ConfigError(
            "load local config",
            path,
            f"{where} must set model and/or thinking only (got {', '.join(unknown) or 'nothing'})",
        )
    values: dict[str, str] = {}
    for key, value in entry.items():
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(
                "load local config", path, f"{where}.{key} must be a non-empty string"
            )
        values[key] = value.strip()
    choice = ModelChoice(model=values.get("model"), thinking=values.get("thinking"))
    validate_choice(client, choice, path)
    return choice


def _parse_scope_map(
    raw: Any, client: str, scope: Scope, path: Path
) -> dict[str, ModelChoice]:
    if raw is None:
        return {}
    where = f"models.{client}.{scope.value}"
    if scope is Scope.ALL:
        return {ALL_KEY: _parse_choice(raw, client, where, path)}
    if not isinstance(raw, dict):
        raise ConfigError("load local config", path, f"{where} must be an object")
    return {
        str(key): _parse_choice(value, client, f"{where}.{key}", path)
        for key, value in cast(dict[str, Any], raw).items()
    }


def _parse_models(raw: Any, path: Path) -> dict[str, ClientModels]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError("load local config", path, "models must be an object")
    out: dict[str, ClientModels] = {}
    for client, block in cast(dict[str, Any], raw).items():
        if client not in SUPPORTED_CLIENTS:
            raise ConfigError("load local config", path, f"unknown client {client!r}")
        if not isinstance(block, dict):
            raise ConfigError(
                "load local config", path, f"models.{client} must be an object"
            )
        typed = cast(dict[str, Any], block)
        unknown = sorted(set(typed) - {scope.value for scope in Scope})
        if unknown:
            raise ConfigError(
                "load local config",
                path,
                f"models.{client} has unknown key(s): {', '.join(unknown)}",
            )
        out[client] = ClientModels(
            scopes={
                scope: _parse_scope_map(typed.get(scope.value), client, scope, path)
                for scope in Scope
            }
        )
    return out


def _parse_client_metadata(raw: Any, path: Path) -> dict[str, dict[str, Any]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError(
            "load local config", path, "client_metadata must be an object"
        )
    out: dict[str, dict[str, Any]] = {}
    for client, meta in cast(dict[str, Any], raw).items():
        if client not in CLIENT_METADATA_CLIENTS or not isinstance(meta, dict):
            raise ConfigError(
                "load local config",
                path,
                f"client_metadata supports only {sorted(CLIENT_METADATA_CLIENTS)} objects, "
                f"got {client!r}",
            )
        typed = {str(k): v for k, v in cast(dict[str, Any], meta).items()}
        try:
            validate_pi_metadata(typed, path)
        except CatalogValidationError as exc:
            raise ConfigError("load local config", path, exc.reason) from exc
        out[client] = typed
    return out


def parse_config_data(data: dict[str, Any], path: Path) -> LocalConfig:
    unknown = sorted(set(data) - LOCAL_CONFIG_ALLOWED_KEYS)
    if unknown:
        raise ConfigError(
            "load local config", path, f"unknown top-level key(s): {', '.join(unknown)}"
        )
    version = data.get("version", LOCAL_CONFIG_VERSION)
    if version != LOCAL_CONFIG_VERSION:
        raise ConfigError("load local config", path, f"unsupported version {version!r}")
    return LocalConfig(
        models=_parse_models(data.get("models"), path),
        client_metadata=_parse_client_metadata(data.get("client_metadata"), path),
        source=path,
    )


def read_config_file(path: Path) -> LocalConfig:
    data = read_json_object(
        path, "load local config", lambda op, p, msg: ConfigError(op, p, msg)
    )
    return parse_config_data(data, path)


def load_local_config(
    path: Path, repo_root: Path, *, must_exist: bool = False
) -> LocalConfig:
    """Load the config; a missing default file is the empty, model-free config.

    `must_exist` is set for a path the user named, so a typo fails instead of silently
    rendering every role without the models that user chose.
    """
    expanded = path.expanduser()
    ensure_outside_repo(expanded, repo_root)
    if not expanded.exists():
        if must_exist:
            raise ConfigError("load local config", expanded, "file does not exist")
        return LocalConfig(source=expanded)
    if not expanded.is_file():
        raise ConfigError("load local config", expanded, "not a regular file")
    return read_config_file(expanded)


def ensure_outside_repo(path: Path, repo_root: Path) -> None:
    """User choices must never land in, or be read from, the public catalog checkout."""
    try:
        validate_target_path(repo_root, path)
    except AgentsError as exc:
        raise ConfigError(
            "check local config path",
            path,
            "config file must live outside the catalog checkout",
        ) from exc


def target_problem(
    catalog: Catalog, client: str, scope: Scope, key: str | None
) -> str | None:
    """Why a choice for this scope could never apply, or None when it can."""
    if scope is Scope.CATEGORY and key not in {
        r.category for r in catalog.roles.values()
    }:
        return f"unknown category {key!r}"
    if scope is Scope.ROLE:
        role = catalog.roles.get(key or "")
        if role is None:
            return f"unknown role {key!r}"
        if not role.supports(client):
            return f"role {key!r} does not install into {client}"
    return None


def stale_entries(config: LocalConfig, catalog: Catalog) -> list[str]:
    """Stored choices the catalog can no longer apply, as `models.<client>.<scope>.<id>`."""
    stale: list[str] = []
    for client, block in config.models.items():
        for scope, key, _ in block.entries():
            if target_problem(catalog, client, scope, key) is not None:
                stale.append(f"models.{client}.{scope.value}.{key}")
    return stale


def check_catalog_ids(config: LocalConfig, catalog: Catalog) -> None:
    """Fail closed on renamed or mistyped IDs rather than silently dropping a choice."""
    stale = stale_entries(config, catalog)
    if stale:
        raise ConfigError(
            "check local config",
            config.source,
            f"choices name roles or categories the catalog cannot apply: {', '.join(stale)}; "
            + STALE_ID_HINT,
        )


def save_local_config(config: LocalConfig, path: Path, repo_root: Path) -> None:
    """Write owner-only, since the file can reveal which providers a user pays for."""
    expanded = path.expanduser()
    ensure_outside_repo(expanded, repo_root)
    if expanded.is_symlink():
        raise ConfigError(
            "save local config", expanded, "refusing to write through a symlink"
        )
    try:
        expanded.parent.mkdir(parents=True, mode=LOCAL_CONFIG_DIR_MODE, exist_ok=True)
    except OSError as exc:
        raise ConfigError(
            "save local config", expanded.parent, f"mkdir failed: {exc}"
        ) from exc
    text = json.dumps(config.to_json(), indent=2, sort_keys=False) + "\n"
    atomic_write_text(expanded, text, LOCAL_CONFIG_FILE_MODE)
