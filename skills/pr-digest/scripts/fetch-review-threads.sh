#!/usr/bin/env bash
# Fetch all PR review threads via GraphQL and merge into a single
# $WORKDIR/review-threads.json.
#
# WHY GraphQL: REST review comments do not expose thread resolution state
# (isResolved/isOutdated), which the digest needs to triage and resolve
# outdated threads safely. Page through reviewThreads until hasNextPage is
# false; also surface per-thread comment pagination gaps.
#
# Usage:
#   fetch-review-threads.sh <workdir> <owner> <repo> <number>
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source-path=SCRIPTDIR source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

require_gh
require_jq

[ "$#" -eq 4 ] || die "usage: fetch-review-threads.sh <workdir> <owner> <repo> <number>"
workdir="$1"
owner="$2"
repo="$3"
number="$4"
ensure_workdir "$workdir"

# GraphQL query kept inline because it is the contract with GitHub's schema.
# $endCursor is optional; gh api graphql omits it on the first page.
# shellcheck disable=SC2016
query='query($owner: String!, $repo: String!, $pr: Int!, $endCursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100, after: $endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          originalLine
          diffSide
          comments(first: 100) {
            pageInfo { hasNextPage endCursor }
            nodes {
              id
              url
              body
              author { login }
              createdAt
              outdated
              path
              line
              originalLine
              diffHunk
            }
          }
        }
      }
    }
  }
}'

page=1
cursor=""
# Accumulate thread nodes across pages; the merged array is the stable
# artifact the digest triages, regardless of how many pages GitHub returned.
jq -n '[]' >"$workdir/review-threads.json.tmpl"
pagination_gaps="$workdir/thread-pagination-gaps.txt"
: >"$pagination_gaps"

while :; do
	if [ "$page" -eq 1 ]; then
		raw=$(gh api graphql -f owner="$owner" -f repo="$repo" -F pr="$number" -f query="$query")
	else
		raw=$(gh api graphql -f owner="$owner" -f repo="$repo" -F pr="$number" -f endCursor="$cursor" -f query="$query")
	fi

	# Extract this page's thread nodes and append to the merged array.
	printf '%s' "$raw" |
		jq -c '[.data.repository.pullRequest.reviewThreads.nodes[]]' \
			>"$workdir/page-$page.json"

	# Merge: append page nodes to running merged array.
	jq -s '.[0] + .[1]' "$workdir/review-threads.json.tmpl" "$workdir/page-$page.json" \
		>"$workdir/review-threads.json"
	mv "$workdir/review-threads.json" "$workdir/review-threads.json.tmpl"

	# Record per-thread comment pagination gaps so read coverage can be honest.
	if printf '%s' "$raw" | jq -e '
		.data.repository.pullRequest.reviewThreads.nodes[]
		| select(.comments.pageInfo.hasNextPage == true)
		| .id' >/dev/null 2>&1; then
		printf '%s' "$raw" |
			jq -r '.data.repository.pullRequest.reviewThreads.nodes[]
				| select(.comments.pageInfo.hasNextPage == true)
				| "thread \(.id) has more than 100 comments (unfetched)"' \
				>>"$pagination_gaps"
	fi

	# Advance or stop based on thread-level pagination.
	has_next=$(printf '%s' "$raw" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage')
	if [ "$has_next" != "true" ]; then
		break
	fi
	cursor=$(printf '%s' "$raw" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.endCursor')
	page=$((page + 1))
done

mv "$workdir/review-threads.json.tmpl" "$workdir/review-threads.json"
rm -f "$workdir"/page-*.json

# Always leave the gaps file even when empty, so the digest can check existence.
chmod 600 "$workdir/review-threads.json" "$pagination_gaps"
printf '%s\n' "$workdir/review-threads.json"
