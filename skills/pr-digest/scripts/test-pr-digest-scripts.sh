#!/usr/bin/env bash
# Focused self-tests for reusable pr-digest shell helpers.
# These tests avoid network calls by stubbing gh where needed.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source-path=SCRIPTDIR source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

tmp="$(mktemp -d "${TMPDIR:-/tmp}/pr-digest-test.XXXXXX")"
top_level_workdir=""
cleanup_wrong_name=""
cleanup_symlink=""
cleanup() {
	rm -rf "$tmp"
	[ -z "$top_level_workdir" ] || rm -rf "$top_level_workdir"
	[ -z "$cleanup_wrong_name" ] || rm -rf "$cleanup_wrong_name"
	[ -z "$cleanup_symlink" ] || rm -f "$cleanup_symlink"
}
trap cleanup EXIT

assert_eq() {
	local expected="$1" actual="$2" label="$3"
	if [ "$expected" != "$actual" ]; then
		printf 'FAIL %s\nexpected: %s\nactual:   %s\n' "$label" "$expected" "$actual" >&2
		exit 1
	fi
}

assert_file() {
	[ -f "$1" ] || die "missing expected file: $1"
}

assert_eq 'owner repo 123' "$(parse_pr_url 'https://github.com/owner/repo/pull/123')" 'plain github url'
assert_eq 'owner repo 123' "$(parse_pr_url 'https://github.com/owner/repo/pull/123/files')" 'trailing path'
assert_eq 'owner repo 123' "$(parse_pr_url 'https://github.com/owner/repo/pull/123?src=copy#discussion_r1')" 'query and fragment'
assert_eq 'owner repo 123' "$(parse_pr_url 'https://ghe.example.test/owner/repo/pull/123/commits')" 'enterprise host'
if parse_pr_url 'not-a-pr-url' >/dev/null; then
	die 'non-url unexpectedly parsed'
fi

