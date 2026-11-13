#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
readonly script_dir subject=$script_dir/commit.sh
readonly COMMIT_BODY='Keep signed commits compatible with repository message policy.'
readonly ESCAPED_NEWLINE_MESSAGE='fix(skill): escaped\n\nBody'
readonly ESCAPED_NEWLINE_ERROR='error: commit message contains literal \n; use actual newlines'
tmp=$(mktemp -d)
readonly tmp
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin"

cat >"$tmp/bin/git" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'git' >>"$TEST_LOG"; printf ' <%s>' "$@" >>"$TEST_LOG"; printf '\n' >>"$TEST_LOG"
case "${1:-}" in
  branch) printf '%s\n' "${FAKE_BRANCH:-feature/test}" ;;
  remote) printf '%s\n' "${FAKE_ORIGIN:-git@github.com:other/repo.git}" ;;
  config) [[ -n ${FAKE_TRUNK_OWNERS:-} ]] && printf '%s\n' "$FAKE_TRUNK_OWNERS" ;;
  symbolic-ref) [[ -n ${FAKE_DEFAULT:-} ]] && printf 'origin/%s\n' "$FAKE_DEFAULT" ;;
  diff) [[ ! -e "$TEST_STAGE" && ${FAKE_PRESTAGED:-0} == 0 ]] ;;
  add) : >"$TEST_STAGE" ;;
  reset) rm -f "$TEST_STAGE" ;;
  commit) [[ ${FAKE_COMMIT_FAIL:-0} == 0 && -e "$TEST_STAGE" ]] ;;
esac
EOF
chmod +x "$tmp/bin/git"
export PATH="$tmp/bin:$PATH" TEST_LOG="$tmp/log" TEST_STAGE="$tmp/stage"
unset GIT_TRUNK_OWNERS FAKE_TRUNK_OWNERS

assert_absent() {
	if grep -F -- "$1" "$TEST_LOG" >/dev/null; then
		echo "unexpected command: $1" >&2
		exit 1
	fi
}

bash "$subject" 'fix(skill): test exact signing' --body "$COMMIT_BODY" -- 'file one.txt'
grep -Fx 'git <add> <--> <file one.txt>' "$TEST_LOG" >/dev/null
grep -Fx "git <commit> <-s> <-S> <-m> <fix(skill): test exact signing> <-m> <$COMMIT_BODY>" "$TEST_LOG" >/dev/null

: >"$TEST_LOG"
rm -f "$TEST_STAGE"
if FAKE_BRANCH=trunk FAKE_DEFAULT=trunk bash "$subject" 'fix: reject default' --body "$COMMIT_BODY" -- file.txt >/dev/null 2>&1; then
	echo 'configured default branch was accepted' >&2
	exit 1
fi
assert_absent 'git <commit>'

: >"$TEST_LOG"
rm -f "$TEST_STAGE"
if FAKE_BRANCH=trunk bash "$subject" 'fix: reject fallback default' --body "$COMMIT_BODY" -- file.txt >/dev/null 2>&1; then
	echo 'fallback default branch was accepted' >&2
	exit 1
fi
assert_absent 'git <commit>'

: >"$TEST_LOG"
rm -f "$TEST_STAGE"
if FAKE_COMMIT_FAIL=1 bash "$subject" 'fix: rollback index' --body "$COMMIT_BODY" -- file.txt >/dev/null 2>&1; then
	echo 'commit failure was ignored' >&2
	exit 1
fi
[[ ! -e $TEST_STAGE ]]
grep -Fx 'git <reset> <--quiet> <--> <file.txt>' "$TEST_LOG" >/dev/null

: >"$TEST_LOG"
rm -f "$TEST_STAGE"
if FAKE_PRESTAGED=1 bash "$subject" 'fix: reject staged' --body "$COMMIT_BODY" -- file.txt >/dev/null 2>&1; then
	echo 'pre-staged changes were accepted' >&2
	exit 1
fi
assert_absent 'git <add>'

