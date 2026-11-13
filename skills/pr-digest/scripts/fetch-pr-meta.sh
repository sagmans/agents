#!/usr/bin/env bash
# Fetch PR metadata via `gh pr view` into $WORKDIR/pr.json.
# Covers title, body, author, state, draft, refs, mergeability, review
# decision, commits, files, additions/deletions, and timestamps — everything
# the digest needs to compare PR prose against actual development.
#
# Usage:
#   fetch-pr-meta.sh <workdir> <pr-ref>
#   pr-ref: PR number or URL (accepted by `gh pr view`)
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source-path=SCRIPTDIR source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

require_gh
require_jq

[ "$#" -eq 2 ] || die "usage: fetch-pr-meta.sh <workdir> <pr-ref>"
workdir="$1"
pr_ref="$2"
ensure_workdir "$workdir"

# Field set mirrors the digest's scope so a re-run never silently drops a
# dimension the report promises to cover.
gh pr view "$pr_ref" \
	--json number,url,title,body,author,state,isDraft,baseRefName,headRefName,mergeable,reviewDecision,commits,files,additions,deletions,changedFiles,createdAt,updatedAt \
	>"$workdir/pr.json"

chmod 600 "$workdir/pr.json"
printf '%s\n' "$workdir/pr.json"
