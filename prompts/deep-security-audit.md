---
description: Deep structured security audit of current worktree changes
argument-hint: "[scope, base ref, or authorized local target]"
---

# Deep Security Audit

Perform a deep, adversarial, report-only security audit of `${@:-the entire current worktree against origin/<default-branch>}`.

Primary deliverable: a deep, structured, evidence-backed security audit report that explains actual attack surface, trust boundaries, vulnerability paths, exploitability, impact, and remediation. Use every safe capability already available—repository and history inspection, architectural and data-flow reasoning, adversarial manual review, tests and local reproduction, authoritative web intelligence, specialist skills or agents, and applicable scanners—to maximize depth and confidence. The surface inventory exists to prevent blind spots; it must support rather than replace investigation. Never substitute checklist completion, tool output, or a tooling catalog for vulnerability analysis.

Define the entire in-scope security audit surface, investigate each applicable area as deeply as available evidence permits, and leave no surface silently omitted. Missing tools, failed analyses, unavailable environments, or incomplete evidence block only their dependent techniques; continue every independent path. Keep coverage gaps and tooling recommendations for the end of the report.

## Safety boundary

- Treat the repository source tree as read-only. Keep any scanner database, cache, SARIF, log, downloaded advisory data, or other transient artifact inside one dedicated temporary directory outside the repository; remove it before reporting.
- Use locally runnable tools that are open source or available at zero monetary cost for the exact repository, user, and audit scope. Prefer open-source tools. Free/community proprietary editions are eligible only after verifying their license permits this use and the run cannot incur charges. Exclude paid features, metered APIs, billing-enabled services, expiring trials, surprise-cost paths, and hosted scanners that require source upload. An existing subscription or credential does not by itself prove zero incremental cost.
- Treat automated tools as optional accelerators, not audit prerequisites. Use only eligible tools already installed and ready. Never install, upgrade, bootstrap, authenticate, auto-update, or download a tool, plugin, executable, container image, language package, rule pack, or analyzer pack—even temporarily or project-locally. Never invoke installer-capable fallbacks such as unpinned `npx`, `uvx`, `pipx`, `go install`, `cargo install`, package-manager install commands, remote bootstrap scripts, or automatic container pulls. Tool-required advisory or vulnerability databases may be refreshed only into the dedicated temporary audit directory when the installed tool supports this safely, the authoritative source and integrity are verified, and no executable code is installed. Never pause the current pass for tool setup. When a missing tool would materially improve coverage, continue with manual reasoning and eligible alternatives, then place the tool and resulting blind spot in the final `Uncovered audit surface and user-run follow-up` register with purpose, license and edition, authoritative source, zero-cost eligibility, version to pin, checksums/signature verification, user-performed isolated installation method, authentication/readiness requirements, and readiness command.
- Never expose source, findings, credentials, secrets, personal data, proprietary artifacts, or telemetry to an external service. Disable scanner telemetry; every Semgrep invocation must use `--metrics=off`, and avoid configurations that fetch unpinned remote rules.
- Restrict active testing to an existing disposable local environment or an explicitly authorized non-production target in the argument. Never probe production, public infrastructure, unrelated hosts, or third-party systems. Never weaken a guard, persistence boundary, or host security control merely to make a proof succeed.
- Use synthetic accounts, secrets, and data. Stop before destructive operations, denial of service, persistence, privilege changes outside the disposable target, outbound exfiltration, purchases, publishing, or external submissions.
- Prefer passive inspection and safe local reproduction. Record active testing as `blocked` when authorization, isolation, realistic fixtures, or cleanup proof is absent.

## Scope

