---
description: Create GitHub issues with intelligent template detection and structured user interview
agent: "build"
---

# Issue

You are executing the `/issue` command. Follow steps in order. Take action.

ASCII flow:

  scan templates -> select/fallback -> interview user -> generate issue -> create on GitHub

## Input

- `$1` - (optional) issue type: `bug`, `feature`, `docs`, or target repo `owner/repo`
- `$2` - (optional) if $1 is repo, this is the issue type

Parse arguments:

- If `$1` is empty: full flow (detect template, interview, create)
- If `$1` matches `owner/repo` format: use as target repo, `$2` as type
- If `$1` is `bug|feature|docs`: skip template detection, use specified type

---

## STEP 1: Detect repository and templates

Run:

```bash
# Get repo info
gh repo view --json nameWithOwner,url

# Check for issue templates
ls -la .github/ISSUE_TEMPLATE/ 2>/dev/null || echo "NO_TEMPLATE_DIR"
ls -la .github/ISSUE_TEMPLATE.md 2>/dev/null || echo "NO_SINGLE_TEMPLATE"

# If templates exist, show them
cat .github/ISSUE_TEMPLATE/*.md 2>/dev/null | head -200
cat .github/ISSUE_TEMPLATE/*.yml 2>/dev/null | head -200
```

---

## STEP 2: Parse templates or use fallback

## If templates exist

- Parse YAML/MD templates
- Extract: `name`, `description`, `labels`, required fields
- Present options to user:

> "Found issue templates:
>
> 1. Bug Report - Report a bug or unexpected behavior
> 2. Feature Request - Suggest a new feature
> 3. Documentation - Report docs issues
> 4. Custom - Use generic template
>
> Choose template:"

Wait for user selection.

## If NO templates

> "No issue templates found. Using generic format."

Proceed with fallback template.

---

## STEP 3: Interview user (adaptive)

Based on template type, ask targeted questions. Keep it SHORT and FOCUSED.
Gather all necessary information from the codebase and local system as much
as possible, then start interviewing.

## Bug Report Interview

```text
┌──────────────────────────────────────────────────────────┐
│ BUG REPORT INTERVIEW                                     │
├──────────────────────────────────────────────────────────┤
│ Q1: What's broken? (1-2 sentences)                       │
│ Q2: Steps to reproduce? (numbered list)                  │
│ Q3: Expected vs actual behavior?                         │
│ Q4: Environment? (OS, version, browser, etc.)            │
│ Q5: Error messages/logs? (if any)                        │
│ Q6: Severity? (blocker/critical/major/minor/trivial)     │
└──────────────────────────────────────────────────────────┘
```

Ask ONE question at a time. Wait for response.

## Feature Request Interview

```text
┌──────────────────────────────────────────────────────────┐
│ FEATURE REQUEST INTERVIEW                                │
├──────────────────────────────────────────────────────────┤
│ Q1: What problem does this solve?                        │
│ Q2: Proposed solution? (brief)                           │
│ Q3: Alternatives considered?                             │
│ Q4: Who benefits? (use case)                             │
│ Q5: Priority? (nice-to-have/should-have/must-have)       │
└──────────────────────────────────────────────────────────┘
```

## Documentation Issue Interview

```text
┌──────────────────────────────────────────────────────────┐
│ DOCS ISSUE INTERVIEW                                     │
├──────────────────────────────────────────────────────────┤
│ Q1: What's missing/incorrect?                            │
│ Q2: Where? (file/section/URL)                            │
│ Q3: Suggested improvement?                               │
└──────────────────────────────────────────────────────────┘
```

## Generic Interview

```text
┌──────────────────────────────────────────────────────────┐
│ GENERIC ISSUE INTERVIEW                                  │
├──────────────────────────────────────────────────────────┤
│ Q1: Issue type? (bug/feature/docs/question/other)        │
│ Q2: Title? (clear, concise)                              │
│ Q3: Description? (what/why/context)                      │
│ Q4: Additional context? (links, screenshots, etc.)       │
└──────────────────────────────────────────────────────────┘
```

---

## STEP 4: Generate issue content

Based on interview responses, generate:

## Title

- Clear, specific, searchable
- Prefix with type: `[Bug]`, `[Feature]`, `[Docs]`
- Max 80 characters

## Body (Bug Report)

````markdown
## Description
<brief description of the bug>

## Steps to Reproduce
1. <step 1>
2. <step 2>
3. <step 3>

## Expected Behavior
<what should happen>

## Actual Behavior
<what actually happens>

## Environment
- OS: <os>
- Version: <version>
- <other relevant info>

## Error Logs
```text
<error messages if any>
```

## Additional Context

<screenshots, links, etc.>
````

## Body (Feature Request)

```markdown
## Problem Statement
<what problem this solves>

## Proposed Solution
<brief description of the solution>

## Alternatives Considered
<other approaches and why they weren't chosen>

## Use Case
<who benefits and how>

## Additional Context
<mockups, examples, etc.>
```

## Body (Generic)

```markdown
## Description
<clear description>

## Context
<relevant background>

## Additional Information
<any other details>
```

---

## STEP 5: Review draft with user

Show complete draft:

> "**Issue Draft**
>
> **Repository:** `<owner>/<repo>`
> **Type:** <bug/feature/docs>
>
> **Title:**
> `<proposed title>`
>
> **Labels:** `<inferred labels>`
>
> **Body:**
> `<proposed body>`
>
> ---
>
> Options:
>
> 1. Create issue
> 2. Edit title
> 3. Edit body
> 4. Add/change labels
> 5. Abort"

Wait for user response.

---

## STEP 6: Create issue

If user approves:

```bash
gh issue create \
  --title "<title>" \
  --body "$(cat <<'EOF'
<body>
EOF
)" \
  --label "<labels>"
```

If labels specified but don't exist:
> "Label '`<label>`' doesn't exist. Create it? (y/n)"

---

## STEP 7: Confirm and report

Run:

```bash
gh issue view <issue_number> --json number,url,title,state
```

Report:
> "**Issue Created**
>
> **Number:** `#<number>`
> **URL:** `<url>`
> **Title:** `<title>`
> **Status:** Open
>
> Next:
>
> 1. Open in browser
> 2. Add assignees
> 3. Link to project
> 4. Done"

Wait for user action.

---

## STEP 8: Optional enhancements

If user requests:

## Add assignees

```bash
gh issue edit <number> --add-assignee <user>
```

## Add to project

```bash
gh project item-add <project_number> --owner <owner> --url <issue_url>
```

## Link to milestone

```bash
gh issue edit <number> --milestone <milestone>
```

Confirm each action.
