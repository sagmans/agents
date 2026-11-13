#!/usr/bin/env bash
# Shared helpers for pr-digest scripts.
# WHY centralised: every fetch/resolve script needs gh+jq presence checks,
# private workdir creation, and GitHub PR URL parsing. Duplicating these
# invites drift and leaked permissions on temp dirs.
#
# Source from another script:
#   SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
#   # shellcheck source=skills/pr-digest/scripts/lib/common.sh
#   . "$SCRIPT_DIR/lib/common.sh"

# Print to stderr and exit non-zero. Keep messages actionable so agents
# can surface them directly to the user.
die() {
	printf 'pr-digest: %s\n' "$*" >&2
	exit 1
}

# Fail fast when the GitHub CLI is unavailable or unauthenticated; without it
# no PR data can be fetched, so partial progress would be misleading.
require_gh() {
	command -v gh >/dev/null 2>&1 || die "gh CLI not found. Install: https://cli.github.com/"
	gh auth status >/dev/null 2>&1 || die "gh not authenticated. Run: gh auth login"
}

# jq is used to normalise paginated --slurp output and merge GraphQL pages.
require_jq() {
	command -v jq >/dev/null 2>&1 || die "jq not found. Install via your package manager."
}

# The artifact normalizer uses PEP 604 unions, so an older interpreter fails at
# import time with a traceback instead of a setup error an agent can act on.
PYTHON_MIN_VERSION="3.10"

require_python3() {
	command -v python3 >/dev/null 2>&1 || die "python3 not found. Install Python ${PYTHON_MIN_VERSION} or newer; process-artifacts.py imports it."
	if ! python3 -c 'import sys; floor = tuple(int(part) for part in sys.argv[1].split(".")); raise SystemExit(0 if sys.version_info[:2] >= floor else 1)' "$PYTHON_MIN_VERSION"; then
		die "python3 $(python3 -V 2>&1 | awk '{print $2}') is older than ${PYTHON_MIN_VERSION}, which process-artifacts.py requires."
	fi
}

# Print the current directory's GitHub slug.
# WHY: a bare PR number is only meaningful inside one repository, and gh
# resolves a number against the caller's working directory. Pinning it with an
# explicit --repo keeps a digest from silently reading a different repository's
# pull request.
current_repo_slug() {
	local slug
	if ! slug=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null) || [ -z "$slug" ]; then
		die "cannot determine the current GitHub repository. Pass a full PR URL, or run from a checkout whose remote is on GitHub."
	fi
	printf '%s\n' "$slug"
}

# Create a private temp workdir for PR artifacts. Restrictive perms because
# PR diffs and comments may contain sensitive data. Prints the path.
mkworkdir() {
	local wd
	wd=$(mktemp -d "${TMPDIR:-/tmp}/pr-digest.XXXXXX") || die "mktemp -d failed"
	chmod 700 "$wd"
	printf '%s\n' "$wd"
}

# Validate that a workdir exists before writing into it. Tighten perms on
# purpose because every caller writes untrusted PR artifacts there.
ensure_workdir() {
	local wd="$1"
	[ -d "$wd" ] || die "workdir does not exist: $wd"
	chmod 700 "$wd"
}

# Parse a GitHub PR URL into "owner repo number" on stdout.
# Accepts github.com, GitHub Enterprise hosts, query/hash suffixes, and
# trailing paths like /files, /commits, /diff. Returns non-zero (no die)
# so callers can branch on non-URL inputs.
parse_pr_url() {
	local url path owner repo number
	url="$1"
	url="${url%%\?*}"
	url="${url%%#*}"
	# Match https://<host>/<owner>/<repo>/pull/<number>(/...)
	if printf '%s' "$url" | grep -Eq '^https?://[^/]+/[^/]+/[^/]+/pull/[0-9]+(/.*)?$'; then
		path=$(printf '%s' "$url" | sed -E 's|^https?://[^/]+/||')
		IFS=/ read -r owner repo _ number _ <<<"$path"
		printf '%s %s %s\n' "$owner" "$repo" "$number"
		return 0
	fi
	return 1
}
