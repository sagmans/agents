#!/usr/bin/env bash
# End-to-end clean-room dogfooding suite exercising ./setup and commit helpers
# inside disposable temporary HOME and Git directories without touching $HOME.
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly REPO_ROOT

readonly EXPECTED_SKILLS='skills (12):'
readonly EXPECTED_ROLES='roles (58):'
readonly EXPECTED_PROMPTS='prompts (4):'
readonly EXPECTED_COMMANDS='commands (8):'
readonly EXPECTED_THEMES='themes (1):'
readonly EXPECTED_PI_MODEL='model: "anthropic/claude-sonnet-4-5"'
readonly UNMANAGED_MARKER='user-owned-content'
readonly TEST_BODY='Verify clean-room trunk protection behavior.'

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/agents-dogfood.XXXXXX")"
readonly TMP_DIR

cleanup() {
	case "$TMP_DIR" in
	*/agents-dogfood.*) rm -rf -- "$TMP_DIR" ;;
	esac
}
trap cleanup EXIT

fail() {
	printf 'dogfood FAILED: %s\n' "$1" >&2
	exit 1
}

assert_file() {
	[ -f "$1" ] || fail "expected file missing: $1"
}

assert_symlink() {
	[ -L "$1" ] || fail "expected symlink missing: $1"
}

assert_contains() {
	local file="$1" needle="$2"
	grep -Fq -- "$needle" "$file" || fail "expected '$needle' in $file"
}

assert_not_contains() {
	local file="$1" needle="$2"
	if grep -Fq -- "$needle" "$file"; then
		fail "unexpected '$needle' found in $file"
	fi
}

cd "$REPO_ROOT"

# 1. Validate catalog counts and strict invariants
validate_out="$(./setup validate --strict)"
printf '%s\n' "$validate_out"
list_out="$(./setup list)"
for marker in \
	"$EXPECTED_SKILLS" \
	"$EXPECTED_ROLES" \
	"$EXPECTED_PROMPTS" \
	"$EXPECTED_COMMANDS" \
	"$EXPECTED_THEMES"; do
	printf '%s\n' "$list_out" | grep -Fq -- "$marker" || fail "missing count marker: $marker"
done

# 2. Dry-run leaves target HOME untouched
h1="$TMP_DIR/h1"
./setup --dry-run --all --home "$h1" >/dev/null
[ ! -e "$h1" ] || fail "dry-run created $h1"

# 3. Full clean-room installation with model map and Claude styles
./setup --all --styles --model-map adapters/pi/model-map.example.json --home "$h1" >/dev/null
assert_symlink "$h1/.claude/skills/commit"
assert_symlink "$h1/.config/opencode/skills/pr-digest"
assert_file "$h1/.pi/agent/agents/architecture-reviewer.md"
assert_contains "$h1/.pi/agent/agents/architecture-reviewer.md" "$EXPECTED_PI_MODEL"
assert_file "$h1/.config/opencode/agents/architecture-reviewer.md"
assert_contains "$h1/.config/opencode/agents/architecture-reviewer.md" '"edit": "deny"'
assert_file "$h1/.config/opencode/agents/feature-implementer.md"
assert_not_contains "$h1/.config/opencode/agents/feature-implementer.md" '"edit": "deny"'
assert_file "$h1/.pi/agent/prompts/deep-code-review.md"
assert_file "$h1/.pi/agent/themes/violet-orbit.json"
assert_file "$h1/.config/opencode/commands/validate_pr_reviews.md"
assert_file "$h1/.claude/output-styles/visual-concise.md"
assert_file "$h1/.claude/hooks/visual-reminder.sh"
[ -x "$h1/.claude/hooks/visual-reminder.sh" ] || fail "Claude hook is not executable"
hook_out="$(printf '{}' | "$h1/.claude/hooks/visual-reminder.sh")"
[ -n "$hook_out" ] || fail "Claude visual-reminder hook emitted empty stdout"

