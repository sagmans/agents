#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
readonly script_dir
readonly github_pr="$script_dir/../../github/scripts/github-pr.sh"

[[ -f $github_pr ]] || {
	echo "error: github skill script not found: $github_pr" >&2
	exit 1
}

exec bash "$github_pr" "$@"
