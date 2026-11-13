"""Interactive terminal setup wizard using pure Python stdlib."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from .catalog import Catalog
from .constants import SUPPORTED_CLIENTS
from .deploy import Selection
from .errors import RenderError
from .render import ModelMap, load_model_map

InputFn = Callable[[str], str]


def _prompt_line(prompt: str, input_fn: InputFn, default: str = "") -> str:
    raw = input_fn(prompt).strip()
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
        print(f"warning: ignored unrecognized choice(s): {', '.join(invalid)}", file=sys.stderr)
    return tuple(chosen)


def _select_clients(input_fn: InputFn) -> tuple[str, ...]:
    print("\nAvailable clients:")
    for idx, client in enumerate(SUPPORTED_CLIENTS, 1):
        print(f"  {idx}. {client}")
    raw = _prompt_line("Select clients (comma numbers/names or 'all') [all]: ", input_fn, "all")
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


def run_interactive_wizard(
    catalog: Catalog,
    *,
    home: Path,
    default_copy: bool = False,
    default_dry_run: bool = False,
    default_model_map: Path | None = None,
    input_fn: InputFn = input,
) -> Selection | None:
    """Guide interactive client/asset selection cleanly before any file writes."""
    try:
        return _run_wizard_prompts(
            catalog,
            home=home,
            default_copy=default_copy,
            default_dry_run=default_dry_run,
            default_model_map=default_model_map,
            input_fn=input_fn,
        )
    except (EOFError, KeyboardInterrupt):
        print("\nAborted without changes.")
        return None


def _run_wizard_prompts(
    catalog: Catalog,
    *,
    home: Path,
    default_copy: bool,
    default_dry_run: bool,
    default_model_map: Path | None,
    input_fn: InputFn,
) -> Selection | None:
    print("agents setup wizard (plug-and-play installer)")
    print(f"Target home: {home}")
    print(
        f"Catalog: {len(catalog.skills)} skills, {len(catalog.roles)} roles, "
        f"{len(catalog.prompts)} prompts, {len(catalog.opencode_commands)} commands, "
        f"{len(catalog.themes)} themes, {len(catalog.claude_styles)} styles"
    )
    clients = _select_clients(input_fn)
    skill_ids = _select_subset("skills", tuple(sorted(catalog.skills)), input_fn)
    role_ids = _select_subset("roles", tuple(sorted(catalog.roles)), input_fn)
    prompt_ids = _select_subset("Pi prompts", tuple(sorted(catalog.prompts)), input_fn) if "pi" in clients else ()
    command_ids = (
        _select_subset("OpenCode commands", tuple(sorted(catalog.opencode_commands)), input_fn)
        if "opencode" in clients
        else ()
    )
    theme_ids = _select_subset("Pi themes", tuple(sorted(catalog.themes)), input_fn) if "pi" in clients else ()
    include_styles = (
        _prompt_yes_no("Install Claude output styles & hooks?", input_fn, default=False)
        if "claude" in clients
        else False
    )
    copy_skills = _prompt_yes_no("Copy skill directories instead of symlinking?", input_fn, default=default_copy)
    default_mm_str = str(default_model_map) if default_model_map else ""
    model_map_raw = _prompt_line(
        f"Optional --model-map JSON path [{default_mm_str or 'none'}]: ",
        input_fn,
        default_mm_str,
    )
    model_map: ModelMap = (
        load_model_map(Path(model_map_raw))
        if model_map_raw and model_map_raw != "none"
        else load_model_map(None)
    )
    dry_run = _prompt_yes_no("Preview changes with --dry-run first?", input_fn, default=default_dry_run)

    print("\nSummary:")
    print(f"  clients  : {', '.join(clients)}")
    print(f"  skills   : {len(skill_ids)} ({'copy' if copy_skills else 'symlink'})")
    print(f"  roles    : {len(role_ids)}")
    print(f"  extras   : prompts={len(prompt_ids)} commands={len(command_ids)} themes={len(theme_ids)} styles={include_styles}")
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
        model_map=model_map,
        dry_run=dry_run,
        sync=False,
    )


def is_interactive_tty() -> bool:
    """Only launch the prompt menu automatically when stdin and stdout are TTYs."""
    return sys.stdin.isatty() and sys.stdout.isatty()
