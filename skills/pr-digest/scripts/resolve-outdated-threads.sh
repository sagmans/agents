#!/usr/bin/env bash
# Resolve GitHub-marked outdated, unresolved review threads and report results.
# Reads the merged review-threads.json produced by fetch-review-threads.sh.
#
# Safety: ONLY threads where isResolved=false AND isOutdated=true are touched.
# Valid, ambiguous, or already-resolved threads are left alone. Each
# resolution attempt is reported so the digest can distinguish
# OUTDATED_RESOLVED from OUTDATED_UNRESOLVED.
#
# Usage:
#   resolve-outdated-threads.sh <review-threads.json>
#
# Output (JSON on stdout): array of {id, path, line, status} where status is
# OUTDATED_RESOLVED or OUTDATED_UNRESOLVED.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source-path=SCRIPTDIR source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

require_gh
require_jq

[ "$#" -ge 1 ] || die "usage: resolve-outdated-threads.sh <review-threads.json> [--confirm]"
threads_file="$1"
shift || true
confirm=no
for arg in "$@"; do
	case "$arg" in
	--confirm) confirm=yes ;;
	*) die "unknown argument: $arg" ;;
	esac
done

[ -f "$threads_file" ] || die "review threads file not found: $threads_file"

# Select candidate threads: unresolved + GitHub-marked outdated. Anything
# else is intentionally excluded from mutation.
candidates=$(jq -c '[.[] | select(.isResolved == false and .isOutdated == true)
	| {id, path, line, originalLine}]' "$threads_file")
count=$(printf '%s' "$candidates" | jq 'length')

if [ "$count" -eq 0 ]; then
	printf '[]\n'
	printf 'no outdated unresolved threads to resolve\n' >&2
	exit 0
fi

# Give the caller a chance to abort remote mutations when policy requires it.
# --confirm skips the prompt for non-interactive orchestrator runs.
if [ "$confirm" != "yes" ]; then
	printf 'About to resolve %s outdated unresolved thread(s):\n' "$count" >&2
	printf '%s' "$candidates" | jq -r '.[] | "  \(.id)  \(.path):\(.line // .originalLine)"' >&2
	printf 'Proceed? [y/N] ' >&2
	read -r answer
	case "$answer" in
	y | Y | yes | YES) ;;
	*)
		printf 'aborted; no threads resolved\n' >&2
		printf '[]\n'
		exit 0
		;;
	esac
fi

tmp_candidates=$(mktemp "${TMPDIR:-/tmp}/pr-digest-candidates.XXXXXX") || die "mktemp failed"
trap 'rm -f "$tmp_candidates"' EXIT
printf '%s' "$candidates" | jq -c '.[]' >"$tmp_candidates"

results="[]"
while IFS= read -r candidate; do
	id=$(printf '%s' "$candidate" | jq -r '.id')
	# Mutation resolves the whole thread. GitHub GraphQL can return HTTP 200
	# with an errors array, so verify the response body before reporting success.
	# shellcheck disable=SC2016
	if response=$(gh api graphql -f thread="$id" -f query='mutation($thread: ID!) {
		resolveReviewThread(input: {threadId: $thread}) {
			thread { id isResolved }
		}
	}' 2>/dev/null) && printf '%s' "$response" | jq -e '
		(.errors | not) and (.data.resolveReviewThread.thread.isResolved == true)
	' >/dev/null; then
		status="OUTDATED_RESOLVED"
	else
		status="OUTDATED_UNRESOLVED"
	fi
	results=$(jq -c --arg status "$status" --argjson item "$candidate" \
		'. + [$item + {status: $status}]' <<<"$results")
done <"$tmp_candidates"

printf '%s\n' "$results"
resolved=$(printf '%s' "$results" | jq '[.[] | select(.status == "OUTDATED_RESOLVED")] | length')
unresolved=$(printf '%s' "$results" | jq '[.[] | select(.status == "OUTDATED_UNRESOLVED")] | length')
printf 'outdated threads resolved: %s; failed: %s\n' "$resolved" "$unresolved" >&2
