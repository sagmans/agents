"""`./setup models`: view and change the user-local model choices, by flag, file, or prompt.

Installs read the same file, so a choice made here takes effect on the next install. Nothing here
invents a model: non-interactive calls change only what a flag or file names explicitly. Loading
skips the catalog ID check that installs apply, so `show` and `clear` can repair a file that
names a removed role; every write is checked before it is saved.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .catalog import Catalog
from .config_args import add_config_flag, config_path_from_args, load_config_for_edit
from .constants import MODEL_CLEAR_TOKEN, SUPPORTED_CLIENTS, THINKING_CLIENTS
from .errors import AgentsError, ConfigError
from .local_config import (
    ALL_KEY,
    STALE_ID_HINT,
    LocalConfig,
    ModelChoice,
    Scope,
    read_config_file,
    save_local_config,
    stale_entries,
    target_problem,
)

InputFn = Callable[[str], str]
_QUIT_TOKENS: frozenset[str] = frozenset({"q", "quit", "exit"})
_STALE_MARK = "(not applied: " + STALE_ID_HINT + ")"


class ModelsWizardCancelled(Exception):
    """Raised when the user quits the editor; nothing is saved."""


def add_models_parser(sub: Any) -> None:
    """Register `models` with its actions; `show` is the default."""
    p = sub.add_parser(
        "models",
        help="Show or change user-local model choices (never stored in this repository)",
    )
    # Root flags given before `models` must survive, as for every other subcommand.
    _add_common(p)
    actions = p.add_subparsers(dest="models_action")
    _add_common(
        actions.add_parser("show", help="Print the config path and every stored choice")
    )
    for name, helptext in (
        (
            "set",
            "Store a model and/or thinking level for one scope, keeping other fields",
        ),
        ("clear", "Remove the choice for one scope"),
    ):
        ap = actions.add_parser(name, help=helptext)
        _add_common(ap)
        ap.add_argument("--client", required=True, choices=SUPPORTED_CLIENTS)
        scope = ap.add_mutually_exclusive_group()
        scope.add_argument("--category", help="Category ID (default: client-wide)")
        scope.add_argument("--role", help="Role ID (default: client-wide)")
        if name == "set":
            ap.add_argument("--model", help="Client-native model ID")
            ap.add_argument("--thinking", help="Thinking level (pi only)")
    ap = actions.add_parser(
        "import", help="Merge a JSON file with the same schema into the config"
    )
    _add_common(ap)
    ap.add_argument("file", type=Path)
    _add_common(actions.add_parser("edit", help="Change choices interactively"))


def _add_common(parser: argparse.ArgumentParser) -> None:
    """Accept `--home` and `--config` before or after the action word."""
    add_config_flag(parser, suppress_default=True)
    parser.add_argument(
        "--home",
        type=Path,
        default=argparse.SUPPRESS,
        help="Home whose config is used (default: your home)",
    )


def _scope_of(args: argparse.Namespace) -> tuple[Scope, str | None]:
    if getattr(args, "role", None):
        return Scope.ROLE, str(args.role)
    if getattr(args, "category", None):
        return Scope.CATEGORY, str(args.category)
    return Scope.ALL, None


def _print_config(config: LocalConfig, path: Path, catalog: Catalog) -> None:
    print(f"config: {path} ({'present' if path.exists() else 'absent'})")
    if not config.models:
        print("no model choices: every role renders without a model field")
    for client in SUPPORTED_CLIENTS:
        block = config.models.get(client)
        if block is None or block.is_empty:
            continue
        print(f"{client}:")
        for scope, key, choice in block.entries():
            parts = [f"model={choice.model}"] if choice.model else []
            parts += [f"thinking={choice.thinking}"] if choice.thinking else []
            if target_problem(catalog, client, scope, key) is not None:
                parts.append(_STALE_MARK)
            shown = "" if scope is Scope.ALL else key
            print(f"  {scope.label:<11} {shown:<44} {' '.join(parts)}")
    if config.client_metadata:
        print(f"client_metadata: {', '.join(sorted(config.client_metadata))}")


def _require_target(
    catalog: Catalog, client: str, scope: Scope, key: str | None
) -> None:
    problem = target_problem(catalog, client, scope, key)
    if problem is not None:
        raise ConfigError("edit local config", None, problem)


def run_models_command(
    args: argparse.Namespace, catalog: Catalog, input_fn: InputFn = input
) -> int:
    """Apply one models action; writes are checked, and entries already stored are kept."""
    path = config_path_from_args(args)
    config = load_config_for_edit(args, catalog)
    action = getattr(args, "models_action", None) or "show"
    if action == "show":
        _print_config(config, path, catalog)
        return 0
    if action == "set":
        if args.model is None and args.thinking is None:
            raise AgentsError("models set", None, "pass --model and/or --thinking")
        scope, key = _scope_of(args)
        _require_target(catalog, args.client, scope, key)
        updated = config.with_overlay(
            args.client, scope, key, ModelChoice(args.model, args.thinking)
        )
    elif action == "clear":
        scope, key = _scope_of(args)
        block = config.models.get(args.client)
        if block is None or block.get(scope, key or ALL_KEY) is None:
            raise ConfigError(
                "models clear",
                path,
                f"nothing stored for {args.client} {scope.label} {key or ''}".rstrip(),
            )
        updated = config.with_choice(args.client, scope, key, None)
    elif action == "import":
        incoming = read_config_file(args.file.expanduser())
        stale = stale_entries(incoming, catalog)
        if stale:
            raise ConfigError(
                "import local config",
                args.file,
                f"choices the catalog cannot apply: {', '.join(stale)}",
            )
        updated = config.merged_with(incoming)
    else:
        try:
            updated = edit_models_interactively(config, catalog, input_fn)
        except (EOFError, KeyboardInterrupt, ModelsWizardCancelled):
            print("\nAborted without changes.")
            return 0
        if updated == config:
            print("no changes")
            return 0
    save_local_config(updated, path, catalog.repo_root)
    print(f"saved {updated.entry_count()} model choice(s) to {path}")
    return 0


def _ask(prompt: str, input_fn: InputFn, default: str = "") -> str:
    raw = input_fn(prompt).strip()
    if raw.lower() in _QUIT_TOKENS:
        raise ModelsWizardCancelled
    return raw or default


def _pick(label: str, options: tuple[str, ...], input_fn: InputFn) -> str | None:
    """Return one option by number or name; blank means done."""
    for idx, opt in enumerate(options, 1):
        print(f"  {idx}. {opt}")
    while True:
        raw = _ask(f"{label} (number or name, blank = done): ", input_fn)
        if not raw:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        if raw in options:
            return raw
        print(f"  unknown choice: {raw}")


def _ask_choice(
    client: str, current: ModelChoice | None, input_fn: InputFn
) -> ModelChoice | None:
    """Blank keeps a field; the clear token removes it. Returns None to drop the entry."""
    cur = current or ModelChoice()
    model = _ask(
        f"    model [{cur.model or 'none'}] ('{MODEL_CLEAR_TOKEN}' clears): ",
        input_fn,
        cur.model or "",
    )
    thinking = cur.thinking or ""
    if client in THINKING_CLIENTS:
        thinking = _ask(
            f"    thinking [{cur.thinking or 'none'}] ('{MODEL_CLEAR_TOKEN}' clears): ",
            input_fn,
            thinking,
        )
    new_model = None if model in ("", MODEL_CLEAR_TOKEN) else model
    new_thinking = None if thinking in ("", MODEL_CLEAR_TOKEN) else thinking
    if new_model is None and new_thinking is None:
        return None
    return ModelChoice(model=new_model, thinking=new_thinking)


def _pick_scope(
    catalog: Catalog, client: str, input_fn: InputFn
) -> tuple[Scope, str | None] | None:
    """Ask for a scope, then its ID; only IDs that can apply to `client` are offered."""
    by_label = {scope.label: scope for scope in Scope}
    picked = _pick("scope", tuple(by_label), input_fn)
    if picked is None:
        return None
    scope = by_label[picked]
    if scope is Scope.ALL:
        return scope, None
    roles = [r for r in catalog.roles.values() if r.supports(client)]
    options = (
        sorted({r.category for r in roles})
        if scope is Scope.CATEGORY
        else sorted(r.role_id for r in roles)
    )
    key = _pick(scope.label, tuple(options), input_fn)
    return None if key is None else (scope, key)


def edit_models_interactively(
    config: LocalConfig, catalog: Catalog, input_fn: InputFn = input
) -> LocalConfig:
    """Walk client, then scope, then value; invalid input is reported and asked again."""
    print("Model choices: role overrides category, category overrides client-wide.")
    print("Unset scopes render no model field, so the client's own default applies.")
    while True:
        client = _pick("client", SUPPORTED_CLIENTS, input_fn)
        if client is None:
            return config
        target = _pick_scope(catalog, client, input_fn)
        if target is None:
            continue
        scope, key = target
        block = config.models.get(client)
        current = block.get(scope, key or ALL_KEY) if block is not None else None
        try:
            config = config.with_choice(
                client, scope, key, _ask_choice(client, current, input_fn)
            )
        except ConfigError as exc:
            print(f"  rejected: {exc.reason}")
