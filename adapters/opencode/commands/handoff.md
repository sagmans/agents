---
description: Generate comprehensive handoff document for context transfer
agent: build
---
# Handoff Command

Generate a comprehensive handoff document for transferring context between agents or sessions.

## Usage

```text
/handoff <next-goal>
```

The `$ARGUMENTS` variable captures everything after `/handoff` and becomes the **primary directive** for the next agent. This drives the entire handoff context.

### Examples

| Command | `$ARGUMENTS` Value | Purpose |
| --------- | ------------------- | --------- |
| `/handoff complete next task` | `complete next task` | Finish current epsilon task |
| `/handoff eliminate other deps` | `eliminate other deps` | Remove external dependencies |
| `/handoff remove all occurrences of deprecated API` | `remove all occurrences of deprecated API` | Find and delete deprecated code |
| `/handoff implement container approach` | `implement container approach` | Switch to containerized solution |
| `/handoff fix failing tests` | `fix failing tests` | Address test failures |
| `/handoff refactor to use new API` | `refactor to use new API` | Migrate to new API |
| `/handoff investigate memory leak` | `investigate memory leak` | Debug performance issue |
| `/handoff prepare for production` | `prepare for production` | Final checks and deployment prep |

### Goal Patterns

- **Action + Target**: "implement X", "fix Y", "refactor Z"
- **Outcome-oriented**: "complete migration", "eliminate debt"
- **Problem-focused**: "resolve conflict", "unblock deployment"

---

## Generated Handoff Document

When `/handoff $ARGUMENTS` is invoked, generate the following document:

---

### Metadata

| Field | Value |
| ------- | ------- |
| **Generated** | YYYY-MM-DD HH:MM TZ |
| **From** | agent-name / person-name |
| **Session ID** | (optional: session/thread identifier) |
| **Previous Handoff** | (link to prior handoff if continuing) |
| **Working Directory** | `/absolute/path/to/project` |
| **Git Branch** | `current-branch-name` |

---

### 1. Main Objective

## What are you trying to accomplish

- **Primary goal:** $ARGUMENTS
- **Success criteria:** (define what "done" looks like for "$ARGUMENTS")
- **Expected outcome:** (observable result after completing the goal)

---

### 2. Current State

What's done, fixed, completed, failed, or given up.

Filter this section to highlight items **relevant to achieving "$ARGUMENTS"**.

#### Completed (relevant to goal)

- [ ] Task/change that helps achieve $ARGUMENTS
- [ ] Task/change that helps achieve $ARGUMENTS

#### Fixed (relevant to goal)

- [ ] Issue resolved that was blocking $ARGUMENTS
- [ ] Issue resolved that was blocking $ARGUMENTS

#### Failed / Rolled Back (relevant to goal)

- [ ] Attempt — why it failed, what was learned
- [ ] Attempt — why it failed, what was learned

#### Given Up / Blocked (relevant to goal)

- [ ] Blocker — why blocked, who can unblock, impact on $ARGUMENTS
- [ ] Blocker — why blocked, who can unblock, impact on $ARGUMENTS

---

### 3. Direction

## What's the overall strategy for achieving "$ARGUMENTS"

- **Strategic approach:**
- **Key decisions made:**
- **Assumptions made:**
- **Constraints / Non-negotiables:**

---

### 4. Decisions Made

## Timestamped decisions with rationale for future reference

| When | Decision | Rationale | Alternatives Rejected |
| --- | --- | --- | --- |
| YYYY-MM-DD | Decision related to $ARGUMENTS | Why this was chosen | What was considered |

---

### 5. Active Tasks

## Epsilon task IDs (highest to lowest priority)

Prioritize tasks that contribute to "$ARGUMENTS".

| Priority | Task ID | Status | Description | Owner | Relevance to Goal |
| ---------- | --------- | -------- | ------------- | ------- | ------------------- |
| Critical | #123 | in_progress | Task description | @agent | Directly blocks $ARGUMENTS |
| High | #124 | todo | Task description | unassigned | Required for $ARGUMENTS |
| Medium | #125 | blocked | Task description | @human | Nice-to-have for $ARGUMENTS |

---

### 6. Environment

## Current execution context

| Component | Version / State |
| ----------- | ----------------- |
| Language / Runtime | e.g., Python 3.12, Node 20 |
| Key Dependencies | e.g., Django 5.0, React 18 |
| Virtual Environment | `/path/to/venv` or `none` |
| Container | `running` / `not running` |
| Environment Variables | `ENV_VAR_1=xxx` (non-sensitive only) |
| Services Running | localhost:3000, localhost:5432 |

---

### 7. Critical Nuances & Checkpoints

Notes, warnings, and important context for "$ARGUMENTS".

#### Warnings / Gotchas

- ⚠️ Dangerous assumption that could derail $ARGUMENTS:
- ⚠️ Known issue when working toward $ARGUMENTS:
- ⚠️ Risk specific to this goal:

