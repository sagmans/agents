---
description: Exhaustively analyze code structure and design an evidence-backed decomposition
argument-hint: "[scope]"
---

# Decomposition Opportunities

Perform a comprehensive, report-only decomposition analysis of ${@:-the current branch development scope}.

Primary deliverable: an exhaustive, evidence-backed decomposition report that maps the relevant codebase, identifies every material decomposition opportunity, and specifies a coherent target structure in which every authored code file affected by the proposal contains fewer than 500 physical lines. The target must improve architecture, ownership, abstraction quality, maintainability, and discoverability—not merely distribute lines among more files.

## Safety boundary

- Treat the repository as read-only. Do not edit, format, generate, install, stage, commit, push, publish, deploy, or mutate external systems.
- Use repository-provided and already-installed analysis tools only. Never install or upgrade dependencies, plugins, language servers, scanners, or rule packs.
- Keep temporary measurements outside the repository and remove them before reporting. Do not upload source or findings to external services.
- Restrict execution to deterministic inspection and safe local checks. Never run production-touching, credential-consuming, destructive, or externally mutating commands.
- Web research is read-only. Prefer current primary sources, official documentation, standards, original pattern authors, and peer-reviewed work; distinguish evidence from opinion.

## Scope and completion contract

- With no argument, use the current branch development scope. Resolve a verified default-branch reference from local repository metadata without fetching or mutating state, record that reference, and compute its merge-base with `HEAD`.
- Build the initial changed-path set as the union of committed branch changes since that merge-base, staged changes, unstaged changes, and untracked files. Account explicitly for added, modified, deleted, copied, and renamed paths, including both old and new identities when they affect dependency or ownership analysis.
- Expand the initial set into a related-file closure. Follow imports, exports, callers, consumers, tests, fixtures, schemas, generators, configuration, build and deployment paths, entry points, adapters, public contracts, dynamic registration, and change-coupled files in both dependency directions. Continue until another relationship pass adds no material file; give every included or excluded candidate an evidence-backed disposition.
- With an argument, let that explicit scope replace the branch-development initial set, then apply the same related-file closure. State the interpretation and inspect every authored code file inside it. An explicit repository-root scope such as `.` requests whole-repository analysis.
- If a default-branch reference or merge-base cannot be verified, analyze observable staged, unstaged, and untracked paths as partial evidence, identify committed branch coverage as blocked, and state the exact evidence needed to close it. Never guess a base or silently substitute the entire repository.
- Read all applicable repository instructions and architecture documentation before evaluating structure. Derive conventions from the repository; never invent them from ecosystem defaults.
- Inventory the complete scope before prioritizing. Sampling, inspecting only files already known to be large, or stopping after finding several opportunities is incomplete.
- Maintain an internal coverage ledger for every in-scope authored file and every related file inspected. Give each one a terminal status: `decompose`, `consolidate`, `keep`, `artifact-excluded`, or `blocked`.
- Continue independent analysis when one language, tool, file, or runtime path is blocked. Record the exact blind spot and evidence needed to close it.

### Authored-code line limit

The hard target applies to human-maintained source, tests, scripts, and executable configuration. Every such target file must contain at most 499 physical lines, including comments and blanks, so the rule is deterministic across languages.

Also report non-comment source lines when a trustworthy language-aware tool is already available. State exact definitions, commands, tool versions, and exclusions because physical lines, source lines, statements, and generated lines are different measurements.

Inventory but exclude generated code, vendored dependencies, lockfiles, snapshots, compiled output, machine-produced fixtures, and data assets from the hard limit when repository evidence confirms that status. Oversized excluded artifacts still require an owner and remediation at their generator, schema, template, or upstream source when their size harms review, security, performance, or workflows. Never recommend hand-editing generated or vendored output.

The 499-line ceiling is a constraint, not proof of quality. Analyze smaller files for poor boundaries, duplication, misplaced policy, shallow indirection, and consolidation opportunities. Reject arbitrary splitting of cohesive files.

## Method

Use exhaustive discovery followed by adversarial verification and deduplicated synthesis. Partition broad scopes by coherent directories or subsystems, then reconcile cross-boundary dependencies centrally. Every claim must trace to repository evidence; every proposed boundary must account for its callers and tests.

### 1. Establish the repository model

Record:

