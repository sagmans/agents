---
description: Validate GitHub PR review comments, extract actionable tasks, and save to a structured file
agent: "build"
---

# Validate PR Reviews

You are executing the `/validate_pr_reviews` command. Follow steps in order. Take action.

ASCII flow:

  PR URL -> fetch threads -> filter unresolved -> validate each -> save `PR_REVIEW_<id>.md`

**Input:** `$1` (PR URL, e.g., `https://github.com/owner/repo/pull/123`)

---

## STEP 1: Parse and validate PR URL

PR URL provided: `$1`

Extract from URL:

- `owner`: repository owner
- `repo`: repository name
- `pr_id`: pull request number

Validate format:

- Must match `https://github.com/<owner>/<repo>/pull/<number>`

If `$1` is empty or invalid:
> "Invalid PR URL format. Expected: <https://github.com/owner/repo/pull/123>"
> STOP.

---

## STEP 2: Fetch PR metadata and review threads

Run:

```bash
# Get PR info
gh pr view <pr_id> --repo <owner>/<repo> --json title,body,author,state,baseRefName,headRefName

# Get all review comments (includes threads)
gh api repos/<owner>/<repo>/pulls/<pr_id>/comments --paginate

# Get review threads with resolution status
gh api graphql -f query='
query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          comments(first: 50) {
            nodes {
              body
              author { login }
              createdAt
            }
          }
        }
      }
    }
  }
}' -f owner=<owner> -f repo=<repo> -F pr=<pr_id>
```

If PR not found or inaccessible:
> "Cannot access PR. Check URL and permissions."
> STOP.

---

## STEP 3: Filter unresolved threads

From GraphQL response, filter threads where:

- `isResolved: false`
- `isOutdated: false` (optional: include outdated with flag)

Build list:

```text
Thread #N:
  File: <path>
  Line: <line>
  Author: <author>
  Comment: <body>
  Replies: [list of replies]
```

If no unresolved threads:
> "No unresolved review threads found. PR is clean!"
> STOP.

Report:
> "Found N unresolved threads. Validating..."

---

## STEP 4: Validate each thread

For each unresolved thread, analyze:

## 4.1 Fetch current code context

```bash
# Get the file content at PR head
gh api repos/<owner>/<repo>/contents/<path>?ref=<headRefName> | jq -r '.content' | base64 -d
```

## 4.2 Validation criteria

| Check | Valid | Invalid |
| ------- | ------- | --------- |
| Code still exists at line | ✓ | File/line removed |
| Comment is actionable | ✓ | Vague/opinion-only |
| Suggestion is technically correct | ✓ | Wrong/outdated info |
| Not already addressed | ✓ | Fixed in later commit |

## 4.3 Classify each thread

- `VALID`: Actionable, accurate, not addressed
- `INVALID_OUTDATED`: Code no longer exists
- `INVALID_ADDRESSED`: Already fixed
- `INVALID_INCORRECT`: Technically wrong suggestion
- `NEEDS_DISCUSSION`: Subjective or unclear

Show progress:
> "Thread #N: `<status>` - `<brief reason>`"

---

## STEP 5: Generate summary

Create summary table:

```text
┌─────────┬───────┬──────────┬─────────────┬─────────────────┐
│ Thread  │ File  │ Line     │ Status      │ Summary         │
├─────────┼───────┼──────────┼─────────────┼─────────────────┤
│ #1      │ x.ts  │ 42       │ VALID       │ Add error check │
│ #2      │ y.go  │ 15       │ INVALID     │ Already fixed   │
└─────────┴───────┴──────────┴─────────────┴─────────────────┘
```

Report:
> "Validation complete:
>
> - Valid tasks: N
> - Invalid/Outdated: M
> - Needs discussion: K"

---

## STEP 6: Save to file

Generate `PR_REVIEW_<pr_id>.md` in current directory:

```markdown
# PR Review Tasks - #<pr_id>

**PR:** <title>
**URL:** <pr_url>
**Author:** <author>
**Generated:** <timestamp>

## Summary

- Total unresolved threads: N
- Valid actionable tasks: X
- Invalid/Outdated: Y
- Needs discussion: Z

## Valid Tasks

### Task 1: <brief title>
- **File:** `<path>`
- **Line:** <line>
- **Reviewer:** @<author>
- **Comment:**
  > <original comment>
- **Action Required:**
  <clear description of what needs to be done>

### Task 2: ...

## Needs Discussion

### Thread N: <brief title>
- **File:** `<path>`
- **Reason:** <why it needs discussion>
- **Original Comment:**
  > <comment>

## Invalid/Skipped

| Thread | File | Reason |
|--------|------|--------|
| #N | x.ts | Code removed |
| #M | y.go | Already addressed in commit abc123 |
```

Write file:

```bash
# File will be created in current directory
ls -la PR_REVIEW_<pr_id>.md
```

---

## STEP 7: Report and next steps

Report:
> "**PR Review Validation Complete**
>
> **File:** `PR_REVIEW_<pr_id>.md`
> **Valid Tasks:** N
>
> Next steps:
>
> 1. Review the generated file
> 2. Address valid tasks
> 3. Respond to 'Needs Discussion' items
> 4. Re-request review when done"

Ask:
> "Options:
>
> 1. Open file in editor
> 2. Show valid tasks inline
> 3. Start addressing tasks
> 4. Done"