- With no argument, resolve the repository's default branch from local `origin/HEAD` or other authoritative repository evidence and use `origin/<default-branch>` as the audit base. Never substitute the current branch's upstream tracking branch.
- Audit the complete delta from that base through the working tree: every committed change between the base and `HEAD`, every staged and unstaged tracked-file change, every deletion and rename, and the full content of every non-ignored untracked file.
- With an argument, treat it as an explicit scope, base, or authorized local-target override and state the interpretation before auditing. An explicit target grants access only to that target; it does not expand authorization to dependencies, adjacent infrastructure, production, or third parties.
- Inventory the complete in-scope codebase surface before narrowing analysis by risk: every component, caller, consumer, entry point, source, sink, test, schema, migration, configuration, dependency, generated artifact, build/release path, deployment manifest, environment, external integration, and operational control. The delta determines finding ownership and priority, not which security surfaces exist.
- Inspect changed code plus every repository-wide path needed to establish reachability, control coverage, variants, and security impact. Audit unchanged surfaces deeply enough to classify applicability and expose changed assumptions or bypasses.
- Report vulnerabilities introduced, exposed, or materially worsened by this worktree. Record directly relevant pre-existing vulnerabilities separately so ownership remains clear.
- Infer intended security behavior from the request, commits, tests, documentation, `SECURITY.md`, threat models, architecture, configuration, deployment evidence, repository conventions, and standards the project claims. Mark unresolved intent; never invent requirements.
- Distinguish production runtime, build/CI, development, test, local-user, administrator, and source-controlled contexts. Do not elevate same-user tooling, robustness, data-loss prevention, or defense-in-depth concerns into vulnerabilities without a credible trust-boundary crossing.

## Assurance baseline

Use current authoritative sources and pin every referenced version. As of August 2026, consider at least:

- OWASP Top 10:2025, ASVS 5.0.0, API Security Top 10:2023, WSTG 4.2, MASVS/MASTG, SAMM 2.1, Cheat Sheet Series, and applicable IoT guidance.
- OWASP GenAI LLM Top 10:2026, Agentic Applications Top 10:2026, AISVS 1.0, LLMSVS 2.0, MCP Top 10, and AI Agent Security guidance when AI, agents, models, RAG, or MCP is present.
- NIST SSDF 1.1, CSF 2.0, SP 800-63-4, SP 800-161r1, SP 800-204D, applicable cryptographic standards, AI RMF, and the Generative AI Profile. Treat draft standards as drafts.
- MITRE CWE, the current CWE Top 25, CAPEC, ATT&CK, and ATLAS where they sharpen root-cause, abuse-path, or adversary analysis.
- CISA Secure by Design, Known Exploited Vulnerabilities, SBOM/VEX guidance, and memory-safety guidance.
- SLSA 1.2, in-toto, Sigstore, CycloneDX or SPDX, OpenVEX, and OpenSSF Scorecard for supply-chain assurance.
- RFC 9700 for OAuth security, RFC 8725 for JWT, WebAuthn, OpenID FAPI, and other implemented RFCs/specifications.
- PCI DSS, ISO 27001, SOC 2, HIPAA, GDPR, FedRAMP, CIS Benchmarks, DISA STIGs, or other compliance overlays only when project scope or claims make them applicable. Compliance is evidence context, not proof of security.

Verify online version drift only through primary sources when web access is available. Standards guide coverage; actual code, configuration, reachability, and runtime behavior decide findings.

## Method

Work threat-model first, then fan out across independent audit angles using every safe capability the environment provides. Use finder -> adversarial verification -> deduplicated synthesis. Trace every candidate through actual data flow, control flow, state transitions, trust boundaries, deployment configuration, and tests. Search protection layers in the language, framework, middleware, application, infrastructure, and operational configuration before issuing a verdict. Automated results seed investigation; deep manual analysis and evidence-based verification remain mandatory even when scanners report no findings.

Maintain one exhaustive surface register as an internal audit control. Seed it from the full taxonomy in this prompt, then expand it from repository evidence, architecture, dependencies, protocols, deployment targets, generated artifacts, and discovered trust boundaries. Give every surface exactly one terminal status: `finding`, `reviewed-no-finding`, `user-action-recommended`, `not-applicable`, or `blocked`. For applicable surfaces, record techniques attempted, evidence inspected, depth achieved, and residual blind spots. Tool absence or failure never means `reviewed-no-finding`: attempt manual tracing and eligible alternatives, preserve the exact error, continue independent work, then report what remains uncovered. Spend audit effort on high-risk reachable paths and proof, not repetitive matrix prose.

