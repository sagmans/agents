#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
readonly script_dir subject=$script_dir/cleanup-after-merge.sh
tmp=$(mktemp -d)
readonly tmp remote=$tmp/remote.git default_tree=$tmp/project feature_tree=$tmp/feature dirty_tree=$tmp/dirty raced_tree=$tmp/raced pull_fail_tree=$tmp/pull-fail updater=$tmp/updater race_tree=$tmp/race race_moved_tree=$tmp/race-moved race_late_tree=$tmp/race-late race_late_moved_tree=$tmp/race-late-moved stale_tree=$tmp/stale race_bin=$tmp/race-bin
trap 'rm -rf "$tmp"' EXIT

export GIT_AUTHOR_NAME='Cleanup Test'
export GIT_AUTHOR_EMAIL='cleanup@example.invalid'
export GIT_COMMITTER_NAME=$GIT_AUTHOR_NAME
export GIT_COMMITTER_EMAIL=$GIT_AUTHOR_EMAIL
# Host signing policies can require keys unavailable to disposable fixture repos.
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

fail() {
	printf 'test failed: %s\n' "$*" >&2
	exit 1
}

assert_contains() {
	grep -F "$2" "$1" >/dev/null || fail "missing '$2' in $1"
}

assert_before() {
	local first second
	first=$(grep -nF "$2" "$1" | cut -d: -f1)
	second=$(grep -nF "$3" "$1" | cut -d: -f1)
	[[ -n $first && -n $second && $first -lt $second ]] ||
		fail "expected '$2' before '$3' in $1"
}

assert_ref_absent() {
	if git -C "$default_tree" show-ref --verify --quiet "$1"; then
		fail "unexpected ref: $1"
	fi
}

assert_remote_absent() {
	if git -C "$default_tree" ls-remote --exit-code --heads origin "refs/heads/$1" >/dev/null 2>&1; then
		fail "unexpected remote branch: $1"
	fi
}

assert_remote_oid() {
	local actual
	actual=$(git -C "$default_tree" ls-remote --heads origin "refs/heads/$1" | awk '{print $1}')
	[[ $actual == "$2" ]] || fail "unexpected remote oid for $1: $actual"
}

run_cleanup() {
	local directory=$1 output=$2 branch=$3 expected=$4
	(
		cd -- "$directory"
		bash "$subject" "$branch" main "$expected" >"$output" 2>&1
	)
}

# Hosts delete or advance a merged head branch asynchronously, so the remote can
# change between any two of the script's reads. Only a git shim reproduces those
# windows deterministically: it lets the numbered ls-remote observation return
# first, then mutates the remote behind the script. RACE_TRIGGER selects which
# read races: 1 is preflight, 2 is the read before the delete push, so trigger 2
# is what makes the push itself get rejected.
mkdir -p "$race_bin"
race_real_git=$(command -v git)
cat >"$race_bin/git" <<'SHIM'
#!/usr/bin/env bash
if [[ $* == *ls-remote* ]]; then
  count=0
  [[ -e $RACE_STATE ]] && count=$(<"$RACE_STATE")
  count=$((count + 1))
  printf '%s\n' "$count" >"$RACE_STATE"
  output=$("$RACE_REAL_GIT" "$@" 2>&1)
  status=$?
  if [[ $count -eq $RACE_TRIGGER ]]; then
    case $RACE_ACTION in
      delete) "$RACE_REAL_GIT" --git-dir="$RACE_REMOTE" update-ref -d "refs/heads/$RACE_BRANCH" ;;
      advance) "$RACE_REAL_GIT" -C "$RACE_UPDATER" push --quiet origin "$RACE_BRANCH" ;;
    esac
  fi
  printf '%s\n' "$output"
  exit "$status"
fi
exec "$RACE_REAL_GIT" "$@"
SHIM
chmod +x "$race_bin/git"