# 4. Idempotent rerun and status check across all clients
rerun_out="$(./setup --all --styles --model-map adapters/pi/model-map.example.json --home "$h1")"
printf '%s\n' "$rerun_out" | grep -Fq 'written=0 ' || fail "rerun rewrote unchanged files: $rerun_out"
status_out="$(./setup status --model-map adapters/pi/model-map.example.json --home "$h1")"
for client in pi opencode claude codex cursor gemini; do
	printf '%s\n' "$status_out" | grep -Eq "^${client}: installed=[1-9][0-9]* stale=0 missing=0 " ||
		fail "unexpected status for $client: $status_out"
done

# 5. Pre-existing unmanaged file conflict fails closed without overwriting
h2="$TMP_DIR/h2"
mkdir -p "$h2/.claude/skills/commit"
printf '%s\n' "$UNMANAGED_MARKER" >"$h2/.claude/skills/commit/SKILL.md"
if conflict_err="$(./setup --client claude --skill commit --home "$h2" 2>&1)"; then
	fail "installer overwrote unmanaged pre-existing skill file"
fi
printf '%s\n' "$conflict_err" | grep -Fq 'unmanaged destination exists:' ||
	fail "unexpected conflict error: $conflict_err"
assert_contains "$h2/.claude/skills/commit/SKILL.md" "$UNMANAGED_MARKER"

# 6. Sibling user file survives managed uninstall
printf '%s\n' "$UNMANAGED_MARKER" >"$h1/.claude/agents/user-custom.md"
./setup uninstall --home "$h1" >/dev/null
assert_file "$h1/.claude/agents/user-custom.md"
assert_contains "$h1/.claude/agents/user-custom.md" "$UNMANAGED_MARKER"
[ ! -e "$h1/.claude/skills/commit" ] || fail "uninstall left managed Claude skill behind"
[ ! -e "$h1/.pi/agent/agents/architecture-reviewer.md" ] || fail "uninstall left managed Pi role behind"

# 7. Snapshot --copy mode installs real directory, reports clean status, uninstalls via root flags
h3="$TMP_DIR/h3"
./setup --client codex --skill commit --role bug-fix-engineer --copy --home "$h3" >/dev/null
[ -d "$h3/.codex/skills/commit" ] && [ ! -L "$h3/.codex/skills/commit" ] || fail "--copy did not create a real directory"
assert_file "$h3/.codex/agents/bug-fix-engineer.md"
copy_status="$(./setup --status --client codex --skill commit --role bug-fix-engineer --copy --home "$h3")"
printf '%s\n' "$copy_status" | grep -Fq 'codex: installed=2 stale=0 missing=0 unmanaged=0' ||
	fail "unexpected copy status: $copy_status"
./setup --uninstall --client codex --home "$h3" >/dev/null
[ ! -e "$h3/.codex/skills/commit" ] || fail "uninstall left copied skill behind"

# 8. Interactive quit leaves disk untouched and unknown ID fails closed
h4="$TMP_DIR/h4"
printf 'q\n' | ./setup --interactive --home "$h4" >/dev/null
[ ! -e "$h4" ] || fail "interactive quit created $h4"
if unknown_err="$(./setup --skill does-not-exist --home "$h4" 2>&1)"; then
	fail "unknown skill ID unexpectedly succeeded"
fi
printf '%s\n' "$unknown_err" | grep -Fq 'unknown skill ID' ||
	fail "unexpected unknown-skill error: $unknown_err"

# 9. Commit helper refuses direct commit on main for unowned origin
fake_repo="$TMP_DIR/unowned-repo"
mkdir -p "$fake_repo"
(
	cd "$fake_repo"
	GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 git init -q -b main
	GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 git remote add origin https://github.com/other/repo.git
	printf 'probe\n' >trunk.txt
	if trunk_err="$(GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_TRUNK_OWNERS='' \
		bash "$REPO_ROOT/skills/commit/scripts/commit.sh" \
		'fix(test): block unowned trunk commit' --body "$TEST_BODY" -- trunk.txt 2>&1)"; then
		fail "commit helper allowed commit on unowned main branch"
	fi
	printf '%s\n' "$trunk_err" | grep -Fq 'refusing to commit on default branch: main' ||
		fail "unexpected trunk-guard error: $trunk_err"
)

printf 'dogfood passed\n'