- repository type, languages, frameworks, package and build systems, supported runtimes, and deployment units
- top-level and relevant subtree structure, source roots, test roots, generated roots, and ownership boundaries
- application, library, service, CLI, UI, worker, job, plugin, migration, infrastructure, and data-pipeline entry points
- public APIs, commands, events, schemas, persisted formats, configuration contracts, and external integrations
- existing architecture rules, dependency constraints, code-generation rules, test strategy, and release compatibility requirements

Produce a concise current tree annotated with each directory's responsibility. Identify ambiguous names, misplaced files, parallel structures, and locations where likely changes are difficult to discover.

Completion criterion: every in-scope source root and runtime path has a stated purpose, evidence, and review route or blocker.

### 2. Run complete LoC analysis

Enumerate every authored code file in the resolved initial set and related-file closure. Use repository-aware language classification first; inspect unknown extensions and mixed-content files manually rather than silently excluding them.

Report:

- physical lines for every authored file
- non-comment source lines where trustworthy tooling exists
- language, role, generated status, and test/production classification
- resolved-scope totals and distributions by language, directory, subsystem, and file role
- descending file-size ranking
- all files at 500 lines or more as hard violations
- files from 400 through 499 lines as near-limit growth risks requiring explicit assessment
- measurement failures, unsupported languages, minified files, embedded code, and classification uncertainty

Do not let aggregate statistics hide individual files. Reconcile tool output against the resolved-scope inventory so every in-scope authored path appears exactly once.

Completion criterion: the authored-file inventory count equals the sum of all terminal statuses, and every hard violation has a symbol dossier and target disposition.

### 3. Build symbol dossiers

For every file at 500 lines or more, and every smaller file with a material decomposition opportunity, inventory all meaningful symbols with a language-aware compiler, AST, index, LSP, tags tool, or repository-native analyzer when available. Fall back to careful textual tracing and state the limitation.

Include functions, methods, classes, interfaces, types, modules, components, hooks, routes, handlers, commands, queries, jobs, migrations, fixtures, and test groups as applicable. For each symbol record:

- exact path and line range
- visibility and public/exported status
- current responsibility and abstraction level
- owned state, invariants, side effects, and error policy
- dependencies, dependents, callers, consumers, and tests
- approximate size and available complexity signals
- duplication or semantic overlap
- change-coupling evidence from history when available
- proposed disposition: keep, move, split, merge, inline, delete, or block
- proposed destination and contract

Trace dynamic registration, reflection, dependency injection, framework conventions, code generation, string-based references, and runtime discovery so a missing static edge does not become a false orphan claim.

Completion criterion: every meaningful symbol in every oversized authored file has one disposition, and move maps reconcile with both current and proposed trees.

### 4. Diagnose architecture and dependencies

Map actual, not aspirational, structure:

- domains, business capabilities, bounded contexts, packages, modules, layers, features, and runtime processes
- dependency direction, strongly connected components, cycles, fan-in, fan-out, and unstable hubs
- public versus internal surfaces and accidental API exposure
- data authority, persistence ownership, shared mutable state, caches, queues, and transaction boundaries
- policy versus mechanism, domain logic versus transport or infrastructure, and validation ownership
- synchronous and asynchronous control flow, temporal coupling, lifecycle ordering, retries, and failure isolation
- cross-cutting concerns such as authorization, observability, configuration, localization, and error mapping
- test boundaries, fixture ownership, mock seams, and build or deployment coupling

Use change history when available to find files and symbols that repeatedly change together or trigger shotgun edits. Separate logical coupling from coincidental co-change.

Completion criterion: every proposed split states its dependency direction, data and side-effect ownership, public contract, failure boundary, and test seam.

### 5. Find every material decomposition opportunity

Examine every in-scope file and cross-file relationship for:

- oversized files, symbols, test suites, registries, schemas, and configuration modules
- mixed responsibilities or reasons to change
- low cohesion, high coupling, cycles, unstable dependencies, and boundary leakage
- mixed abstraction levels, orchestration tangled with policy, and domain logic tied to frameworks or I/O
- feature scattering, shotgun surgery, hidden temporal coupling, and shared mutable state
- duplicated policy, validation, transformations, types, constants, tests, and configuration
- catch-all `utils`, `helpers`, `common`, `shared`, `types`, manager, service, controller, or index modules without clear ownership
- shallow wrappers, pass-through modules, excessive re-exports, fragmented one-symbol files, and navigation cost
- misplaced state or side effects, ambiguous data authority, and inconsistent error ownership
- overly broad public APIs, weak types, primitive obsession, data clumps, and inappropriate intimacy
- extension mechanisms, conditional modes, and switch growth that indicate a plugin, strategy, registry, or polymorphic seam
- dead code, obsolete compatibility paths, speculative abstractions, and consolidation or deletion opportunities
- test files whose fixtures, scenarios, levels, or responsibilities need independent ownership
- discoverability problems where names, locations, and directory structure obscure likely change paths

