"""`./setup models`: view and change the user-local model choices, by flag, file, or prompt.

Installs read the same file, so a choice made here takes effect on the next install. Nothing here
invents a model: non-interactive calls change only what a flag or file names explicitly.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .catalog import Catalog
from .constants import MODEL_CLEAR_TOKEN, SUPPORTED_CLIENTS, THINKING_CLIENTS
from .errors import AgentsError, ConfigError
from .local_config import (
    ALL_SCOPE,
    LocalConfig,
    ModelChoice,
    check_catalog_ids,
    read_config_file,
    save_local_config,
)

InputFn = Callable[[str], str]
ConfigLoader = Callable[[argparse.Namespace, Catalog], LocalConfig]
FlagAdder = Callable[..., None]
_QUIT_TOKENS: frozenset[str] = frozenset({"q", "quit", "exit"})
_SCOPE_LABELS: dict[str, str] = {
    ALL_SCOPE: "client-wide",
    "categories": "category",
    "roles": "role",
}


class ModelsWizardCancelled(Exception):
    """Raised when the user quits the editor; nothing is saved."""


def add_models_parser(sub: Any, add_config_flags: FlagAdder) -> None:
    """Register `models` with its actions; `show` is the default."""
    p = sub.add_parser(
        "models",
        help="Show or change user-local model choices (never stored in this repository)",
    )
    _add_common(p, add_config_flags, suppress=False)
    actions = p.add_subparsers(dest="models_action")
    _add_common(
        actions.add_parser(
            "show", help="Print the config path and every stored choice"
        ),
        add_config_flags,
    )
    for name, helptext in (
        ("set", "Store a model and/or thinking level for one scope"),
        ("clear", "Remove the choice for one scope"),
    ):
        ap = actions.add_parser(name, help=helptext)
        _add_common(ap, add_config_flags)
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
    _add_common(ap, add_config_flags)
    ap.add_argument("file", type=Path)
    _add_common(
        actions.add_parser("edit", help="Change choices interactively"),
        add_config_flags,
    )


def _add_common(
    parser: argparse.ArgumentParser,
    add_config_flags: FlagAdder,
    *,
    suppress: bool = True,
) -> None:
    """Accept `--home` and config flags before or after the action word."""
    add_config_flags(parser, suppress_defaults=suppress)
    parser.add_argument(
        "--home",
        type=Path,
        default=argparse.SUPPRESS if suppress else Path.home(),
        help="Home whose config is used (default: your home)",
    )


def _scope_of(args: argparse.Namespace) -> tuple[str, str | None]:
    if getattr(args, "role", None):
        return "roles", str(args.role)
    if getattr(args, "category", None):
        return "categories", str(args.category)
    return ALL_SCOPE, None


def _print_config(config: LocalConfig, path: Path) -> None:
    print(f"config: {path} ({'present' if path.exists() else 'absent'})")
    if not config.models:
        print("no model choices: every role renders without a model field")
    for client in SUPPORTED_CLIENTS:
        block = config.models.get(client)
        if block is None or block.is_empty:
            continue
        rows: list[tuple[str, str, ModelChoice]] = []
        if block.all is not None:
            rows.append((ALL_SCOPE, "*", block.all))
        rows += [("categories", k, v) for k, v in sorted(block.categories.items())]
        rows += [("roles", k, v) for k, v in sorted(block.roles.items())]
        print(f"{client}:")
        for scope, key, choice in rows:
            parts = [f"model={choice.model}"] if choice.model else []
            parts += [f"thinking={choice.thinking}"] if choice.thinking else []
            print(f"  {_SCOPE_LABELS[scope]:<11} {key:<44} {' '.join(parts)}")
    if config.client_metadata:
        print(f"client_metadata: {', '.join(sorted(config.client_metadata))}")


def run_models_command(
    args: argparse.Namespace,
    catalog: Catalog,
    path: Path,
    load_config: ConfigLoader,
    input_fn: InputFn = input,
) -> int:
    """Apply one models action; every write is validated against the catalog first."""
    if getattr(args, "no_config", False):
        raise AgentsError("models", None, "--no-config cannot be combined with models")
    config = load_config(args, catalog)
    action = getattr(args, "models_action", None) or "show"
    if action == "show":
        _print_config(config, path)
        return 0
    if action == "set":
        if args.model is None and args.thinking is None:
            raise AgentsError("models set", None, "pass --model and/or --thinking")
        scope, key = _scope_of(args)
        updated = config.with_choice(
            args.client, scope, key, ModelChoice(args.model, args.thinking)
        )
    elif action == "clear":
        scope, key = _scope_of(args)
        updated = config.with_choice(args.client, scope, key, None)
    elif action == "import":
        updated = config.merged_with(read_config_file(args.file.expanduser()))
    else:
        try:
            updated = edit_models_interactively(config, catalog, input_fn)
        except (EOFError, KeyboardInterrupt, ModelsWizardCancelled):
            print("\nAborted without changes.")
            return 0
    check_catalog_ids(updated, catalog)
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


def edit_models_interactively(
    config: LocalConfig, catalog: Catalog, input_fn: InputFn = input
) -> LocalConfig:
    """Walk client, then scope, then value; invalid input is reported and asked again."""
    categories = tuple(sorted({r.category for r in catalog.roles.values()}))
    roles = tuple(sorted(catalog.roles))
    print("Model choices: role overrides category, category overrides client-wide.")
    print("Unset scopes render no model field, so the client's own default applies.")
    while True:
        client = _pick("client", SUPPORTED_CLIENTS, input_fn)
        if client is None:
            return config
        scope_name = _pick("scope", ("client-wide", "category", "role"), input_fn)
        if scope_name is None:
            continue
        scope, key = ALL_SCOPE, None
        if scope_name == "category":
            key = _pick("category", categories, input_fn)
            scope = "categories"
        elif scope_name == "role":
            key = _pick("role", roles, input_fn)
            scope = "roles"
        if scope != ALL_SCOPE and key is None:
            continue
        block = config.models.get(client)
        current = None
        if block is not None:
            current = (
                block.all
                if scope == ALL_SCOPE
                else (block.categories if scope == "categories" else block.roles).get(
                    key or ""
                )
            )
        try:
            config = config.with_choice(
                client, scope, key, _ask_choice(client, current, input_fn)
            )
        except ConfigError as exc:
            print(f"  rejected: {exc.reason}")
