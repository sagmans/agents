---
description: Create atomic, secure git commits with intelligent changeset grouping
agent: "build"
---

# Commit

You are executing the /commit command. Follow these steps exactly. Take action on each step.

## Input

- `$1` - (optional) `staged` to commit only staged files

Parse arguments:

- If `$ARGUMENTS` is empty: commit all tracked changes, check for related untracked files
- If `$1` is `staged`: commit only staged files, skip untracked check

---

## STEP 1: Get repository state

Run these commands now:

```bash
git status --porcelain
git diff --stat
git diff --cached --stat
git log --oneline -5
```

Parse output. If no changes exist, respond "Nothing to commit" and stop.

---

## STEP 2: Check untracked files

Skip this step if user passed `staged` argument.

From git status output, find untracked files. Check if any relate to modified files:

- Same directory
- Similar names (foo.ts changed → foo.test.ts untracked)
- Associated configs

If related untracked files exist, stop and ask:
> "Found potentially related untracked files:
>
> - [list files]
>
> Options:
>
> 1. Track them and include next commits
> 2. Continue without them
> 3. Abort
>
> Choose:"

Wait for user response before continuing.

---

## STEP 3: Security scan

Scan diff for secrets. Run:

```bash
git diff HEAD
```

Search for these patterns:

- API keys: `sk-`, `pk_live_`, `pk_test_`, `api[_-]?key`
- Secrets: `password\s*=`, `secret\s*=`, `token\s*=`
- Auth: `bearer`, `auth[_-]?token`, `access[_-]?token`
- Keys: `BEGIN.*PRIVATE KEY`, `AKIA`, `aws_secret`
- Files: `.env` (not .example), `credentials.json`, `*.pem`, `*.key`

## If ANY match found

1. Show exact location (file:line) and matched content
2. Explain the security risk
3. Respond: "COMMIT BLOCKED - sensitive data detected"
4. Suggest fix (env vars, .gitignore)
5. **STOP. Do not proceed.**

Then, use semgrep_* tools in toolbox and run complete scan.

---

## STEP 4: Plan atomic commits

Analyze all changes. Group into logical commits:

- By feature/functionality
- By type (code, tests, docs, config, deps)
- By module/component

Each commit must be independently valid. Keep tests with their implementation.

Show the plan:
> "Proposed commits:
>
> 1. type(scope): description
>    - file1, file2
> 2. type(scope): description
>    - file3"

Proceed after showing plan.

---

## STEP 5: Create commits

For each planned commit, execute:

```bash
git add <files>
git commit -sS -m "<type>(<scope>): <description>

<why this change>"
```

## CRITICAL: Always use `-sS` for GPG signature and sign-off. No exceptions

Types: feat, fix, docs, style, refactor, perf, test, ci, build, chore

Do not exceed 80 char limit per line.

---

## STEP 6: Confirm results

Run:

```bash
git log --oneline -n <number_of_commits_created>
```

Report:
> "Created N commit(s):
>
> - hash1 message1
> - hash2 message2"
