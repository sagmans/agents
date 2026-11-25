#!/usr/bin/env bash
# End-to-end clean-room dogfooding suite exercising ./setup and commit helpers
# inside disposable temporary HOME and Git directories without touching $HOME.
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly REPO_ROOT

readonly EXPECTED_PACKS='packs (8):'
readonly EXPECTED_SKILLS='skills (12):'
readonly EXPECTED_ROLES='roles (51):'
readonly EXPECTED_PROMPTS='prompts (4):'
readonly EXPECTED_COMMANDS='commands (8):'
readonly EXPECTED_THEMES='themes (1):'
# Placeholder IDs: the catalog ships no provider or model names, so tests use neutral ones.
readonly TEST_MODEL='example-provider/model-a'
readonly TEST_ROLE_MODEL='example-provider/model-b'
readonly SHARED_SKILLS_SUBPATH='.agents/skills'
readonly LEGACY_PI_SKILLS_SUBPATH='.pi/agent/skills'
readonly UNMANAGED_MARKER='user-owned-content'
readonly TEST_BODY='Verify clean-room trunk protection behavior.'

TMP_BASE="${TMPDIR:-/tmp}"
TMP_DIR="$(mktemp -d "${TMP_BASE%/}/agents-dogfood.XXXXXX")"
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

# Never read or write the real user's model config: calls without --home use a scratch
# XDG config directory, and calls with --home read only that sandbox.
export XDG_CONFIG_HOME="$TMP_DIR/xdg"

# 1. Validate catalog counts and strict invariants
validate_out="$(./setup validate --strict)"
printf '%s\n' "$validate_out"
list_out="$(./setup list)"
for marker in \
	"$EXPECTED_PACKS" \
	"$EXPECTED_SKILLS" \
	"$EXPECTED_ROLES" \
	"$EXPECTED_PROMPTS" \
	"$EXPECTED_COMMANDS" \
	"$EXPECTED_THEMES"; do
	printf '%s\n' "$list_out" | grep -Fq -- "$marker" || fail "missing count marker: $marker"
done
packs_out="$(./setup list --kind packs)"
printf '%s\n' "$packs_out" | grep -Fq 'delivery: skills=8 roles=0 prompts=0 commands=5' ||
	fail "unexpected packs breakdown: $packs_out"

# 2. Dry-run leaves target HOME untouched
h1="$TMP_DIR/h1"
./setup --dry-run --all --home "$h1" >/dev/null
[ ! -e "$h1" ] || fail "dry-run created $h1"

# 3. Full clean-room installation with no model config renders no model field anywhere
./setup --all --styles --home "$h1" >/dev/null
if grep -rlq '^model:' "$h1/.pi/agent/agents" "$h1/.config/opencode/agents" "$h1/.claude/agents" \
	"$h1/.codex/agents" "$h1/.cursor/agents" "$h1/.gemini/agents"; then
	fail "a role rendered a model field without a model config"
fi
[ ! -e "$h1/.config/agents" ] || fail "install without a choice created a model config"
assert_file "$h1/.pi/agent/agents/pi-startup-profiler.md"
[ ! -e "$h1/.claude/agents/pi-startup-profiler.md" ] || fail "Pi-only role installed into Claude"

# 3b. Model choices live in the user-local config and cascade role > category > client
./setup models set --client pi --model "$TEST_MODEL" --thinking high --home "$h1" >/dev/null
./setup models set --client pi --category review --thinking max --home "$h1" >/dev/null
./setup models set --client pi --role architecture-reviewer --model "$TEST_ROLE_MODEL" --home "$h1" >/dev/null
config_mode="$(stat -f '%Lp' "$h1/.config/agents/config.json" 2>/dev/null || stat -c '%a' "$h1/.config/agents/config.json")"
[ "$config_mode" = 600 ] || fail "model config is not owner-only: $config_mode"
if ./setup models set --client claude --thinking high --home "$h1" >/dev/null 2>&1; then
	fail "thinking accepted for a client without thinking support"
