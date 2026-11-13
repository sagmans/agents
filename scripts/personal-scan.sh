#!/usr/bin/env bash
# Fail closed when private machine paths, internal issue keys, personal provider
# IDs, or private repo references appear in tracked, untracked, or staged text.
set -euo pipefail

MODE="repo"
if [ "${1:-}" = "--staged" ]; then
	MODE="staged"
	shift
fi
if [ "$#" -gt 0 ]; then
	echo >&2 "usage: personal-scan.sh [--staged]"
	exit 2
fi

command -v python3 >/dev/null 2>&1 || {
	echo >&2 "❌ personal-scan: python3 missing"
	exit 1
}

REPO_ROOT="$(cd "$(git rev-parse --show-toplevel)" && pwd -P)"
cd "$REPO_ROOT"

# Split literal tokens across shell strings so this scanner never triggers a
# false positive against itself while still enforcing exact patterns.
BANNED_REGEX="("
BANNED_REGEX+="/Us""ers/"
BANNED_REGEX+="|/ho""me/dev"
BANNED_REGEX+="|tail""scale|\.ts\.net"
BANNED_REGEX+="|linear""\.app"
BANNED_REGEX+="|AS""G-[0-9]+"
BANNED_REGEX+="|assag""man"
BANNED_REGEX+="|qwen-token""-plan/"
BANNED_REGEX+="|(^|[^A-Za-z0-9_])za""i/"
BANNED_REGEX+="|(^|[^A-Za-z0-9_])xa""i/"
BANNED_REGEX+="|openai/gpt-5\.6""-sol"
BANNED_REGEX+="|poteto""-agent"
BANNED_REGEX+="|pi-startup-""profiler"
BANNED_REGEX+="|agents""box"
BANNED_REGEX+="|pony""tail"
BANNED_REGEX+="|her""dr"
BANNED_REGEX+="|source/""me([^A-Za-z0-9_]|$)"
BANNED_REGEX+="|(^|[^A-Za-z0-9_])do""tf([^A-Za-z0-9_]|$)"
BANNED_REGEX+="|ai-""files"
BANNED_REGEX+=")"

is_skipped_path() {
	case "$1" in
	.githooks/pre-push.d/90-* | .githooks/commit-msg.d/90-* | *.pdf)
		return 0
		;;
	esac
	return 1
}

if [ "$MODE" = "staged" ]; then
	index="${PROJECT_HOOK_INDEX_FILE:-${GIT_INDEX_FILE:-$(git rev-parse --git-path index)}}"
	paths_file="$(mktemp "${TMPDIR:-/tmp}/personal-scan-staged.XXXXXX")"
	cleanup_staged() {
		case "$paths_file" in
		*/personal-scan-staged.*) rm -f -- "$paths_file" ;;
		esac
	}
	trap cleanup_staged EXIT

	raw_file="$(mktemp "${TMPDIR:-/tmp}/personal-scan-raw.XXXXXX")"
	cleanup_all() {
		cleanup_staged
		case "$raw_file" in
		*/personal-scan-raw.*) rm -f -- "$raw_file" ;;
		esac
	}
	trap cleanup_all EXIT

	GIT_INDEX_FILE="$index" git diff --cached --raw -z --no-renames --diff-filter=ACM >"$raw_file"
	staged_paths=()
	while IFS= read -r -d '' meta && IFS= read -r -d '' path; do
		read -r _ mode _ <<<"$meta"
		case "$mode" in
		100644 | 100755) ;;
		*) continue ;;
		esac
		is_skipped_path "$path" && continue
		staged_paths+=("$path")
	done <"$raw_file"

	[ "${#staged_paths[@]}" -gt 0 ] || exit 0
	printf ':%s\n' "${staged_paths[@]}" >"$paths_file"
	GIT_INDEX_FILE="$index" python3 - "$BANNED_REGEX" "$paths_file" <<'PY'
import pathlib
import re
import subprocess
import sys

pattern = re.compile(sys.argv[1], re.IGNORECASE)
specs = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8").splitlines()
payload = "\n".join(specs).encode("utf-8") + b"\n"
proc = subprocess.Popen(
    ["git", "cat-file", "--batch"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
out, err = proc.communicate(payload, timeout=60)
if proc.returncode != 0:
    print(f"❌ personal-scan: git cat-file failed: {err.decode('utf-8', 'replace')}", file=sys.stderr)
    sys.exit(1)

idx = 0
failures = 0
for spec in specs:
    nl = out.find(b"\n", idx)
    if nl == -1:
        print(f"❌ personal-scan: truncated batch output for {spec}", file=sys.stderr)
        sys.exit(1)
    header = out[idx:nl].decode("utf-8", "replace")
    parts = header.split()
    if len(parts) < 3 or parts[1] == "missing":
        print(f"❌ personal-scan: cannot read staged object {spec}: {header}", file=sys.stderr)
        sys.exit(1)
    size = int(parts[2])
    start = nl + 1
    blob = out[start:start + size]
    idx = start + size + 1
    path = spec[1:]
    text = blob.replace(b"\x00", b"").decode("utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        match = pattern.search(line)
        if match:
            print(f"{path}:{lineno}: banned personal pattern '{match.group(0)}': {line.strip()[:120]}", file=sys.stderr)
            failures += 1
if failures:
    print(f"❌ personal-scan: {failures} match(es) of blocked personal/private references", file=sys.stderr)
    sys.exit(1)
PY
else
	files_file="$(mktemp "${TMPDIR:-/tmp}/personal-scan-repo.XXXXXX")"
	cleanup_repo() {
		case "$files_file" in
		*/personal-scan-repo.*) rm -f -- "$files_file" ;;
		esac
	}
	trap cleanup_repo EXIT

	git ls-files -z --cached --others --exclude-standard >"$files_file"
	python3 - "$BANNED_REGEX" "$files_file" <<'PY'
import pathlib
import re
import sys

pattern = re.compile(sys.argv[1], re.IGNORECASE)
raw_paths = pathlib.Path(sys.argv[2]).read_bytes().split(b"\x00")
failures = 0
for raw in raw_paths:
    if not raw:
        continue
    path = raw.decode("utf-8", errors="surrogateescape")
    if path.startswith((".githooks/pre-push.d/90-", ".githooks/commit-msg.d/90-")) or path.lower().endswith(".pdf"):
        continue
    p = pathlib.Path(path)
    if p.is_symlink() or not p.is_file():
        continue
    text = p.read_bytes().replace(b"\x00", b"").decode("utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        match = pattern.search(line)
        if match:
            print(f"{path}:{lineno}: banned personal pattern '{match.group(0)}': {line.strip()[:120]}", file=sys.stderr)
            failures += 1
if failures:
    print(f"❌ personal-scan: {failures} match(es) of blocked personal/private references", file=sys.stderr)
    sys.exit(1)
PY
fi
