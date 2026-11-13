# Agent Guide

## Repository Overview

This repository provides portable agent skills, role definitions, client
adapters, prompt templates, themes, and a zero-dependency `./setup` installer
that works across Pi, OpenCode, Claude Code, Codex, Cursor, and Gemini CLI.

## Structure

- `skills/` - Portable `SKILL.md` packages and companion scripts/tests
- `roles/` - Client-neutral role `DEFINITION.md` and `manifest.json` packages
- `adapters/` - Client-specific role metadata, output styles, hooks, and plugins
- `prompts/` - Reusable agent workflow prompts
- `themes/` - UI theme configurations
- `mcp/` - Inert example MCP configurations (no live credentials)
- `tools/agents_cli/` - Pure-stdlib Python implementation behind `./setup`
- `scripts/` - Validation, leakage guard, hook setup, and clean-room dogfooding

## Setup and Verification

Install Git hooks once per clone and run the full repository check suite:

```sh
./scripts/setup-hooks
make check
```

## Git Hooks and Commit Convention

Checks run in `.githooks/`. Never use `--no-verify` or bypass local hooks.

Commit messages must follow `.githooks/GIT_CONVENTION.md` (Conventional Commits
with a WHY-focused body and `Signed-off-by` DCO trailer, signed with GPG via
`git commit -s -S`). Generic and repository hooks require `gitleaks`,
`osv-scanner`, `semgrep`, `lizard`, `markdownlint-cli2`, `pyright`,
`shellcheck`, and `shfmt` (plus `actionlint` and `zizmor` when workflows
change). Any missing tool fails the hook.