### 1. Establish evidence and intelligence

- Record base, head, worktree state, requested scope, excluded paths, repository type, languages, frameworks, package managers, build systems, deployment targets, and supported runtimes.
- Read security policy, prior threat models, advisories, audit artifacts, changelogs, dependency manifests, lockfiles, generated code policy, and deployment documentation.
- Search CVEs, GHSAs, CISA KEV, OSV, vendor advisories, patch commits, and known framework bypasses relevant to changed components and resolved dependency versions.
- Inspect git history and blame where security checks, validation, authorization, sandboxing, cryptography, logging, or safe defaults were removed or weakened.
- For each relevant historical patch, test alternate entry points, sibling paths, default-state gaps, compatibility branches, normalization differences, and incomplete variants.

Completion criterion: every in-scope component has identified applicability, intent, runtime, assets, historical intelligence, and an explicit review path or blocker; every changed security-relevant component has full evidence.

### 2. Build the attack-surface model

- Inventory components, services, processes, jobs, libraries, plugins, agents, models, data stores, queues, caches, external services, CI jobs, artifacts, deployment units, identities, and trust zones.
- Inventory attacker-controlled inputs from network requests, files, URLs, databases, caches, queues, events, webhooks, logs, environment variables, command lines, configuration, repositories, generated artifacts, model context, and third-party responses.
- Inventory security-sensitive sinks: authorization decisions, queries, commands, interpreters, templates, files, outbound requests, deserializers, cryptographic operations, secret access, logs, model tools, package publication, deployment, and privileged APIs.
- Classify assets and data by confidentiality, integrity, availability, privacy, financial, safety, and tenant impact.
- Model high-risk DFD and control-flow slices with actors, stores, transformations, trust-boundary crossings, authority, validation, and failure behavior.
- Define realistic attacker positions: anonymous, authenticated, another tenant, lower privilege, local user, malicious input producer, compromised dependency, CI contributor, operator, plugin, agent, MCP server, and upstream service.
- Generate abuse cases and attack hypotheses using STRIDE, CAPEC, attack trees, state-machine abuse, second-order attacks, parser differentials, races, supply-chain compromise, and LINDDUN where privacy applies.

Completion criterion: every in-scope entry point and security decision maps to assets, attacker control, trust boundaries, sinks, and abuse hypotheses; every universal taxonomy surface is present in the register as applicable or explicitly `not-applicable`; unknowns are explicit.

### 3. Select and execute applicable tools

Inspect availability and versions without changing the environment. Prefer repository-provided commands and configuration. Execute complementary tools already available only where their language, framework, target, and security model apply; scanners produce candidates, never verdicts. Missing tools never prevent the deep manual audit.

When available, use Piolium's report-only specialist methodology while preserving the zero-cost gate:

- Consult `audit` for advisory intelligence, patch-bypass analysis, attack-surface structure, deep bug hunting, false-positive elimination, variants, and reporting. Reproduce applicable phases with eligible tools below. Run CodeQL or Semgrep Pro requirements only when their exact edition and this repository's use are verified as zero-cost and license-permitted; otherwise use the free alternatives and record reduced coverage.
- Use `differential-review` for risk-first delta analysis and blast-radius tracing.
- Use `security-threat-model`, `spec-to-code-compliance`, `supply-chain-risk-auditor`, `agentic-actions-auditor`, `insecure-defaults`, `sharp-edges`, `zeroize-audit`, and `wooyun-legacy` for applicable specialist surfaces.
- Use `codeql` and `semgrep` only when their selected editions pass the zero-cost and license gate; use `sarif-parsing` for result normalization, `fp-check` for adversarial triage, `variant-analysis` and custom rules for confirmed root-cause patterns, and `vuln-report` only as a report structure.

Apply this tool matrix conditionally:

