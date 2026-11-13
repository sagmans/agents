#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
readonly script_dir subject=$script_dir/git.sh
tmp=$(mktemp -d)
readonly tmp
trap 'rm -rf "$tmp"' EXIT

export GIT_AUTHOR_NAME='Git Editor Test'
export GIT_AUTHOR_EMAIL='git-editor@example.invalid'
export GIT_COMMITTER_NAME=$GIT_AUTHOR_NAME
export GIT_COMMITTER_EMAIL=$GIT_AUTHOR_EMAIL
# Fixture repos live in a temporary directory without signing keys or host
# editor settings, so isolate git configuration from user globals.
export GIT_CONFIG_GLOBAL=/dev/null

readonly editor=$tmp/hostile-editor.sh marker=$tmp/editor.log
export MARKER_PATH=$marker
cat >"$editor" <<'EDITOR'
#!/usr/bin/env bash
printf 'editor consulted: %s\n' "${1:-}" >>"$MARKER_PATH"
exit 1
EDITOR
chmod +x "$editor"

fail() {
	printf 'test failed: %s\n' "$*" >&2
	exit 1
}

assert_editor_unused() {
	[[ ! -s $marker ]] || fail "git consulted the interactive editor: $(cat "$marker")"
}

assert_rebase_finished() {
	[[ ! -d $1/.git/rebase-merge ]] || fail "rebase is still paused in $1"
}

new_repo() {
	local repo=$1
	git init -q -b main "$repo"
	# The editor is configured per fixture repo so no host config can hide the regression.
	git -C "$repo" config core.editor "$editor"
	printf 'base\n' >"$repo/f.txt"
	git -C "$repo" add f.txt
	git -C "$repo" commit -qm 'base'
}

make_conflicted_rebase() {
	local repo=$1
	new_repo "$repo"
	git -C "$repo" switch -qc feature
	printf 'feature\n' >"$repo/f.txt"
	git -C "$repo" commit -qam 'feature: keep this message'
	git -C "$repo" switch -q main
	printf 'main\n' >"$repo/f.txt"
	git -C "$repo" commit -qam 'main change'
	git -C "$repo" switch -q feature
	git -C "$repo" rebase main >/dev/null 2>&1 || true
	printf 'resolved\n' >"$repo/f.txt"
	git -C "$repo" add f.txt
}

# A plain command run with the same fixture proves the host editor would be used.
control=$tmp/rebase-control
make_conflicted_rebase "$control"
: >"$marker"
(cd "$control" && env -u GIT_EDITOR git rebase --continue >/dev/null 2>&1) || true
[[ -s $marker ]] || fail 'control rebase never consulted the fixture editor; the regression could go unnoticed'
[[ -d $control/.git/rebase-merge ]] || fail 'control rebase unexpectedly finished'

host_config=$tmp/rebase-host-config
make_conflicted_rebase "$host_config"
: >"$marker"
(cd "$host_config" && bash "$subject" rebase-continue >"$host_config/git-sh.log" 2>&1) ||
	fail "rebase-continue failed with host core.editor configured: $(cat "$host_config/git-sh.log")"
assert_editor_unused
assert_rebase_finished "$host_config"
[[ $(git -C "$host_config" log -1 --format=%s) == 'feature: keep this message' ]] || fail 'rebase-continue changed the recorded message'

inherited=$tmp/rebase-inherited-editor
make_conflicted_rebase "$inherited"
: >"$marker"
(cd "$inherited" && env GIT_EDITOR="$editor" bash "$subject" rebase-continue >"$inherited/git-sh.log" 2>&1) ||
	fail "rebase-continue honoured an inherited interactive editor: $(cat "$inherited/git-sh.log")"
assert_editor_unused
assert_rebase_finished "$inherited"

merge_repo=$tmp/merge
new_repo "$merge_repo"
git -C "$merge_repo" switch -qc topic
printf 'topic\n' >"$merge_repo/f.txt"
git -C "$merge_repo" commit -qam 'topic: keep this message'
git -C "$merge_repo" switch -q main
printf 'main\n' >"$merge_repo/f.txt"
git -C "$merge_repo" commit -qam 'main change'
git -C "$merge_repo" merge topic >/dev/null 2>&1 || true
printf 'resolved\n' >"$merge_repo/f.txt"
git -C "$merge_repo" add f.txt
: >"$marker"
(cd "$merge_repo" && bash "$subject" merge-continue >"$merge_repo/git-sh.log" 2>&1) ||
	fail "merge-continue failed: $(cat "$merge_repo/git-sh.log")"
assert_editor_unused
[[ ! -e $merge_repo/.git/MERGE_HEAD ]] || fail 'merge is still paused'
[[ $(git -C "$merge_repo" log -1 --format=%s) == "Merge branch 'topic'" ]] || fail 'merge-continue did not create the merge commit'

printf 'git editor tests passed\n'
