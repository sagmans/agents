# Client Compatibility

Each client consumes either native package manifests or rendered local layouts
created by `./setup`.

## Native Package Discovery vs `./setup`

| Client | Native Package Support | `./setup --client` Target Paths Under `$HOME` | Notes |
| --- | --- | --- | --- |
| Pi | `package.json` (`skills`, `prompts`, `themes`) | `.pi/agent/skills`, `.pi/agent/agents`, `.pi/agent/prompts`, `.pi/agent/themes` | Use `--model-map` to bind models per role |
| OpenCode | Skills via `npx skills` | `.config/opencode/skills`, `.config/opencode/agents`, `.config/opencode/commands` | Non-mutating roles keep `edit: deny` |
| Claude Code | `.claude-plugin/` marketplace | `.claude/skills`, `.claude/agents`, `.claude/output-styles`, `.claude/hooks` | Pass `--styles` for style and hook |
| Codex | Skills via `npx skills` | `.codex/skills`, `.codex/agents` | Renders flat Markdown role specs |
| Cursor | Skills via `npx skills` | `.cursor/skills`, `.cursor/agents` | Renders portable agent definitions |
| Gemini CLI | `adapters/gemini/plugin.json`, `npx skills` | `.gemini/skills`, `.gemini/agents` | Use `--copy` where symlinks are restricted |

## Common `./setup` Options

| Flag | Effect |
| --- | --- |
| `--all` | Deploy all validated skills, roles, prompts, commands, and themes |
| `--client <name>` | Limit installation, status, or uninstall to one client (repeatable) |
| `--skill <id>`, `--role <id>` | Deploy specific catalog IDs selectively |
| `--model-map <file>` | Apply user-owned model bindings from JSON (`adapters/pi/model-map.example.json`) |
| `--copy` | Copy skill directories as snapshots instead of creating symlinks |
| `--styles` | Install Claude Code visual output style and prompt-reminder hook |
| `--dry-run` | Print planned operations without touching disk |
| `--status`, `--uninstall` | Report drift (`stale`, `missing`, `unmanaged`) or remove managed entries only |

## Custom Home Directories

Pass `--home <path>` to target an isolated home directory or project sandbox
for testing without modifying `~/.claude`, `~/.config`, or `~/.pi`.
