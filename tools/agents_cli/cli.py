"""Command-line interface routing flags and subcommands cleanly."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .catalog import Catalog, load_catalog, validate_catalog
from .constants import SUPPORTED_CLIENTS
from .deploy import (
    DeploySummary,
    Selection,
    has_managed_claude_styles,
    inspect_status,
    install_selection,
    uninstall_selection,
)
from .errors import AgentsError
from .interactive import is_interactive_tty, run_interactive_wizard
from .render import load_model_map, render_role_for_client


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _add_selection_flags(parser: argparse.ArgumentParser, *, suppress_defaults: bool) -> None:
    def _kw(default: Any, **extra: Any) -> dict[str, Any]:
        # Subparsers suppress defaults so root flags given before a subcommand are never overwritten.
        opts: dict[str, Any] = dict(extra)
        opts["default"] = argparse.SUPPRESS if suppress_defaults else default
        return opts

    parser.add_argument("--all", action="store_true", help="Install all skills, roles, prompts, commands, themes", **_kw(False))
    parser.add_argument("--client", action="append", choices=SUPPORTED_CLIENTS, help="Target client (repeatable)", **_kw(None))
    parser.add_argument("--skill", action="append", help="Skill ID to install (repeatable)", **_kw([]))
    parser.add_argument("--role", action="append", help="Role ID to install (repeatable)", **_kw([]))
    parser.add_argument("--prompt", action="append", help="Prompt ID to install for Pi", **_kw([]))
    parser.add_argument("--command", action="append", help="Command ID to install for OpenCode", **_kw([]))
    parser.add_argument("--theme", action="append", help="Theme ID to install for Pi", **_kw([]))
    parser.add_argument("--styles", action="store_true", help="Include Claude output styles and reminder hook", **_kw(False))
    parser.add_argument("--copy", action="store_true", help="Copy skills instead of creating symlinks", **_kw(False))
    parser.add_argument("--model-map", type=Path, help="Optional JSON model-map file for rendered roles", **_kw(None))
    parser.add_argument("--home", type=Path, help="Override target home directory", **_kw(Path.home()))
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without touching disk", **_kw(False))
    parser.add_argument("--interactive", action="store_true", help="Launch interactive setup menu", **_kw(False))


def _build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="./setup",
        description="Install portable skills, roles, prompts, and themes across agent clients.",
    )
    _add_selection_flags(root, suppress_defaults=False)
    mode_group = root.add_mutually_exclusive_group()
    mode_group.add_argument("--status", action="store_true", help="Inspect installation status without changes")
    mode_group.add_argument("--uninstall", action="store_true", help="Remove managed installations without touching user files")

    sub = root.add_subparsers(dest="subcommand")
    p_install = sub.add_parser("install", help="Install selected assets")
    _add_selection_flags(p_install, suppress_defaults=True)

    p_un = sub.add_parser("uninstall", help="Uninstall managed entries")
    p_un.add_argument("--client", action="append", choices=SUPPORTED_CLIENTS, default=argparse.SUPPRESS)
    p_un.add_argument("--home", type=Path, default=argparse.SUPPRESS)
    p_un.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)

    p_st = sub.add_parser("status", help="Show drift and ownership status")
    _add_selection_flags(p_st, suppress_defaults=True)

    p_ls = sub.add_parser("list", help="List available skills, roles, prompts, commands, and themes")
    p_ls.add_argument("--kind", choices=("all", "skills", "roles", "prompts", "commands", "themes"), default="all")

    p_ren = sub.add_parser("render", help="Print rendered client Markdown for one role")
    p_ren.add_argument("role_id", help="Role ID to render")
    p_ren.add_argument("--client", required=True, choices=SUPPORTED_CLIENTS)
    p_ren.add_argument("--model-map", type=Path, default=argparse.SUPPRESS)

    p_val = sub.add_parser("validate", help="Validate repository catalog structure")
    p_val.add_argument("--strict", action="store_true", help="Fail if skills or roles catalog is empty")
    return root


def _resolve_ids(requested: list[str], available: Mapping[str, object], kind: str) -> tuple[str, ...]:
    unknown = [item for item in requested if item not in available]
    if unknown:
        raise AgentsError(f"select {kind}", ", ".join(unknown), f"unknown {kind} ID(s)")
    return tuple(dict.fromkeys(requested))


def _selection_from_args(args: argparse.Namespace, catalog: Catalog, *, default_all: bool) -> Selection:
    has_explicit_filters = any((args.skill, args.role, args.prompt, args.command, args.theme))
    if args.all and has_explicit_filters:
        raise AgentsError("select assets", None, "cannot combine --all with --skill/--role/--prompt/--command/--theme")

    clients = tuple(dict.fromkeys(args.client)) if args.client else SUPPORTED_CLIENTS
    select_all = bool(args.all) or (default_all and not has_explicit_filters and not args.styles)
    if not has_explicit_filters and not args.styles and args.client:
        select_all = True

    skill_ids = tuple(sorted(catalog.skills)) if select_all else _resolve_ids(args.skill, catalog.skills, "skill")
    role_ids = tuple(sorted(catalog.roles)) if select_all else _resolve_ids(args.role, catalog.roles, "role")
    prompt_ids = tuple(sorted(catalog.prompts)) if select_all else _resolve_ids(args.prompt, catalog.prompts, "prompt")
    command_ids = (
        tuple(sorted(catalog.opencode_commands))
        if select_all
        else _resolve_ids(args.command, catalog.opencode_commands, "command")
    )
    theme_ids = tuple(sorted(catalog.themes)) if select_all else _resolve_ids(args.theme, catalog.themes, "theme")

    return Selection(
        clients=clients,
        skill_ids=skill_ids,
        role_ids=role_ids,
        prompt_ids=prompt_ids,
        command_ids=command_ids,
        theme_ids=theme_ids,
        include_styles=bool(args.styles),
        copy_skills=bool(args.copy),
        model_map=load_model_map(args.model_map),
        dry_run=bool(args.dry_run),
        sync=select_all,
    )


def _print_summary(action: str, summary: DeploySummary) -> None:
    prefix = f"[dry-run] {action}" if summary.dry_run else action
    print(
        f"{prefix}: written={summary.written} unchanged={summary.unchanged} "
        f"removed={summary.removed} paths={len(summary.planned_paths)}"
    )


def _cmd_list(catalog: Catalog, kind: str) -> int:
    sections: list[tuple[str, list[str]]] = [
        ("skills", sorted(catalog.skills)),
        ("roles", sorted(catalog.roles)),
        ("prompts", sorted(catalog.prompts)),
        ("commands", sorted(catalog.opencode_commands)),
        ("themes", sorted(catalog.themes)),
    ]
    for name, items in sections:
        if kind == "all" or kind == name:
            print(f"{name} ({len(items)}): {', '.join(items)}")
    return 0


def _cmd_validate(repo_root: Path, *, strict: bool) -> int:
    report = validate_catalog(repo_root, strict_nonempty=strict)
    print(
        f"Valid catalog: {report.skills_count} skills, {report.roles_count} roles, "
        f"{report.prompts_count} prompts, {report.commands_count} commands, "
        f"{report.themes_count} themes, {report.styles_count} styles, {report.hooks_count} hooks"
    )
    return 0


def _cmd_status(catalog: Catalog, args: argparse.Namespace) -> int:
    sel = _selection_from_args(args, catalog, default_all=True)
    if not sel.include_styles and "claude" in sel.clients and has_managed_claude_styles(catalog.repo_root, args.home):
        sel = Selection(
            clients=sel.clients,
            skill_ids=sel.skill_ids,
            role_ids=sel.role_ids,
            prompt_ids=sel.prompt_ids,
            command_ids=sel.command_ids,
            theme_ids=sel.theme_ids,
            include_styles=True,
            copy_skills=sel.copy_skills,
            model_map=sel.model_map,
            dry_run=True,
            sync=sel.sync,
        )
    for st in inspect_status(catalog, args.home, sel):
        print(
            f"{st.client}: installed={st.installed} stale={st.stale} "
            f"missing={st.missing} unmanaged={st.unmanaged}"
        )
        for detail in st.details:
            print(f"  - {detail}")
    return 0


def _cmd_install(catalog: Catalog, args: argparse.Namespace, argv: list[str]) -> int:
    bare_args = [tok for tok in argv if tok != "install"]
    if args.interactive or (not bare_args and is_interactive_tty()):
        wiz_sel = run_interactive_wizard(
            catalog,
            home=args.home,
            default_copy=bool(args.copy),
            default_dry_run=bool(args.dry_run),
            default_model_map=args.model_map,
        )
        if wiz_sel is None:
            return 0
        _print_summary("install", install_selection(catalog, args.home, wiz_sel))
        return 0
    if not bare_args:
        _build_parser().print_help()
        return 0
    sel = _selection_from_args(args, catalog, default_all=bool(args.all))
    if not sel.has_assets:
        raise AgentsError("install", None, "nothing selected; pass --all, --client, or asset flags")
    _print_summary("install", install_selection(catalog, args.home, sel))
    return 0


def _run_action(args: argparse.Namespace, repo_root: Path, argv: list[str]) -> int:
    subcmd: str | None = getattr(args, "subcommand", None)
    if subcmd is not None and (args.status or args.uninstall):
        raise AgentsError("parse arguments", subcmd, "cannot mix --status/--uninstall with a subcommand")
    if subcmd == "validate":
        return _cmd_validate(repo_root, strict=bool(args.strict))
    catalog = load_catalog(repo_root)
    if subcmd == "list":
        return _cmd_list(catalog, str(args.kind))
    if subcmd == "render":
        if args.role_id not in catalog.roles:
            raise AgentsError("render", args.role_id, "unknown role ID")
        print(render_role_for_client(catalog.roles[args.role_id], args.client, load_model_map(args.model_map)), end="")
        return 0
    if subcmd == "uninstall" or args.uninstall:
        clients = tuple(dict.fromkeys(args.client)) if args.client else SUPPORTED_CLIENTS
        _print_summary("uninstall", uninstall_selection(catalog, args.home, clients, dry_run=bool(args.dry_run)))
        return 0
    if subcmd == "status" or args.status:
        return _cmd_status(catalog, args)
    return _cmd_install(catalog, args, argv)


def main(argv: list[str] | None = None, *, repo_root: Path | None = None) -> int:
    """CLI entrypoint reporting structured errors cleanly to stderr."""
    args_list = list(sys.argv[1:] if argv is None else argv)
    args = _build_parser().parse_args(args_list)
    root = _default_repo_root() if repo_root is None else repo_root
    try:
        return _run_action(args, root, args_list)
    except AgentsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
