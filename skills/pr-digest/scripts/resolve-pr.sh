#!/usr/bin/env bash
# Resolve PR coordinates (number, owner, repo, url, head/base refs) from:
#   1. an explicit GitHub PR URL or PR number argument, or
#   2. the active PR for the current branch (no argument).
# Emits one JSON object on stdout so downstream scripts and the orchestrator
# can consume a single source of truth for PR identity.
#
# Usage:
#   resolve-pr.sh                       # active PR for current branch
#   resolve-pr.sh <pr-url|pr-number>    # explicit PR
#
# Exit non-zero with guidance if gh is missing, auth fails, or no PR resolves.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source-path=SCRIPTDIR source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

require_gh
require_jq

input="${1:-}"

# Fetch the PR identity fields. --json keeps output machine-readable and
# avoids leaking unrelated repo state. When no input is given, build an
# empty argv so `gh pr view` resolves the active-branch PR rather than
# receiving a stray empty-string argument it would reject.
#
# A bare number is pinned with an explicit --repo because gh would otherwise
# resolve it against the caller's working directory and could digest a
# different repository's PR without any signal.
if [ -n "$input" ]; then
	case "$input" in
	-*)
		die "invalid PR reference: $input"
		;;
	*[!0-9]*)
		set -- "$input"
		;;
	*)
		repo_slug=$(current_repo_slug)
		printf 'pr-digest: PR %s resolves against the current checkout %s\n' "$input" "$repo_slug" >&2
		set -- "$input" --repo "$repo_slug"
		;;
	esac
else
	set --
fi
if ! raw=$(gh pr view "$@" --json number,url,headRefName,baseRefName); then
	if [ -n "$input" ]; then
		die "could not resolve PR from input: $input"
	else
		die "no active PR for current branch. Pass a PR URL or number."
	fi
fi

number=$(printf '%s' "$raw" | jq -r '.number')
url=$(printf '%s' "$raw" | jq -r '.url')
head=$(printf '%s' "$raw" | jq -r '.headRefName')
base=$(printf '%s' "$raw" | jq -r '.baseRefName')

# Derive owner/repo from the PR URL so REST/GraphQL endpoints can be built
# without a second gh call. URL is the canonical source from gh itself.
if ! coords=$(parse_pr_url "$url"); then
	die "unexpected PR URL format, cannot parse owner/repo: $url"
fi
read -r owner repo _ <<<"$coords"

jq -n \
	--arg number "$number" \
	--arg owner "$owner" \
	--arg repo "$repo" \
	--arg url "$url" \
	--arg head "$head" \
	--arg base "$base" \
	'{number: ($number|tonumber), owner: $owner, repo: $repo, url: $url,
	  headRefName: $head, baseRefName: $base}'
