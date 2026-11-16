# Client Compatibility

Each client consumes either native package manifests or rendered local layouts
created by `./setup`.

## Native Package Discovery vs `./setup`

| Client | Native Package Support | `./setup --client` Target Paths Under `$HOME` | Notes |
| --- | --- | --- | --- |
| Pi | `package.json` (`skills`, `prompts`, `themes`) | `.agents/skills`, `.pi/agent/agents`, `.pi/agent/prompts`, `.pi/agent/themes` | Native shared skill discovery; use `--model-map` for roles |
| OpenCode | Skills via `npx skills` | `.config/opencode/skills`, `.config/opencode/agents`, `.config/opencode/commands` | Non-mutating roles keep `edit: deny` |
| Claude Code | `.claude-plugin/` marketplace | `.claude/skills`, `.claude/agents`, `.claude/output-styles`, `.claude/hooks` | Pass `--styles` for style and hook |
| Codex | Skills via `npx skills` | `.codex/skills`, `.codex/agents` | Renders flat Markdown role specs |
| Cursor | Skills via `npx skills` | `.cursor/skills`, `.cursor/agents` | Renders portable agent definitions |
| Gemini CLI | `adapters/gemini/plugin.json`, `npx skills` | `.gemini/skills`, `.gemini/agents` | Use `--copy` where symlinks are restricted |

## Shared Pi Skills

Pi discovers `~/.agents/skills` directly. `./setup --client pi` uses this shared
location instead of deploying another copy to `~/.pi/agent/skills`. Other client
paths and native package resources do not change.

Existing shared skills remain protected: setup refuses to overwrite entries
that it does not own. Select only missing skills, or review ownership before
replacing an existing installation.

This change does not move old installations automatically. Before retiring an
entry from `~/.pi/agent/skills`, compare its complete contents with the shared
entry. Keep differing or unique content, and archive redundant entries outside
both discovery directories. Keep the archive until the next startup confirms
that the expected skills load. Restore archived entries to their original paths
to roll back; restoring duplicates also restores collision warnings.

Status and uninstall use the new shared location. Old Pi entries and their
ownership manifest remain untouched; review them separately before cleanup.

## Common `./setup` Options

| Flag | Effect |
| --- | --- |
| `--all` | Deploy all validated skills, roles, prompts, commands, and themes |
| `--pack <id>` | Deploy all skills, roles, prompts, and commands in a category pack (repeatable) |
| `--client <name>` | Limit installation, status, or uninstall to one client (repeatable) |
| `--skill <id>`, `--role <id>` | Deploy specific catalog IDs selectively |
| `--model-map <file>` | Apply user-owned model bindings, Pi `client_metadata`, and `role_appendices` from JSON (`adapters/pi/model-map.example.json`) |
| `--copy` | Copy skill directories as snapshots instead of creating symlinks |
| `--styles` | Install Claude Code visual output style and prompt-reminder hook |
| `--dry-run` | Print planned operations without touching disk |
| `--status`, `--uninstall` | Report drift (`stale`, `missing`, `unmanaged`) or remove managed entries only |

## Custom Home Directories

Pass `--home <path>` to target an isolated home directory or project sandbox
for testing without modifying `~/.agents`, `~/.claude`, `~/.config`, or `~/.pi`.
