"""User-local model choices and client metadata kept outside every repository.

The public catalog carries no provider or model names. Each user picks models per client, per
category, or per role with `./setup models`; install, status, and render read the same file, and a
missing file means no model field is rendered, so each client applies its own default.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from .adapters import validate_pi_metadata
from .catalog import Catalog
from .constants import (
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
    MODEL_SCOPES,
    SUPPORTED_CLIENTS,
    THINKING_CLIENTS,
    VALID_PI_THINKING_LEVELS,
)
from .errors import CatalogValidationError, ConfigError
from .fs_ops import atomic_write_text, read_json_object, validate_target_path

# Client-wide scope key inside one client's block; category and role maps sit beside it.
ALL_SCOPE = "all"


@dataclass(frozen=True)
class ModelChoice:
    """One user choice; either field may be unset so a narrower scope can refine a wider one."""

    model: str | None = None
    thinking: str | None = None

    def as_json(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if self.model is not None:
            out["model"] = self.model
        if self.thinking is not None:
            out["thinking"] = self.thinking
        return out


@dataclass(frozen=True)
class ClientModels:
    """Choices for one client, resolved role first, then category, then client-wide."""

    all: ModelChoice | None = None
    categories: dict[str, ModelChoice] = field(default_factory=dict[str, ModelChoice])
    roles: dict[str, ModelChoice] = field(default_factory=dict[str, ModelChoice])

    @property
    def is_empty(self) -> bool:
        return self.all is None and not self.categories and not self.roles


@dataclass(frozen=True)
class LocalConfig:
    """Parsed local config; the empty default renders every role without a model."""

    models: dict[str, ClientModels] = field(default_factory=dict[str, ClientModels])
    client_metadata: dict[str, dict[str, Any]] = field(
        default_factory=dict[str, dict[str, Any]]
    )
    source: Path | None = None

    def resolve(self, client: str, category: str, role_id: str) -> ModelChoice:
        """Merge field by field so a role can override only its thinking level, for example."""
        block = self.models.get(client)
        if block is None:
            return ModelChoice()
        model: str | None = None
        thinking: str | None = None
        for choice in (
            block.roles.get(role_id),
            block.categories.get(category),
            block.all,
        ):
            if choice is None:
                continue
            model = model if model is not None else choice.model
            thinking = thinking if thinking is not None else choice.thinking
        return ModelChoice(model=model, thinking=thinking)

    def to_json(self) -> dict[str, Any]:
        models: dict[str, Any] = {}
        for client in SUPPORTED_CLIENTS:
            block = self.models.get(client)
            if block is None or block.is_empty:
                continue
            out: dict[str, Any] = {}
            if block.all is not None:
                out[ALL_SCOPE] = block.all.as_json()
            for scope, entries in (
                ("categories", block.categories),
                ("roles", block.roles),
            ):
                if entries:
                    out[scope] = {k: entries[k].as_json() for k in sorted(entries)}
            models[client] = out
        data: dict[str, Any] = {"version": LOCAL_CONFIG_VERSION, "models": models}
        if self.client_metadata:
            data["client_metadata"] = self.client_metadata
        return data

    def with_choice(
        self, client: str, scope: str, key: str | None, choice: ModelChoice | None
    ) -> LocalConfig:
        """Return a copy with one scope set, or removed when `choice` is None or empty."""
        if client not in SUPPORTED_CLIENTS:
            raise ConfigError(
                "edit local config", self.source, f"unknown client {client!r}"
            )
        if choice is not None:
            validate_choice(client, choice, self.source)
        block = self.models.get(client, ClientModels())
        empty = choice is None or (choice.model is None and choice.thinking is None)
        new_value = None if empty else choice
        if scope == ALL_SCOPE:
            new_block = ClientModels(
                all=new_value, categories=block.categories, roles=block.roles
            )
        else:
            if key is None:
                raise ConfigError("edit local config", self.source, "missing scope ID")
            current = dict(block.categories if scope == "categories" else block.roles)
            if new_value is None:
                current.pop(key, None)
            else:
                current[key] = new_value
            new_block = (
                ClientModels(all=block.all, categories=current, roles=block.roles)
                if scope == "categories"
                else ClientModels(
                    all=block.all, categories=block.categories, roles=current
                )
            )
        models = dict(self.models)
        models[client] = new_block
        return LocalConfig(
            models=models, client_metadata=self.client_metadata, source=self.source
        )

    def merged_with(self, other: LocalConfig) -> LocalConfig:
        """Overlay `other` on this config; its entries win where both set one."""
        result = LocalConfig(
            models=dict(self.models),
            client_metadata={**self.client_metadata, **other.client_metadata},
            source=self.source,
        )
        for client, block in other.models.items():
            if block.all is not None:
                result = result.with_choice(client, ALL_SCOPE, None, block.all)
            for key, choice in block.categories.items():
                result = result.with_choice(client, "categories", key, choice)
            for key, choice in block.roles.items():
                result = result.with_choice(client, "roles", key, choice)
        return result

    def entry_count(self) -> int:
        return sum(
            (block.all is not None) + len(block.categories) + len(block.roles)
            for block in self.models.values()
        )


def default_config_path(home: Path) -> Path:
    """Honor XDG for the real home only, so `--home` sandboxes never read the user's file."""
    xdg = os.environ.get(LOCAL_CONFIG_XDG_ENV, "").strip()
    if xdg and home.expanduser().resolve() == Path.home().resolve():
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
    raw: Any, client: str, scope: str, path: Path
) -> dict[str, ModelChoice]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError(
            "load local config", path, f"models.{client}.{scope} must be an object"
        )
    return {
        str(key): _parse_choice(value, client, f"models.{client}.{scope}.{key}", path)
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
        unknown = sorted(set(typed) - {ALL_SCOPE, *MODEL_SCOPES})
        if unknown:
            raise ConfigError(
                "load local config",
                path,
                f"models.{client} has unknown key(s): {', '.join(unknown)}",
            )
        all_raw = typed.get(ALL_SCOPE)
        out[client] = ClientModels(
            all=None
            if all_raw is None
            else _parse_choice(all_raw, client, f"models.{client}.all", path),
            categories=_parse_scope_map(
                typed.get("categories"), client, "categories", path
            ),
            roles=_parse_scope_map(typed.get("roles"), client, "roles", path),
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
        if client != "pi" or not isinstance(meta, dict):
            raise ConfigError(
                "load local config",
                path,
                f"client_metadata supports only a pi object, got {client!r}",
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


def load_local_config(path: Path, repo_root: Path) -> LocalConfig:
    """Load the local config if present; a missing file is the empty, model-free config."""
    expanded = path.expanduser()
    ensure_outside_repo(expanded, repo_root)
    if not expanded.exists():
        return LocalConfig(source=expanded)
    if not expanded.is_file():
        raise ConfigError("load local config", expanded, "not a regular file")
    return read_config_file(expanded)


def ensure_outside_repo(path: Path, repo_root: Path) -> None:
    """User choices must never land in, or be read from, the public catalog checkout."""
    validate_target_path(repo_root, path)


def check_catalog_ids(config: LocalConfig, catalog: Catalog) -> None:
    """Fail closed on renamed or mistyped IDs rather than silently dropping a choice."""
    categories = {role.category for role in catalog.roles.values()}
    role_ids = set(catalog.roles)
    for client, block in config.models.items():
        for scope, known, entries in (
            ("categories", categories, block.categories),
            ("roles", role_ids, block.roles),
        ):
            unknown = sorted(set(entries) - known)
            if unknown:
                raise ConfigError(
                    "check local config",
                    config.source,
                    f"models.{client}.{scope} names unknown ID(s): {', '.join(unknown)}",
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
