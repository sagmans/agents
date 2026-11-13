# Security Model

Security controls govern role permissions, local deployment, example MCP
configurations, and Git hooks before changes reach `main`.

## Trust Boundaries

```text
Repository Catalog (Read-Only Source)
  ├─> ./setup (Stdlib Python, Offline Only)
  │     ├─ Rejects targets inside repo tree
  │     ├─ Rejects unmanaged destination collisions
  │     └─ Tracks managed entries in .agents-manifest.json
  └─> Local Client Home ($HOME)
        ├─ Skills: symlinks or 0o644/0o755 copied snapshots
        ├─ Roles: YAML-escaped frontmatter (0o644)
        └─ Claude hooks: explicit executable scripts (0o755)
```

## Role Execution Guardrails

- **Deny-by-default OpenCode permissions:** `./setup validate` enforces
  wildcard `"edit": "deny"` on every role outside `MUTATING_ENGINEER_ROLES`, and
  all 43 non-mutating catalog roles also configure `"subagent": "deny"` and
  `"shell": "ask"`.
- **Permission resource strictness:** OpenCode permission validation accepts
  only wildcard `"resource": "*"` rules until resource-scoped nested rules are
  rendered explicitly.
- **Explicit mutating set:** Only the 15 engineering roles in
  `MUTATING_ENGINEER_ROLES` omit the wildcard `edit: deny` guard.

## Installer Safeguards

- **Zero runtime dependencies:** `./setup` runs strictly on the Python 3
  standard library and performs zero network requests.
- **Collision protection:** Before writing or linking any path, `./setup`
  verifies ownership in `.agents-manifest.json` and aborts if an unmanaged user
  file occupies a destination path.
- **Clean uninstall:** `./setup uninstall` deletes only paths recorded in
  `.agents-manifest.json` and leaves sibling user files untouched.
- **Control-character escaping:** Role frontmatter escapes quotes, backslashes,
  control characters, and Unicode line separators (`U+0085`, `U+2028`, `U+2029`).

## Inert MCP Policy

Templates in [mcp/examples](../mcp/README.md) contain no active credentials,
private hostnames, or implicit registrations. All secrets use `${ENV_VAR}`
placeholders and pinned version/tag placeholders (`<pinned-version>`,
`<pinned-tag>`).

## Pre-Commit and Pre-Push Gates

Every commit and push passes through `.githooks/` and `scripts/check.sh`:

1. `scripts/personal-scan.sh` blocks private paths, tokens, and internal IDs.
2. `gitleaks` scans staged blobs and commit ranges for secrets.
3. `pyright`, `lizard`, `semgrep`, `shellcheck`, `shfmt`, and `markdownlint-cli2`
   enforce type, complexity, static analysis, shell, and documentation checks.
4. `scripts/dogfood.sh` exercises clean-room installation, drift detection, and
   fail-closed conflicts inside temporary `$HOME` directories.