- Structural and data-flow analysis: CodeQL when its CLI license permits zero-cost analysis of this repository, otherwise Semgrep Community Edition, Joern, compiler/language AST and CFG analyzers, and architecture-specific manual tracing. For CodeQL, build a fresh temporary database, verify extractor coverage/errors, use explicit suites and locally available packs, and investigate zero findings as possible extraction/model failure. Record cross-file/interprocedural blind spots for every fallback.
- Pattern and taint analysis: Semgrep Community Edition is the default. Semgrep Pro is eligible only when the user has confirmed a non-trial, zero-incremental-cost entitlement for this repository and source remains local. Use pinned official, repository, Trail of Bits, 0xdea, Decurity, and architecture-specific rules only when locally available and applicable. Log exact engine/rules, use `--metrics=off`, and state edition limitations.
- Agent-assisted candidate discovery: Vercel `deepsec` is Apache-2.0; its non-AI `scan` phase is eligible when state stays outside the source tree. Its `process`, `triage`, and `revalidate` phases are eligible only after the user proves model inference is hard-capped at zero cost; otherwise exclude them because upstream warns large scans may be extremely expensive. OpenAI `codex-security` has an Apache-2.0 client but scanning requires Codex Security access and model inference; use it only after the user proves license eligibility, local-source handling, and hard-zero run cost, otherwise mark it unavailable.
- Language analyzers: SpotBugs/FindSecBugs and Jazzer for JVM; Bandit/Pysa/Atheris for Python; gosec/govulncheck/native fuzzing for Go; cargo-audit/cargo-deny/cargo-geiger/Miri/cargo-fuzz for Rust; Brakeman/bundler-audit for Ruby; Security Code Scan/DevSkim for .NET; Psalm taint analysis for PHP; Clang analyzers, sanitizers, Infer, Cppcheck, and Valgrind for native code; Slither/Mythril/Echidna/Foundry for Solidity.
- Secrets: Gitleaks, TruffleHog, detect-secrets, or an existing repository-native open-source scanner. Treat discovered credentials as sensitive; never print full values or verify them against external providers.
- Dependencies and SBOM: OSV-Scanner, Trivy, Grype, Syft, CycloneDX/SPDX tooling, Dependency-Check, Dependency-Track, native package-manager audits, GitHub Advisory Database, CISA KEV, EPSS, deps.dev, and OpenSSF Scorecard. Prove package identity, affected version, runtime presence, vulnerable feature use, and reachable path.
- Supply-chain integrity: lockfile verification, SLSA provenance, in-toto attestations, Sigstore/Cosign/Rekor, VEX/OpenVEX, and GUAC metadata when present. Passively inspect existing GitHub artifact attestations when the repository already uses them, but require open-source local verification. Verify signatures and attestations are enforced, not merely generated.
- CI/CD: zizmor, actionlint, OpenSSF Scorecard, open-source dependency-review tooling, existing StepSecurity evidence, and `agentic-actions-auditor` for GitHub Actions. Resolve local composite actions and reusable workflows; inspect external actions at pinned identities when source is available.
- IaC and policy: Checkov, KICS, Trivy configuration scanning, OPA/Conftest, Gatekeeper, Kyverno, and open-source format/schema validators. Do not adopt archived Terrascan as new coverage.
- Containers and Kubernetes: Trivy, Grype, Syft, Dockle, Hadolint, Kubescape, kube-bench, kubeaudit, admission policies, Falco/Tracee evidence, and Cosign verification. Treat inactive kube-hunter as legacy supplemental evidence only.
- Cloud posture: Prowler, ScoutSuite, Steampipe/Powerpipe, and CloudSploit only against an explicitly authorized non-production account or exported configuration. Passively review exported evidence from provider-native services when supplied, but do not depend on proprietary cloud scanners.
- Web and API: OWASP ZAP, Burp Suite Community Edition, Schemathesis, RESTler, reviewed Nuclei templates, browser developer tools, and eligible protocol-aware clients only against an authorized disposable target. Use naabu, RustScan, or license-permitted zero-cost Nmap for port discovery and testssl.sh or SSLyze for TLS only inside that target boundary. Exclude Burp Professional/DAST and all paid scanner features.
- Dynamic and fuzz testing: libFuzzer, AFL++, honggfuzz, local ClusterFuzzLite harnesses, Jazzer, Atheris, Go fuzzing, cargo-fuzz, Hypothesis, QuickCheck/proptest, Schemathesis, RESTler, boofuzz, sanitizers, Valgrind, Miri, and Wycheproof vectors where applicable.
- Mobile, desktop, browser extensions, binaries, and firmware: MobSF, Frida, objection, JADX, apktool, Ghidra, radare2/Rizin, angr, platform signing/entitlement tools, `web-ext lint`, Electron's official checklist, Binwalk, EMBA, FACT, QEMU, or FirmAE when artifacts and safe environments exist. Treat Electronegativity as supplemental, not authoritative modern Electron coverage.
- Runtime and configuration assurance: OpenSCAP, Lynis, Cinc Auditor, Falco, Tracee, osquery, CIS-CAT Lite, and policy/runtime evidence when the authorized environment exists and each license permits the target use. Exclude CIS-CAT Pro and other paid assessor editions.

