# Codex Client Adapter

Use `./setup --client codex` to install portable skills and role definitions
for Codex without duplicating source files.

## Installed Layout

| Asset | Source | Target Under `$HOME` |
| --- | --- | --- |
| Skills | `skills/<id>/` | `~/.codex/skills/<id>` |
| Roles | `roles/<id>/` | `~/.codex/agents/<id>.md` |

## Usage

Preview changes first:

```sh
./setup --client codex --dry-run
```

Install all skills and roles for Codex:

```sh
./setup --client codex
```

Check drift or uninstall cleanly later:

```sh
./setup status --client codex
./setup uninstall --client codex
```
