# Authoring Contract

All catalog assets follow strict structure and naming rules enforced by
`./setup validate --strict` and `make check`.

## Asset Contracts

| Kind | Location | Required Structure |
| --- | --- | --- |
| Category pack | `packs.json` | Unique `id` in `VALID_CATEGORIES`, `name`, `summary`, and member `skills`, `prompts`, `commands` |
| Skill | `skills/<id>/SKILL.md` | YAML frontmatter with matching `name` and non-empty `description` |
| Role | `roles/<category>/<id>/` | `manifest.json` (`id`, `category`, `name`, `summary`, optional `clients` list for a client-bound role) + `DEFINITION.md` |
| Pi role adapter | `adapters/pi/roles/<id>/metadata.json` | Optional keys in `PI_ALLOWED_METADATA_FIELDS`; no `model` or `thinking` |
| Role appendix | `adapters/{pi,opencode}/roles/<id>/APPENDIX.md` | Client-only tool bindings appended to that client's render; no frontmatter |
| OpenCode adapter | `adapters/opencode/roles/<id>/metadata.json` | Optional keys in `OPENCODE_ALLOWED_METADATA_FIELDS`; non-mutating roles deny edits |
| Prompt | `prompts/<id>.md` | Valid UTF-8 Markdown with H1 heading |
| OpenCode command | `adapters/opencode/commands/<id>.md` | Valid UTF-8 Markdown matching Markdown lint rules |
| Theme | `themes/<id>.json` | Valid JSON object |
| Claude style / hook | `adapters/claude/{output-styles,hooks}/` | `.md` style or executable `.sh` hook passing `shellcheck` and `shfmt` |

## Role Writing Rules

Routing reads only a role's `summary`; the body loads only after the role is picked.
Keep both short and make each role's boundary obvious next to its siblings.

- **One job per role.** Add a role only when its tools, permissions, output, or
  trigger differ from every existing role. Otherwise extend the nearest role.
- **`summary` is the trigger.** Start with "Use to", "Use when", "Use before",
  "Use after", "Use for", "Use only", or "Use as", name the situation, and say
  whether the role is read-only. Keep it at most 220 characters.
- **Body at most 90 lines.** Workflow steps are heuristics, not scripts; state
  the reason for a rule instead of shouting it.
- **Name siblings in `Scope`.** Every "Out" item points to the role that owns it.
- **Mutation stance comes from `MUTATING_ENGINEER_ROLES`.** Only listed roles
  edit files; every other role is report-only and its OpenCode adapter denies
  edits. `Rules` carries the stance line that `role_guardrail` in
  `tools/agents_cli/constants.py` returns, verbatim and once
  (`REPORT_ONLY_GUARDRAIL`, `MUTATING_GUARDRAIL`, or the `general-purpose`
  fallback override), so every role states the same guardrail.
  `OPENCODE_EDIT_DENIED_ROLES` lists mutating roles that OpenCode still runs
  read-only.

Catalog loading enforces the summary form, the line cap, the section order,
the Workflow step count, and the stance line on every command, not only
`validate --strict`.

## Required `DEFINITION.md` Sections

Every role definition starts with an H1 title and has exactly these 7
level-2 (`##`) headings, in this order. Headings inside fenced `Output`
templates do not count:

| Section | Holds |
| --- | --- |
| `Mission` | One short paragraph: the outcome and the stance (report-only or mutating) |
| `Scope` | `In:` and `Out:` lines; each `Out:` item names the owning role |
| `Inputs` | Required and optional inputs, and what blocks the work |
| `Workflow` | 4-7 numbered steps |
| `Rules` | Decision rules, severity bar, and security and mutation guardrails |
| `Output` | The exact report or change summary shape |
| `Done When` | The completion and evidence bar |

## Adding or Updating Assets

1. Keep identifiers lowercase alphanumeric with hyphens or underscores
   (`^[a-z0-9][a-z0-9_-]*$`, max 64 chars).
2. Omit provider names, model IDs, thinking levels, and secrets. Users choose
   models with `./setup models`; `scripts/personal-scan.sh` rejects provider
   and model IDs. Use `${ENV_VAR}` placeholders in `mcp/examples/`.
3. Add only first-party roles. Do not copy agents that third-party skills or
   plugins install; those stay with their upstream package.
4. Format shell scripts with `shfmt -w` and Python files with `ruff format`,
   then verify clean linting and strict validation:

```sh
./setup validate --strict
make check
```