fi
if ./setup models set --client pi --role no-such-role --model "$TEST_MODEL" --home "$h1" >/dev/null 2>&1; then
	fail "model choice accepted for an unknown role"
fi
if ./setup models set --client claude --role pi-startup-profiler --model "$TEST_MODEL" --home "$h1" >/dev/null 2>&1; then
	fail "model choice accepted for a role the client never installs"
fi
# Setting one field keeps the other field stored at the same scope.
./setup models set --client pi --role feature-implementer --model "$TEST_ROLE_MODEL" --home "$h1" >/dev/null
./setup models set --client pi --role feature-implementer --thinking low --home "$h1" >/dev/null
./setup models show --home "$h1" | grep -E '^  role +feature-implementer ' | grep -Fq "model=$TEST_ROLE_MODEL thinking=low" ||
	fail "setting thinking dropped the stored model"
./setup --all --styles --home "$h1" >/dev/null
# Pi discovers the shared location natively; a second deployment causes collisions.
assert_symlink "$h1/$SHARED_SKILLS_SUBPATH/commit"
[ ! -e "$h1/$LEGACY_PI_SKILLS_SUBPATH" ] || fail "installer created duplicate Pi skills"
assert_symlink "$h1/.claude/skills/commit"
assert_symlink "$h1/.config/opencode/skills/pr-digest"
assert_file "$h1/.pi/agent/agents/architecture-reviewer.md"
assert_contains "$h1/.pi/agent/agents/architecture-reviewer.md" "model: \"$TEST_ROLE_MODEL\""
assert_contains "$h1/.pi/agent/agents/architecture-reviewer.md" 'thinking: "max"'
assert_contains "$h1/.pi/agent/agents/ci-watcher.md" "model: \"$TEST_MODEL\""
assert_contains "$h1/.pi/agent/agents/ci-watcher.md" 'thinking: "high"'
assert_not_contains "$h1/.claude/agents/ci-watcher.md" 'model:'
assert_contains "$h1/.pi/agent/agents/browser-qa-specialist.md" '# Pi Tool Binding'
assert_not_contains "$h1/.claude/agents/browser-qa-specialist.md" '# Pi Tool Binding'
assert_contains "$h1/.config/opencode/agents/general-purpose.md" '# OpenCode Scope'
assert_contains "$h1/.pi/agent/agents/architecture-reviewer.md" 'display_name: "Architecture Reviewer"'
assert_file "$h1/.config/opencode/agents/architecture-reviewer.md"
assert_contains "$h1/.config/opencode/agents/architecture-reviewer.md" 'permissions: ['
assert_contains "$h1/.config/opencode/agents/architecture-reviewer.md" '{"action":"edit","resource":"*","effect":"deny"}'
assert_not_contains "$h1/.config/opencode/agents/architecture-reviewer.md" 'permission:'
assert_file "$h1/.config/opencode/agents/feature-implementer.md"
assert_not_contains "$h1/.config/opencode/agents/feature-implementer.md" '{"action":"edit","resource":"*","effect":"deny"}'
assert_file "$h1/.pi/agent/prompts/deep-code-review.md"
assert_file "$h1/.pi/agent/themes/violet-orbit.json"
assert_file "$h1/.config/opencode/commands/validate_pr_reviews.md"
assert_file "$h1/.claude/output-styles/visual-concise.md"
assert_file "$h1/.claude/hooks/visual-reminder.sh"
[ -x "$h1/.claude/hooks/visual-reminder.sh" ] || fail "Claude hook is not executable"
hook_out="$(printf '{}' | "$h1/.claude/hooks/visual-reminder.sh")"
[ -n "$hook_out" ] || fail "Claude visual-reminder hook emitted empty stdout"

