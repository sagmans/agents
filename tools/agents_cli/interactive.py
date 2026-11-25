"""Interactive terminal setup wizard using pure Python stdlib."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from .catalog import Catalog
from .constants import SUPPORTED_CLIENTS
from .deploy import Selection
from .errors import RenderError
from .local_config import LocalConfig
from .packs import expand_pack_assets

InputFn = Callable[[str], str]
_QUIT_TOKENS: frozenset[str] = frozenset({"q", "quit", "exit"})
_CUSTOM_TOKEN = "custom"


class _WizardCancelled(Exception):
    """Raised cleanly when the user enters a quit token during interactive prompts."""


def _prompt_line(prompt: str, input_fn: InputFn, default: str = "") -> str:
    raw = input_fn(prompt).strip()
    if raw.lower() in _QUIT_TOKENS:
        raise _WizardCancelled
    return raw if raw else default


def _prompt_yes_no(prompt: str, input_fn: InputFn, *, default: bool = False) -> bool:
    hint = "[Y/n]" if default else "[y/N]"
    ans = _prompt_line(f"{prompt} {hint}: ", input_fn).lower()
    if not ans:
        return default
    return ans in {"y", "yes"}


def _parse_index_or_names(
    raw: str, options: tuple[str, ...], *, allow_none: bool = False
) -> tuple[str, ...]:
    token = raw.strip().lower()
    if token == "all":
        return options
    if allow_none and token == "none":
        return ()
    chosen: list[str] = []
    invalid: list[str] = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        if item.isdigit():
            idx = int(item) - 1
            if 0 <= idx < len(options):
                if options[idx] not in chosen:
                    chosen.append(options[idx])
            else:
                invalid.append(item)
        elif item in options:
            if item not in chosen:
                chosen.append(item)
        else:
            invalid.append(item)
    if invalid:
        print(
            f"warning: ignored unrecognized choice(s): {', '.join(invalid)}",
            file=sys.stderr,
        )
    return tuple(chosen)


def _select_clients(input_fn: InputFn) -> tuple[str, ...]:
    print("\nAvailable clients:")
    for idx, client in enumerate(SUPPORTED_CLIENTS, 1):
        print(f"  {idx}. {client}")
    raw = _prompt_line(
        "Select clients (comma numbers/names or 'all') [all]: ", input_fn, "all"
    )
    picked = _parse_index_or_names(raw, SUPPORTED_CLIENTS)
    if not picked:
        raise RenderError("interactive setup", None, "no valid client selected")
    return picked


def _select_subset(
    label: str, items: tuple[str, ...], input_fn: InputFn, *, default: str = "all"
) -> tuple[str, ...]:
    if not items:
        return ()
    raw = _prompt_line(
        f"Install {label}? ({len(items)} available; 'all', 'none', or comma names) [{default}]: ",
        input_fn,
        default,
    )
    return _parse_index_or_names(raw, items, allow_none=True)


def _select_packs_or_custom(
    catalog: Catalog, clients: tuple[str, ...], input_fn: InputFn
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Let users pick purpose packs quickly while keeping 'custom' per-asset selection."""
    pack_ids = tuple(catalog.packs)
    if pack_ids:
        print("\nAvailable packs:")
        for idx, pid in enumerate(pack_ids, 1):
            p = catalog.packs[pid]
            print(
                f"  {idx}. {pid} ({len(p.skill_ids)} skills, {len(p.role_ids)} roles, "
                f"{len(p.prompt_ids)} prompts, {len(p.command_ids)} commands) - {p.summary}"
            )
        raw = _prompt_line(
            "Select packs ('all', 'custom', or comma numbers/names) [all]: ",
            input_fn,
            "all",
        )
        if raw.strip().lower() != _CUSTOM_TOKEN:
            picked = _parse_index_or_names(raw, pack_ids)
            if not picked:
                raise RenderError("interactive setup", None, "no valid pack selected")
            skills, roles, prompts, commands = expand_pack_assets(catalog.packs, picked)
            return (
                skills,
                roles,
                prompts if "pi" in clients else (),
                commands if "opencode" in clients else (),
            )

    skill_ids = _select_subset("skills", tuple(sorted(catalog.skills)), input_fn)
    role_ids = _select_subset("roles", tuple(sorted(catalog.roles)), input_fn)
    prompt_ids = (
        _select_subset("Pi prompts", tuple(sorted(catalog.prompts)), input_fn)
        if "pi" in clients
        else ()
    )
    command_ids = (
        _select_subset(
            "OpenCode commands", tuple(sorted(catalog.opencode_commands)), input_fn
        )
        if "opencode" in clients
        else ()
    )
    return skill_ids, role_ids, prompt_ids, command_ids


