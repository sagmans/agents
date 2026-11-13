#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
readonly script_dir
tmp=$(mktemp -d)
readonly tmp config=$tmp/signing.gitconfig
trap 'rm -rf "$tmp"' EXIT

# Missing SSH keys expose accidental inheritance without invoking a signing agent.
printf '[commit]\n\tgpgsign = true\n[gpg]\n\tformat = ssh\n' >"$config"

# Exercise real cleanup operations under hostile host policy, not source assertions.
GIT_CONFIG_GLOBAL=$config GIT_CONFIG_SYSTEM=$config GIT_CONFIG_NOSYSTEM=0 \
	bash "$script_dir/cleanup-after-merge.test.sh"
