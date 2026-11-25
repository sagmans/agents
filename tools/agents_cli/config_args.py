"""Command-line flags that locate the user-local model config, shared by every subcommand.

Install, status, render, and `models` import these directly so they agree on which file is read
and how a missing or stale file is treated.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .catalog import Catalog
from .local_config import (
    EMPTY_CONFIG,
    LocalConfig,
    check_catalog_ids,
    default_config_path,
    load_local_config,
)


def add_config_flag(parser: argparse.ArgumentParser, *, suppress_default: bool) -> None:
    """`--config` alone, for `models`, which always edits a file and so cannot ignore one."""
    parser.add_argument(
        "--config",
        type=Path,
        help="User-local model config (default: $XDG_CONFIG_HOME/agents/config.json)",
        default=argparse.SUPPRESS if suppress_default else None,
    )


def add_config_flags(
    parser: argparse.ArgumentParser, *, suppress_defaults: bool
) -> None:
    """`--config` or `--no-config`, for commands that render roles."""
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--config",
        type=Path,
        help="User-local model config (default: $XDG_CONFIG_HOME/agents/config.json)",
        default=argparse.SUPPRESS if suppress_defaults else None,
    )
    group.add_argument(
        "--no-config",
        action="store_true",
        help="Ignore the local config; render every role without a model",
        default=argparse.SUPPRESS if suppress_defaults else False,
    )


def _explicit_path(args: argparse.Namespace) -> Path | None:
    explicit: Path | None = getattr(args, "config", None)
    return explicit.expanduser() if explicit else None


def config_path_from_args(args: argparse.Namespace) -> Path:
    home: Path = getattr(args, "home", None) or Path.home()
    return _explicit_path(args) or default_config_path(home)


def load_config_for_edit(args: argparse.Namespace, catalog: Catalog) -> LocalConfig:
    """Read without the catalog ID check, so `models` can show and clear stale entries."""
    return load_local_config(config_path_from_args(args), catalog.repo_root)


def config_for_render(args: argparse.Namespace, catalog: Catalog) -> LocalConfig:
    """Read for install, status, and render: a named file must exist and IDs must be current."""
    if getattr(args, "no_config", False):
        return EMPTY_CONFIG
    config = load_local_config(
        config_path_from_args(args),
        catalog.repo_root,
        must_exist=_explicit_path(args) is not None,
    )
    check_catalog_ids(config, catalog)
    return config