For every proposed or executed tool, verify its current license and edition from the authoritative source. Record name, version, license, edition, zero-cost basis, target, exclusions, configuration, rules, command, analysis quality, exit status, finding counts, and limitations. Never claim a tool ran when it did not, that a free client makes a paid backend free, or that a trial/free tier cannot incur cost without checking its billing controls.

Completion criterion: every applicable automated technique is executed with quality evidence or marked `user-action-recommended`, `blocked`, or `not-applicable`; failures trigger manual or eligible-tool fallback where possible and never halt unrelated coverage; every result is retained only as a candidate for manual verification.

### 4. Perform adversarial manual analysis

Analyze every applicable surface below. For each, test happy, boundary, malformed, adversarial, concurrent, failure, recovery, compatibility, and mixed-version paths.

#### Trust, identity, and authority

- Authentication lifecycle: enrollment, login, MFA/passkeys, credential storage, throttling, enumeration, recovery, linking, suspension, revocation, and fallback.
- Federation and tokens: OAuth/OIDC/PKCE, redirects, issuer/audience, nonce/state, sender constraints, scopes, token exchange, SAML conditions/signatures, SCIM provisioning, JWT/JOSE algorithm and key selection, replay, expiry, and rotation.
- Session lifecycle: fixation, cookie attributes/scope, browser storage, privilege-change rotation, logout, concurrent sessions, timeout, refresh-token reuse, and invalidation.
- Authorization: deny-by-default, BOLA/IDOR, BFLA, property authorization, RBAC/ABAC/ReBAC/ACL composition, delegation, impersonation, support/admin access, confused deputies, and stale policy state.
- Isolation: cross-user, tenant, origin, account, project, region, queue, cache, search index, analytics, export, backup, and control-plane/data-plane boundaries.

#### Input, parser, and execution safety

- SQL, NoSQL, LDAP, XPath, ORM, command, argument, template, expression, code, log, header/CRLF, SMTP, CSV/formula, and client-side injection.
- Reflected, stored, DOM, mutation, and second-order XSS; context-specific encoding, sanitization, CSP, Trusted Types, and framework escape hatches.
- SSRF, URL parser confusion, redirect handling, DNS rebinding, proxy bypass, metadata endpoints, and outbound allowlists.
- Path traversal, symlink/hard-link attacks, archive traversal, temporary files, uploads, polyglots, executable placement, parser vulnerabilities, and decompression bombs.
- Unsafe deserialization, prototype pollution, object hydration, XML entities, parser bombs, regex denial of service, and untrusted code/module/plugin loading.
- Unicode, encoding, normalization, canonicalization, duplicate fields, content-type disagreement, request smuggling/desynchronization, signature canonicalization, and validation-order differentials.

#### Web, API, messaging, and integrations

