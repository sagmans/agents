#!/usr/bin/env bash
# Run the complete deterministic pr-digest pipeline.
#
# This is the single entry point agents should run first. It calls the dedicated
# isolated scripts in order, resolves mechanical thread cleanup, then produces
# structured processed artifacts that make the final report a judgment task
# instead of a parsing/scripting task.
#
# Usage:
#   ./pr-digest.sh [<pr-url|number>] [--resolve-outdated] [--keep-workdir]
#   ./pr-digest.sh [<pr-url|number>] --triage-candidates <file> [--keep-workdir]
#
# Output: JSON object containing workdir and processed artifact paths.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source-path=SCRIPTDIR source=scripts/lib/common.sh
. "$SCRIPT_DIR/scripts/lib/common.sh"

require_gh
require_jq
require_python3

input=""
keep_workdir="no"
resolve_outdated="no"
triage_candidates=""

while [ "$#" -gt 0 ]; do
	case "$1" in
	--keep-workdir)
		keep_workdir="yes"
		shift
		;;
	--triage-candidates)
		[ "$#" -ge 2 ] || die "--triage-candidates requires a JSON file path"
		triage_candidates="$2"
		shift 2
		;;
	--resolve-outdated)
		resolve_outdated="yes"
		shift
		;;
	--help | -h)
		cat <<'EOF'
Usage:
  ./pr-digest.sh [<pr-url|number>] [--resolve-outdated] [--keep-workdir]
  ./pr-digest.sh [<pr-url|number>] --triage-candidates <file> [--keep-workdir]

Runs the full PR digest pipeline:
  1. resolve PR coordinates (a bare number is pinned to the current checkout)
  2. fetch metadata, comments, diff, checks, review threads
  3. resolve GitHub-marked outdated unresolved threads (only with --resolve-outdated)
  4. optionally resolve evidence-backed stale/invalid/addressed threads from a triage file
  5. re-fetch review threads after cleanup
  6. process all artifacts into structured JSON and markdown files

Prints a JSON object with output paths. The workdir survives on failure so the
fetched artifacts stay diagnosable, and is removed on success unless
--keep-workdir was passed.
EOF
		exit 0
		;;
	*)
		if [ -n "$input" ]; then
			die "only one PR input is accepted"
		fi
		input="$1"
		shift
		;;
	esac
done

umask 077
workdir=$(mkworkdir)

# Artifact retention is decided here rather than by the caller: a failed run is
# exactly when the fetched diff, comments, and stderr are needed, while a
# successful run should leave nothing in TMPDIR.
cleanup_workdir_on_exit() {
	status=$?
	if [ "$keep_workdir" = "yes" ] || [ "$status" -ne 0 ]; then
		[ "$status" -eq 0 ] || printf 'pr-digest: pipeline failed (exit %s)\n' "$status" >&2
		printf 'pr-digest: kept workdir %s\n' "$workdir" >&2
	else
		bash "$SCRIPT_DIR/scripts/cleanup-workdir.sh" "$workdir" >&2 ||
			printf 'pr-digest: cleanup failed; remove %s with scripts/cleanup-workdir.sh\n' "$workdir" >&2
	fi
}
trap cleanup_workdir_on_exit EXIT

if [ -n "$input" ]; then
	coords=$(bash "$SCRIPT_DIR/scripts/resolve-pr.sh" "$input")
else
	coords=$(bash "$SCRIPT_DIR/scripts/resolve-pr.sh")
fi
printf '%s' "$coords" >"$workdir/coords.json"
chmod 600 "$workdir/coords.json"

number=$(printf '%s' "$coords" | jq -r '.number')
owner=$(printf '%s' "$coords" | jq -r '.owner')
repo=$(printf '%s' "$coords" | jq -r '.repo')
url=$(printf '%s' "$coords" | jq -r '.url')

# Echo the resolved identity: a wrong repository must be visible before the
# digest is read, not discovered afterwards.
printf 'pr-digest: digesting %s (%s/%s#%s)\n' "$url" "$owner" "$repo" "$number" >&2

manifest="$workdir/manifest.txt"
{
	printf 'workdir: %s\n' "$workdir"
	printf 'pr: %s\n' "$url"
	printf 'coords: %s/%s#%s\n' "$owner" "$repo" "$number"
	printf 'keep_workdir: %s\n' "$keep_workdir"
	printf 'fetched:\n'
} >"$manifest"
chmod 600 "$manifest"

run_and_manifest() {
	local script="$1"
	shift
	local out
	out=$(bash "$SCRIPT_DIR/scripts/$script" "$workdir" "$@") ||
		die "$script failed; its partial artifacts are in $workdir"
	printf '%s\n' "$out" | sed 's/^/  /' >>"$manifest"
}

# Dedicated fetch scripts. Keep each concern isolated and reusable.
run_and_manifest fetch-pr-meta.sh "$url"
run_and_manifest fetch-comments.sh "$owner" "$repo" "$number"
run_and_manifest fetch-diff.sh "$url"
run_and_manifest fetch-checks.sh "$url"
run_and_manifest fetch-review-threads.sh "$owner" "$repo" "$number"

# Dedicated resolver scripts. Outdated cleanup is deterministic from GitHub's
# isOutdated flag but still mutates the remote PR, so it stays behind an explicit
# flag: a plain digest must never change the repository it read.
# Stale/invalid/addressed cleanup requires an explicit evidence file.
outdated_results="$workdir/outdated-resolutions.json"
if [ "$resolve_outdated" = "yes" ]; then
	bash "$SCRIPT_DIR/scripts/resolve-outdated-threads.sh" "$workdir/review-threads.json" --confirm >"$outdated_results"
else
	printf '[]\n' >"$outdated_results"
	printf 'pr-digest: outdated threads left untouched; pass --resolve-outdated to resolve them\n' >&2
fi
chmod 600 "$outdated_results"
printf '  %s\n' "$outdated_results" >>"$manifest"

triage_results="$workdir/triaged-resolutions.json"
if [ -n "$triage_candidates" ]; then
	[ -f "$triage_candidates" ] || die "triage candidates file not found: $triage_candidates"
	bash "$SCRIPT_DIR/scripts/resolve-triaged-threads.sh" "$workdir/review-threads.json" "$triage_candidates" --confirm >"$triage_results"
else
	printf '[]\n' >"$triage_results"
fi
chmod 600 "$triage_results"
printf '  %s\n' "$triage_results" >>"$manifest"

# Re-fetch after any remote cleanup so processed artifacts reflect current PR state.
run_and_manifest fetch-review-threads.sh "$owner" "$repo" "$number"

processed_json=$(python3 "$SCRIPT_DIR/scripts/process-artifacts.py" "$workdir")
processed_index="$workdir/processed/index.json"
printf '%s\n' "$processed_json" >"$processed_index"
chmod 600 "$processed_index"
printf '  %s\n' "$processed_index" >>"$manifest"

jq -n \
	--arg workdir "$workdir" \
	--arg pr "$url" \
	--arg owner "$owner" \
	--arg repo "$repo" \
	--argjson number "$number" \
	--arg keepWorkdir "$keep_workdir" \
	--slurpfile processed "$processed_index" \
	--slurpfile outdated "$outdated_results" \
	--slurpfile triaged "$triage_results" \
	'{
		workdir: $workdir,
		keepWorkdir: ($keepWorkdir == "yes"),
		pr: {owner: $owner, repo: $repo, number: $number, url: $pr},
		processed: $processed[0],
		resolutions: {
			outdated: $outdated[0],
			triaged: $triaged[0]
		}
	}'
