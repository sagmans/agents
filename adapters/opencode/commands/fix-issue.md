---
description: Automatically fix GitHub issues - validate, plan, implement, and commit in isolated worktree
agent: "build"
---

# Fix Issue

You are executing the `/fix-issue` command. Follow steps in order. Take action.

ASCII flow:

```text
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Issue  │───▶│ Validate │───▶│   Plan   │───▶│ Worktree │───▶│Implement │───▶│  Done    │
│  URL    │    │ & Assess │    │  (agent) │    │  Setup   │    │ + Commit │    │          │
└─────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                   │                │                              │
                   ▼                ▼                              ▼
              INVALID?          REJECT?                      Auto-commit
               STOP              STOP                       at checkpoints
```

## Input

- `$1` - Issue URL or number (required), e.g., `https://github.com/owner/repo/issues/123` or `#123` or `123`
- `$2` - (optional) `--dry-run` to validate and plan only, don't implement

Parse arguments:

- If `$1` is empty: STOP with "Usage: /fix-issue <issue-url|#number> [--dry-run]"
- If `$ARGUMENTS` contains `--dry-run`: set DRY_RUN=true

---

## STEP 1: Parse and fetch issue

Issue reference provided: `$1`

Extract issue reference:

- URL format: `https://github.com/<owner>/<repo>/issues/<number>`
- Number format: `#123` or `123` (uses current repo)

Run:

```bash
# Get current repo context
gh repo view --json nameWithOwner,defaultBranchRef 2>/dev/null

# Fetch complete issue data
gh issue view <number> --repo <owner>/<repo> --json \
  number,title,body,author,state,labels,assignees,comments,createdAt,updatedAt

# Get linked PRs if any
gh api repos/<owner>/<repo>/issues/<number>/timeline --paginate | \
  jq '[.[] | select(.event == "cross-referenced" or .event == "connected")]'
```

If issue not found:
> "Issue not found or inaccessible. Check URL/permissions."
> STOP.

If issue is closed:
> "Issue `#<number>` is already closed. Proceed anyway? (y/n)"
> Wait for response.

---

## STEP 2: Extract and structure issue data

Parse issue into structured format:

```text
┌─────────────────────────────────────────────────────────────┐
│ ISSUE #<number>: <title>                                    │
├─────────────────────────────────────────────────────────────┤
│ Type:        <bug|feature|docs|question|unknown>            │
│ Author:      @<author>                                      │
│ Created:     <date>                                         │
│ Labels:      <label1>, <label2>                             │
│ Assignees:   <assignee1>, <assignee2>                       │
├─────────────────────────────────────────────────────────────┤
│ DESCRIPTION:                                                │
│ <parsed body - first 500 chars>                             │
├─────────────────────────────────────────────────────────────┤
│ KEY DETAILS EXTRACTED:                                      │
│ • Problem: <what's wrong>                                   │
│ • Location: <files/components mentioned>                    │
│ • Repro Steps: <if bug>                                     │
│ • Expected: <desired behavior>                              │
│ • Environment: <versions, OS, etc.>                         │
├─────────────────────────────────────────────────────────────┤
│ COMMENTS: <count>                                           │
│ • @user1: <summary of comment>                              │
│ • @user2: <summary of comment>                              │
└─────────────────────────────────────────────────────────────┘
```

---

## STEP 3: Validate issue legitimacy

Perform validation checks:

| Check | Method | Result |
| ------- | -------- | -------- |
| **Clarity** | Is problem clearly stated? | ✓/✗ |
| **Reproducibility** | Are steps provided (if bug)? | ✓/✗/N/A |
| **Scope** | Is scope reasonable for single fix? | ✓/✗ |
| **Duplicate** | Search for similar issues | ✓/✗ |
| **Relevance** | Does it apply to current codebase? | ✓/✗ |
| **Feasibility** | Can this be fixed/implemented? | ✓/✗ |

Run duplicate check:

```bash
gh issue list --repo <owner>/<repo> --state all --search "<key terms>" --limit 10 --json number,title,state
```

Run codebase relevance check:

```bash
# Search for mentioned files/functions
rg -l "<mentioned_identifier>" --type-add 'code:*.{ts,js,go,py,rs,java}' -t code 2>/dev/null | head -10
```

## Validation verdict