# 4. Idempotent rerun and status check across all clients
rerun_out="$(./setup --all --styles --home "$h1")"
printf '%s\n' "$rerun_out" | grep -Fq 'written=0 ' || fail "rerun rewrote unchanged files: $rerun_out"
status_out="$(./setup status --home "$h1")"
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
mkdir -p "$h2/$SHARED_SKILLS_SUBPATH/commit"
printf '%s\n' "$UNMANAGED_MARKER" >"$h2/$SHARED_SKILLS_SUBPATH/commit/SKILL.md"
if shared_conflict_err="$(./setup --client pi --skill commit --home "$h2" 2>&1)"; then
	fail "installer overwrote unmanaged shared skill"
fi
printf '%s\n' "$shared_conflict_err" | grep -Fq 'unmanaged destination exists:' ||
	fail "unexpected shared conflict error: $shared_conflict_err"
assert_contains "$h2/$SHARED_SKILLS_SUBPATH/commit/SKILL.md" "$UNMANAGED_MARKER"

# 6. Sibling user file survives managed uninstall
printf '%s\n' "$UNMANAGED_MARKER" >"$h1/.claude/agents/user-custom.md"
./setup uninstall --home "$h1" >/dev/null
assert_file "$h1/.claude/agents/user-custom.md"
assert_contains "$h1/.claude/agents/user-custom.md" "$UNMANAGED_MARKER"
[ ! -e "$h1/.claude/skills/commit" ] || fail "uninstall left managed Claude skill behind"
[ ! -e "$h1/$SHARED_SKILLS_SUBPATH/commit" ] || fail "uninstall left managed shared skill behind"
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

# Pi copy mode must retain shared-directory ownership without touching legacy content.
h5="$TMP_DIR/h5"
mkdir -p "$h5/$LEGACY_PI_SKILLS_SUBPATH/user-custom"
printf '%s\n' "$UNMANAGED_MARKER" >"$h5/$LEGACY_PI_SKILLS_SUBPATH/user-custom/SKILL.md"
./setup --client pi --skill commit --copy --home "$h5" >/dev/null
[ -d "$h5/$SHARED_SKILLS_SUBPATH/commit" ] && [ ! -L "$h5/$SHARED_SKILLS_SUBPATH/commit" ] || fail "Pi --copy did not create shared directory"
shared_copy_status="$(./setup status --client pi --skill commit --copy --home "$h5")"
printf '%s\n' "$shared_copy_status" | grep -Fq 'pi: installed=1 stale=0 missing=0 unmanaged=0' ||
	fail "unexpected Pi copy status: $shared_copy_status"
./setup uninstall --client pi --home "$h5" >/dev/null
[ ! -e "$h5/$SHARED_SKILLS_SUBPATH/commit" ] || fail "uninstall left copied shared skill behind"
assert_contains "$h5/$LEGACY_PI_SKILLS_SUBPATH/user-custom/SKILL.md" "$UNMANAGED_MARKER"

# 8. Symlinked destination directory preserves logical path in status and blocks writes
h_sym="$TMP_DIR/h_sym"
ext_cmds="$TMP_DIR/external-commands"
mkdir -p "$h_sym/.config/opencode" "$ext_cmds"
printf '%s\n' "$UNMANAGED_MARKER" >"$ext_cmds/commit.md"
ln -s "$ext_cmds" "$h_sym/.config/opencode/commands"
sym_status="$(./setup status --client opencode --command commit --home "$h_sym")"
printf '%s\n' "$sym_status" | grep -Fq "unmanaged: $h_sym/.config/opencode/commands/commit.md" ||
	fail "status leaked resolved symlink path: $sym_status"
if sym_err="$(./setup --client opencode --command pr --home "$h_sym" 2>&1)"; then
	fail "installer traversed unmanaged symlinked parent directory"
fi
printf '%s\n' "$sym_err" | grep -Fq "unmanaged symlinked directory: $h_sym/.config/opencode/commands" ||
	fail "unexpected symlinked-parent error: $sym_err"