mkdir -p "$tmp/bin" "$tmp/work" "$tmp/work-invalid" "$tmp/work-pending"
cat >"$tmp/bin/gh" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
case "$*" in
  'auth status') exit 0 ;;
  'repo view --json nameWithOwner -q .nameWithOwner')
    if [ "${PR_DIGEST_TEST_NO_REPO:-0}" = "1" ]; then
      printf 'none of the git remotes correspond to a known GitHub host\n' >&2
      exit 1
    fi
    printf 'owner/repo\n' ;;
  'pr view 7 --repo owner/repo --json number,url,headRefName,baseRefName') printf '{"number":7,"url":"https://github.com/owner/repo/pull/7","headRefName":"feature","baseRefName":"main"}\n' ;;
  'pr view https://github.com/owner/repo/pull/123 --json number,url,headRefName,baseRefName') printf '{"number":123,"url":"https://github.com/owner/repo/pull/123","headRefName":"feature","baseRefName":"main"}\n' ;;
  pr\ view\ https://github.com/owner/repo/pull/123\ --json\ number,url,title,body,author,state,isDraft,baseRefName,headRefName,mergeable,reviewDecision,commits,files,additions,deletions,changedFiles,createdAt,updatedAt) printf '{"number":123,"url":"https://github.com/owner/repo/pull/123","title":"fix: picker","body":"Body","author":{"login":"dev"},"state":"OPEN","isDraft":false,"baseRefName":"main","headRefName":"feature","mergeable":"MERGEABLE","reviewDecision":"","commits":[{"oid":"abcdef123","messageHeadline":"fix: picker","messageBody":""}],"files":[{"path":"file.ts","additions":2,"deletions":1,"changeType":"MODIFIED"}],"additions":2,"deletions":1,"changedFiles":1,"createdAt":"2026-01-01T00:00:00Z","updatedAt":"2026-01-01T00:00:00Z"}\n' ;;
  'api repos/owner/repo/issues/123/comments --paginate --slurp') printf '[[{"html_url":"https://github.com/owner/repo/pull/123#issuecomment-1","user":{"login":"bot"},"body":"status note"},{"html_url":"https://github.com/owner/repo/pull/123#issuecomment-2","user":{"login":"Codacy[bot]"},"body":"Found 1 high risk\\rissue"}]]\n' ;;
  'api repos/owner/repo/pulls/123/reviews --paginate --slurp') printf '[[{"user":{"login":"reviewer"},"state":"CHANGES_REQUESTED","body":"Line1\\rLine2","html_url":"https://github.com/owner/repo/pull/123#pullrequestreview-1"}]]\n' ;;
  'api repos/owner/repo/pulls/123/comments --paginate --slurp') printf '[[]]\n' ;;
  api\ graphql\ -f\ owner=owner\ -f\ repo=repo\ -F\ pr=123*)
    if [ -n "${PR_DIGEST_TEST_THREADS_FILE:-}" ]; then
      cat "$PR_DIGEST_TEST_THREADS_FILE"
      exit 0
    fi
    printf '{"data":{"repository":{"pullRequest":{"reviewThreads":{"pageInfo":{"hasNextPage":false,"endCursor":null},"nodes":[{"id":"THREAD_open","isResolved":false,"isOutdated":false,"path":"file.ts","line":10,"originalLine":10,"diffSide":"RIGHT","comments":{"pageInfo":{"hasNextPage":false,"endCursor":null},"nodes":[{"id":"COMMENT_open","url":"https://github.com/owner/repo/pull/123#discussion_r1","body":"Use a safer guard","author":{"login":"reviewer"},"createdAt":"2026-01-01T00:00:00Z","outdated":false,"path":"file.ts","line":10,"originalLine":10,"diffHunk":"@@"}]}}]}}}}}\n' ;;
  api\ graphql\ -f\ thread=T_ok*) printf '{"data":{"resolveReviewThread":{"thread":{"id":"T_ok","isResolved":true}}}}\n' ;;
  api\ graphql\ -f\ thread=T_skip_current*) printf '{"data":{"resolveReviewThread":{"thread":{"id":"T_skip_current","isResolved":true}}}}\n' ;;
  api\ graphql\ -f\ thread=T_addressed*) printf '{"data":{"resolveReviewThread":{"thread":{"id":"T_addressed","isResolved":true}}}}\n' ;;
  api\ graphql\ -f\ thread=*)
    if [ -n "${PR_DIGEST_TEST_MARKER:-}" ]; then printf '%s\n' "$*" >> "$PR_DIGEST_TEST_MARKER"; fi
    printf '{"data":{"resolveReviewThread":{"thread":{"id":"THREAD","isResolved":true}}}}\n' ;;
  'pr diff https://github.com/owner/repo/pull/123 --patch') printf 'diff --git a/file.ts b/file.ts\n+new\n-old\n' ;;
  'pr checks https://github.com/owner/repo/pull/123 --json name,bucket,state,workflow,link,description,startedAt,completedAt') printf '[{"name":"CI","bucket":"pass","state":"SUCCESS","workflow":"test","link":"https://ci.example","description":"ok","startedAt":"","completedAt":""}]\n' ;;
  'pr checks 123 --json name,bucket,state,workflow,link,description,startedAt,completedAt') printf 'checks unavailable\n' >&2; exit 2 ;;
  'pr checks 124 --json name,bucket,state,workflow,link,description,startedAt,completedAt') printf '[{"name":"CI","bucket":"pending","state":"PENDING","workflow":"test","link":"https://ci.example","description":"waiting","startedAt":"","completedAt":""}]\n'; exit 8 ;;
  'pr checks 125 --json name,bucket,state,workflow,link,description,startedAt,completedAt') printf '{}\n[]\n'; exit 2 ;;
  *) printf 'unexpected gh args: %s\n' "$*" >&2; exit 99 ;;
esac
STUB
chmod +x "$tmp/bin/gh"

threads="$tmp/threads.json"
cat >"$threads" <<'JSON'
[
  {"id":"T_ok","isResolved":false,"isOutdated":true,"path":"file.sh","line":7,"originalLine":6},
  {"id":"T_skip_resolved","isResolved":true,"isOutdated":true,"path":"done.sh","line":1},
  {"id":"T_skip_current","isResolved":false,"isOutdated":false,"path":"current.sh","line":2},
  {"id":"T_addressed","isResolved":false,"isOutdated":false,"path":"addressed.ts","line":9}
]
JSON

out=$(PATH="$tmp/bin:$PATH" bash "$SCRIPT_DIR/resolve-outdated-threads.sh" "$threads" --confirm)
assert_eq '1' "$(printf '%s' "$out" | jq 'length')" 'resolver candidate count'
assert_eq 'T_ok' "$(printf '%s' "$out" | jq -r '.[0].id')" 'resolver id'
assert_eq 'file.sh' "$(printf '%s' "$out" | jq -r '.[0].path')" 'resolver path'
assert_eq '7' "$(printf '%s' "$out" | jq -r '.[0].line')" 'resolver line'
assert_eq 'OUTDATED_RESOLVED' "$(printf '%s' "$out" | jq -r '.[0].status')" 'resolver status'