If INVALID:
> "**Issue Validation Failed**
>
> Issues found:
>
> - `<issue 1>`
> - `<issue 2>`
>
> Recommendation: <ask author for clarification / close as duplicate / etc.>
>
> Proceed anyway? (y/n)"

If VALID:
> "**Issue Validated** ✓
>
> Confidence: <high|medium|low>
> Scope: <small|medium|large>
> Estimated complexity: <trivial|moderate|complex>"

---

## STEP 4: Create implementation plan via "plan" agent

Invoke the plan agent with structured context:

```text
Use the "plan" agent to create a detailed implementation plan.

Context:
- Issue: #<number> - <title>
- Type: <bug|feature>
- Repository: <owner>/<repo>
- Description: <full issue body>
- Key files identified: <list>
- Comments context: <relevant comments>

Requirements:
1. Analyze the codebase to understand current implementation
2. Identify all files that need modification
3. Break down into atomic, testable tasks
4. Include test requirements
5. Identify potential risks/blockers
6. Estimate effort per task

Output format:
- Task list with clear acceptance criteria
- File change map
- Test plan
- Risk assessment
```

Wait for plan agent to complete.

---

## STEP 5: Present plan for approval

Display the plan:

```text
┌─────────────────────────────────────────────────────────────┐
│ IMPLEMENTATION PLAN - Issue #<number>                       │
├─────────────────────────────────────────────────────────────┤
│ Worktree: fix-issue-<number>-<slug>                           │
│ Branch: fix/issue-<number>-<slug>                           │
│ Estimated tasks: N                                          │
│ Files affected: M                                           │
├─────────────────────────────────────────────────────────────┤
│ TASKS:                                                      │
│ □ 1. <task description>                     [checkpoint]    │
│      Files: file1.ts, file2.ts                              │
│ □ 2. <task description>                                     │
│      Files: file3.ts                                        │
│ □ 3. Write/update tests                     [checkpoint]    │
│      Files: file1.test.ts                                   │
│ □ 4. Update documentation                                   │
│      Files: README.md                                       │
├─────────────────────────────────────────────────────────────┤
│ RISKS:                                                      │
│ • <potential risk 1>                                        │
│ • <potential risk 2>                                        │
└─────────────────────────────────────────────────────────────┘
```

Ask:
> "**Plan Review**
>
> Options:
>
> 1. **Approve** - Create worktree and start implementation
> 2. **Modify** - Adjust the plan
> 3. **Reject** - Cancel and provide feedback
>
> Choose:"

Wait for user response.

If rejected: STOP.
If modify: Loop back to refine plan.

---

## STEP 6: Setup worktree and branch

Check ownership with `git remote get-url origin` against the ownership table in the global `AGENTS.md`.

**If owned repository (trunk flow):** stay on `main` in the current clone. Run `git fetch origin` and `git rebase origin/main`, then skip to Confirm. Use no branch or worktree.

**If external repository:** follow the steps below.

Determine branch name:

```bash
# Slugify issue title
SLUG=$(echo "<title>" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | head -c 30)
BRANCH="fix/issue-<number>-${SLUG}"
```

Check if bare repo (worktree mode):

```bash
git rev-parse --is-bare-repository
```

## If bare repository (worktree mode)

```bash
# Get default branch
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@')

# Create worktree with new branch
WORKTREE_PATH="../<repo>-issue-<number>"
git worktree add -b "$BRANCH" "$WORKTREE_PATH" "origin/$DEFAULT_BRANCH"

# Enter worktree
cd "$WORKTREE_PATH"
```

## If regular repository

```bash
# Ensure on latest default branch
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@')
git fetch origin "$DEFAULT_BRANCH"
git checkout -b "$BRANCH" "origin/$DEFAULT_BRANCH"
```

Confirm:
> "**Workspace Ready**
>
> Branch: `<branch>`
> Location: `<path>`
>
> Starting implementation..."

---

## STEP 7: Execute implementation

For each task in the plan:

## 7.1 Pre-task

- Update todo list with current task as `in_progress`
- Announce:

  > **Task `N/<total>`:** `<description>`

## 7.2 Implementation

- Analyze relevant files
- Make necessary changes
- Follow project coding standards
- Ensure changes are minimal and focused

## 7.3 Validation

- Run linter if configured:

  ```bash
  npm run lint 2>/dev/null || pnpm lint 2>/dev/null || yarn lint 2>/dev/null || true
  ```