run_race_cleanup() {
	local directory=$1 output=$2 branch=$3 expected=$4 action=$5 trigger=$6 race_updater=${7:-}
	(
		cd -- "$directory"
		RACE_STATE=$tmp/race-state-$action-$trigger RACE_ACTION=$action RACE_TRIGGER=$trigger \
			RACE_REMOTE=$remote RACE_BRANCH=$branch RACE_REAL_GIT=$race_real_git \
			RACE_UPDATER=$race_updater \
			PATH="$race_bin:$PATH" bash "$subject" "$branch" main "$expected" >"$output" 2>&1
	)
}

git init --quiet --bare "$remote"
git init --quiet --initial-branch=main "$default_tree"
git -C "$default_tree" remote add origin "$remote"
printf 'base\n' >"$default_tree/base.txt"
printf '.local-secret\n' >"$default_tree/.gitignore"
git -C "$default_tree" add base.txt .gitignore
git -C "$default_tree" commit --quiet -m 'initial'
git -C "$default_tree" push --quiet --set-upstream origin main
git --git-dir="$remote" symbolic-ref HEAD refs/heads/main

git -C "$default_tree" worktree add --quiet -b feature/test "$feature_tree"
printf 'feature\n' >"$feature_tree/feature.txt"
git -C "$feature_tree" add feature.txt
git -C "$feature_tree" commit --quiet -m 'feature'
feature_head=$(git -C "$feature_tree" rev-parse HEAD)
git -C "$feature_tree" push --quiet --set-upstream origin feature/test
git -C "$default_tree" merge --quiet --squash feature/test >/dev/null 2>&1
git -C "$default_tree" commit --quiet -m 'merge feature'
git -C "$default_tree" push --quiet origin main

git clone --quiet "$remote" "$updater"
printf 'remote advance\n' >"$updater/remote.txt"
git -C "$updater" add remote.txt
git -C "$updater" commit --quiet -m 'advance remote main'
git -C "$updater" push --quiet origin main
remote_main=$(git -C "$updater" rev-parse HEAD)
[[ $(git -C "$default_tree" rev-parse HEAD) != "$remote_main" ]] || fail 'default fixture was not behind remote'

full_output=$tmp/full-output
run_cleanup "$feature_tree" "$full_output" feature/test "$feature_head"
assert_contains "$full_output" 'default pull   ok'
assert_contains "$full_output" 'worktree       ok'
assert_contains "$full_output" 'local branch   ok'
assert_contains "$full_output" 'remote branch  ok'
assert_contains "$full_output" 'result         complete'
assert_before "$full_output" 'worktree       ok' 'local branch   ok'
assert_before "$full_output" 'local branch   ok' 'remote branch  ok'
assert_before "$full_output" 'remote branch  ok' 'default pull   ok'
[[ $(git -C "$default_tree" rev-parse HEAD) == "$remote_main" ]] || fail 'default branch was not fast-forwarded'
[[ ! -e $feature_tree ]] || fail 'feature worktree was not removed'
assert_ref_absent refs/heads/feature/test
assert_remote_absent feature/test

absent_output=$tmp/absent-output
run_cleanup "$default_tree" "$absent_output" feature/test "$feature_head"
assert_contains "$absent_output" 'worktree       absent'
assert_contains "$absent_output" 'local branch   absent'
assert_contains "$absent_output" 'remote branch  absent'
assert_contains "$absent_output" 'result         complete'

if run_cleanup "$default_tree" "$tmp/same-branch-output" main "$remote_main"; then
	fail 'default branch cleanup unexpectedly succeeded'
fi
assert_contains "$tmp/same-branch-output" 'merged and default branches must differ'

git -C "$default_tree" worktree add --quiet -b feature/dirty "$dirty_tree"
dirty_head=$(git -C "$dirty_tree" rev-parse HEAD)
git -C "$dirty_tree" push --quiet --set-upstream origin feature/dirty
printf 'uncommitted\n' >>"$dirty_tree/base.txt"
printf 'untracked\n' >"$dirty_tree/notes.tmp"
printf 'ignored secret\n' >"$dirty_tree/.local-secret"
dirty_output=$tmp/dirty-output
run_cleanup "$default_tree" "$dirty_output" feature/dirty "$dirty_head"
assert_contains "$dirty_output" 'discarded files removing:'
assert_contains "$dirty_output" 'M base.txt'
assert_contains "$dirty_output" '?? notes.tmp'
assert_contains "$dirty_output" '!! .local-secret'
assert_contains "$dirty_output" 'worktree       ok'
assert_contains "$dirty_output" 'local branch   ok'
assert_contains "$dirty_output" 'remote branch  ok'
assert_contains "$dirty_output" 'result         complete'
[[ ! -e $dirty_tree ]] || fail 'dirty worktree was not removed'
assert_ref_absent refs/heads/feature/dirty
assert_remote_absent feature/dirty

