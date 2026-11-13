#!/usr/bin/env bash
# Shared classification and static/security check helpers used by both
# scripts/check.sh and .githooks/pre-commit.d/20-staged-checks so local checks
# and commit gates enforce the exact same file rules.

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

classify_repo_path() {
	local path="$1"
	local lower
	lower="$(printf '%s' "$path" | tr '[:upper:]' '[:lower:]')"

	case "$lower" in
	.githooks/pre-commit.d/* | .githooks/pre-push.d/*)
		CHECK_SHELL_FILES+=("$path")
		CHECK_CODE_FILES+=("$path")
		return 0
		;;
	.githooks/*)
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
	command -v shellcheck >/dev/null 2>&1 || {
		echo >&2 "❌ shell check: shellcheck missing"
		return 1
	}
	command -v shfmt >/dev/null 2>&1 || {
		echo >&2 "❌ shell check: shfmt missing"
		return 1
	}
	shellcheck -x -- "${CHECK_SHELL_FILES[@]}"
	shfmt -d -- "${CHECK_SHELL_FILES[@]}"
}

run_python_checks() {
	[ "${#CHECK_PY_FILES[@]}" -gt 0 ] || return 0
	command -v pyright >/dev/null 2>&1 || {
		echo >&2 "❌ python check: pyright missing"
		return 1
	}
	pyright -- "${CHECK_PY_FILES[@]}"
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