- Run type check if TypeScript:

  ```bash
  npx tsc --noEmit 2>/dev/null || true
  ```

- Run relevant tests:

  ```bash
  npm test -- --findRelatedTests <changed_files> 2>/dev/null || true
  ```

## 7.4 Checkpoint commit (at marked tasks)

```bash
git add <changed_files>
git commit -sS -m "fix(#<issue_number>): <task description>

Part of #<issue_number>
- <change 1>
- <change 2>"
```

Report progress:
> "**Checkpoint:** Task N complete ✓
> Commit: `<hash>` - `<message>`"

---

## STEP 8: Run full test suite

After all tasks complete:

```bash
# Detect and run test suite
if [ -f "package.json" ]; then
  npm test 2>&1 || pnpm test 2>&1 || yarn test 2>&1
elif [ -f "Cargo.toml" ]; then
  cargo test 2>&1
elif [ -f "go.mod" ]; then
  go test ./... 2>&1
elif [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then
  pytest 2>&1 || python -m pytest 2>&1
fi
```

If tests fail:
> "**Tests Failed**
>
> Failures:
> `<test output>`
>
> Options:
>
> 1. Fix failing tests
> 2. Skip tests and continue
> 3. Abort implementation"

Wait for user decision.

---

## STEP 9: Final commit and summary

Create final commit if uncommitted changes remain:

```bash
git status --porcelain
```

If changes exist:

```bash
git add -A
git commit -sS -m "fix(#<issue_number>): <issue_title>

Closes #<issue_number>

Changes:
- <summary of all changes>

Tested: <test status>"
```

Generate summary:

```text
┌─────────────────────────────────────────────────────────────┐
│ IMPLEMENTATION COMPLETE                                     │
├─────────────────────────────────────────────────────────────┤
│ Issue:    #<number> - <title>                               │
│ Worktree: <worktree>                                        │
│ Branch:   <branch>                                          │
│ Commits:  <count>                                           │
│ Files:    <count> changed                                   │
│ Tests:    <passed|failed|skipped>                           │
├─────────────────────────────────────────────────────────────┤
│ COMMITS:                                                    │
│ • <hash1> <message1>                                        │
│ • <hash2> <message2>                                        │
│ • <hash3> <message3>                                        │
├─────────────────────────────────────────────────────────────┤
│ FILES CHANGED:                                              │
│ M  src/component.ts         (+45, -12)                      │
│ M  src/component.test.ts    (+30, -0)                       │
│ A  src/utils/helper.ts      (+25, -0)                       │
└─────────────────────────────────────────────────────────────┘
```

---

## STEP 10: Next steps

**If owned repository (trunk flow):** do not show the menu below. A push to an owned repository after the hooks and checks pass is not a critical decision. Load the `ship` skill (rebase, review, tests, dogfood, `git push origin main`) and reference the issue with `Fixes #<number>` in the commit body. The hooks and checks are the push gate. Escalate to the user only a critical decision or an ambiguity. Then STOP.

**If external repository:** show the menu.

> "**Issue `#<number>` Fixed** ✓
>
> Worktree `<worktree>` is ready.
> Branch `<branch>` is ready.
>
> Next steps:
>
> 1. **Push branch** - `git push -u origin <branch>`
> 2. **Create PR** - `/pr` to create pull request
> 3. **Review changes** - `git diff <default_branch>..HEAD`
> 4. **Run more tests** - Manual verification
>
> Choose action (or 'done'):"

Wait for user action.

If user chooses "Create PR":

- Execute `/pr` command automatically
- Link PR to issue with `Closes #<number>` or `Fixes #<number>`

---

## ERROR HANDLING

Throughout execution, handle errors gracefully:

| Error | Action |
| ------- | -------- |
| Git conflict | Pause, show conflict, ask user to resolve |
| Test failure | Show failure, offer to fix or skip |
| Lint error | Auto-fix if possible, else show and continue |
| Build error | Stop, show error, ask for guidance |
| API rate limit | Wait and retry with backoff |

On any critical failure:
> "**Implementation Paused**
>
> Error: `<description>`
> Location: Task N - `<task name>`
>
> Options:
>
> 1. Retry current task
> 2. Skip and continue
> 3. Abort (changes preserved in branch)
>
> Choose:"

**NEVER** delete the branch or lose work. All progress is preserved in commits.