git -C "$default_tree" worktree add --quiet -b feature/raced "$raced_tree"
printf 'raced\n' >"$raced_tree/raced.txt"
git -C "$raced_tree" add raced.txt
git -C "$raced_tree" commit --quiet -m 'raced feature'
raced_head=$(git -C "$raced_tree" rev-parse HEAD)
git -C "$raced_tree" push --quiet --set-upstream origin feature/raced
git -C "$updater" fetch --quiet origin feature/raced
git -C "$updater" switch --quiet --force-create feature/raced origin/feature/raced
printf 'advanced\n' >>"$updater/raced.txt"
git -C "$updater" add raced.txt
git -C "$updater" commit --quiet -m 'advance raced feature'
git -C "$updater" push --quiet origin feature/raced
advanced_head=$(git -C "$updater" rev-parse HEAD)
raced_output=$tmp/raced-output
if run_cleanup "$default_tree" "$raced_output" feature/raced "$raced_head"; then
	fail 'advanced remote branch cleanup unexpectedly succeeded'
fi
assert_contains "$raced_output" 'worktree       skipped: remote branch moved after merge'
assert_contains "$raced_output" 'local branch   skipped: remote branch moved after merge'
assert_contains "$raced_output" 'remote branch  failed:'
assert_contains "$raced_output" 'result         incomplete'
[[ -e $raced_tree ]] || fail 'raced worktree was removed'
git -C "$default_tree" show-ref --verify --quiet refs/heads/feature/raced || fail 'raced local branch was removed'
assert_remote_oid feature/raced "$advanced_head"

git -C "$default_tree" switch --quiet -c feature/primary
printf 'primary feature\n' >"$default_tree/primary.txt"
git -C "$default_tree" add primary.txt
git -C "$default_tree" commit --quiet -m 'primary feature'
primary_head=$(git -C "$default_tree" rev-parse HEAD)
git -C "$default_tree" push --quiet --set-upstream origin feature/primary
printf 'dirty primary\n' >>"$default_tree/base.txt"
printf 'untracked primary\n' >"$default_tree/primary-notes.tmp"
printf 'ignored primary\n' >"$default_tree/.local-secret"
primary_output=$tmp/primary-output
run_cleanup "$default_tree" "$primary_output" feature/primary "$primary_head"
assert_contains "$primary_output" 'worktree       reused for default update'
assert_contains "$primary_output" 'discarded files removing:'
assert_contains "$primary_output" 'M base.txt'
assert_contains "$primary_output" '?? primary-notes.tmp'
assert_contains "$primary_output" '!! .local-secret'
assert_contains "$primary_output" 'local branch   ok'
assert_contains "$primary_output" 'remote branch  ok'
assert_contains "$primary_output" 'default switch ok'
assert_contains "$primary_output" 'default pull   ok'
assert_before "$primary_output" 'remote branch  ok' 'default switch ok'
[[ $(git -C "$default_tree" branch --show-current) == main ]] || fail 'primary worktree did not switch to default branch'
[[ ! -e $default_tree/primary.txt ]] || fail 'primary feature file survived default switch'
[[ ! -e $default_tree/primary-notes.tmp ]] || fail 'primary untracked file survived cleanup'
[[ ! -e $default_tree/.local-secret ]] || fail 'primary ignored file survived cleanup'
[[ $(<"$default_tree/base.txt") == base ]] || fail 'primary tracked modification survived cleanup'
assert_ref_absent refs/heads/feature/primary
assert_remote_absent feature/primary