def run_interactive_wizard(
    catalog: Catalog,
    *,
    home: Path,
    default_copy: bool = False,
    default_dry_run: bool = False,
    config: LocalConfig | None = None,
    input_fn: InputFn = input,
) -> Selection | None:
    """Guide interactive client/asset selection cleanly before any file writes."""
    try:
        return _run_wizard_prompts(
            catalog,
            home=home,
            default_copy=default_copy,
            default_dry_run=default_dry_run,
            config=config if config is not None else LocalConfig(),
            input_fn=input_fn,
        )
    except (EOFError, KeyboardInterrupt, _WizardCancelled):
        print("\nAborted without changes.")
        return None


def _run_wizard_prompts(
    catalog: Catalog,
    *,
    home: Path,
    default_copy: bool,
    default_dry_run: bool,
    config: LocalConfig,
    input_fn: InputFn,
) -> Selection | None:
    print("agents setup wizard (plug-and-play installer; enter 'q' to quit)")
    print(f"Target home: {home}")
    print(
        f"Catalog: {len(catalog.packs)} packs, {len(catalog.skills)} skills, {len(catalog.roles)} roles, "
        f"{len(catalog.prompts)} prompts, {len(catalog.opencode_commands)} commands, "
        f"{len(catalog.themes)} themes, {len(catalog.claude_styles)} styles"
    )
    clients = _select_clients(input_fn)
    skill_ids, role_ids, prompt_ids, command_ids = _select_packs_or_custom(
        catalog, clients, input_fn
    )
    theme_ids = (
        _select_subset("Pi themes", tuple(sorted(catalog.themes)), input_fn)
        if "pi" in clients
        else ()
    )
    include_styles = (
        _prompt_yes_no("Install Claude output styles & hooks?", input_fn, default=False)
        if "claude" in clients
        else False
    )
    copy_skills = _prompt_yes_no(
        "Copy skill directories instead of symlinking?", input_fn, default=default_copy
    )
    dry_run = _prompt_yes_no(
        "Preview changes with --dry-run first?", input_fn, default=default_dry_run
    )

    print("\nSummary:")
    print(f"  clients  : {', '.join(clients)}")
    print(f"  skills   : {len(skill_ids)} ({'copy' if copy_skills else 'symlink'})")
    print(f"  roles    : {len(role_ids)}")
    print(
        f"  models   : {config.entry_count()} choice(s) from the local config"
        " (change with `./setup models edit`)"
    )
    print(
        f"  extras   : prompts={len(prompt_ids)} commands={len(command_ids)} themes={len(theme_ids)} styles={include_styles}"
    )
    if not _prompt_yes_no("Proceed?", input_fn, default=True):
        print("Aborted without changes.")
        return None
    return Selection(
        clients=clients,
        skill_ids=skill_ids,
        role_ids=role_ids,
        prompt_ids=prompt_ids,
        command_ids=command_ids,
        theme_ids=theme_ids,
        include_styles=include_styles,
        copy_skills=copy_skills,
        config=config,
        dry_run=dry_run,
        sync=False,
    )


def is_interactive_tty() -> bool:
    """Only launch the prompt menu automatically when stdin and stdout are TTYs."""
    return sys.stdin.isatty() and sys.stdout.isatty()
