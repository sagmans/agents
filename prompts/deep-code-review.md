---
description: Deep adversarial review of current worktree changes
argument-hint: "[scope or base ref]"
---

# Deep Code Review

Perform a deep, adversarial, report-only code review of `${@:-the entire current worktree against origin/<default-branch>}`.

## Scope

- With no argument, resolve the repository's default branch from local `origin/HEAD` or other authoritative repository evidence and use `origin/<default-branch>` as the review base. Never substitute the current branch's upstream tracking branch.
- Review the complete delta from that base through the working tree: every committed change between the base and `HEAD`, every staged and unstaged tracked-file change, every deletion and rename, and the full content of every non-ignored untracked file.
- With an argument, treat it as an explicit scope or base override and state the interpretation before reviewing.
- Review changed code and the relevant callers, consumers, tests, configuration, generated artifacts, and operational paths needed to establish impact.
- Report only issues introduced, exposed, or materially worsened by this worktree. Record important pre-existing issues separately only when they directly affect the change.
- Derive intended behavior from the request, commits, tests, documentation, and repository conventions. Mark unresolved intent explicitly; never invent requirements.

## Method

Fan out across independent review angles. Trace each candidate through actual control flow, data flow, state transitions, call sites, and tests. Adversarially verify reachability and impact, deduplicate overlapping findings, and discard unsupported speculation before synthesis.

Analyze every applicable dimension:

- Functional correctness: requirement fit, regressions, edge and boundary cases, invariants, state transitions, concurrency, ordering, and observable behavior.
- Error handling and failure semantics: error detection and classification, context-preserving propagation across boundaries, exception/result mapping, cleanup, retry eligibility, bounded retries, backoff and jitter, idempotency, timeout ownership and budgets, cancellation propagation, partial failure, fallback behavior, fail-open/fail-closed behavior, and diagnostics.
- Booboo/defect hunt: wrong assumptions, off-by-one errors, nullability, stale state, race conditions, resource leaks, exception masking, unsafe fallbacks, and feature-gate leaks.
- Security and privacy: trust boundaries, authentication, authorization, input handling, injection, traversal, confused-deputy paths, secrets, sensitive data, logging, unsafe defaults, and dependency risk.
- Architecture and design: responsibility ownership, dependency direction, cohesion, coupling, module depth, boundary leakage, data authority, failure isolation, rollout, rollback, and evolution cost.
- Abstractions and decomposition: shallow indirection, leaky contracts, misplaced policy, mixed abstraction levels, oversized responsibilities, speculative generality, and useful module/function seams. Do not recommend decomposition that merely moves complexity.
- Redundancy and reuse: duplicated behavior, policy, state, validation, tests, configuration, helpers, and missed canonical repository or platform capabilities. Distinguish intentional duplication from drift-prone duplication.
- Complexity: cyclomatic and cognitive complexity, branch/state explosion, temporal coupling, hidden modes, algorithmic cost, repeated traversal, concurrency complexity, operational complexity, and essential versus accidental complexity.
- Simplification: deletion, derivation instead of synchronization, canonical paths, fewer states/options/layers/dependencies, smaller interfaces, clearer invariants, and YAGNI opportunities. Preserve required safety, compatibility, diagnostics, and observability.
- Compatibility: APIs, CLIs, configuration, defaults, errors, serialization, persisted data, mixed versions, supported runtimes/platforms, installation, migration, and rollback.
- Performance and resilience: realistic hot paths, asymptotic behavior, I/O, memory, fan-out, caching, backpressure, contention, recovery, and resource exhaustion.
- Logging, monitoring, observability, and traceability: structured logs, metrics, distributed traces, request/job correlation, context propagation, lifecycle and event coverage, signal names and semantics, units, cardinality, sampling, health and readiness signals, alertability, audit trails, dashboards and runbooks, privacy-safe redaction, and whether operators can detect and diagnose failures without exposing secrets or personal data.
- Test quality and coverage: behavior-to-test traceability, happy paths, boundaries, failures, negative/security cases, integration seams, concurrency, recovery, determinism, realism, over-mocking, brittle assertions, and whether tests would catch each plausible regression.
- Clean code and maintainability: truthful names, focused responsibilities, explicit side effects, readable control flow, locality, weak types, magic values, comments explaining rationale, and consistency with sound local patterns.
- Documentation, configuration, build, CI, and developer experience: contract drift, unsafe commands, missing migration guidance, reproducibility, diagnosability, and confusing workflows.

## Finding bar

Report a finding only when evidence establishes a concrete correctness, security, compatibility, performance, operability, testing, or maintenance consequence. Avoid cosmetic preferences, generic best-practice recitations, praise, and hypothetical future concerns without a credible failure scenario.

For every finding provide:

- Severity: `Critical`, `High`, `Medium`, or `Low`.
- Confidence: `High`, `Medium`, or `Low`.
- Exact evidence: `path:line`, relevant symbols, and causal trace.
- Trigger or failure scenario.
- User, security, data, operational, testing, or maintenance impact.
- Smallest practical correction; include test proof needed.
- Dimension tags.

## Report

1. Review boundary, inferred intent, and limitations.
2. Prioritized findings, sorted by severity then confidence. Merge duplicates.
3. Coverage matrix listing every analysis dimension as `finding`, `reviewed-no-finding`, or `blocked`, with concise evidence or blocker.
4. Residual risks, unverified assumptions, and missing test proofs.
5. If nothing meets the finding bar, state: `No high-confidence actionable findings.`

READ ONLY. JUST REPORT. Do not edit, format, generate, install, stage, commit, push, post comments, mutate external systems, or run commands that can change repository or environment state.