git -C "$default_tree" worktree add --quiet -b feature/race "$race_tree"
race_head=$(git -C "$race_tree" rev-parse HEAD)
git -C "$race_tree" push --quiet --set-upstream origin feature/race
race_output=$tmp/race-output
if ! run_race_cleanup "$default_tree" "$race_output" feature/race "$race_head" delete 1; then
	fail 'cleanup after remote auto-delete unexpectedly failed'
fi
assert_contains "$race_output" 'worktree       ok'
assert_contains "$race_output" 'local branch   ok'
assert_contains "$race_output" 'remote branch  absent: deleted remotely during cleanup'
assert_contains "$race_output" 'default pull   ok'
assert_contains "$race_output" 'result         complete'
[[ ! -e $race_tree ]] || fail 'race worktree was not removed'
assert_ref_absent refs/heads/feature/race
assert_ref_absent refs/remotes/origin/feature/race
assert_remote_absent feature/race

git -C "$default_tree" worktree add --quiet -b feature/race-moved "$race_moved_tree"
printf 'race moved\n' >"$race_moved_tree/race.txt"
git -C "$race_moved_tree" add race.txt
git -C "$race_moved_tree" commit --quiet -m 'race moved feature'
race_moved_head=$(git -C "$race_moved_tree" rev-parse HEAD)
git -C "$race_moved_tree" push --quiet --set-upstream origin feature/race-moved
git -C "$updater" fetch --quiet origin feature/race-moved
git -C "$updater" switch --quiet --force-create feature/race-moved origin/feature/race-moved
printf 'late work\n' >>"$updater/race.txt"
git -C "$updater" add race.txt
git -C "$updater" commit --quiet -m 'advance race-moved after merge'
race_moved_advanced=$(git -C "$updater" rev-parse HEAD)
race_moved_output=$tmp/race-moved-output
if run_race_cleanup "$default_tree" "$race_moved_output" feature/race-moved "$race_moved_head" advance 1 "$updater"; then
	fail 'cleanup after a remote advance unexpectedly succeeded'
fi
assert_contains "$race_moved_output" 'worktree       ok'
assert_contains "$race_moved_output" 'local branch   ok'
assert_contains "$race_moved_output" "remote branch  failed: moved during cleanup: expected $race_moved_head, found $race_moved_advanced"
assert_contains "$race_moved_output" 'result         incomplete'
[[ ! -e $race_moved_tree ]] || fail 'race-moved worktree was not removed'
assert_ref_absent refs/heads/feature/race-moved
assert_remote_oid feature/race-moved "$race_moved_advanced"

git -C "$default_tree" worktree add --quiet -b feature/race-late "$race_late_tree"
race_late_head=$(git -C "$race_late_tree" rev-parse HEAD)
git -C "$race_late_tree" push --quiet --set-upstream origin feature/race-late
race_late_output=$tmp/race-late-output
if ! run_race_cleanup "$default_tree" "$race_late_output" feature/race-late "$race_late_head" delete 2; then
	fail 'cleanup after a mid-push remote delete unexpectedly failed'
fi
assert_contains "$race_late_output" 'worktree       ok'
assert_contains "$race_late_output" 'local branch   ok'
assert_contains "$race_late_output" 'remote branch  absent: deleted remotely during cleanup'
assert_contains "$race_late_output" 'default pull   ok'
assert_contains "$race_late_output" 'result         complete'
[[ ! -e $race_late_tree ]] || fail 'race-late worktree was not removed'
assert_ref_absent refs/heads/feature/race-late
assert_ref_absent refs/remotes/origin/feature/race-late
assert_remote_absent feature/race-late

git -C "$default_tree" worktree add --quiet -b feature/race-late-moved "$race_late_moved_tree"
printf 'race late moved\n' >"$race_late_moved_tree/race.txt"
git -C "$race_late_moved_tree" add race.txt
git -C "$race_late_moved_tree" commit --quiet -m 'race late moved feature'
race_late_moved_head=$(git -C "$race_late_moved_tree" rev-parse HEAD)
git -C "$race_late_moved_tree" push --quiet --set-upstream origin feature/race-late-moved
git -C "$updater" fetch --quiet origin feature/race-late-moved
git -C "$updater" switch --quiet --force-create feature/race-late-moved origin/feature/race-late-moved
printf 'late work\n' >>"$updater/race.txt"
git -C "$updater" add race.txt
git -C "$updater" commit --quiet -m 'advance race-late-moved during cleanup'
race_late_moved_advanced=$(git -C "$updater" rev-parse HEAD)
race_late_moved_output=$tmp/race-late-moved-output
if run_race_cleanup "$default_tree" "$race_late_moved_output" feature/race-late-moved "$race_late_moved_head" advance 2 "$updater"; then
	fail 'cleanup after a mid-push remote advance unexpectedly succeeded'