if bash "$subject" 'invalid message' --body "$COMMIT_BODY" -- file.txt >/dev/null 2>&1; then
	echo 'invalid message was accepted' >&2
	exit 1
fi

: >"$TEST_LOG"
rm -f "$TEST_STAGE"
escaped_error=$tmp/escaped-newline-error
if bash "$subject" "$ESCAPED_NEWLINE_MESSAGE" --body "$COMMIT_BODY" -- file.txt >/dev/null 2>"$escaped_error"; then
	echo 'escaped newline message was accepted' >&2
	exit 1
fi
grep -Fx "$ESCAPED_NEWLINE_ERROR" "$escaped_error" >/dev/null
assert_absent 'git <branch>'

: >"$TEST_LOG"
rm -f "$TEST_STAGE"
FAKE_BRANCH=main FAKE_ORIGIN='git@github.com:acme-org/repo.git' GIT_TRUNK_OWNERS=acme-org \
	bash "$subject" 'feat(cli): allow configured trunk owner' --body "$COMMIT_BODY" -- trunk.txt
grep -Fx "git <commit> <-s> <-S> <-m> <feat(cli): allow configured trunk owner> <-m> <$COMMIT_BODY>" "$TEST_LOG" >/dev/null

: >"$TEST_LOG"
rm -f "$TEST_STAGE"
if FAKE_BRANCH=main FAKE_ORIGIN='git@github.com:other-org/repo.git' GIT_TRUNK_OWNERS=acme-org \
	bash "$subject" 'feat: reject unowned trunk' --body "$COMMIT_BODY" -- trunk.txt >/dev/null 2>&1; then
	echo 'unowned default branch was accepted with configured trunk owner' >&2
	exit 1
fi
assert_absent 'git <commit>'

: >"$TEST_LOG"
rm -f "$TEST_STAGE"
if FAKE_BRANCH=main FAKE_ORIGIN='git@github.com:acme-org/repo.git' FAKE_TRUNK_OWNERS=acme-org GIT_TRUNK_OWNERS='' \
	bash "$subject" 'feat: empty env overrides git config' --body "$COMMIT_BODY" -- trunk.txt >/dev/null 2>&1; then
	echo 'explicit empty GIT_TRUNK_OWNERS did not override git config' >&2
	exit 1
fi
assert_absent 'git <commit>'

: >"$TEST_LOG"
rm -f "$TEST_STAGE"
FAKE_BRANCH=main FAKE_ORIGIN='git@github.com:acme-org/repo.git' FAKE_TRUNK_OWNERS=$'first-org\nacme-org' \
	bash "$subject" 'feat(cli): allow multiline trunkOwners config' --body "$COMMIT_BODY" -- trunk.txt
grep -Fx "git <commit> <-s> <-S> <-m> <feat(cli): allow multiline trunkOwners config> <-m> <$COMMIT_BODY>" "$TEST_LOG" >/dev/null

: >"$TEST_LOG"
rm -f "$TEST_STAGE"
FAKE_BRANCH=main FAKE_ORIGIN='git@github.com:AcMe.Org/repo.git' GIT_TRUNK_OWNERS='First-Org, acme.org .' \
	bash "$subject" 'feat(cli): match owner case-insensitively and literally' --body "$COMMIT_BODY" -- trunk.txt
grep -Fx "git <commit> <-s> <-S> <-m> <feat(cli): match owner case-insensitively and literally> <-m> <$COMMIT_BODY>" "$TEST_LOG" >/dev/null

: >"$TEST_LOG"
rm -f "$TEST_STAGE"
if FAKE_BRANCH=main FAKE_ORIGIN='git@github.com:acmexorg/repo.git' GIT_TRUNK_OWNERS='acme.org, .' \
	bash "$subject" 'feat: reject unescaped dot wildcard' --body "$COMMIT_BODY" -- trunk.txt >/dev/null 2>&1; then
	echo 'literal dot check matched regex wildcard' >&2
	exit 1
fi
assert_absent 'git <commit>'

printf 'commit script tests passed\n'
