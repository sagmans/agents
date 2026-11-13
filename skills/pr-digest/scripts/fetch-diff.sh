#!/usr/bin/env bash
# Fetch the PR diff as a patch into $WORKDIR/diff.patch.
# A patch (not --name-only) preserves line context so the digest can inspect
# surrounding hunks when triaging review threads at a path/line.
#
# Usage:
#   fetch-diff.sh <workdir> <pr-ref>
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source-path=SCRIPTDIR source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

require_gh

[ "$#" -eq 2 ] || die "usage: fetch-diff.sh <workdir> <pr-ref>"
workdir="$1"
pr_ref="$2"
ensure_workdir "$workdir"

# --patch gives raw unified diff. Empty diffs (no changes) are valid; do not
# treat them as failure, just write the (possibly empty) file.
gh pr diff "$pr_ref" --patch >"$workdir/diff.patch" 2>"$workdir/diff.stderr" || {
	# Surface diff fetch errors but still leave the file for partial coverage.
	printf 'gh pr diff failed: %s\n' "$(cat "$workdir/diff.stderr")" >&2
}
rm -f "$workdir/diff.stderr"
chmod 600 "$workdir/diff.patch"
printf '%s\n' "$workdir/diff.patch"
