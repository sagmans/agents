#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
readonly script_dir subject=$script_dir/github-pr.sh
tmp=$(mktemp -d)
readonly tmp
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin"

cat >"$tmp/bin/gh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'gh' >>"$TEST_LOG"; printf ' <%s>' "$@" >>"$TEST_LOG"; printf '\n' >>"$TEST_LOG"
[[ ${1:-} != auth || ${FAKE_AUTH_FAIL:-0} == 0 ]] || exit 1
if [[ $* == 'repo view '* && $* == *'--jq .nameWithOwner'* ]]; then
  printf '%s\n' "${FAKE_REPO:-owner/repo}"
elif [[ $* == 'repo view '* && $* == *'--jq .defaultBranchRef.name'* ]]; then
  printf '%s\n' "${FAKE_DEFAULT:-main}"
elif [[ $* == 'repo view '* && $* == *'--jq .url'* ]]; then
  printf '%s\n' "${FAKE_REPO_URL:-https://github.com/owner/repo}"
elif [[ $* == 'pr view '* && $* == *'--jq [.url, .headRefName, (.isCrossRepository | tostring)] | @tsv'* ]]; then
  printf '%s\t%s\t%s\n' "${FAKE_PR_URL:-https://github.com/owner/repo/pull/42}" "${FAKE_HEAD:-feature/test}" "${FAKE_CROSS:-false}"
elif [[ $* == 'pr view '* && $* == *'--jq .url'* ]]; then
  printf '%s\n' "${FAKE_PR_URL:-https://github.com/owner/repo/pull/42}"
fi
EOF
cat >"$tmp/bin/git" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'git' >>"$TEST_LOG"; printf ' <%s>' "$@" >>"$TEST_LOG"; printf '\n' >>"$TEST_LOG"
case ${1:-} in
  remote) printf 'git@github.com:owner/repo.git\n' ;;
  ls-remote) exit "${FAKE_REMOTE_STATUS:-0}" ;;
esac
EOF
chmod +x "$tmp/bin/gh" "$tmp/bin/git"
export PATH="$tmp/bin:$PATH" TEST_LOG="$tmp/log"

assert_absent() {
	if grep -F -- "$1" "$TEST_LOG" >/dev/null; then
		echo "unexpected command: $1" >&2
		exit 1
	fi
}

for mutation in 'create title body main head' 'edit 42 title body'; do
	: >"$TEST_LOG"
	read -r -a arguments <<<"$mutation"
	if bash "$subject" "${arguments[@]}" >/dev/null 2>&1; then
		echo "unguarded mutation accepted: $mutation" >&2
		exit 1
	fi
	assert_absent 'gh <pr> <create>'
	assert_absent 'gh <pr> <edit>'
	assert_absent 'gh <pr> <merge>'
done

if bash "$subject" merge --confirm 42 >/dev/null 2>&1; then
	echo 'legacy merge command was accepted' >&2
	exit 1
fi
assert_absent 'gh <pr> <merge>'
assert_absent 'git <push>'

: >"$TEST_LOG"
touch "$tmp/body.md"
if FAKE_AUTH_FAIL=1 bash "$subject" create --confirm 'feat: title' "$tmp/body.md" main feature/test >/dev/null 2>&1; then
	echo 'failed preflight was ignored' >&2
	exit 1
fi
assert_absent 'gh <pr> <create>'

: >"$TEST_LOG"
if bash "$subject" create --confirm 'feat: title' "$tmp/body.md" main main >/dev/null 2>&1; then
	echo 'default head was accepted' >&2
	exit 1
fi
assert_absent 'gh <pr> <create>'

: >"$TEST_LOG"
bash "$subject" create --confirm 'feat: title' "$tmp/body.md" main feature/test >/dev/null
grep -Fx "gh <pr> <create> <--title> <feat: title> <--body-file> <$tmp/body.md> <--base> <main> <--head> <feature/test>" "$TEST_LOG" >/dev/null

: >"$TEST_LOG"
bash "$subject" edit --confirm 42 'fix: title' "$tmp/body.md" >/dev/null
grep -Fx "gh <pr> <edit> <42> <--title> <fix: title> <--body-file> <$tmp/body.md>" "$TEST_LOG" >/dev/null

: >"$TEST_LOG"
bash "$subject" view 42 >/dev/null
grep -E 'gh <pr> <view> <42> <--json> <[^>]*title,body[^>]*>' "$TEST_LOG" >/dev/null

printf 'github script tests passed\n'
