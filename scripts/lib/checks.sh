#!/usr/bin/env bash
# Shared classification, pinned-tool resolution, and static/security check
# helpers used by both scripts/check.sh and .githooks/pre-commit.d/20-staged-checks
# so local checks and commit gates enforce the exact same file rules and pins.

MISE_CONFIG_REL="mise.toml"
RUFF_CONFIG_REL="ruff.toml"
PYRIGHT_CONFIG_REL="pyrightconfig.json"

# Track tools already verified for a given mise.toml path in this process so
# preflight + per-language calls do not repeat mise/version checks.
CHECK_VERIFIED_PINS=""

# Arrays populated by classify_repo_path() for the caller:
#   CHECK_JSON_FILES, CHECK_SHELL_FILES, CHECK_MD_FILES,
#   CHECK_PY_FILES, CHECK_LIZARD_FILES, CHECK_CODE_FILES, CHECK_SKILL_TESTS
reset_classified_lists() {
	CHECK_JSON_FILES=()
	CHECK_SHELL_FILES=()
	CHECK_MD_FILES=()
	CHECK_PY_FILES=()
	CHECK_LIZARD_FILES=()
	CHECK_CODE_FILES=()
	CHECK_SKILL_TESTS=()
}

# Append global mise-managed tool directories (from $HOME, never from a working
# tree's mise.toml) so non-pinned global tools like lizard and markdownlint-cli2
# resolve reliably without shadowing repo-pinned tool versions.
append_global_mise_path() {
	local bin_paths=""
	command -v mise >/dev/null 2>&1 || return 0
	bin_paths="$(mise -C "$HOME" bin-paths 2>/dev/null | paste -sd: -)" || bin_paths=""
	if [ -n "$bin_paths" ]; then
		PATH="$PATH:$bin_paths"
		export PATH
	fi
}

# Map a logical check tool name to "mise_key|binary|version_sed".
pinned_tool_spec() {
	case "$1" in
	shellcheck) printf '%s\n' 'shellcheck|shellcheck|s/^version: *//p' ;;
	shfmt) printf '%s\n' 'shfmt|shfmt|1s/^v//p' ;;
	ruff) printf '%s\n' 'ruff|ruff|1s/^ruff //p' ;;
	pyright) printf '%s\n' 'npm:pyright|pyright|1s/^pyright //p' ;;
	*)
		echo >&2 "❌ tool pin: unsupported tool '$1'"
		return 1
		;;
	esac
}

# Parse exact X.Y.Z [tools] pins from mise.toml with stdlib tomllib so invalid
# TOML, missing tables, non-string pins, and missing entries all fail closed.
load_mise_pins() {
	local mise_file="$1"
	shift
	[ -f "$mise_file" ] || {
		echo >&2 "❌ tool pin: missing $mise_file"
		return 1
	}
	command -v python3 >/dev/null 2>&1 || {
		echo >&2 "❌ tool pin: python3 missing"
		return 1
	}
	python3 - "$mise_file" "$@" <<'PY'
import re
import sys
import tomllib

mise_path = sys.argv[1]
keys = sys.argv[2:]
semver_re = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")

try:
    with open(mise_path, "rb") as fh:
        data = tomllib.load(fh)
except Exception as exc:
    print(f"❌ tool pin: invalid TOML in {mise_path}: {exc}", file=sys.stderr)
    sys.exit(1)

tools = data.get("tools")
if not isinstance(tools, dict):
    print(f"❌ tool pin: missing [tools] table in {mise_path}", file=sys.stderr)
    sys.exit(1)

for key in keys:
    val = tools.get(key)
    if not isinstance(val, str):
        print(f"❌ tool pin: missing string pin for '{key}' in [tools] of {mise_path}", file=sys.stderr)
        sys.exit(1)
    if not semver_re.match(val):
        print(f"❌ tool pin: non-exact version '{val}' for '{key}' in {mise_path} (expected X.Y.Z)", file=sys.stderr)
        sys.exit(1)
    print(f"{key}={val}")
PY
}