A finding requires a concrete consequence: difficult change, defect risk, inconsistent policy, excessive coordination, fragile tests, unsafe ownership, review burden, or measurable navigation/build/runtime cost. Avoid style-only findings and pattern recitations.

For each opportunity provide exact evidence, affected symbols and consumers, consequence, smallest defensible boundary, target files, expected benefit, tradeoffs, migration risk, and proof needed. Merge symptoms with the same root cause.

### 6. Research project-fit approaches

Research current architecture, abstraction, design-pattern, and refactoring guidance that fits the discovered languages, frameworks, domain, deployment model, and failure constraints. Cite primary or official sources with title, publisher or author, URL, and access date. Verify that guidance still applies to the project's versions.

Use these as reasoning lenses, not mandatory patterns:

- information hiding and decomposition around change-prone design decisions rather than processing order
- high cohesion, low coupling, stable dependency direction, acyclic dependencies, and deep modules with narrow interfaces
- domain capabilities, ubiquitous language, aggregates, and bounded contexts when domain complexity supports them
- modular monoliths and vertical feature slices when process-level distribution is unnecessary
- ports and adapters, onion, clean, or layered boundaries when domain policy must remain independent of volatile infrastructure
- pipelines and explicit phase contracts for independently meaningful transformations
- strategy, plugin, microkernel, registry, mediator, facade, adapter, anti-corruption layer, and dependency inversion where concrete variation or integration pressure exists
- event-driven boundaries, CQRS, or distributed services only when independent deployment, scaling, ownership, latency, consistency, and operational evidence justify their cost
- framework-appropriate component, state, effect, route, command, job, schema, and test decomposition
- incremental refactoring through characterization tests, preparatory refactoring, parallel change, branch by abstraction, and strangler-style replacement when compatibility demands coexistence

Foundational starting points include Parnas's information-hiding decomposition criteria, Fowler's refactoring catalog and incremental migration patterns, Microsoft and AWS architecture guidance, and language-specific official architecture documentation. Expand beyond them based on project evidence:

- <https://john.cs.olemiss.edu/~hcc/csci555/notes/localcopy/Parnas_Criteria_Decomposing.pdf>
- <https://refactoring.com/catalog/>
- <https://martinfowler.com/bliki/BranchByAbstraction.html>
- <https://martinfowler.com/bliki/ParallelChange.html>
- <https://martinfowler.com/bliki/StranglerFigApplication.html>
- <https://learn.microsoft.com/en-us/azure/architecture/microservices/model/microservice-boundaries>
- <https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html>
- <https://docs.sonarsource.com/sonarqube-server/user-guide/code-metrics/metrics-definition>

Lines, complexity, coupling, duplication, cycles, and change frequency are complementary signals. Never use one metric as architectural proof.

### 7. Compare real target designs

For each consequential subsystem, generate at least two materially different target decompositions. Cosmetic renames or the same layers with different filenames are one option, not several.

Compare options on:

- responsibility and invariant ownership
- cohesion, coupling, dependency direction, and cycle risk
- interface depth and information hiding
- data authority, consistency, transaction, and failure semantics
- discoverability and reader navigation load
- testability and realistic integration seams
- public API, compatibility, rollout, and rollback
- performance, security, observability, build, and deployment effects
- team ownership and independent changeability
- migration complexity and removable transitional machinery

Select one design per area and explain why it dominates under repository constraints. Prefer subtraction, consolidation, reuse, and clearer ownership before adding abstractions. Do not turn a file decomposition request into a microservice migration without compelling operational evidence.

### 8. Specify the target tree and move map

Provide an implementation-ready proposed tree. For every created, retained, renamed, merged, or deleted authored file state:

- responsibility and reason to exist
- projected physical-line range with growth headroom; upper bound must be 499
- symbols it owns
- symbols moved from or to it
- public and internal interfaces
- allowed dependencies and forbidden reverse dependencies
- state, data, side-effect, validation, and error ownership
- corresponding unit, integration, contract, end-to-end, or characterization tests

