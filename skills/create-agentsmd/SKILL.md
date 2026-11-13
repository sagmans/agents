---
name: create-agentsmd
description: Create, revise, or audit repository AGENTS.md files from verified project evidence and agents.md conventions. Use whenever the user asks for AGENTS.md, agent instructions, repository guidance for coding agents, nested agent guidance, or alignment with agents.md.
---

# Create AGENTS.md

Build a compact **operating map** for agents. `AGENTS.md` complements human
documentation; it should expose repository-specific facts and sharp edges that
change how an agent works, not restate the README or generic engineering advice.

Read [references/conventions.md](references/conventions.md) before drafting.

## 1. Resolve scope

1. Confirm the target repository or subtree.
2. Find every applicable `AGENTS.md` from repository root to target directory.
3. Read existing instructions completely. Preserve valid local constraints and
   avoid conflicts with parent guidance.
4. If the request could mean either a root file or subtree-specific file, inspect
   the layout first. Ask only when repository evidence cannot decide placement.

Completion: target path and inherited instruction scope are known.

## 2. Gather repository evidence

Inspect authoritative files before writing:

- package/build manifests and lockfiles
- entrypoints and high-value source/test directories
- CI workflows and repository-owned validation scripts
- README, CONTRIBUTING, security, release, and architecture documents
- existing nested agent instructions

Trace commands to their owning scripts or CI definitions. Run safe inspection
commands when useful. Never invent commands, paths, versions, support claims, or
policies from ecosystem convention.

Completion: each proposed instruction maps to current repository evidence.

## 3. Choose placement

Use one root `AGENTS.md` for guidance applying broadly. Add a nested file only
when a subtree has materially different commands, architecture, ownership, or
safety constraints. Keep nested guidance self-contained and compatible with the
root because agent implementations differ in how they combine instruction files.

When revising an existing file, make the smallest evidence-backed edit. Do not
replace useful project knowledge merely to impose a preferred template.

Completion: placement is narrow enough to avoid irrelevant context and broad
enough to cover intended work.

## 4. Draft the operating map

Use standard Markdown. No heading schema is mandatory. Include only sections
that earn their context cost, commonly:

- concise project purpose and runtime boundary
- high-value repository map
- exact setup, focused-check, and full-validation commands
- repository-specific architecture or coding constraints
- testing completion criteria
- privacy, security, generated-file, dependency, or release boundaries
- links to authoritative docs instead of duplicated detail

Prefer executable commands and checkable completion criteria. Explain why a
non-obvious constraint exists when that reason prevents future drift.

Exclude:

- personas, conversational style, or response-length rules
- generic principles agents already know
- exhaustive directory inventories
- duplicated README or CONTRIBUTING prose
- volatile details with a better source of truth
- absolute maintainer-local paths
- unverified claims or commands

Completion: every line changes agent behavior and has a repository source.

## 5. Validate

1. Re-read the draft against applicable parent and nested instructions.
2. Verify referenced paths, links, and commands exist.
3. Run the repository's relevant documentation or full validation gate when
   practical; otherwise state exactly what was not run.
4. Review the diff for duplication, contradiction, stale specificity, and scope
   leakage.
5. Report the created or changed paths, evidence used, validation run, and any
   unresolved decision.

Completion: file is concise, evidence-backed, conflict-free, and validation is
truthfully reported.
