---
description: Create GitHub pull requests with intelligent change analysis and comprehensive descriptions
agent: "build"
---

# PR

You are executing the /pr command. Follow these steps exactly. Take action on each step.

## Input

- `$1` - (optional) `draft` or base branch name
- `$2` - (optional) base branch if `$1` is `draft`

Parse arguments:

- If `$ARGUMENTS` is empty: create PR from current branch against default base
- If `$1` is `draft`: create as draft PR, use `$2` as base branch if provided
- Otherwise: `$1` is the base branch

---

## STEP 1: Validate repository state

Run these commands now:

```bash
git status --porcelain
git branch --show-current
git remote -v
```

## Requirements

1. Working tree must be clean (no uncommitted changes)
2. Must be on a feature branch (not main/master)
3. Must have a remote configured

## If working tree dirty

> "Working tree has uncommitted changes. Please commit or stash them first."
> STOP.

## If on main/master

> "You are on the main/master branch. Switch to a feature branch first."
> STOP.

## If no remote

> "No remote repository configured. Add a remote first."
> STOP.

---

## STEP 2: Analyze branch divergence

Determine base branch:

- If argument provided → use that
- If not → check default branch (main/master) using:

  ```bash
  git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'
  ```

- If no default → ask user

Check if branch is ahead of remote:

```bash
git rev-list --count @{u}..HEAD
```

## If 0 (not ahead)

> "Branch is not ahead of remote. No changes to PR."
> STOP.

Check divergence from base:

```bash
git log <base-branch>..HEAD --oneline
git diff <base-branch>..HEAD --stat
```

---

## STEP 3: Security scan

Scan all changes for secrets. Run:

```bash
git diff <base-branch>..HEAD
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
3. Respond: "PR BLOCKED - sensitive data detected"
4. Suggest fix (env vars, .gitignore, amend commits)
5. **STOP. Do not proceed.**

---

## STEP 4: Analyze commits and changes

Analyze all commits in this PR:

```bash
git log <base-branch>..HEAD --pretty=format:"%h %s" --reverse
git diff <base-branch>..HEAD --shortstat
```

Categorize changes:

- Features (new functionality)
- Bug fixes
- Breaking changes
- Documentation updates
- Refactoring
- Performance improvements
- Tests
- Dependencies

Identify:

- Primary focus of the PR
- Related files/modules
- Breaking changes
- Migration notes needed

---

## STEP 5: Draft PR content

Generate PR title and description:

## Title format

- Single line, imperative mood
- Include type prefix if needed: `feat:`, `fix:`, `docs:`, etc.
- Maximum 72 characters

## Description structure

```markdown
## Summary
[Brief 2-3 sentence overview of what this PR does and why]

## Changes
- [Bullet list of major changes]
- [Group by type or feature]
- [Include scope when helpful]

## Breaking Changes
[If any, explain what breaks and how to migrate]
[If none, state "None"]

## Testing
[How to test these changes]
[Test coverage added]
[Manual testing steps if applicable]

## Checklist
- [ ] Code follows project style guidelines
- [ ] Tests added/updated and passing
- [ ] Documentation updated
- [ ] No new warnings generated
```

---

## STEP 6: Review draft with user

Show the complete draft:
> "**Pull Request Draft**"
>
> "**Base:** `<base-branch>`"
> "**Head:** `<current-branch>`"
> "**Draft:** <yes/no>"
>
> "**Title:**"
> `<proposed title>`
>
> "**Description:**"
> `<proposed description>`
>
> "**Commits:**"
> `<count>` commit(s) from `<base-branch>`..HEAD
> `<list commit hashes and messages>`

Ask:
> "Options:
>
> 1. Create PR with this draft
> 2. Edit title/description
> 3. Change base branch
> 4. Abort
>
> Choose:"

Wait for user response.

---

## STEP 7: Ensure branch is pushed

Check if branch is pushed to remote:

```bash
git branch -vv | grep '*' | grep -q '\[.*ahead'
```

If ahead (not fully pushed):

```bash
git push -u origin <current-branch>
```

---

## STEP 8: Create the PR

Execute:

```bash
gh pr create \
  --title "<title>" \
  --body "<description>" \
  --base <base-branch> \
  <draft_flag>
```

Where `<draft_flag>` is `--draft` if draft argument provided.

## CRITICAL

- Use heredoc for multi-line body to preserve formatting
- Ensure body is properly escaped
- Verify remote tracking exists

---

## STEP 9: Confirm and verify

Run:

```bash
gh pr view --web
```

Or show:

```bash
gh pr view --json url,number,title,state
```

Report:
> "**Pull Request Created**"
>
> "**URL:** `<pr-url>`"
> "**Number:** `#<pr-number>`"
> "**Title:** `<title>`"
> "**Status:** <open/draft>"
> "**Base:** `<base-branch>` → `<current-branch>`"
>
> "`<commits_count>` commits, `<additions>`+ `<deletions>`- lines changed"

Ask if user wants to:

1. Open PR in browser
2. Add reviewers/labels
3. Create next steps

Wait for final user action.

---

## STEP 10: Optional enhancements

If user requests reviewers/labels:

## Add reviewers

```bash
gh pr edit <pr-number> --add-reviewer <user1,user2>
```

## Add labels

```bash
gh pr edit <pr-number> --add-label "label1,label2"
```

## Set milestone

```bash
gh pr edit <pr-number> --milestone <milestone>
```

Confirm each action after completion.
