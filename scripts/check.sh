#!/usr/bin/env bash
# Fail-closed repository validation suite executed locally (`make check`) and
# on pushed tips via `.githooks/pre-push.d/20-repo-checks`.
set -euo pipefail

SKIP_GITLEAKS=0
if [ "${1:-}" = "--skip-gitleaks" ]; then
	SKIP_GITLEAKS=1
	shift
fi
if [ "$#" -gt 0 ]; then
	echo >&2 "usage: check.sh [--skip-gitleaks]"
	exit 2
fi

REPO_ROOT="$(cd "$(git rev-parse --show-toplevel)" && pwd -P)"
cd "$REPO_ROOT"

# shellcheck source-path=SCRIPTDIR source=lib/checks.sh
. "$REPO_ROOT/scripts/lib/checks.sh"

REQUIRED_TOOLS=(
	python3
	git
	shellcheck
	shfmt
	pyright
	lizard
	semgrep
	markdownlint-cli2
	gitleaks
)

for tool in "${REQUIRED_TOOLS[@]}"; do
	if ! command -v "$tool" >/dev/null 2>&1; then
		echo >&2 "❌ check: required tool missing on PATH: $tool"
		exit 1
	fi
done

echo "==> Personal leakage guard"
./scripts/personal-scan.sh

files_list="$(mktemp "${TMPDIR:-/tmp}/repo-check-files.XXXXXX")"
cleanup() {
	case "$files_list" in
	*/repo-check-files.*) rm -f -- "$files_list" ;;
	esac
}
trap cleanup EXIT

git ls-files -z --cached --others --exclude-standard >"$files_list"
reset_classified_lists
while IFS= read -r -d '' path; do
	[ -L "$path" ] && continue
	[ -f "$path" ] || continue
	classify_repo_path "$path"
done <"$files_list"

echo "==> JSON syntax check"
run_json_checks

echo "==> Shellcheck and shfmt"
run_shell_checks

echo "==> Markdown lint"
if [ "${#CHECK_MD_FILES[@]}" -gt 0 ]; then
	md_args=()
	for path in "${CHECK_MD_FILES[@]}"; do
		md_args+=(":$path")
	done
	markdownlint-cli2 --no-globs "${md_args[@]}"
fi

echo "==> Python strict type check, complexity, and SAST"
run_python_checks
run_lizard_checks
run_semgrep_checks "$REPO_ROOT/.githooks/lib/semgrep"

if [ "$SKIP_GITLEAKS" -eq 0 ]; then
	echo "==> Gitleaks repository history check"
	gl_out="$(gitleaks git --config .githooks/lib/gitleaks.toml --redact --no-banner --log-level warn . 2>&1)" || {
		printf '%s\n' "$gl_out" >&2
		exit 1
	}
	if printf '%s\n' "$gl_out" | grep -qE '(^|[[:space:]])ERR([[:space:]]|$)'; then
		printf '%s\n' "$gl_out" >&2
		echo >&2 "❌ check: gitleaks reported an error while scanning"
		exit 1
	fi
fi

if [ -e ./setup ]; then
	if [ ! -x ./setup ]; then
		echo >&2 "❌ check: ./setup exists but is not executable"
		exit 1
	fi
	echo "==> Catalog validation"
	./setup validate
fi

if [ "${#CHECK_SKILL_TESTS[@]}" -gt 0 ]; then
	echo "==> Skill script tests"
	for t in "${CHECK_SKILL_TESTS[@]}"; do
		bash -- "$t"
	done
fi

if [ -e ./scripts/dogfood.sh ]; then
	if [ ! -x ./scripts/dogfood.sh ]; then
		echo >&2 "❌ check: ./scripts/dogfood.sh exists but is not executable"
		exit 1
	fi
	echo "==> Clean-room dogfooding suite"
	./scripts/dogfood.sh
fi

echo "✅ All repository checks passed"
