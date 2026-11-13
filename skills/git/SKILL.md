---
name: git
description: "Use when inspecting or changing Git repository state, committing, continuing paused operations, or cleaning up after a confirmed PR merge."
---
# Git

## Related skills

Load `commit` for commits. Load `github` and `pr` for GitHub PR work. Load `pr-merge` to land an existing PR, `ship` for normal delivery, or `ship-asap` only for an explicitly requested emergency delivery. Do not reload the skill that delegated to `git`.

## Native Git by default

Use native Git for inspection, staging, branches, worktrees, synchronization, and recovery. The helpers below are exceptions, not a replacement CLI. Resolve script paths relative to this skill; run them in the target repository.

- Create commits through `commit/scripts/commit.sh` from the `commit` skill. It owns signed DCO commits and staging safeguards.
- Pull with `--ff-only`. Rebase feature branches onto their base instead of merging locally.
- Owned repositories (`origin` owner matches a configured owner in `GIT_TRUNK_OWNERS` or `git config --get-all agents.trunkOwners`, and `gh repo view "$(git remote get-url origin)" --json isFork --jq .isFork` prints `false`; name `origin` because a bare `gh repo view` reads `upstream` in fork clones; any other output or an error means not owned): push only when the local hooks and the project's checks pass, without prompting for routine delivery approval unless a critical decision or ambiguity exists.
- All other repositories, including forks and external branches: push only with user approval.
- A force-push or history rewrite is critical in every repository. When an approved rewrite requires force, use `--force-with-lease`, never `--force`.
- Inspect affected paths and refs before destructive operations; obtain explicit approval before discarding work or deleting branches. Use non-force branch deletion and exclude ignored files from cleaning, except through the confirmed post-merge cleanup below.
- Never modify Git configuration or bypass hooks. For unattended native commands, use process-scoped pager/editor/prompt settings when needed; do not disable a sequence editor when the task requires editing the rebase plan.

## Helpers

Optional reports:

```bash
bash scripts/git.sh summary
bash scripts/git.sh detail
```

After resolving and staging conflicts and running relevant checks, use the matching continuation helper:

```bash
bash scripts/git.sh rebase-continue
bash scripts/git.sh cherry-pick-continue
bash scripts/git.sh revert-continue
bash scripts/git.sh merge-continue
```

These preserve the recorded message and override interactive editor, sequence editor, pager, and terminal credential prompts through process environment only. They do not resolve conflicts, authorize the operation, or guarantee signing of rewritten commits. `merge-continue` is only for an already-authorized merge in a repository that permits it. Use native Git for abort/skip after inspecting what will be discarded.

## Post-merge cleanup

After a confirmed PR merge, run the bundled composite cleanup immediately:

```bash
bash scripts/cleanup-after-merge.sh <merged-branch> <default-branch> <expected-head> [remote]
```

It first verifies local and remote merged branches still equal the confirmed PR head. It then reports tracked modifications plus untracked and ignored entries that cleanup will discard, removes the linked worktree (or cleans and reuses the primary worktree), force-deletes the local branch because squash merges do not preserve ancestry, and deletes the remote branch with a force-with-lease guard. The remote branch is re-read after the slow worktree removal and deleted only while it still equals the confirmed PR head, because hosts that delete head branches on merge remove it during cleanup and Git reports that rejection identically to a branch that moved: absence reports `absent: deleted remotely during cleanup` and cleanup continues, a moved branch reports both object IDs and exits nonzero, and a delete rejected mid-push is classified by one more read. Any absence also drops the stale `refs/remotes/<remote>/<branch>` tracking ref, so every absence path ends in the state an accepted delete produces. Only after merged leftovers are gone does it switch the selected worktree to the default branch when needed and pull with `--ff-only`. Missing resources count as already clean. A failed cleanup operation stops dependent deletion; a failed default update is reported after cleanup and exits nonzero.

The helper is repository-agnostic: it never runs setup, relinking, builds, deployment, or other repository-specific post-merge operations. After any cleanup attempt that removes or reuses the merged worktree, run applicable repository-specific safety follow-ups even if the final default update failed, and report both outcomes. Never use those follow-ups to replace failed Git cleanup.

GitHub PR operations remain owned by `pr` and `github`.
