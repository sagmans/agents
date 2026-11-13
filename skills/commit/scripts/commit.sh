#!/usr/bin/env bash
set -euo pipefail

readonly FALLBACK_DEFAULT_BRANCH_PATTERN='^(main|master|trunk)$'
# Owned non-fork repositories may commit trunk-based on the default branch when
# owners are configured via GIT_TRUNK_OWNERS or `git config --get-all agents.trunkOwners`.
# Note: this local check only verifies origin ownership, not whether origin is a fork.
readonly OWNER_TOKEN_PATTERN='^[A-Za-z0-9._-]+$'
readonly ORIGIN_PREFIX_PATTERN='^(git@github\.com:|ssh://git@github\.com/|https://github\.com/)([^/]+)/[^/]+$'
readonly CONVENTIONAL_MESSAGE_PATTERN='^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\([^)]+\))?!?: .+'
readonly ESCAPED_NEWLINE_SEQUENCE='\n'
readonly ESCAPED_NEWLINE_ERROR='error: commit message contains literal \n; use actual newlines'
readonly EMPTY_BODY_ERROR='error: commit body must not be empty'
readonly MULTILINE_SUBJECT_ERROR='error: commit subject must be a single line'
readonly BODY_CARRIAGE_RETURN_ERROR='error: commit body contains carriage returns'

usage() {
	echo 'Usage: commit.sh "type(scope): message" --body "why this change exists" -- <path>...' >&2
	exit 2
}

[[ $# -ge 5 && $2 == --body && $4 == -- ]] || usage
message=$1
body=$3
readonly message body
shift 4

# Separate paragraphs keep repository message hooks effective without shell escapes.
[[ $body =~ [^[:space:]] ]] || {
	echo "$EMPTY_BODY_ERROR" >&2
	exit 2
}
[[ $message != *$'\n'* && $message != *$'\r'* ]] || {
	echo "$MULTILINE_SUBJECT_ERROR" >&2
	exit 2
}
[[ $body != *$'\r'* ]] || {
	echo "$BODY_CARRIAGE_RETURN_ERROR" >&2
	exit 2
}
paths=("$@")
readonly paths

[[ $message != *"$ESCAPED_NEWLINE_SEQUENCE"* && $body != *"$ESCAPED_NEWLINE_SEQUENCE"* ]] || {
	echo "$ESCAPED_NEWLINE_ERROR" >&2
	exit 2
}

[[ $message =~ $CONVENTIONAL_MESSAGE_PATTERN ]] || {
	echo 'error: message must use Conventional Commits format' >&2
	exit 2
}

branch=$(git branch --show-current)
readonly branch
[[ -n $branch ]] || {
	echo 'error: detached HEAD' >&2
	exit 1
}

# External repositories keep the branch-and-PR flow, so the default-branch
# guard fails closed unless origin matches a configured trunk owner.
origin_url=$(git remote get-url origin 2>/dev/null || true)
readonly origin_url

is_owned_origin() {
	local url="$1" raw_owners origin_owner owner lower_owner
	local -a owner_list=()
	[[ $url =~ $ORIGIN_PREFIX_PATTERN ]] || return 1
	origin_owner=$(printf '%s' "${BASH_REMATCH[2]}" | tr '[:upper:]' '[:lower:]')
	if [[ ${GIT_TRUNK_OWNERS+set} == set ]]; then
		raw_owners=$GIT_TRUNK_OWNERS
	else
		raw_owners=$(git config --get-all agents.trunkOwners 2>/dev/null || true)
	fi
	raw_owners=${raw_owners//,/ }
	raw_owners=${raw_owners//$'\n'/ }
	read -r -a owner_list <<<"$raw_owners"
	for owner in "${owner_list[@]}"; do
		[[ $owner == "." || $owner == ".." ]] && continue
		[[ $owner =~ $OWNER_TOKEN_PATTERN ]] || continue
		lower_owner=$(printf '%s' "$owner" | tr '[:upper:]' '[:lower:]')
		if [[ $origin_owner == "$lower_owner" ]]; then
			return 0
		fi
	done
	return 1
}

owned_repository=false
is_owned_origin "$origin_url" && owned_repository=true
readonly owned_repository

default_ref=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)
readonly default_ref
default_branch=${default_ref#origin/}
readonly default_branch
if [[ $owned_repository != true ]]; then
	if [[ -n $default_ref ]]; then
		[[ $branch != "$default_branch" ]] || {
			echo "error: refusing to commit on default branch: $branch" >&2
			exit 1
		}
	elif [[ $branch =~ $FALLBACK_DEFAULT_BRANCH_PATTERN ]]; then
		echo "error: refusing to commit on default branch: $branch" >&2
		exit 1
	fi
fi

git diff --cached --quiet || {
	echo 'error: index already contains staged changes' >&2
	exit 1
}

cleanup_needed=true
cleanup() {
	local status=$?
	if [[ $cleanup_needed == true ]]; then
		git reset --quiet -- "${paths[@]}" || echo 'error: failed to restore index after commit failure' >&2
	fi
	exit "$status"
}
trap cleanup EXIT

git add -- "${paths[@]}"
git diff --cached --quiet && {
	echo 'error: selected paths contain no changes' >&2
	exit 1
}

git commit -s -S -m "$message" -m "$body"
cleanup_needed=false
