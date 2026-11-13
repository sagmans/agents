#!/usr/bin/env bash
# Fetch standalone PR comments into the workdir:
#   - issue-comments.json : top-level issue comments
#   - reviews.json        : review summaries (approve/request-changes/comment)
#   - review-comments.json: inline review comments (REST view)
# The GraphQL review-threads fetch (fetch-review-threads.sh) is separate
# because REST review comments do not expose thread resolution state.
# `--paginate --slurp` returns an array of pages; flatten to one array so
# downstream triage does not need to know pagination happened.
#
# Usage:
#   fetch-comments.sh <workdir> <owner> <repo> <number>
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source-path=SCRIPTDIR source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

require_gh
require_jq

[ "$#" -eq 4 ] || die "usage: fetch-comments.sh <workdir> <owner> <repo> <number>"
workdir="$1"
owner="$2"
repo="$3"
number="$4"
ensure_workdir "$workdir"

# Issue comments live under the issues API (PRs are issues in GitHub's model).
gh api "repos/${owner}/${repo}/issues/${number}/comments" --paginate --slurp |
	jq '[.[][]]' >"$workdir/issue-comments.json"

# Reviews are top-level review submissions; their inline comments come later.
gh api "repos/${owner}/${repo}/pulls/${number}/reviews" --paginate --slurp |
	jq '[.[][]]' >"$workdir/reviews.json"

# REST review comments are fetched for dedup against GraphQL threads; the
# thread fetch is authoritative for resolution state.
gh api "repos/${owner}/${repo}/pulls/${number}/comments" --paginate --slurp |
	jq '[.[][]]' >"$workdir/review-comments.json"

chmod 600 "$workdir/issue-comments.json" "$workdir/reviews.json" "$workdir/review-comments.json"
printf '%s\n' "$workdir/issue-comments.json" "$workdir/reviews.json" "$workdir/review-comments.json"
