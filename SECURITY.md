# Security Policy

## Scope and Trust Model

This repository distributes agent skills, role definitions, prompts, themes,
example MCP templates, and a zero-dependency Python installer (`./setup`). All
configuration and installation actions run strictly on the local filesystem and
treat external inputs as untrusted.

- **No network installs at setup time:** `./setup` copies, symlinks, or renders
  repository assets into a target client home directory without fetching remote
  code or packages.
- **No automatic secret ingestion:** Example MCP templates use environment
  variable placeholders (`${ENV_VAR}`) and never contain live tokens or hostnames.
- **Preflight before mutation:** Installations validate catalog integrity,
  reject destinations inside the repository tree, and refuse to overwrite
  unmanaged files unless explicitly handled.
- **Permission minimization:** Generated Markdown files and configurations use
  `0o644` permissions; only explicit hook scripts receive `0o755`.

## Local Enforcement Gates

Before any commit or push leaves a clone, Git hooks enforce:

1. **Secret scanning:** `gitleaks` scans staged blobs and commit ranges.
2. **SAST and complexity:** `semgrep` and `lizard` inspect code changes.
3. **Static checks and formatting:** `pyright`, `shellcheck`, `shfmt`, and
   `markdownlint-cli2` validate scripts, types, and documentation.
4. **Dependency hygiene:** `osv-scanner` audits any tracked lockfiles.
5. **Personal data guard:** `scripts/personal-scan.sh` blocks environment-specific
   paths, internal issue IDs, and private provider strings.

## Reporting a Vulnerability

Do not open a public issue for security vulnerabilities. Report findings
privately through GitHub Security Advisories for this repository and include:

- Affected file path, skill, role, or `./setup` subcommand
- Reproduction steps and impact assessment
- Suggested remediation, if available
