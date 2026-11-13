---
name: diff-guide
description: Use when repository changes are ready for handoff or completion reporting, or when explaining a worktree, branch, commit range, or pull request changeset.
---

# Diff Guide

## Core principle

Turn the actual changeset into a structured explanation, not a changelog. Group exact hunks by purpose so the reader can connect intent, decisions, effects, evidence, and risk without reconstructing them from file order.

## Establish the change set

1. Identify the changeset boundary from repository evidence: worktree, staged changes, branch base, commit range, or pull request.
2. Inspect the diff, diff statistics, file status, and relevant validation results.
3. Account for every changed file and hunk. Never recreate patch text from memory.
4. Separate independent purposes. If one hunk mixes purposes, keep it intact under its dominant purpose and flag the coupling.

## Handoff format

### Changeset map

Lead with a compact table:

| Order | Purpose | Files and hunks | Risk | Diff focus |
| --- | --- | --- | --- | --- |

Order purposes by dependency, impact, and risk. Put contracts, data models, security boundaries, migrations, and core behavior before adapters, tests, generated output, and documentation.

### Purpose: [outcome]

For each purpose, provide these parts:

- **Why:** The user-visible or engineering outcome.
- **Decisions:** Non-obvious choices, rejected alternatives, compatibility constraints, and trade-offs.
- **Actual diff:** Verbatim unified diff headers and complete hunks in a `diff` fence. Include enough unchanged context to locate and understand each change.
- **Diff guidance:** Explain how the hunk changes behavior, which dependencies or invariants it affects, which edge cases matter, and what evidence supports the change.

A hunk appears once. Cross-reference it from another purpose instead of duplicating it. Preserve paths, hunk headers, added lines, removed lines, and context exactly.

### Validation and residual risk

Finish with:

- Commands or real usage performed and their outcomes.
- Untested behavior, blocked checks, assumptions, and residual risks.
- A coverage statement that names any changed content not shown inline.

## Large and non-text changes

Show every human-authored text hunk inline. For generated files, lockfiles, snapshots, or bulk formatting, show the source hunk that caused the output and provide the exact artifact path, diff statistics, generator or verification command, and inspection method. For binary files, provide the path, old/new metadata, purpose, and visual or domain-specific verification. Never invent omitted patch lines.

If the human-authored patch is too large for a usable message, provide a complete diff artifact and include its path or link. Keep the changeset map and highest-risk actual hunks inline. State exactly which hunks remain in the artifact.

## Quality gate

Before delivery, confirm:

- The changeset boundary is explicit.
- Every changed file and hunk is accounted for.
- Purpose groups explain why, not only what.
- Decisions expose information absent from the patch.
- Diff blocks contain actual patch text.
- Diff guidance names concrete effects, checks, invariants, and risks.
- Validation claims match fresh evidence.

## References

- [Google: Writing good CL descriptions](https://google.github.io/eng-practices/review/developer/cl-descriptions.html)
- [Google: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
- [Google: Navigating a CL in review](https://google.github.io/eng-practices/review/reviewer/navigate.html)
- [GitHub: Reviewing proposed changes](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/reviewing-proposed-changes-in-a-pull-request)
- [Git: git-diff](https://git-scm.com/docs/git-diff)