fi
assert_contains "$race_late_moved_output" 'worktree       ok'
assert_contains "$race_late_moved_output" 'local branch   ok'
assert_contains "$race_late_moved_output" "remote branch  failed: moved during cleanup: expected $race_late_moved_head, found $race_late_moved_advanced"
assert_contains "$race_late_moved_output" 'result         incomplete'
[[ ! -e $race_late_moved_tree ]] || fail 'race-late-moved worktree was not removed'
assert_ref_absent refs/heads/feature/race-late-moved
assert_remote_oid feature/race-late-moved "$race_late_moved_advanced"

# A host can delete the merged branch before cleanup starts. The tracking ref is
# then the only residue left behind, so this path must prune it too.
git -C "$default_tree" worktree add --quiet -b feature/preflight-absent "$stale_tree"
stale_head=$(git -C "$stale_tree" rev-parse HEAD)
git -C "$stale_tree" push --quiet --set-upstream origin feature/preflight-absent
git --git-dir="$remote" update-ref -d refs/heads/feature/preflight-absent
git -C "$default_tree" show-ref --verify --quiet refs/remotes/origin/feature/preflight-absent ||
	fail 'fixture did not leave a stale tracking ref'
stale_output=$tmp/stale-output
if ! run_cleanup "$default_tree" "$stale_output" feature/preflight-absent "$stale_head"; then
	fail 'cleanup with a preflight-absent remote branch unexpectedly failed'
fi
assert_contains "$stale_output" 'worktree       ok'
assert_contains "$stale_output" 'local branch   ok'
assert_contains "$stale_output" 'remote branch  absent'
assert_contains "$stale_output" 'result         complete'
if grep -F 'deleted remotely during cleanup' "$stale_output" >/dev/null; then
	fail 'preflight-absent cleanup reported the mid-cleanup deletion path'
fi
[[ ! -e $stale_tree ]] || fail 'preflight-absent worktree was not removed'
assert_ref_absent refs/heads/feature/preflight-absent
assert_ref_absent refs/remotes/origin/feature/preflight-absent

git -C "$default_tree" worktree add --quiet -b feature/pull-fail "$pull_fail_tree"
pull_fail_head=$(git -C "$pull_fail_tree" rev-parse HEAD)
git -C "$pull_fail_tree" push --quiet --set-upstream origin feature/pull-fail
printf 'local divergence\n' >"$default_tree/local.txt"
git -C "$default_tree" add local.txt
git -C "$default_tree" commit --quiet -m 'diverge local main'
git -C "$updater" switch --quiet main
printf 'remote divergence\n' >"$updater/other.txt"
git -C "$updater" add other.txt
git -C "$updater" commit --quiet -m 'diverge remote main'
git -C "$updater" push --quiet origin main
pull_fail_output=$tmp/pull-fail-output
if run_cleanup "$default_tree" "$pull_fail_output" feature/pull-fail "$pull_fail_head"; then
	fail 'cleanup after failed pull unexpectedly succeeded'
fi
assert_contains "$pull_fail_output" 'worktree       ok'
assert_contains "$pull_fail_output" 'local branch   ok'
assert_contains "$pull_fail_output" 'remote branch  ok'
assert_contains "$pull_fail_output" 'default pull   failed'
assert_contains "$pull_fail_output" 'result         incomplete'
[[ ! -e $pull_fail_tree ]] || fail 'pull-fail worktree was not removed'
assert_ref_absent refs/heads/feature/pull-fail
assert_remote_absent feature/pull-fail

printf 'cleanup-after-merge tests passed\n'
