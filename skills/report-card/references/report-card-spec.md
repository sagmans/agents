# Report Card Specification

Every closeout report uses four fixed sections so reviewers can audit claims,
evidence, open items, and references in one consistent layout.

## Sections and Status Rules

| Section | Holds | Allowed statuses |
| --- | --- | --- |
| `Prior work` | Baseline state, related issues, baseline checks, prior commits | `Done`, `Partial`, `Blocked`, `None` |
| `Results` | Claim paired beside exact verification evidence, SHA, source, and gaps | `Done`, `Partial`, `Blocked`, `None` |
| `Next` | Open work, pending decisions, or residual risks (`None` when empty) | `Partial`, `Blocked`, `None` |
| `Links` | Confirmable links built from session tool output | Unstatused |

- **Overall status precedence:** `Blocked > Partial > Done` across statused sections (`None` does not degrade `Done`; if every statused section is `None`, the overall status is `None`).
- **`Next` status rule:** Set `Next` to `None` when empty, `Partial` when optional follow-up exists, and `Blocked` when progress waits on an external decision or dependency.

## Evidence Discipline

- Pair every Result claim directly with verifiable command output, SHA, or observed state from the current session.
- State explicitly what was skipped or could not be tested (`NOT_CHECKED`).
- Never embed credentials, private tokens, or internal-only hostnames in rendered cards.
