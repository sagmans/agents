#!/usr/bin/env bash
set -euo pipefail

readonly DEFAULT_LOG_COUNT=10
readonly NON_INTERACTIVE_EDITOR=true
readonly NON_INTERACTIVE_PAGER=cat
readonly DISABLED_TERMINAL_PROMPT=0

# Paused operations must retain their messages rather than wait for an agent's TTY.
export GIT_EDITOR=$NON_INTERACTIVE_EDITOR
export GIT_SEQUENCE_EDITOR=$NON_INTERACTIVE_EDITOR
export GIT_PAGER=$NON_INTERACTIVE_PAGER
export GIT_TERMINAL_PROMPT=$DISABLED_TERMINAL_PROMPT

# A closed interface prevents this helper from becoming a second Git CLI.
usage() {
	cat >&2 <<'EOF'
Usage: git.sh summary | detail
       git.sh rebase-continue | merge-continue | cherry-pick-continue | revert-continue
Use native Git for other operations; use the commit skill for signed DCO commits.
EOF
	exit "${1:-2}"
}

[[ $# -eq 1 ]] || usage
case $1 in
help | -h | --help) usage 0 ;;
summary)
	git status --short --branch
	git diff --stat
	git diff --cached --stat
	git log -"$DEFAULT_LOG_COUNT" --oneline --decorate
	;;
detail)
	git status --branch
	git remote -v
	git log -"$DEFAULT_LOG_COUNT" --format=fuller --decorate --stat
	git diff
	git diff --cached
	;;
rebase-continue | merge-continue | cherry-pick-continue | revert-continue)
	exec git "${1%-continue}" --continue
	;;
*) usage ;;
esac