#### Checkpoints to Hit

- [ ] Verify X before proceeding with $ARGUMENTS
- [ ] Get approval from @person for Y related to $ARGUMENTS

#### External Dependencies

- Waiting on: (what's needed to achieve $ARGUMENTS)
- ETA: (when expected)

#### Decisions Pending

- [ ] Decision needed that affects $ARGUMENTS (needs @decision-maker)

---

### 8. Key Files & Patterns

Important files, keywords, and search terms for "$ARGUMENTS".

#### File Paths

| Purpose | Path | Relevance to $ARGUMENTS |
| --------- | ------ | ------------------------ |
| Main config | `config/settings.py` | Contains config for... |
| Entry point | `src/main.py` | Starting point for... |
| Tests | `tests/unit/test_feature.py` | Tests covering... |
| Documentation | `docs/architecture.md` | Design decisions for... |

#### Code Patterns

```python
# Example pattern relevant to $ARGUMENTS
```

#### Keywords for Search

- `TODO($ARGUMENTS):` — marks items for this goal
- `FIXME:` — known issues
- `HACK:` — temporary workarounds

---

### 9. Main Focus

## Where should the next agent spend their time

## Primary directive (from `/handoff $ARGUMENTS`)

> **$ARGUMENTS**

## Scope boundaries for "$ARGUMENTS"

- **In scope:** (what the next agent SHOULD do to achieve the goal)
- **Out of scope:** (what the next agent should NOT do — prevents scope creep)

**Secondary priorities:** (fallbacks if primary is blocked)

1. First fallback if $ARGUMENTS is blocked
2. Second fallback

## Success criteria for "$ARGUMENTS"

- [ ] Observable outcome that confirms the goal is achieved
- [ ] Test/verification that proves completion

---

### 10. Next Steps

## Concrete actions to achieve "$ARGUMENTS" (in priority order)

1. **[PRIORITY]** Action that directly advances $ARGUMENTS — expected outcome
2. Action that supports $ARGUMENTS — expected outcome
3. Action that prepares for $ARGUMENTS — expected outcome

---

### 11. Rollback Plan

## How to undo recent changes if "$ARGUMENTS" goes wrong

| Change | Rollback Command | Last Known Good |
| -------- | ------------------ | ----------------- |
| Database migration | `alembic downgrade -1` | commit `abc1234` |
| Config change | `git checkout -- config/` | commit `def5678` |
| Dependency update | `pip install package==old.version` | `requirements.txt` |

---

### Pre-Handoff Checklist

Before completing this handoff for "$ARGUMENTS", verify:

- [ ] All epsilon tasks updated with current status
- [ ] Key files committed/pushed (if applicable)
- [ ] No uncommitted secrets in working directory (`git diff`, scan for API keys)
- [ ] Next steps are concrete and actionable (not vague)
- [ ] Blockers clearly identified with owner/contact
- [ ] Environment section accurately reflects current state
- [ ] Decision log includes all significant choices made
- [ ] **Goal "$ARGUMENTS" is clearly understood and achievable**

---

## Key Principles

| Principle | Description |
| ----------- | ------------- |
| **Be specific** | Use numbers, dates, file paths, task IDs, commit hashes |
| **Include context** | Explain *why*, not just *what* |
| **Highlight risks** | Call out dangerous assumptions and failure modes |
| **Prioritize clearly** | Highest priority first; use Critical/High/Medium/Low |
| **Make actionable** | Next agent should know exactly what to do |
| **Assume amnesia** | Write for someone with zero prior context |
| **Filter by goal** | Only include information relevant to achieving $ARGUMENTS |

---

## When to Use

- Ending a session with another agent taking over
- Handing off to a human for review/decision
- Breaking complex work into chunks
- Recording progress before switching contexts
- Before long breaks (lunch, end of day, weekends)
- When context becomes too large to hold in working memory

---

## Quick Template (Minimal)

For rapid handoffs, use this condensed version:

```markdown
## Handoff: $ARGUMENTS

**From:** @agent | **When:** YYYY-MM-DD HH:MM
**Next Goal:** $ARGUMENTS

### Objective
Achieve: $ARGUMENTS

### State (filtered for this goal)
- ✅ Done: [list]
- 🔄 In Progress: [list]
- ❌ Blocked: [list]

### Next Steps for "$ARGUMENTS"
1. [Action 1]
2. [Action 2]

### Risks
- [Warning 1]
```

---

## Handoff Generation Checklist

When user runs `/handoff $ARGUMENTS`, populate the template:

1. **Insert `$ARGUMENTS`** into all sections marked with the variable
2. **Filter Current State** — only include items relevant to achieving the goal
3. **Prioritize Next Steps** — order actions that lead to goal completion
4. **Identify blockers** — what could prevent achieving $ARGUMENTS
5. **Set boundaries** — what's in/out of scope for this specific goal
6. **Define success criteria** — how will the next agent know $ARGUMENTS is achieved?