Ensure symbols that change together remain discoverable together. Avoid technical-layer sprawl, generic dumping grounds, one-method modules, interfaces with one accidental implementation, and abstractions that merely relocate complexity.

Reconcile totals: every current symbol has exactly one target disposition; every target file has owned symbols; every current oversized authored file is deleted or projected below 500 lines; every target authored file is projected below 500 lines.

### 9. Design a safe migration roadmap

Order work as independently verifiable slices:

1. establish characterization, contract, and boundary tests around behavior that moves
2. introduce the smallest target seam
3. move one cohesive responsibility with its tests
4. migrate and verify every caller, including dynamic and external consumers
5. preserve old and new paths temporarily only when compatibility evidence requires parallel change
6. validate behavior, performance-sensitive paths, errors, security controls, observability, and file limits after each slice
7. remove old paths, temporary adapters, feature flags, duplicated state, and compatibility facades once migration evidence permits
8. re-run repository-wide dependency, cycle, dead-export, line-count, build, test, and real non-production workflow checks

For each slice list exact files and symbols, prerequisites, compatibility strategy, test-first proof, rollback point, and completion criterion. Identify commit seams without committing. Keep the repository buildable and behaviorally coherent after every slice.

### 10. Adversarially verify the proposal

Before reporting, challenge each recommendation:

- Does the boundary hide a decision or only move lines?
- Will changes remain local, or does the new interface leak internals?
- Did the design create more concepts, files, navigation, or coordination than it removed?
- Are cycles, shared state, duplicated policy, or temporal coupling merely relocated?
- Does every caller, test, schema, configuration, generated path, and runtime registration still resolve?
- Are projected line counts plausible from symbol sizes rather than wishful equal division?
- Is a proposed pattern justified by observed variation or only by fashion?
- Could deletion, consolidation, a deeper module, or a smaller interface solve the same problem?
- Can the migration be rolled back without mixed-state corruption or broken compatibility?
- Would a maintainer know where to make the next likely change?

Discard or revise recommendations that fail. Record unresolved assumptions and the evidence needed to settle them.

## Report structure

1. **Boundary and limitations** — interpreted scope, verified default-branch reference and merge-base when used, initial changed-path set, related-file closure, repository state, definitions, exclusions, tools, commands, versions, and blockers.
2. **Executive summary** — architecture posture, authored-file count, hard violations, near-limit files, principal root causes, and selected target direction.
3. **Current repository map** — annotated tree, entry points, domains or capabilities, public contracts, data authority, and dependency direction.
4. **LoC inventory** — totals and distributions, complete descending authored-file table, violation register, near-limit register, and excluded-artifact register.
5. **Oversized-file symbol dossiers** — complete symbol tables with line ranges, dependencies, consumers, tests, and dispositions.
6. **Architecture diagnosis** — cohesion, coupling, cycles, ownership, state, side effects, failure boundaries, test seams, and discoverability.
7. **Decomposition opportunity register** — prioritized, deduplicated findings with exact `path:line` evidence, consequence, target boundary, tradeoffs, and proof.
8. **Design alternatives** — materially different options per consequential area and explicit selection rationale.
9. **Selected target structure** — proposed tree and per-file responsibility, projected lines, interfaces, dependencies, ownership, and tests.
10. **Symbol move map** — every affected current symbol mapped to keep, move, split, merge, inline, delete, or block.
11. **Migration roadmap** — ordered test-first slices, caller migrations, compatibility periods, cleanup, rollback, and completion gates.
12. **Projected compliance proof** — all target authored files with projected maximum physical lines; no value may exceed 499.
13. **Research basis** — project-fit conclusions and cited current primary sources; rejected patterns and why they do not fit.
14. **Coverage matrix** — every in-scope authored file and related inspected file with terminal status and concise evidence; totals must reconcile with inventory.
15. **Residual risks and blocked evidence** — unresolved assumptions, unsupported language analysis, dynamic edges, missing runtime proof, and exact follow-up needed.

Prioritize recommendations by structural leverage, change risk, and dependency order. Distinguish required 499-line compliance from optional architecture improvements. If no smaller file warrants decomposition, say so; do not manufacture work. If any authored file remains projected at 500 lines or more, the report is incomplete unless an explicit blocker names the missing evidence and a concrete path to compliance.

REPORT ONLY. Do not edit source, create repository artifacts, install tools, stage, commit, push, publish, deploy, or mutate external systems.
