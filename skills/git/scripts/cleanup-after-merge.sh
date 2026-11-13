#!/usr/bin/env bash
set -u

readonly DEFAULT_REMOTE=origin

usage() {
	printf 'Usage: cleanup-after-merge.sh <merged-branch> <default-branch> <expected-head> [remote]\n' >&2
	exit 2
}

die() {
	printf 'cleanup-after-merge: error: %s\n' "$*" >&2
	exit 1
}

valid_branch() {
	[[ -n $1 && $1 != -* ]] && git check-ref-format --branch "$1" >/dev/null 2>&1
}

valid_oid() {
	[[ $1 =~ ^[0-9a-fA-F]{40}$ || $1 =~ ^[0-9a-fA-F]{64}$ ]]
}

report() {
	printf 'cleanup-after-merge: %-14s %s\n' "$1" "$2"
}

capture() {
	local output
	if output=$("${@:2}" 2>&1); then
		report "$1" "ok${output:+: $output}"
		return 0
	fi
	report "$1" "failed${output:+: $output}"
	return 1
}

report_discarded_entries() {
	local entries entry
	if ! entries=$(git -C "$1" status --short --ignored --untracked-files=normal 2>&1); then
		report 'discarded files' "check failed${entries:+: $entries}"
		return 1
	fi
	if [[ -z $entries ]]; then
		report 'discarded files' 'none'
		return 0
	fi
	report 'discarded files' 'removing:'
	while IFS= read -r entry; do
		printf 'cleanup-after-merge:   %s\n' "$entry"
	done <<<"$entries"
}

incomplete() {
	report 'result' 'incomplete'
	exit 1
}

# Reads the merged branch tip from the remote into remote_oid/remote_output.
# Returns ls-remote's own status: 0 present, 2 absent, anything else unreadable.
read_remote_oid() {
	local worktree=$1 status=0
	remote_oid=
	remote_output=$(git -C "$worktree" ls-remote --exit-code --heads "$remote" "refs/heads/$merged_branch" 2>&1) || status=$?
	if [[ $status -eq 0 ]]; then
		read -r remote_oid _ <<<"$remote_output"
	fi
	return $status
}

# Absence is the goal of the remote step, so every absence path is a success.
# Each of them leaves the tracking ref behind, and dropping it keeps those paths
# identical to an accepted delete.
forget_remote_branch() {
	git -C "$default_worktree" update-ref -d "refs/remotes/$remote/$merged_branch" >/dev/null 2>&1 || :
}

report_remote_absent() {
	forget_remote_branch
	report 'remote branch' "${1:-absent: deleted remotely during cleanup}"
}

report_remote_moved() {
	report 'remote branch' "failed: moved during cleanup: expected $expected_oid, found $remote_oid"
}

# Deletes the remote branch only while it still holds the confirmed PR head.
# Hosts delete merged head branches asynchronously and Git reports that rejection
# with the same '(stale info)' it uses for a branch that moved, so absence is
# proven by reading the ref, never by assuming a host setting or a delay.
finish_remote_branch() {
	local status=0 output push_status=0
	read_remote_oid "$default_worktree" || status=$?
	if [[ $status -eq 2 ]]; then
		report_remote_absent
		return 0
	fi
	if [[ $status -ne 0 ]]; then
		report 'remote branch' "check failed${remote_output:+: $remote_output}"
		return 1
	fi
	if [[ $remote_oid != "$expected_oid" ]]; then
		report_remote_moved
		return 1
	fi
	output=$(git -C "$default_worktree" push --force-with-lease="refs/heads/$merged_branch:$expected_oid" "$remote" ":refs/heads/$merged_branch" 2>&1) || push_status=$?
	if [[ $push_status -eq 0 ]]; then
		report 'remote branch' "ok${output:+: $output}"
		return 0
	fi
	status=0
	read_remote_oid "$default_worktree" || status=$?
	if [[ $status -eq 2 ]]; then
		report_remote_absent
		return 0
	fi
	if [[ $status -eq 0 ]]; then
		report_remote_moved
		return 1
	fi
	report 'remote branch' "failed${output:+: $output}; recheck failed${remote_output:+: $remote_output}"
	return 1
}

