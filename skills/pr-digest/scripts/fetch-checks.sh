#!/usr/bin/env bash
# Fetch PR-attached checks via `gh pr checks` into $WORKDIR/checks.json.
# `gh pr checks` is the source of truth for PR-attached checks (not raw
# Actions runs), per the digest guardrails. A failure marker is written
# separately so the digest can mark read coverage as partial without
# crashing the whole fetch.
#
# Usage:
#   fetch-checks.sh <workdir> <pr-ref>
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source-path=SCRIPTDIR source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

require_gh
require_jq

[ "$#" -eq 2 ] || die "usage: fetch-checks.sh <workdir> <pr-ref>"
workdir="$1"
pr_ref="$2"
ensure_workdir "$workdir"

# Capture stderr so the digest can report *why* checks were unread. The
# checks.failed sentinel drives the UNKNOWN check-state classification.
if gh pr checks "$pr_ref" \
	--json name,bucket,state,workflow,link,description,startedAt,completedAt \
	>"$workdir/checks.json" 2>"$workdir/checks.stderr"; then
	rm -f "$workdir/checks.stderr"
else
	printf '%s\n' "gh pr checks failed" >"$workdir/checks.failed"
	# Nonzero status can still accompany useful pending-check JSON. Replace only
	# empty or malformed output so processing can report the sentinel as UNKNOWN.
	if ! jq -s -e 'length == 1 and (.[0] | type == "array")' "$workdir/checks.json" >/dev/null 2>&1; then
		printf '[]\n' >"$workdir/checks.json"
	fi
	# Keep checks.stderr for the digest's UNKNOWN note.
fi

# Restrict even on failure so partial artifacts stay private.
chmod 600 "$workdir/checks.json" 2>/dev/null || true
[ -f "$workdir/checks.failed" ] && chmod 600 "$workdir/checks.failed"
[ -f "$workdir/checks.stderr" ] && chmod 600 "$workdir/checks.stderr"
printf '%s\n' "$workdir/checks.json"
