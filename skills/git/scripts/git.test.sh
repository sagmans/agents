#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
readonly script_dir subject=$script_dir/git.sh
tmp=$(mktemp -d)
readonly tmp
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin"

# A boundary spy keeps rejection tests from mutating the caller's repository.
cat >"$tmp/bin/git" <<'EOF'
#!/usr/bin/env bash
printf 'git' >>"$TEST_LOG"; printf ' <%s>' "$@" >>"$TEST_LOG"; printf '\n' >>"$TEST_LOG"
printf 'env %s %s %s %s\n' "${GIT_EDITOR:-}" "${GIT_SEQUENCE_EDITOR:-}" "${GIT_PAGER:-}" "${GIT_TERMINAL_PROMPT:-}" >>"$TEST_LOG"
exit "${TEST_GIT_STATUS:-0}"
EOF
chmod +x "$tmp/bin/git"
export PATH="$tmp/bin:$PATH" TEST_LOG="$tmp/log"

for report in summary detail; do
	: >"$TEST_LOG"
	bash "$subject" "$report" >/dev/null
	grep -F 'git <status>' "$TEST_LOG" >/dev/null
	grep -F 'git <log>' "$TEST_LOG" >/dev/null
	grep -F 'git <diff>' "$TEST_LOG" >/dev/null
	grep -F 'git <diff> <--cached>' "$TEST_LOG" >/dev/null
done

for operation in rebase merge cherry-pick revert; do
	: >"$TEST_LOG"
	bash "$subject" "$operation-continue"
	grep -Fx "git <$operation> <--continue>" "$TEST_LOG" >/dev/null
	grep -Fx 'env true true cat 0' "$TEST_LOG" >/dev/null
done

# Unsupported commands and extra arguments must never reach Git.
for invocation in '' 'status' 'commit message path' 'push --confirm' 'reset --confirm hard HEAD' 'summary extra' 'rebase-continue extra'; do
	read -r -a arguments <<<"$invocation"
	: >"$TEST_LOG"
	if bash "$subject" "${arguments[@]}" >/dev/null 2>&1; then
		echo "unexpectedly accepted: $invocation" >&2
		exit 1
	fi
	[[ ! -s $TEST_LOG ]]
done

# A failed continuation must remain a failure for its caller.
status=0
TEST_GIT_STATUS=7 bash "$subject" rebase-continue || status=$?
[[ $status -eq 7 ]]
bash "$subject" help >/dev/null 2>&1
printf 'git helper tests passed\n'
