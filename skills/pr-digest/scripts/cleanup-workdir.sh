#!/usr/bin/env bash
# Delete a pr-digest workdir left over from a digest run.
#
# WHY this exists: SKILL.md requires workdir deletion after the final answer,
# but without a bundled entry point agents either skip deletion (leaking
# private PR artifacts on the host) or improvise ad hoc rm -rf.
#
# WHY strict validation: the path comes from agent-held state and the
# operation is rm -rf. Only a real, non-symlink directory named pr-digest.*
# directly under the canonical ${TMPDIR:-/tmp} and owned by the current user
# may be removed. Everything else is refused so a wrong path can never widen
# the blast radius.
#
# Usage:
#   cleanup-workdir.sh <workdir>
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source-path=SCRIPTDIR source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

[ "$#" -eq 1 ] || die "usage: cleanup-workdir.sh <workdir>"

target=$1
# Refuse symlinks before any test that follows them.
[ -L "$target" ] && die "refusing symlink: $target"
[ -e "$target" ] || die "workdir does not exist: $target"
[ -d "$target" ] || die "not a directory: $target"
[ -O "$target" ] || die "refusing directory not owned by current user: $target"

base=$(basename "$target")
case "$base" in
pr-digest.*) ;;
*) die "refusing directory without pr-digest.* name: $target" ;;
esac

# Canonicalise both sides because macOS maps /tmp to /private/tmp and gives
# each user a random TMPDIR; comparing raw strings would false-refuse or
# false-accept. pwd -P is POSIX; the realpath command is not ubiquitous.
parent=$(cd "$(dirname "$target")" && pwd -P)
tmpdir=$(cd "${TMPDIR:-/tmp}" && pwd -P)
[ "$parent" = "$tmpdir" ] || die "refusing directory outside ${TMPDIR:-/tmp}: $target"

# The :? guards make an empty value abort instead of widening the removal.
rm -rf -- "${parent:?}/${base:?}"
printf 'pr-digest: removed workdir %s\n' "$parent/$base"