- CSRF, CORS, clickjacking, cookies, browser storage, `postMessage`, iframe sandboxing, service workers, mixed content, SRI, source maps, client secrets, cache poisoning/deception, host-header injection, and open redirects.
- REST, SOAP, GraphQL, gRPC, WebSocket, SSE, and custom protocols: inventory, shadow versions, schema enforcement, object/function/property authorization, mass assignment, batching, pagination, filtering, introspection, query complexity, stream lifecycle, reflection, and per-message authorization.
- Rate, quota, payload, recursion, fan-out, concurrency, and cost limits per identity, tenant, operation, and downstream resource.
- Databases, caches, queues, events, webhooks, imports/exports, callbacks, and third-party APIs: authenticity, authorization, replay, ordering, poison messages, stale authority, cache keys, signing, secret rotation, and unsafe upstream trust.

#### Business logic, concurrency, and resilience

- State-machine bypass, invalid transition order, skipped approvals, replay, duplication, idempotency, partial completion, rollback, self-approval, stale reads, and optimistic locking.
- TOCTOU and races around authorization, files, balances, quotas, inventory, entitlements, provisioning, revocation, and distributed locks.
- Price, amount, precision, currency, negative/boundary values, refunds, credits, coupons, limits, time windows, timezone, and abuse-at-scale.
- CPU, memory, disk, descriptors, connections, threads, queues, amplification, backpressure, cancellation, timeout ownership, retry storms, circuit breakers, and cross-tenant denial of service.
- Exceptional conditions: fail-open behavior, exception masking, unsafe fallback, partial failure, stale security state, cleanup, recovery, and feature-gate leakage.

#### Data, privacy, cryptography, and secrets

- Data inventory, minimization, purpose, consent, collection, derivation, sharing, residency, access/export/correction/deletion, retention, backups, telemetry, analytics, re-identification, and cross-tenant privacy.
- Storage, query, row-level policy, migration, backfill, mixed-version, replica, cache, index, backup, secure deletion, and integrity constraints.
- Algorithm/mode/key-size selection, password KDFs, CSPRNG and entropy, AEAD, nonce/IV uniqueness, signatures, domain separation, certificate/hostname validation, TLS/mTLS, downgrade resistance, trust stores, side channels, constant-time checks, and cryptographic migration.
- Key generation, access, custody, rotation, revocation, escrow, destruction, hardware-backed storage, and native zeroization resistant to compiler removal.
- Secrets in code, history, artifacts, packages, images, environment, command lines, process state, logs, crashes, CI, browser bundles, source maps, examples, defaults, and generated files.

#### Configuration, APIs, and secure design

- Fail-open defaults, fallback credentials, debug/admin exposure, permissive bindings/CORS/ACLs, weak algorithms, environment overrides, parse failures, and production/development drift.
- Zero, empty, null, negative, overflow, duplicate, unknown, and malformed values for every security-relevant option.
- Misuse resistance: attacker-controlled algorithm/mode selection, stringly typed permissions, interchangeable key/nonce/token types, ignored security return values, silent failures, and dangerous option combinations.
- Security ownership, policy centralization, canonical validation/authorization paths, duplicated controls, bypass-prone alternate APIs, and compatibility branches.

#### Dependencies, build, release, and operations

- Direct, transitive, optional, build, test, vendored, native, model, plugin, binary, base-image, and external-service dependencies; lockfile integrity; dependency confusion; typosquatting; install scripts; registry fallback; maintainer/takeover risk; vulnerable feature reachability.
- CI trigger trust, expression/shell injection, `pull_request_target`, checkout refs, token permissions, secrets, self-hosted runners, cache/artifact poisoning, untrusted logs, AI-agent prompts, third-party action pinning, and reusable workflow/composite action flow.
- Reproducibility, hermeticity, toolchain provenance, generated artifacts, package publishing, OIDC trusted publishing, signing, attestations, SBOM/VEX, update channels, downgrade protection, rollback, and release authorization.
- Cloud IAM, service accounts, role assumption, public resources, network boundaries, metadata access, KMS policies, cross-account access, IaC drift, and serverless event/identity boundaries.
- Containers/Kubernetes: image provenance, root/capabilities, mounts/sockets, namespaces, seccomp/AppArmor/SELinux, secrets, RBAC, admission, network policy, service-account tokens, resource limits, and signature enforcement.
- Security logs, audit trails, correlation, alertability, redaction, injection resistance, cardinality/sampling, time integrity, incident containment, credential revocation, forensics, disclosure, and patch regression coverage.

