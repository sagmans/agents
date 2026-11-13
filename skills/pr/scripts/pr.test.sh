#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
readonly script_dir
tmp=$(mktemp -d)
readonly tmp
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/skills/pr/scripts" "$tmp/skills/github/scripts"
cp "$script_dir/pr.sh" "$tmp/skills/pr/scripts/pr.sh"

cat >"$tmp/skills/github/scripts/github-pr.sh" <<'EOF'
#!/usr/bin/env bash
printf '<%s>\n' "$@"
EOF

output=$(bash "$tmp/skills/pr/scripts/pr.sh" create title body.md main feature/test)
readonly output
readonly expected=$'<create>\n<title>\n<body.md>\n<main>\n<feature/test>'
[[ $output == "$expected" ]]

rm "$tmp/skills/github/scripts/github-pr.sh"
if bash "$tmp/skills/pr/scripts/pr.sh" view >/dev/null 2>&1; then
	echo 'missing github script was ignored' >&2
	exit 1
fi

printf 'pr script tests passed\n'