triage="$tmp/triage-candidates.json"
cat >"$triage" <<'JSON'
[
  {"id":"T_skip_current","status":"STALE","evidence":"current head no longer contains the reviewed code path"},
  {"id":"T_addressed","status":"ADDRESSED","evidence":"valid feedback was fixed and validated before resolving"}
]
JSON
out=$(PATH="$tmp/bin:$PATH" bash "$SCRIPT_DIR/resolve-triaged-threads.sh" "$threads" "$triage" --confirm)
assert_eq '2' "$(printf '%s' "$out" | jq 'length')" 'triaged resolver candidate count'
assert_eq 'T_skip_current' "$(printf '%s' "$out" | jq -r '.[0].id')" 'triaged resolver stale id'
assert_eq 'current.sh' "$(printf '%s' "$out" | jq -r '.[0].path')" 'triaged resolver stale path'
assert_eq 'STALE_RESOLVED' "$(printf '%s' "$out" | jq -r '.[0].status')" 'triaged resolver stale status'
assert_eq 'T_addressed' "$(printf '%s' "$out" | jq -r '.[1].id')" 'triaged resolver addressed id'
assert_eq 'ADDRESSED_RESOLVED' "$(printf '%s' "$out" | jq -r '.[1].status')" 'triaged resolver addressed status'

PATH="$tmp/bin:$PATH" bash "$SCRIPT_DIR/fetch-checks.sh" "$tmp/work" 123 >/dev/null
assert_file "$tmp/work/checks.failed"
assert_file "$tmp/work/checks.stderr"
assert_file "$tmp/work/checks.json"
assert_eq '[]' "$(<"$tmp/work/checks.json")" 'failed checks JSON fallback'

PATH="$tmp/bin:$PATH" bash "$SCRIPT_DIR/fetch-checks.sh" "$tmp/work-pending" 124 >/dev/null
assert_file "$tmp/work-pending/checks.failed"
assert_eq 'CI' "$(jq -r '.[0].name' "$tmp/work-pending/checks.json")" 'nonzero checks preserve valid JSON'

PATH="$tmp/bin:$PATH" bash "$SCRIPT_DIR/fetch-checks.sh" "$tmp/work-invalid" 125 >/dev/null
assert_eq '[]' "$(<"$tmp/work-invalid/checks.json")" 'failed checks reject JSON streams'

top_level=$(PATH="$tmp/bin:$PATH" bash "$SCRIPT_DIR/../pr-digest.sh" 'https://github.com/owner/repo/pull/123' --keep-workdir)
top_level_workdir=$(printf '%s' "$top_level" | jq -r '.workdir')
report_data=$(printf '%s' "$top_level" | jq -r '.processed.reportData')
digest_input=$(printf '%s' "$top_level" | jq -r '.processed.digestInput')
assert_file "$report_data"
assert_file "$digest_input"
assert_eq 'THREAD_open' "$(jq -r '.threads.unresolved[0].id' "$report_data")" 'top-level unresolved thread id'
assert_eq 'PASS' "$(jq -r '.checks[0].status' "$report_data")" 'top-level check status'
assert_eq 'https://github.com/owner/repo/pull/123' "$(jq -r '.pr.url' "$report_data")" 'top-level pr url'
assert_eq 'REVIEW_SUMMARY' "$(jq -r '.comments.issue[1].status' "$report_data")" 'mixed-case bot review summary status'
assert_eq 'REVIEW_SUBMISSION' "$(jq -r '.comments.reviews[0].status' "$report_data")" 'review submission status'
! grep -q $'\r' "$digest_input" || die 'digest-input.md contains unescaped carriage return'

if PATH="$tmp/bin:$PATH" bash "$SCRIPT_DIR/resolve-pr.sh" --repo >/dev/null 2>&1; then
	die 'resolve-pr accepted option-like PR reference'
fi

# A bare PR number must be pinned to the current repository instead of letting
# gh resolve it against whatever repository the caller's cwd sits in.
assert_eq 'owner repo 7' "$(PATH="$tmp/bin:$PATH" bash "$SCRIPT_DIR/resolve-pr.sh" 7 2>/dev/null | jq -r '.owner + " " + .repo + " " + (.number | tostring)')" 'bare number pinned to current repo'

if PATH="$tmp/bin:$PATH" PR_DIGEST_TEST_NO_REPO=1 bash "$SCRIPT_DIR/resolve-pr.sh" 7 >/dev/null 2>"$tmp/no-repo.err"; then
	die 'bare number resolved without a determinable repository'
fi
grep -qi 'pass a full PR URL' "$tmp/no-repo.err" || die 'bare number failure lacks actionable guidance'