#### Native, local, client, and specialized systems

- Native code: memory corruption, use-after-free, bounds and integer errors, undefined behavior, uninitialized data, format strings, FFI/unsafe boundaries, signal handling, races, privilege dropping, sandboxing, IPC, library search paths, installers, and local update mechanisms.
- CLI/library/plugin/SDK: arguments, stdin, environment, configuration, working directory, executable resolution, terminal escapes, script-consumed output, plugin loading, host/plugin authority, secure defaults, unsafe examples, and malicious consumers.
- Mobile/desktop/browser extension: secure storage, backups, deep links/intents, WebViews/native bridges, IPC sender validation, runtime permissions, certificate handling, context isolation, sandboxing, Node integration, navigation, `openExternal`, extension messaging/permissions/CSP, remote code, signing, entitlements, and updates.
- AI/ML/agents/MCP: direct/indirect prompt injection, goal hijack, tool misuse, excessive agency, identity/privilege abuse, unsafe code execution, RAG/data/memory/context poisoning, sensitive context exfiltration, model/prompt/adapter/embedding supply chain, MCP tool/resource/prompt poisoning, token scope, server identity, capability drift, tool-schema confusion, inter-agent authenticity, loops/cascading failures, denial of wallet, human trust exploitation, output handling, sandbox boundaries, model extraction/inversion, membership inference, evasion, and training/evaluation poisoning.
- Embedded/IoT when present: firmware acquisition, secrets, debug ports, boot trust, update signing, rollback, radio/network protocols, hardware identity, physical attacker, and fail-safe behavior.
- Smart contracts when present: authorization, reentrancy, external calls, oracle/economic manipulation, signature/replay, arithmetic/precision, upgradeability, storage layout, frontrunning/MEV, and invariant violations.

Completion criterion: every surface in the exhaustive register has concrete repository/runtime evidence and terminal status `finding`, `reviewed-no-finding`, `user-action-recommended`, `not-applicable`, or `blocked`; every applicable surface has been covered to the maximum safe depth available, and every incomplete path records the attempted fallback and remaining requirement.

### 5. Verify candidates and hunt variants

For every candidate:

1. Restate the claim as falsifiable source -> propagation -> missing/bypassed control -> sink -> impact.
2. Prove attacker control, required privileges, production-reachable runtime, trust-boundary crossing, and affected security property.
3. Trace every control and transformation across language, framework, middleware, application, infrastructure, and deployment layers.
4. Check intended behavior, `SECURITY.md`, documented threat model, accepted risk, supported configurations, and realistic attacker position.
5. Reproduce safely in existing tests or an isolated local environment where authorized. Preserve concise evidence without sensitive values. State `executed`, `theoretical`, or `blocked`.
6. Write prosecution and defense arguments. Attempt to disprove reachability, exploitability, severity, and novelty.
7. Search semantic variants across sibling entry points, equivalent sinks, alternate encodings, compatibility paths, generated code, other services, and dependency versions using custom queries/rules when useful.
8. Deduplicate by root cause and affected security boundary. Prefer one complete finding with affected locations over repeated symptoms.
9. Require independent cold verification for Critical and High findings when fan-out capability exists. Lower confidence or severity when evidence remains incomplete.

Drop candidates that are unreachable, adequately controlled, by design, test/example-only, local same-user behavior without added authority, admin-only safety, advisory-only without affected use, generic hardening, or unsupported speculation. Keep a missing control when the threat model proves attacker-controlled input reaches a security-sensitive effect without adequate protection; “best practice” alone is neither proof nor dismissal.

