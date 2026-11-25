# Client Compatibility

Each client consumes either native package manifests or rendered local layouts
created by `./setup`.

## Native Package Discovery vs `./setup`

| Client | Native Package Support | `./setup --client` Target Paths Under `$HOME` | Notes |
| --- | --- | --- | --- |
| Pi | `package.json` (`skills`, `prompts`, `themes`) | `.agents/skills`, `.pi/agent/agents`, `.pi/agent/prompts`, `.pi/agent/themes` | Native shared skill discovery; Pi-only roles install here only |
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
| `--config <file>` | Read model choices from this file instead of `$XDG_CONFIG_HOME/agents/config.json` |
| `--no-config` | Ignore the model config for this run; every role renders without a model |
| `--copy` | Copy skill directories as snapshots instead of creating symlinks |
| `--styles` | Install Claude Code visual output style and prompt-reminder hook |
| `--dry-run` | Print planned operations without touching disk |
| `--status`, `--uninstall` | Report drift (`stale`, `missing`, `unmanaged`) or remove managed entries only |

## Custom Home Directories

Pass `--home <path>` to target an isolated home directory or project sandbox
for testing without modifying `~/.agents`, `~/.claude`, `~/.config`, or `~/.pi`.

## Model Choices

`./setup models` writes and every install, status, and render reads one
user-local JSON file. The default path is `$XDG_CONFIG_HOME/agents/config.json`,
or `~/.config/agents/config.json` when `XDG_CONFIG_HOME` is unset. With
`--home <dir>`, only `<dir>/.config/agents/config.json` is used, so sandboxes
never read your real choices. The file must sit outside this repository.

```json
{
  "version": 1,
  "models": {
    "pi": {
      "all": { "model": "<provider/model>", "thinking": "high" },
      "categories": { "review": { "thinking": "max" } },
      "roles": { "feature-implementer": { "model": "<provider/model>" } }
    },
    "opencode": { "roles": { "general-purpose": { "model": "<provider/model>" } } }
  },
  "client_metadata": {
    "pi": { "extensions": true, "exclude_extensions": ["<extension>"] }
  }
}
```

| Rule | Reason |
| --- | --- |
| Resolution order is role, then category, then `all`, field by field | Override only what differs |
| No entry means no `model` or `thinking` field in the rendered role | The client default applies; nothing is invented |
| `thinking` is accepted for `pi` only | Other clients ignore or reject it |
| Model IDs allow only letters, digits, and `. _ : / @ + -` | Blocks frontmatter injection |
| Unknown clients, categories, roles, or keys fail closed | A rename never drops a choice silently |
| `client_metadata` supports `pi` only, with the role adapter key rules | Machine-specific extension lists stay local |
