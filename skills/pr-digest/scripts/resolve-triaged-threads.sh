#!/usr/bin/env bash
# Resolve non-outdated review threads after agent triage marks them stale,
# invalid, or addressed.
#
# Safety: this script does not classify threads. It only executes explicit
# evidence-backed triage candidates produced during pr-digest. GitHub-marked
# outdated threads stay in resolve-outdated-threads.sh so accidental broad
# cleanup cannot hide current reviewer feedback.
#
# Usage:
#   resolve-triaged-threads.sh <review-threads.json> <triage-candidates.json> [--confirm]
#
# triage-candidates.json schema:
#   [
#     {"id":"<thread-id>", "status":"STALE", "evidence":"current head no longer contains ..."},
#     {"id":"<thread-id>", "status":"INVALID", "evidence":"request contradicts ..."},
#     {"id":"<thread-id>", "status":"ADDRESSED", "evidence":"fixed in commit ... and validated by ..."}
#   ]
#
# Output (JSON on stdout): array of {id, path, line, status, evidence} where
# status is <STALE|INVALID|ADDRESSED>_RESOLVED or
# <STALE|INVALID|ADDRESSED>_UNRESOLVED.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source-path=SCRIPTDIR source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

require_gh
require_jq

[ "$#" -ge 2 ] || die "usage: resolve-triaged-threads.sh <review-threads.json> <triage-candidates.json> [--confirm]"
threads_file="$1"
triage_file="$2"
shift 2 || true
confirm=no
for arg in "$@"; do
	case "$arg" in
	--confirm) confirm=yes ;;
	*) die "unknown argument: $arg" ;;
	esac
done

[ -f "$threads_file" ] || die "review threads file not found: $threads_file"
[ -f "$triage_file" ] || die "triage candidates file not found: $triage_file"

jq -e 'type == "array"' "$threads_file" >/dev/null || die "review threads file must contain a JSON array"
jq -e 'type == "array"' "$triage_file" >/dev/null || die "triage candidates file must contain a JSON array"

invalid_candidates=$(jq '[.[] | select(
	(.id | type != "string") or
	((.status // "") | IN("STALE", "INVALID", "ADDRESSED") | not) or
	((.evidence // "") | type != "string") or
	((.evidence // "") | length == 0)
)] | length' "$triage_file")
[ "$invalid_candidates" -eq 0 ] || die "triage candidates require string id, status STALE|INVALID|ADDRESSED, and non-empty evidence"

candidate_count=$(jq 'length' "$triage_file")
if [ "$candidate_count" -eq 0 ]; then
	printf '[]\n'
	printf 'no stale/invalid/addressed triaged threads to resolve\n' >&2
	exit 0
fi

candidates=$(jq -c --slurpfile threads "$threads_file" '
	[.[] as $candidate
		| ($threads[0][] | select(.id == $candidate.id)) as $thread
		| select($thread.isResolved == false and $thread.isOutdated == false)
		| {
			id: $candidate.id,
			kind: $candidate.status,
			path: ($thread.path // $candidate.path),
			line: ($thread.line // $thread.originalLine // $candidate.line),
			originalLine: ($thread.originalLine // null),
			evidence: $candidate.evidence
		}]
' "$triage_file")

resolved_candidate_count=$(printf '%s' "$candidates" | jq 'length')
[ "$resolved_candidate_count" -eq "$candidate_count" ] || die "all triage ids must exist, be unresolved, and not be GitHub-marked outdated"

if [ "$confirm" != "yes" ]; then
	printf 'About to resolve %s stale/invalid/addressed thread(s):\n' "$candidate_count" >&2
	printf '%s' "$candidates" | jq -r '.[] | "  \(.id)  \(.kind)  \(.path):\(.line // .originalLine)  \(.evidence)"' >&2
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

tmp_candidates=$(mktemp "${TMPDIR:-/tmp}/pr-digest-triaged.XXXXXX") || die "mktemp failed"
trap 'rm -f "$tmp_candidates"' EXIT
printf '%s' "$candidates" | jq -c '.[]' >"$tmp_candidates"

results="[]"
while IFS= read -r candidate; do
	id=$(printf '%s' "$candidate" | jq -r '.id')
	kind=$(printf '%s' "$candidate" | jq -r '.kind')
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
		status="${kind}_RESOLVED"
	else
		status="${kind}_UNRESOLVED"
	fi
	results=$(jq -c --arg status "$status" --argjson item "$candidate" \
		'. + [($item | del(.kind) + {status: $status})]' <<<"$results")
done <"$tmp_candidates"

printf '%s\n' "$results"
resolved=$(printf '%s' "$results" | jq '[.[] | select(.status | endswith("_RESOLVED"))] | length')
unresolved=$(printf '%s' "$results" | jq '[.[] | select(.status | endswith("_UNRESOLVED"))] | length')
printf 'stale/invalid/addressed threads resolved: %s; failed: %s\n' "$resolved" "$unresolved" >&2