## Finding bar

Report a finding only when evidence establishes a concrete vulnerability or material security regression. For every finding provide:

- ID and concise vulnerability title.
- Severity: `Critical`, `High`, `Medium`, or `Low`, justified from realistic impact and exploitability; include CVSS 4.0 vector when enough evidence exists.
- Confidence: `High`, `Medium`, or `Low`.
- Status: `executed`, `theoretical`, or `blocked` reproduction.
- Affected scope, exact `path:line`, symbols, commits/configuration, and causal source-to-sink trace.
- Threat actor, attacker-controlled input, prerequisites, crossed trust boundary, and missing or bypassed controls.
- Concrete attack scenario and security impact: confidentiality, integrity, availability, privacy, tenant, financial, safety, supply-chain, or operational.
- Existing protections examined and why they fail or only reduce impact.
- Root cause and variant scope.
- CWE, CAPEC, OWASP, and applicable standard mappings without using taxonomy as evidence.
- Smallest practical correction, safer design direction where necessary, rollout/compatibility implications, and exact regression-test proof required.
- Any assumptions or evidence gaps that would change the verdict.

Avoid generic best-practice recitations, scanner dumps, compliance-only gaps, unverifiable dependency alerts, cosmetic concerns, praise, and hypothetical attacks without a credible path.

## Report

1. Audit boundary: base/head, scope interpretation, inferred intent, authorization, environments, exclusions, and limitations.
2. Executive risk summary: evidence-based overall posture of the worktree delta, highest-risk trust-boundary changes, confirmed findings, and decisions requiring immediate attention.
3. Deep security analysis: architecture and attack-surface model, assets, actors, entry points, sinks, trust boundaries, security controls, highest-risk abuse paths, cross-layer data/control-flow analysis, adversarial hypotheses tested, and meaningful no-finding conclusions.
4. Tool evidence: availability, versions, exact executed analyses/configuration/rules, extraction quality, result counts, blocked tools, and temporary-artifact cleanup status.
5. Prioritized findings sorted by severity then confidence. Merge duplicates and separate directly relevant pre-existing findings.
6. Advisory, dependency, supply-chain, and patch-bypass summary, including reachability verdicts.
7. Coverage matrix listing the entire discovered and taxonomy-derived audit surface plus every applicable standard as `finding`, `reviewed-no-finding`, `user-action-recommended`, `not-applicable`, or `blocked`, with techniques attempted, depth achieved, concise evidence, and blocker. Include totals for each status so omissions are visible.
8. Residual risk: unverified assumptions, partially tested active paths, missing security tests, and evidence needed to strengthen completed coverage.
9. Uncovered audit surface and user-run follow-up: final substantive section, after the deep audit and findings. Enumerate every surface not fully covered because of missing or restricted tools, tool errors, extraction/build failures, unsupported technologies, missing authorization, environments, fixtures, credentials, dependencies, compute, network access, source, documentation, or time. For each state exact surface, coverage achieved, attempted tools/manual fallbacks, exact failure or blocker, resulting blind spot and risk, and evidence needed to close it. Suggest only useful, applicable open-source or zero-cost tools the agent could not run; clearly label setup as a later user action that the agent did not and will not execute, and include purpose, authoritative source, verified license/edition, zero-cost basis, pinned version, integrity verification, safe user-performed project-local or isolated setup, readiness check, exact bounded audit command, expected artifact, and how to return results for continued analysis. Prioritize entries; distinguish required closure from optional depth. If none remain, state `No uncovered applicable audit surfaces.` Never distribute uncovered items only through earlier prose: repeat and consolidate every one here. Keep this appendix subordinate to the security analysis; tool recommendations are not findings.
10. If nothing meets the finding bar, state: `No high-confidence actionable security findings.` This is not a claim that the codebase is secure.

REPORT ONLY. Do not edit source, format files, generate repository artifacts, install, stage, commit, push, post comments, publish advisories, deploy, or mutate external systems. Temporary audit artifacts outside the repository are the only permitted files; remove them before the final report.
