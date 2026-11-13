---
description: Deep review of the entire test setup, coverage, gaps, overlaps, and suite health
argument-hint: "[scope, base ref, or test focus]"
---

# Test Review

Perform a deep, adversarial, report-only review of the complete test setup of ${@:-the entire current repository, including committed changes through the working tree}.

Primary deliverable: a deep, structured, evidence-backed test-quality report covering every test type present in the repository (unit, component, integration, contract, smoke, sanity, regression, end-to-end, acceptance, property-based, fuzz, snapshot/golden, mutation, performance, security, and any other executed check), their harnesses, fixtures, data management, coverage, gaps, overlaps, redundancies, improvement opportunities, simplifications, and cleanup candidates. Focus exclusively on tests and test infrastructure; review production code only to the degree needed to judge whether tests would catch its failures. The taxonomy in this prompt defines the review surface; repository evidence decides applicability and verdicts.

## Safety boundary

- Treat the repository source tree as read-only. Keep any coverage database, report, cache, log, or other transient artifact inside one dedicated temporary directory outside the repository; remove it before reporting.
- Use only tools already installed and ready. Never install, upgrade, bootstrap, authenticate, or download a tool, plugin, coverage engine, or analyzer. When a missing tool would materially improve coverage, continue with manual reasoning and record the tool and blind spot in the final follow-up register.
- Running existing test suites, coverage collectors, and deterministic analysis is permitted when it does not mutate the repository or external systems. Disable telemetry where the tool supports it.
- Never run destructive, networked, credential-consuming, or production-touching tests. Skip or stub nothing silently: record every excluded test with the reason.

## Scope

- With no argument, inventory the entire repository's test surface: every test suite, test file, harness, runner configuration, CI test job, fixture, helper, test double, test-data asset, snapshot, coverage configuration, and test-related documentation, across all languages, components, and deployment targets present.
- With an argument, treat it as an explicit scope or focus override (component, suite, coverage question, or specific test type) and state the interpretation before reviewing.
- Derive intended test strategy from the request, test names and structure, coverage configuration, CI gates, documentation, and repository conventions. Mark unresolved intent explicitly; never invent requirements.
- Distinguish test contexts: pre-commit/local, CI, release-gating, scheduled, manual, environment-specific. Do not elevate local convenience concerns into defects without a credible consequence.

## Assurance baseline

Anchor the review in the shared taxonomy below; web citations are reference anchors, not evidence. Repository files, coverage data, and executed behavior decide findings.

