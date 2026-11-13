#!/usr/bin/env bash
set -euo pipefail

readonly VIEW_FIELDS='url,number,title,body,state,isDraft,mergeable,mergeStateStatus,reviewDecision,headRefName,baseRefName,headRefOid,commits,files,reviews,comments,statusCheckRollup'

usage() {
	cat >&2 <<'EOF'
Usage:
  github-pr.sh preflight
  github-pr.sh view [pr]
  github-pr.sh checks [pr]
  github-pr.sh create --confirm <title> <body-file> <base> <head>
  github-pr.sh edit --confirm <pr> <title> <body-file>
EOF
	exit 2
}

guard() {
	[[ ${1:-} == --confirm ]] || {
		echo 'error: mutation requires --confirm' >&2
		exit 1
	}
}

preflight() {
	local origin
	origin=$(git remote get-url origin)
	gh auth status
	gh repo view "$origin" --json nameWithOwner,defaultBranchRef,url
}

current_repo() {
	local origin
	origin=$(git remote get-url origin)
	gh repo view "$origin" --json nameWithOwner --jq '.nameWithOwner'
}

current_repo_url() {
	local origin
	origin=$(git remote get-url origin)
	gh repo view "$origin" --json url --jq '.url'
}

assert_pr_repo() {
	local url=$1 expected=${2%/} number
	number=${url#"$expected/pull/"}
	[[ $url == "$expected/pull/$number" && $number =~ ^[0-9]+$ ]] || {
		echo "error: PR URL does not match origin repository: $url" >&2
		return 1
	}
}

command=${1:-}
readonly command
[[ -n $command ]] || usage
shift

case $command in
preflight)
	[[ $# -eq 0 ]] || usage
	preflight
	;;
view)
	[[ $# -le 1 ]] || usage
	if [[ $# -eq 0 ]]; then gh pr view --json "$VIEW_FIELDS"; else gh pr view "$1" --json "$VIEW_FIELDS"; fi
	;;
checks)
	[[ $# -le 1 ]] || usage
	if [[ $# -eq 0 ]]; then gh pr checks --json name,bucket,state,workflow,link; else gh pr checks "$1" --json name,bucket,state,workflow,link; fi
	;;
create)
	guard "${1:-}"
	shift
	[[ $# -eq 4 ]] || usage
	preflight >/dev/null
	repo=$(current_repo)
	default=$(gh repo view "$repo" --json defaultBranchRef --jq '.defaultBranchRef.name')
	[[ $4 != "$default" ]] || {
		echo "error: refusing PR from default branch: $4" >&2
		exit 1
	}
	gh pr create --title "$1" --body-file "$2" --base "$3" --head "$4"
	;;
edit)
	guard "${1:-}"
	shift
	[[ $# -eq 3 ]] || usage
	preflight >/dev/null
	repo_url=$(current_repo_url)
	url=$(gh pr view "$1" --json url --jq '.url')
	assert_pr_repo "$url" "$repo_url"
	gh pr edit "$1" --title "$2" --body-file "$3"
	;;
*) usage ;;
esac