[ ! -e "$ext_cmds/pr.md" ] || fail "installer wrote into external symlink target"

# 9. Category pack install, interactive pack selection, and conflict guards
h_pack="$TMP_DIR/h_pack"
./setup --client opencode --pack delivery --pack architecture --home "$h_pack" >/dev/null
assert_symlink "$h_pack/.config/opencode/skills/commit"
[ ! -e "$h_pack/.config/opencode/skills/report-card" ] || fail "unselected review skill installed by delivery/architecture packs"
assert_file "$h_pack/.config/opencode/agents/architecture-designer.md"
assert_file "$h_pack/.config/opencode/agents/codebase-explorer.md"
[ ! -e "$h_pack/.config/opencode/agents/security-reviewer.md" ] || fail "unselected review role installed by delivery/architecture packs"
assert_file "$h_pack/.config/opencode/commands/criticalthink.md"
pack_status="$(./setup status --client opencode --pack delivery --pack architecture --home "$h_pack")"
printf '%s\n' "$pack_status" | grep -Fq 'opencode: installed=25 stale=0 missing=0 unmanaged=0' ||
	fail "unexpected pack status: $pack_status"

h_wiz="$TMP_DIR/h_wiz"
printf 'codex\nresearch\nn\nn\ny\n' | ./setup --interactive --home "$h_wiz" >/dev/null
assert_file "$h_wiz/.codex/agents/web-researcher.md"
assert_file "$h_wiz/.codex/agents/codebase-explorer.md"
[ ! -e "$h_wiz/.codex/skills/commit" ] || fail "research pack unexpectedly installed delivery skill"

if bad_pack_err="$(./setup --pack no-such-pack --home "$h_wiz" 2>&1)"; then
	fail "unknown pack ID unexpectedly succeeded"
fi
printf '%s\n' "$bad_pack_err" | grep -Fq 'unknown pack ID' ||
	fail "unexpected unknown-pack error: $bad_pack_err"
if mix_pack_err="$(./setup --all --pack delivery --home "$h_wiz" 2>&1)"; then
	fail "--all combined with --pack unexpectedly succeeded"
fi
printf '%s\n' "$mix_pack_err" | grep -Fq 'cannot combine --all with --pack' ||
	fail "unexpected --all/--pack conflict error: $mix_pack_err"

# 10. Imported config sets Pi client metadata; injected frontmatter and bad keys fail closed
import_file="$TMP_DIR/import.json"
cat >"$import_file" <<'EOF'
{
  "version": 1,
  "client_metadata": {
    "pi": {
      "extensions": true,
      "exclude_extensions": ["pi-nvim", "pi-subagents"]
    }
  },
  "models": {"opencode": {"categories": {"core": {"model": "example-provider/model-c"}}}}
}
EOF
./setup models import "$import_file" >/dev/null
rendered_browser="$(./setup render browser-qa-specialist --client pi)"
printf '%s\n' "$rendered_browser" | grep -Fq 'extensions: true' || fail "missing imported extensions"
printf '%s\n' "$rendered_browser" | grep -Fq 'exclude_extensions: ["pi-nvim", "pi-subagents"]' || fail "missing imported exclude_extensions"
./setup render codebase-explorer --client opencode | grep -Fq 'model: "example-provider/model-c"' ||
	fail "category model choice not rendered"
if ./setup render codebase-explorer --client opencode --no-config | grep -q '^model:'; then
	fail "--no-config still rendered a model"
fi
# A named config that does not exist must fail, not silently render every role without a model.
if ./setup render codebase-explorer --client opencode --config "$TMP_DIR/missing.json" >/dev/null 2>&1; then
	fail "missing --config file unexpectedly accepted"
fi
if ./setup --config "$TMP_DIR/missing.json" render codebase-explorer --client opencode >/dev/null 2>&1; then
	fail "missing --config before render unexpectedly accepted"
