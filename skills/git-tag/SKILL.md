---
name: git-tag
description: "Create signed annotated release tags and push them to trigger the tag release pipeline. Use when asked to tag, version, or release a repository."
---
# Git Tag

## Related skills

Load `git` first for repository inspection. Load `commit` and `pr` when changes still need to ship before the release. Do not reload a skill that already called this one.

## Workflow

1. Tag only a merged commit on the up-to-date default branch: `git fetch --tags origin` and confirm `HEAD` equals `origin/<default>`.
2. Choose the version with SemVer from existing tags (`git tag --list --sort=-v:refname | head`). Keep the existing prefix style (for example `v1.2.3`). Bump major for breaking changes, minor for features, patch for fixes since the last tag (`git log <last-tag>..HEAD --oneline`).
3. Write a short message: the version and a one-line purpose of the release.
4. Create the tag with the ultimate template exactly:

   ```bash
   git tag -s <tag> -m "<message>"
   ```

5. Verify the signature before pushing:

   ```bash
   git tag -v <tag>
   ```

6. Push only the tag. This triggers the tag release pipeline:

   ```bash
   git push origin <tag>
   ```

7. Report the tag, the tagged commit, and the release pipeline run.

`-s` creates a GPG-signed annotated tag. Never create lightweight (`git tag <tag>`) or unsigned annotated (`git tag -a`) tags, never use `git push --tags`, and never alter Git configuration or bypass hooks. Never add agent, provider, model, or harness attribution to the tag message. Never move, re-create, force-push, or delete a pushed tag without user approval. If signing or verification fails, stop and report to the user.
