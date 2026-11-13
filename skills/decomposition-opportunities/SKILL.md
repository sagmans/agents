---
name: decomposition-opportunities
description: Use when implementing, building, refactoring, restructuring, or reviewing code where file growth, mixed responsibilities, poor discoverability, weak abstractions, tight coupling, clean-code debt, or maintainability risk may emerge.
---

# Decomposition Opportunities

## Core principle

Decompose around ownership, invariants, and reasons to change. File size is a signal, not a boundary criterion: a good split lowers reader load and hides decisions behind a stable interface.

## Growth rule

Keep every authored code file below 500 physical lines (499 maximum), including source, tests, scripts, and executable configuration. Inventory generated, vendored, lock, snapshot, and data artifacts separately; change their source or generator instead of hand-splitting outputs.

Treat 450–499 lines as a growth boundary, not spare capacity. Adding behavior there requires a coherent extraction in the same change or an explicit scope decision. “Smallest diff” means smallest complete maintainable change, not fewest touched files. Never manufacture headroom through compressed formatting, removed tests or useful comments, shortened names, or deferred cleanup.

## Method

1. Inspect repository instructions, the target, neighbors, imports, exports, callers, tests, and seams. Measure projected lines before editing.
2. Map responsibilities, invariants, state authority, side effects, and dependencies. Keep code together when it enforces the same invariant or changes for the same reason.
3. Compare two real boundaries. Prefer a cohesive capability with a truthful name, narrow interface, independent tests, and dependencies toward stable policy.
4. Characterize behavior and work test-first. Extract the smallest coherent unit, migrate every caller, and preserve compatibility only for evidenced consumers.
5. Remove transitional paths. Verify behavior, file sizes, dependency direction, cycles, unused exports, and discoverability.
6. Choose architecture from evidence: domain or feature units, ports for volatile integrations, pipeline phases, or UI state/effect/rendering boundaries. Keep cohesive modules intact when splitting creates shallow wrappers.

### Example

When `checkout.ts` is 470 lines and gains discount rules, extract cohesive rule policy into `discount-policy.ts` with focused tests while checkout keeps orchestration. Moving the last 100 lines into `checkout-utils.ts` satisfies arithmetic, not design.

## Common mistakes

- Splitting by line ranges, symbol counts, or suffixes rather than responsibility.
- Creating `utils`, `helpers`, `common`, or catch-all `types` modules.
- Replacing one large file with shallow pass-through files, re-export facades, or relocated coupling.
- Forcing layers, DDD, ports, plugins, or microservices without repository evidence.

## Pressure checks

| Rationalization | Correction |
| --- | --- |
| “The smallest diff stays in one file.” | Extract a focused owned unit in the same change or surface the conflict. |
| “It still fits below 500.” | A 450–499 line file reached its growth boundary; remaining lines are not patch budget. |
| “Crossing 500 is temporary.” | No deferred exception exists; keep the limit or obtain a scope decision first. |
| “More files mean more complexity.” | Count concepts and interface burden. Reject shallow splits; keep cohesive units. |

Stop and reassess when a change appends to a near-limit file, creates a generic dumping ground, leaves a cycle or compatibility shell, or defers known structural debt.