[[ $# -ge 3 && $# -le 4 ]] || usage
readonly merged_branch=$1 default_branch=$2 expected_head=$3 remote=${4:-$DEFAULT_REMOTE}
valid_branch "$merged_branch" || die "invalid merged branch: $merged_branch"
valid_branch "$default_branch" || die "invalid default branch: $default_branch"
[[ $merged_branch != "$default_branch" ]] || die 'merged and default branches must differ'
valid_oid "$expected_head" || die "expected head must be a full object ID: $expected_head"
git rev-parse --git-dir >/dev/null 2>&1 || die 'not inside a Git repository'
git remote get-url -- "$remote" >/dev/null 2>&1 || die "unknown remote: $remote"
expected_oid=$(git rev-parse --verify "$expected_head^{commit}" 2>/dev/null) || die "invalid expected head: $expected_head"
readonly expected_oid

worktree_data=$(git worktree list --porcelain) || die 'unable to list worktrees'
readonly worktree_data
primary_worktree=
default_worktree=
merged_worktree=
worktree_path=
while IFS=' ' read -r key value; do
	case $key in
	worktree)
		worktree_path=$value
		[[ -n $primary_worktree ]] || primary_worktree=$value
		;;
	branch)
		branch=${value#refs/heads/}
		[[ $branch == "$default_branch" ]] && default_worktree=$worktree_path
		[[ $branch == "$merged_branch" ]] && merged_worktree=$worktree_path
		;;
	esac
done <<<"$worktree_data"
readonly primary_worktree
[[ -n $primary_worktree ]] || die 'unable to locate primary worktree'

if [[ -n $default_worktree && $merged_worktree == "$primary_worktree" ]]; then
	report 'worktree' 'failed: cannot remove the primary worktree while default branch uses another worktree'
	report 'local branch' 'skipped: worktree cleanup failed'
	report 'remote branch' 'skipped: worktree cleanup failed'
	incomplete
fi

default_checked_out=0
if [[ -n $default_worktree ]]; then
	default_checked_out=1
else
	default_worktree=$primary_worktree
fi
readonly default_worktree

# Branch identity and remote lease checks are preflight. They must complete
# before any checkout, worktree, or branch mutation.
local_oid=
if git -C "$primary_worktree" show-ref --verify --quiet "refs/heads/$merged_branch"; then
	local_oid=$(git -C "$primary_worktree" rev-parse --verify "refs/heads/$merged_branch^{commit}")
	if [[ $local_oid != "$expected_oid" ]]; then
		report 'worktree' 'skipped: local branch moved after merge'
		report 'local branch' "failed: expected $expected_oid, found $local_oid"
		report 'remote branch' 'skipped: local branch moved after merge'
		incomplete
	fi
fi

remote_oid=
remote_output=
remote_status=0
read_remote_oid "$primary_worktree" || remote_status=$?
if [[ $remote_status -eq 0 ]]; then
	if [[ $remote_oid != "$expected_oid" ]]; then
		report 'worktree' 'skipped: remote branch moved after merge'
		report 'local branch' 'skipped: remote branch moved after merge'
		report 'remote branch' "failed: expected $expected_oid, found $remote_oid"
		incomplete
	fi
elif [[ $remote_status -ne 2 ]]; then
	report 'worktree' 'skipped: remote branch check failed'
	report 'local branch' 'skipped: remote branch check failed'
	report 'remote branch' "check failed${remote_output:+: $remote_output}"
	incomplete
fi

# A primary worktree cannot be removed. After identity checks, inventory and
# discard its local contents, detach it, then reuse it for the default branch
# after merged refs are deleted.
reused_primary=0
if [[ $merged_worktree == "$primary_worktree" ]]; then
	if ! report_discarded_entries "$primary_worktree"; then
		report 'worktree' 'skipped: local-file inventory failed'
		report 'local branch' 'skipped: worktree cleanup failed'
		report 'remote branch' 'skipped: worktree cleanup failed'
		incomplete
	fi
	if ! capture 'branch detach' git -C "$primary_worktree" switch --detach --discard-changes "$expected_oid"; then
		report 'worktree' 'skipped: merged branch still checked out'
		report 'local branch' 'skipped: merged branch still checked out'
		report 'remote branch' 'skipped: merged branch still checked out'
		incomplete
	fi
	if ! capture 'worktree clean' git -C "$primary_worktree" clean -ffdx; then
		report 'worktree' 'skipped: local-file cleanup failed'
		report 'local branch' 'skipped: worktree cleanup failed'
		report 'remote branch' 'skipped: worktree cleanup failed'
		incomplete
	fi
	merged_worktree=
	reused_primary=1
fi

cd -- "$default_worktree" || die "cannot enter default worktree: $default_worktree"

if [[ $reused_primary -eq 1 ]]; then
	report 'worktree' "reused for default update: $default_worktree"
elif [[ -n $merged_worktree ]]; then
	if ! report_discarded_entries "$merged_worktree"; then
		report 'worktree' 'skipped: local-file inventory failed'
		report 'local branch' 'skipped: worktree cleanup failed'
		report 'remote branch' 'skipped: worktree cleanup failed'
		incomplete
	fi
	if ! capture 'worktree' git -C "$default_worktree" worktree remove --force -- "$merged_worktree"; then
		report 'local branch' 'skipped: worktree cleanup failed'
		report 'remote branch' 'skipped: worktree cleanup failed'
		incomplete
	fi
	if ! capture 'worktree prune' git -C "$default_worktree" worktree prune; then
		report 'local branch' 'skipped: worktree prune failed'
		report 'remote branch' 'skipped: worktree prune failed'
		incomplete
	fi
else
	report 'worktree' 'absent'
fi

if git -C "$default_worktree" show-ref --verify --quiet "refs/heads/$merged_branch"; then
	local_oid=$(git -C "$default_worktree" rev-parse --verify "refs/heads/$merged_branch^{commit}")
	if [[ $local_oid != "$expected_oid" ]]; then
		report 'local branch' "failed: expected $expected_oid, found $local_oid"
		report 'remote branch' 'skipped: local branch moved during cleanup'
		incomplete
	fi
	if ! capture 'local branch' git -C "$default_worktree" branch -D -- "$merged_branch"; then
		report 'remote branch' 'skipped: local branch cleanup failed'
		incomplete
	fi
else
	report 'local branch' 'absent'
fi

if [[ $remote_status -ne 0 ]]; then
	report_remote_absent 'absent'
elif ! finish_remote_branch; then
	incomplete
fi

if [[ $default_checked_out -eq 1 ]]; then
	report 'default switch' "already checked out: $default_worktree"
elif ! capture 'default switch' git -C "$default_worktree" switch -- "$default_branch"; then
	report 'default pull' 'skipped: default branch unavailable'
	incomplete
fi

if ! capture 'default pull' git -C "$default_worktree" pull --ff-only "$remote" "$default_branch"; then
	incomplete
fi

report 'result' 'complete'
