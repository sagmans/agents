# Authoring Contract

All catalog assets follow strict structure and naming rules enforced by
`./setup validate --strict` and `make check`.

## Asset Contracts

| Kind | Location | Required Structure |
| --- | --- | --- |
| Skill | `skills/<id>/SKILL.md` | YAML frontmatter with matching `name` and non-empty `description` |
| Role | `roles/<id>/` | `manifest.json` (`id`, `name`, `summary`) + `DEFINITION.md` |
| Pi role adapter | `adapters/pi/roles/<id>/metadata.json` | Optional keys in `PI_ALLOWED_METADATA_FIELDS`; no hardcoded `model` |
| OpenCode adapter | `adapters/opencode/roles/<id>/metadata.json` | Optional keys in `OPENCODE_ALLOWED_METADATA_FIELDS`; non-mutating roles deny edits |
| Prompt | `prompts/<id>.md` | Valid UTF-8 Markdown with H1 heading |
| OpenCode command | `adapters/opencode/commands/<id>.md` | Valid UTF-8 Markdown matching Markdown lint rules |
| Theme | `themes/<id>.json` | Valid JSON object |
| Claude style / hook | `adapters/claude/{output-styles,hooks}/` | `.md` style or executable `.sh` hook passing `shellcheck` and `shfmt` |

## Required `DEFINITION.md` Sections

Every role definition must include these 12 level-2 (`##`) Markdown headings:

- `Mission`
- `Use When`
- `Do Not Use When`
- `Required Inputs`
- `Preconditions and Blockers`
- `Workflow`
- `Evidence Requirements`
- `Decision Rules`
- `Security and Mutation Guardrails`
- `Handoff Contract`
- `Output Format`
- `Completion Criteria`

## Adding or Updating Assets

1. Keep identifiers lowercase alphanumeric with hyphens or underscores
   (`^[a-z0-9][a-z0-9_-]*$`, max 64 chars).
2. Omit machine-specific provider bindings and secrets; use `--model-map` for
   model choices and `${ENV_VAR}` placeholders in `mcp/examples/`.
3. Format shell scripts with `shfmt -w` and verify clean linting and strict
   validation:

```sh
./setup validate --strict
make check
```