# Outdated-thread resolution mutates the remote PR, so a plain digest must stay
# read-only and only the flagged run may resolve threads.
outdated_threads="$tmp/outdated-threads.json"
cat >"$outdated_threads" <<'JSON'
{"data":{"repository":{"pullRequest":{"reviewThreads":{"pageInfo":{"hasNextPage":false,"endCursor":null},"nodes":[{"id":"T_outdated","isResolved":false,"isOutdated":true,"path":"file.ts","line":9,"originalLine":9,"diffSide":"RIGHT","comments":{"pageInfo":{"hasNextPage":false,"endCursor":null},"nodes":[]}}]}}}}}
JSON

readonly_marker="$tmp/readonly-mutations.log"
readonly_run=$(PR_DIGEST_TEST_THREADS_FILE="$outdated_threads" PR_DIGEST_TEST_MARKER="$readonly_marker" PATH="$tmp/bin:$PATH" bash "$SCRIPT_DIR/../pr-digest.sh" 'https://github.com/owner/repo/pull/123' 2>"$tmp/readonly.err")
assert_eq '0' "$(printf '%s' "$readonly_run" | jq '.resolutions.outdated | length')" 'plain digest resolves no outdated threads'
[ ! -e "$readonly_marker" ] || die 'plain digest mutated review threads'
grep -q -- '--resolve-outdated' "$tmp/readonly.err" || die 'plain digest does not advertise --resolve-outdated'
readonly_workdir=$(printf '%s' "$readonly_run" | jq -r '.workdir')
[ ! -e "$readonly_workdir" ] || die 'successful digest left its workdir behind'

cleanup_marker="$tmp/cleanup-mutations.log"
cleanup_run=$(PR_DIGEST_TEST_THREADS_FILE="$outdated_threads" PR_DIGEST_TEST_MARKER="$cleanup_marker" PATH="$tmp/bin:$PATH" bash "$SCRIPT_DIR/../pr-digest.sh" 'https://github.com/owner/repo/pull/123' --resolve-outdated 2>/dev/null)
assert_eq '1' "$(printf '%s' "$cleanup_run" | jq '.resolutions.outdated | length')" 'flagged digest resolves outdated threads'
assert_file "$cleanup_marker"

# A failing pipeline keeps its artifacts and prints the path that removes them.
failure_output=""
if failure_output=$(PR_DIGEST_TEST_NO_REPO=1 PATH="$tmp/bin:$PATH" bash "$SCRIPT_DIR/../pr-digest.sh" 7 2>&1 >/dev/null); then
	die 'bare number without a repository unexpectedly succeeded'
fi
failed_workdir=$(printf '%s\n' "$failure_output" | sed -n 's/^pr-digest: kept workdir //p' | head -1)
[ -n "$failed_workdir" ] || die 'failed pipeline did not print the retained workdir path'
[ -d "$failed_workdir" ] || die 'failed pipeline did not retain its workdir'
bash "$SCRIPT_DIR/cleanup-workdir.sh" "$failed_workdir" >/dev/null

cleanup_script="$SCRIPT_DIR/cleanup-workdir.sh"

if bash "$cleanup_script" >/dev/null 2>&1; then
	die 'cleanup accepted a missing argument'
fi
if bash "$cleanup_script" "$tmp/does-not-exist" >/dev/null 2>&1; then
	die 'cleanup accepted a nonexistent path'
fi

cleanup_wrong_name=$(mktemp -d "${TMPDIR:-/tmp}/pr-cleanup-test.XXXXXX")
if bash "$cleanup_script" "$cleanup_wrong_name" >/dev/null 2>&1; then
	die 'cleanup accepted a directory without a pr-digest.* name'
fi
[ -d "$cleanup_wrong_name" ] || die 'cleanup removed a refused wrong-name directory'

outside_workdir="$tmp/pr-digest.outside"
mkdir "$outside_workdir"
if bash "$cleanup_script" "$outside_workdir" >/dev/null 2>&1; then
	die 'cleanup accepted a pr-digest.* directory outside TMPDIR'
fi
[ -d "$outside_workdir" ] || die 'cleanup removed a refused outside-TMPDIR directory'

mkdir "$tmp/symlink-target"
cleanup_symlink="${TMPDIR:-/tmp}/pr-digest.symlink.$$"
ln -s "$tmp/symlink-target" "$cleanup_symlink"
if bash "$cleanup_script" "$cleanup_symlink" >/dev/null 2>&1; then
	die 'cleanup accepted a symlink'
fi
[ -L "$cleanup_symlink" ] || die 'cleanup removed a refused symlink'
[ -d "$tmp/symlink-target" ] || die 'cleanup followed a refused symlink'

bash "$cleanup_script" "$top_level_workdir" >/dev/null
[ ! -e "$top_level_workdir" ] || die 'cleanup left a valid workdir behind'

printf 'pr-digest script self-tests passed\n'