fi
# Root flags before the subcommand must reach it: a sandbox --home never touches the real config.
h_root="$TMP_DIR/h-root"
./setup --home "$h_root" models set --client claude --model "$TEST_MODEL" >/dev/null
assert_file "$h_root/.config/agents/config.json"
./setup --home "$h_root" render ci-watcher --client claude | grep -Fq "model: \"$TEST_MODEL\"" ||
	fail "--home before render ignored"
if ./setup models clear --client claude --role ci-watcher --home "$h_root" >/dev/null 2>&1; then
	fail "clear of a scope with nothing stored reported success"
fi
# Import merges client metadata key by key, like model fields.
meta_a="$TMP_DIR/meta-a.json"
meta_b="$TMP_DIR/meta-b.json"
printf '{"client_metadata":{"pi":{"extensions":true,"exclude_extensions":["ext-a"]}}}' >"$meta_a"
printf '{"client_metadata":{"pi":{"exclude_extensions":["ext-b"]}}}' >"$meta_b"
./setup models import "$meta_a" --home "$h_root" >/dev/null
./setup models import "$meta_b" --home "$h_root" >/dev/null
rendered_meta="$(./setup render ci-watcher --client pi --home "$h_root")"
printf '%s\n' "$rendered_meta" | grep -Fq 'extensions: true' || fail "metadata import dropped a key"
printf '%s\n' "$rendered_meta" | grep -Fq 'exclude_extensions: ["ext-b"]' || fail "metadata import did not update a key"
# A stored choice for a role the catalog dropped blocks renders, but `models` can still show and
# clear it, so the file never needs a hand edit.
stale_config="$XDG_CONFIG_HOME/agents/config.json"
python3 - "$stale_config" <<'PY'
import json, sys
path = sys.argv[1]
data = json.load(open(path))
data["models"].setdefault("pi", {}).setdefault("roles", {})["retired-role"] = {"thinking": "low"}
json.dump(data, open(path, "w"))
PY
if ./setup render codebase-explorer --client pi >/dev/null 2>&1; then
	fail "render ignored a choice for a removed role"
fi
./setup models show | grep -F 'retired-role' | grep -Fq 'not applied' || fail "show hid a stale choice"
./setup models clear --client pi --role retired-role >/dev/null
./setup render codebase-explorer --client pi >/dev/null || fail "clear did not repair a stale choice"

bad_import="$TMP_DIR/bad-import.json"
printf '{"models":{"pi":{"all":{"model":"x\\n---\\ninjected: true"}}}}' >"$bad_import"
if ./setup models import "$bad_import" >/dev/null 2>&1; then
	fail "model ID frontmatter injection unexpectedly succeeded"
fi
printf '{"role_appendices":{}}' >"$bad_import"
if ./setup models import "$bad_import" >/dev/null 2>&1; then
	fail "legacy overlay key unexpectedly accepted"
fi

# 10b. Interactive model editor writes only what the user typed
printf 'opencode\nrole\nweb-researcher\nexample-provider/model-d\n\n' | ./setup models edit >/dev/null
./setup render web-researcher --client opencode | grep -Fq 'model: "example-provider/model-d"' ||
	fail "interactive model choice not rendered"

# 11. Interactive quit leaves disk untouched and unknown ID fails closed
h4="$TMP_DIR/h4"
printf 'q\n' | ./setup --interactive --home "$h4" >/dev/null
[ ! -e "$h4" ] || fail "interactive quit created $h4"
if unknown_err="$(./setup --skill does-not-exist --home "$h4" 2>&1)"; then
	fail "unknown skill ID unexpectedly succeeded"
fi
printf '%s\n' "$unknown_err" | grep -Fq 'unknown skill ID' ||
	fail "unexpected unknown-skill error: $unknown_err"

# 12. Commit helper refuses direct commit on main for unowned origin
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
