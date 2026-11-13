---
description: Generic GitHub release flow with safe defaults + project-specific next steps
agent: "build"
---

# Release

You are executing the `/release` command. Follow steps in order. Take action.

ASCII flow:

  prep (project) -> commit -> signed tag -> push -> GH release -> post-release (project)

## Input

- `$1` - (optional) version (`X.Y.Z`), bump type (`major|minor|patch`), or flag (`draft|no-push`)
- `$2` - (optional) additional flag if `$1` is version/bump

Parse arguments:

- If `$ARGUMENTS` is empty: infer version + notes
- If `$1` matches `X.Y.Z`: use exact version
- If `$1` is `major|minor|patch`: bump from last tag
- If `$ARGUMENTS` contains `draft`: create GitHub release as draft
- If `$ARGUMENTS` contains `no-push`: skip pushing (commit/tag only)

---

## STEP 1: Repo preflight

Run:

```bash
git status --porcelain
git branch --show-current
git remote -v
git describe --tags --abbrev=0 2>/dev/null || echo "NO_TAGS"
```

Rules:

- If working tree dirty: STOP and ask user to commit/stash first
- If no remote: STOP

---

## STEP 2: Choose version (interactive if needed)

Run:

```bash
git tag -l --sort=-creatordate | head -n 20
# if last tag exists:
git log --oneline <lastTag>..HEAD
# if NO_TAGS (first release):
git log --oneline --reverse | head -n 50
```

Decide `VERSION`:

- If user provided `X.Y.Z`: use it
- Else if user provided `major|minor|patch`: bump from `<lastTag>`
- Else propose bump using hints (ask user to confirm):
  - MAJOR: any "Breaking" / "!" / migration notes
  - MINOR: any `feat:`
  - PATCH: otherwise

STOP and ask:
> "Proposed VERSION: vX.Y.Z (confirm or edit?)"

---

## STEP 3: Security scan (block on secrets)

If `<lastTag>` exists, scan the release diff:

```bash
git diff <lastTag>..HEAD
```

If `NO_TAGS` (first release), scan tracked files instead:

```bash
git ls-files | rg -n "(^|/)\.env$|credentials\.json$|\.pem$|\.key$"
git grep -nE "sk-|pk_live_|pk_test_|api[_-]?key|password\s*=|secret\s*=|token\s*=|bearer|auth[_-]?token|access[_-]?token|AKIA|aws_secret|BEGIN.*PRIVATE KEY"
```

Search patterns:

- API keys: `sk-`, `pk_live_`, `pk_test_`, `api[_-]?key`
- Secrets: `password\s*=`, `secret\s*=`, `token\s*=`
- Auth: `bearer`, `auth[_-]?token`, `access[_-]?token`
- Keys: `BEGIN.*PRIVATE KEY`, `AKIA`, `aws_secret`
- Files: `.env` (not `.example`), `credentials.json`, `*.pem`, `*.key`

If ANY match:

- Show `file:line` + matched content
- Explain risk
- Respond exactly: `RELEASE BLOCKED - sensitive data detected`
- Suggest fix (env vars, gitignore, rotate keys)
- STOP

---

## STEP 4: Prep release commit (project-specific)

This step IS project-specific.

Do:

- If `RELEASE.md` exists: follow it
- Else infer likely version/changelog files and ask before editing

Heuristics (only if present):

- Node: `package.json` (+ `package-lock.json`/`bun.lock`/`pnpm-lock.yaml`)
- Rust: `Cargo.toml`
- Python: `pyproject.toml` / `setup.cfg`
- Go: tag-only releases are common (no version file)
- Changelog: `CHANGELOG.md`

Goal:

- Update version to `X.Y.Z` where appropriate
- Move "Unreleased" notes into `## [X.Y.Z] - YYYY-MM-DD` when applicable

Then show:

```bash
git diff --stat
```

Ask:
> "Proceed to commit release changes? (yes/no)"

---

## STEP 5: Create release commit (standard)

Run:

```bash
git status --porcelain
```

If nothing to commit:

- Ask user if this repo uses tag-only releases
- If yes: skip commit and continue to tagging
- If no: STOP (missing release prep changes)

Commit (ALWAYS sign and sign off):

```bash
git add <release-files>
git commit -sS -m "Release vX.Y.Z"
```

---

## STEP 6: Create signed tag (standard)

ALWAYS signed tag:

```bash
git tag -s -m "Release vX.Y.Z" vX.Y.Z
```

---

## STEP 7: Push (standard)

If `no-push` arg: skip.

Else (robust push):

```bash
# pick remote (prefer origin; else first remote)
REMOTE="origin"
git remote | rg -qx "origin" || REMOTE="$(git remote | head -n 1)"

# ensure upstream exists
git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo "NO_UPSTREAM"

# if NO_UPSTREAM:
git push -u "$REMOTE" "$(git branch --show-current)"

# always push tag explicitly (works even if tag-only release)
git push "$REMOTE" vX.Y.Z
```

---

## STEP 8: Create GitHub release (standard)

Build notes:

- Prefer `CHANGELOG.md` section `X.Y.Z`
- Else summarize commits since last tag

Create or update release:

```bash
# if release exists, edit; else create
(gh release view vX.Y.Z >/dev/null 2>&1 && echo "EXISTS") || echo "MISSING"

# create
gh release create vX.Y.Z --title "vX.Y.Z" --notes "$(cat <<'EOF'
<notes>
EOF
)" <optional --draft>

# or edit
gh release edit vX.Y.Z --notes "$(cat <<'EOF'
<notes>
EOF
)"
```

Report the release URL.

---

## STEP 9: Post-release actions (PROJECT-SPECIFIC)

After GH release, STOP and do one of:

A) Infer next actions by repo signals, then ask user to choose:

- npm publish: `package.json`
- crates.io publish: `Cargo.toml`
- PyPI publish: `pyproject.toml`
- Docker publish: `Dockerfile` / `.github/workflows/*docker*`
- Homebrew: `Formula/` or docs mentioning brew
- Docs deploy: `mkdocs.yml`, `docusaurus.config.*`, `docs/` + workflow

B) If unsure, ask:
> "What are the project-specific release steps after GitHub release for this repo?"

Rules:

- Clearly label which commands require human auth/OTP and confirm before running
- Do NOT guess credentials or run destructive commands