- Testing levels and types: unit, integration, system, acceptance, E2E ([testing taxonomy](https://softwareengineeringauthority.com/software-testing-types)); smoke/sanity/regression distinctions ([TechTarget](https://www.techtarget.com/searchsoftwarequality/answer/Software-retest-regression-smoke-and-sanity-testing-Whats-the-difference)); consumer-driven contract testing ([Microsoft Engineering Playbook](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/cdc-testing/)).
- Strategy shapes: test pyramid vs testing trophy vs honeycomb/diamond ([Microsoft Playbook comparison](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/e2e-testing/testing-comparison/), [web.dev test automation strategies](https://web.dev/articles/ta-strategies), [pyramid alternatives](https://josemanuelortega.me/en/when-the-pyramid-doesn-t-apply-the-trophy-the-honeycomb-and-the-diamond), [inverted pyramid anti-pattern](https://beyond.minimumcd.org/docs/anti-patterns/testing/inverted-test-pyramid/)). No shape is universally correct; architecture and failure patterns decide.
- Coverage metrics and limits: statement/branch/path/MC-DC; weak-to-moderate correlation between coverage and fault detection once suite size is controlled ([Inozemtseva & Holmes, ICSE 2014](https://www.cs.ubc.ca/~rtholmes/papers/icse_2014_inozemtseva.pdf), [Wei et al., ETH](https://se.inf.ethz.ch/people/wei/papers/is_coverage_a_good_measure_of_testing_effectiveness.pdf)); mutation testing as effectiveness measure ([Papadakis et al., ACM TSE](https://dl.acm.org/doi/10.1145/2786805.2786858)).
- Test doubles taxonomy and over-mocking brittleness ([Fowler, Mocks Aren't Stubs](https://martinfowler.com/articles/mocksArentStubs.html), [Fowler, TestDouble](https://martinfowler.com/bliki/TestDouble.html)).
- Flakiness causes: async waits, concurrency, order dependence, shared state ([Fowler, Eradicating Non-Determinism](https://martinfowler.com/articles/nonDeterminism.html), [Lam et al., OOPSLA 2020](https://mir.cs.illinois.edu/winglam/publications/2020/LamETAL20OOPSLA.pdf), [flakiness survey, ACM](https://dl.acm.org/doi/fullHtml/10.1145/3476105)).
- Test smells taxonomy and refactoring ([Test Smells catalog](https://testsmells.org/pages/testsmellexamples.html), [Bavota et al. / ASE](https://www.cs.wm.edu/~denys/pubs/ASE'16-TestSmells.pdf)).
- Robustness techniques: property-based, fuzzing, metamorphic testing ([metamorphic survey](https://www.doc.ic.ac.uk/~afd/papers/2021/MET.pdf)), snapshot/golden-master ([snapshot testing](https://www.rustprojectprimer.com/testing/snapshot.html)).
- Suite minimization trade-offs ([Shi et al., evolving test-suite reduction](https://users.ece.utexas.edu/~gligoric/papers/ShiETAL14EvolRed.pdf), [reduction approaches, ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0950584914000949)).
- Test data: factories/builders over shared static fixtures ([factories and builders](https://www.application-architect.com/posts/test-data-management-factories-and-builders/), [fixture critique](https://thoughtbot.com/blog/we-need-to-talk-about-fixtures)).
- E2E discipline: few critical flows, stable selectors, auto-waits, quarantine ([E2E trade-offs, ACM TSE](https://dl.acm.org/doi/10.1109/TSE.2024.3469582)).

## Method

Fan out across independent review angles: inventory -> per-type deep analysis -> cross-suite matrix -> synthesis. Trace each candidate through actual test code, harness execution paths, fixture lifecycles, CI configuration, and production code under test. Adversarially verify every claim: a "gap" requires proving a behavior can fail without any test catching it; an "overlap" requires proving two tests pin the same behavior with equal protection. Deduplicate by root cause; discard unsupported speculation before synthesis.

Maintain one exhaustive internal register of review surfaces. Give every surface exactly one terminal status: `finding`, `reviewed-no-finding`, `not-applicable`, or `blocked`. Report counts in the coverage matrix.

### 1. Inventory the test setup

- Enumerate every suite, runner, harness, configuration, helper, fixture, snapshot, test-data asset, CI test job, gating rule, retry/quarantine mechanism, and coverage collector. Record paths and purposes.
- Classify each suite by type: unit, component, integration, contract, smoke, sanity, regression, E2E, acceptance, property-based, fuzz, snapshot/golden, mutation, performance, security, manual. Flag suites whose placement contradicts their actual behavior (e.g., "unit" tests touching the network or filesystem are integration tests in disguise).
- Map the strategy shape actually in force (pyramid, trophy, honeycomb, inverted pyramid, hourglass) against the architecture, and judge fit rather than conformance to a default.

Completion criterion: every test-bearing path is classified; every suite has an owner purpose and declared type.

### 2. Assess coverage and effectiveness

- Inspect existing coverage configuration, thresholds, and reports. When collectors are already available, run coverage into the temporary directory and record per-component statement/branch numbers with the exact command and version.
- Evaluate coverage as a defect signal, not a vanity metric: high-coverage code with assertion-free or tautological tests is uncovered behavior; low-coverage critical paths are concrete risk. Prefer behavior-to-test traceability over percentages; never recommend chasing a fixed percentage target ([coverage-effectiveness evidence](https://se.inf.ethz.ch/people/wei/papers/is_coverage_a_good_measure_of_testing_effectiveness.pdf)).
- Identify coverage gaps: untested public behavior, error paths, boundaries, concurrency, state transitions, failure/recovery, compatibility, and security-relevant logic. For each gap, state the concrete failure scenario no test would catch.
- Assess assertion quality: assertion density, tautologies, over-broad assertions, snapshot-only verification, exception-only checks, and whether assertions verify outcomes or incidentally re-encode implementation.
- Where mutation testing tooling already exists and is safe to run, sample high-risk components and report mutation scores; otherwise record as `blocked` and follow up in the register.

### 3. Map overlaps and redundancies

- Cross-correlate suites and cases: which behaviors are pinned at multiple levels (unit + integration + E2E) with identical protection? Distinguish intentional level-appropriate duplication (same behavior, different integration confidence) from drift-prone duplication (same scenario, same setup, diverging assertions).
- Apply suite-minimization thinking with its known trade-off: consolidation reduces maintenance and runtime but must not reduce fault-detection power ([test-suite reduction trade-offs](https://users.ece.utexas.edu/~gligoric/papers/ShiETAL14EvolRed.pdf)). Recommend consolidation only with the evidence that protection is preserved.
- Identify redundant test cases within a suite: near-identical setups, parameterization opportunities, duplicate assertions across cases, dead or permanently skipped tests, and tests whose target behavior no longer exists.

### 4. Audit determinism and flakiness

- Search for the known flakiness root causes ([flakiness research](https://mir.cs.illinois.edu/winglam/publications/2020/LamETAL20OOPSLA.pdf), [Fowler on non-determinism](https://martinfowler.com/articles/nonDeterminism.html)): fixed sleeps instead of explicit synchronization, real time/randomness/network without seeds or fakes, shared mutable state, test-order dependence, resource leaks, environment dependence, unbounded concurrency.
- Inspect retry, quarantine, and known-flake mechanisms: a retry is a suppressed defect signal; record every retried/quarantined test with evidence of root-cause status.
- For E2E suites, check selector stability, wait strategies, and hermeticity against the discipline guidance ([E2E trade-offs](https://dl.acm.org/doi/10.1109/TSE.2024.3469582)).

### 5. Review fixtures, data, and doubles

- Fixture lifecycle: setup/teardown correctness, isolation per test, cleanup on failure, shared vs per-test state, ordering assumptions, and leaked resources across suites.
- Test data management: factories/builders with minimal defaults vs monolithic shared fixtures ([factories guidance](https://www.application-architect.com/posts/test-data-management-factories-and-builders/)); mystery-guest dependencies on hidden files or external resources ([test smells](https://testsmells.org/pages/testsmellexamples.html)); stability of snapshot/golden data and its review process.
- Test doubles: classify doubles in use per the taxonomy ([Fowler, TestDouble](https://martinfowler.com/bliki/TestDouble.html)); hunt over-mocking of internals that couples tests to implementation ([Mocks Aren't Stubs](https://martinfowler.com/articles/mocksArentStubs.html)); verify mocks of external boundaries match real contracts and cannot drift silently (contract-test candidates).

### 6. Detect test smells and maintenance debt

- Scan for the cataloged smells ([Test Smells catalog](https://testsmells.org/pages/testsmellexamples.html), [ASE study](https://www.cs.wm.edu/~denys/pubs/ASE'16-TestSmells.pdf)): Assertion Roulette, Eager Test, Mystery Guest, Fragile Test, Obscure Test, Conditional Test Logic, Test Code Duplication, Magic Numbers, Sensitive Equality, Sleepy Test, Resource Optimism, General Fixture, and their local variants.
- Judge harness quality: runner configuration, parallelism safety, timeout ownership, test discovery, naming truthfulness, documentation-vs-behavior drift in test READMEs, and CI gating (which suites gate, which are informational, how flakes are handled).
- Evaluate runtime economics: suite durations, slowest tests, level-misplaced expensive tests, and whether feedback loops match the strategy shape.

### 7. Improvement, simplification, and cleanup opportunities

- For each finding class, propose the smallest practical change: move a case to the cheapest level that still proves the behavior, parameterize duplicates, replace sleeps with synchronization, replace mocks of internals with fakes or real collaborators, split eager tests, add assertion context, retire dead tests, or introduce a missing type (contract, property-based, fuzz, smoke) where evidence shows a real gap — never as checklist compliance.
- Evaluate technique adoption by fit, not fashion: property-based where invariants exist ([metamorphic/property evidence](https://www.doc.ic.ac.uk/~afd/papers/2021/MET.pdf)), contract testing where provider/consumer drift is credible ([CDC testing](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/cdc-testing/)), mutation testing where critical logic needs effectiveness proof ([mutation survey](https://dl.acm.org/doi/10.1145/2786805.2786858)).

## Finding bar

Report a finding only when evidence establishes a concrete testing consequence: a catchable defect that escapes, suite time or maintenance cost with a measured driver, a flake mechanism, or drift-prone duplication. For every finding provide:

- Severity: `Critical`, `High`, `Medium`, or `Low`.
- Confidence: `High`, `Medium`, or `Low`.
- Exact evidence: `path:line`, suite/test names, and causal trace (gap: behavior -> failure scenario -> missing check; overlap: both tests -> shared protection; smell: smell class -> instance).
- Failure or cost scenario.
- Impact: escaped-defect risk, suite runtime, maintenance burden, or signal erosion.
- Smallest practical correction and the proof that protection is preserved.
- Category tags (gap, overlap, redundancy, flake, smell, fixture, doubles, harness, coverage, strategy).

Avoid percentage-chasing recommendations, framework evangelism, praise, generic best-practice recitations, and hypothetical gaps without a credible failure scenario.

## Report

1. Review boundary, interpreted scope, and limitations.
2. Executive summary: strategy shape in force, suite composition by type, headline coverage/effectiveness posture, highest-risk gaps, biggest overlap/redundancy clusters.
3. Per-type analysis: for each test type present — composition, harness, fixtures, doubles, determinism, smell inventory, and verdict; for absent types, state `not-applicable` with the reason or `recommended` with evidence.
4. Coverage analysis: measured numbers where obtained, gap register with failure scenarios, assertion-quality verdict.
5. Overlap and redundancy matrix: behaviors pinned at multiple levels, consolidation candidates with preserved-protection proof, dead/skipped test register.
6. Flakiness and determinism: suspected mechanisms, retried/quarantined inventory, E2E discipline verdict.
7. Prioritized findings sorted by severity then confidence. Merge duplicates.
8. Review-coverage matrix: every surface from the Method sections as `finding`, `reviewed-no-finding`, `not-applicable`, or `blocked`, with concise evidence; include totals.
9. Improvement, simplification, and cleanup roadmap: ordered smallest-change list with expected effect on signal, speed, and maintenance.
10. Uncovered surface and follow-up: surfaces not fully reviewed (missing tools, unrunnable suites, missing environments), exact blocker, resulting blind spot, and user-performed steps with ready commands to close them. If none, state `No uncovered applicable review surfaces.`
11. If nothing meets the finding bar, state: `No high-confidence actionable test findings.` This is not a claim that the suite is effective.

REPORT ONLY. Do not edit source or tests, format files, generate repository artifacts, install, stage, commit, push, or mutate external systems. Temporary analysis artifacts outside the repository are the only permitted files; remove them before the final report.