require_pinned_tool() {
	local bin="$1"
	local expected="$2"
	local sed_expr="$3"
	local raw actual
	command -v "$bin" >/dev/null 2>&1 || {
		echo >&2 "❌ tool check: $bin missing (expected $expected; run: mise install)"
		return 1
	}
	if raw="$("$bin" --version 2>/dev/null)"; then
		actual="$(printf '%s\n' "$raw" | sed -n "$sed_expr" | sed -n '1p')"
	else
		actual=""
	fi
	if [ "$actual" != "$expected" ]; then
		echo >&2 "❌ tool check: $bin version mismatch: expected $expected, got ${actual:-unknown} (run: mise install)"
		return 1
	fi
}

# Resolve and verify exact versions of one or more pinned tools from <mise_file>
# in a single pass. Prepends exact tool@version mise directories ahead of PATH
# while ignoring the working directory's mise config so untrusted temporary
# snapshots and at_sha worktrees succeed even under MISE_PARANOID=1.
ensure_pinned_tools() {
	local mise_file="$1"
	shift
	[ "$#" -gt 0 ] || return 0

	local mise_keys=() bins=() seds=() pending=()
	local tool spec key bin sed_expr token
	for tool in "$@"; do
		token=" ${mise_file}:${tool} "
		case " $CHECK_VERIFIED_PINS " in
		*"$token"*) continue ;;
		esac
		spec="$(pinned_tool_spec "$tool")" || return 1
		IFS='|' read -r key bin sed_expr <<<"$spec"
		pending+=("$tool")
		mise_keys+=("$key")
		bins+=("$bin")
		seds+=("$sed_expr")
	done
	[ "${#pending[@]}" -gt 0 ] || return 0

	local pin_lines
	pin_lines="$(load_mise_pins "$mise_file" "${mise_keys[@]}")" || return 1

	local pins=() line
	while IFS= read -r line; do
		[ -n "$line" ] || continue
		pins+=("${line#*=}")
	done <<<"$pin_lines"

	local mise_specs=() i
	for ((i = 0; i < ${#pending[@]}; i++)); do
		mise_specs+=("${mise_keys[i]}@${pins[i]}")
	done

	if command -v mise >/dev/null 2>&1; then
		local ignored="${MISE_IGNORED_CONFIG_PATHS:+$MISE_IGNORED_CONFIG_PATHS:}$PWD"
		local bin_paths=""
		bin_paths="$(cd / && MISE_IGNORED_CONFIG_PATHS="$ignored" mise bin-paths "${mise_specs[@]}" 2>/dev/null | paste -sd: -)" || bin_paths=""
		if [ -n "$bin_paths" ]; then
			PATH="$bin_paths:$PATH"
			export PATH
		fi
	fi

	for ((i = 0; i < ${#pending[@]}; i++)); do
		require_pinned_tool "${bins[i]}" "${pins[i]}" "${seds[i]}" || return 1
		CHECK_VERIFIED_PINS="${CHECK_VERIFIED_PINS} ${mise_file}:${pending[i]}"
	done
}

classify_repo_path() {
	local path="$1"
	local lower
	lower="$(printf '%s' "$path" | tr '[:upper:]' '[:lower:]')"

	case "$lower" in
	.githooks/*.d/*)
		CHECK_SHELL_FILES+=("$path")
		CHECK_CODE_FILES+=("$path")
		return 0
		;;
	.githooks/* | scripts/setup-hooks)
		return 0
		;;
	esac

	case "$lower" in
	*.json)
		CHECK_JSON_FILES+=("$path")
		;;
	setup | *.sh)
		CHECK_SHELL_FILES+=("$path")
		CHECK_CODE_FILES+=("$path")
		case "$lower" in
		skills/*/scripts/*.test.sh | skills/*/scripts/test-*.sh)
			CHECK_SKILL_TESTS+=("$path")
			;;
		esac
		;;
	*.md | *.markdown)
		CHECK_MD_FILES+=("$path")
		;;
	*.py)
		CHECK_PY_FILES+=("$path")
		CHECK_LIZARD_FILES+=("$path")
		CHECK_CODE_FILES+=("$path")
		;;
	*.js | *.ts)
		CHECK_LIZARD_FILES+=("$path")
		CHECK_CODE_FILES+=("$path")
		;;
	esac
}

# Read NUL-separated repo-relative paths from stdin and classify regular files
# existing under <root_dir> (ignoring symlinks and directories).
classify_nul_paths() {
	local root_dir="$1"
	local path
	while IFS= read -r -d '' path; do
		[ -n "$path" ] || continue
		[ -L "$root_dir/$path" ] && continue
		[ -f "$root_dir/$path" ] || continue
		classify_repo_path "$path"
	done
}

run_json_checks() {
	[ "${#CHECK_JSON_FILES[@]}" -gt 0 ] || return 0
	command -v python3 >/dev/null 2>&1 || {
		echo >&2 "❌ json check: python3 missing"
		return 1
	}
	python3 - "${CHECK_JSON_FILES[@]}" <<'PY'
import json
import pathlib
import sys

failed = False
for raw in sys.argv[1:]:
    try:
        json.loads(pathlib.Path(raw).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"❌ invalid JSON in {raw}: {exc}", file=sys.stderr)
        failed = True
sys.exit(1 if failed else 0)
PY
}

run_shell_checks() {
	[ "${#CHECK_SHELL_FILES[@]}" -gt 0 ] || return 0
	ensure_pinned_tools "$MISE_CONFIG_REL" shellcheck shfmt
	shellcheck -x -- "${CHECK_SHELL_FILES[@]}"
	shfmt -d -- "${CHECK_SHELL_FILES[@]}"
}

run_python_checks() {
	[ "${#CHECK_PY_FILES[@]}" -gt 0 ] || return 0
	[ -s "$RUFF_CONFIG_REL" ] || {
		echo >&2 "❌ python check: missing or empty $RUFF_CONFIG_REL"
		return 1
	}
	[ -s "$PYRIGHT_CONFIG_REL" ] || {
		echo >&2 "❌ python check: missing or empty $PYRIGHT_CONFIG_REL"
		return 1
	}
	ensure_pinned_tools "$MISE_CONFIG_REL" ruff pyright
	ruff format --config "$RUFF_CONFIG_REL" --no-cache --check --diff -- "${CHECK_PY_FILES[@]}"
	ruff check --config "$RUFF_CONFIG_REL" --no-cache -- "${CHECK_PY_FILES[@]}"
	# Check the full project graph via pyrightconfig.json so cross-module type
	# breaks cannot slip past partial-file pre-commit checks, and check any
	# Python files located outside the configured include roots as well.
	pyright --project "$PYRIGHT_CONFIG_REL"
	local extra_py=() py_file
	for py_file in "${CHECK_PY_FILES[@]}"; do
		case "$py_file" in
		tools/* | skills/*) ;;
		*) extra_py+=("$py_file") ;;
		esac
	done
	if [ "${#extra_py[@]}" -gt 0 ]; then
		pyright --project "$PYRIGHT_CONFIG_REL" "${extra_py[@]}"
	fi
}

run_lizard_checks() {
	[ "${#CHECK_LIZARD_FILES[@]}" -gt 0 ] || return 0
	command -v lizard >/dev/null 2>&1 || {
		echo >&2 "❌ complexity check: lizard missing"
		return 1
	}
	lizard -C 15 -L 100 -w -- "${CHECK_LIZARD_FILES[@]}"
}

run_semgrep_checks() {
	local rules_dir="$1"
	[ "${#CHECK_CODE_FILES[@]}" -gt 0 ] || return 0
	command -v semgrep >/dev/null 2>&1 || {
		echo >&2 "❌ sast check: semgrep missing"
		return 1
	}
	if [ ! -d "$rules_dir" ]; then
		echo >&2 "❌ sast check: rules directory missing: $rules_dir"
		return 1
	fi
	shopt -s nullglob
	local rules=("$rules_dir"/*.yml "$rules_dir"/*.yaml)
	shopt -u nullglob
	if [ "${#rules[@]}" -eq 0 ]; then
		echo >&2 "❌ sast check: no rule files found in $rules_dir"
		return 1
	fi
	SEMGREP_SEND_METRICS=off SEMGREP_ENABLE_VERSION_CHECK=0 \
		semgrep scan \
		--config "$rules_dir" \
		--metrics=off \
		--disable-version-check \
		--severity ERROR \
		--error \
		--quiet \
		-- "${CHECK_CODE_FILES[@]}"
}
