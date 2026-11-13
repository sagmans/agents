# Inert MCP Configuration Examples

These templates provide starting structures for common Model Context Protocol
servers without shipping active credentials or auto-enabling external tools.

## Security Rules

| Rule | Why |
| --- | --- |
| Keep tokens in `${ENV_VAR}` placeholders | Prevents accidental secret commits or leakage |
| Pin exact package versions in local configs | Reduces supply-chain drift across updates |
| Scope tokens and databases to least privilege | Read-only tokens and roles limit blast radius |
| Store live configs outside the repository | Keeps machine paths and credentials private |

## Included Examples

- [github.json](examples/github.json) - GitHub API MCP server using `${GITHUB_PERSONAL_ACCESS_TOKEN}`
- [filesystem.json](examples/filesystem.json) - Scoped workspace access bound to `${WORKSPACE_DIR}`
- [postgres.json](examples/postgres.json) - Read-only PostgreSQL access via `${POSTGRES_READONLY_URL}`
- [fetch.json](examples/fetch.json) - Web fetch MCP reference server via `uvx`

## Local Setup

1. Copy the chosen JSON block into your client's ignored local MCP config.
2. Replace or verify pinned package versions before enabling the server.
3. Export required environment variables in your shell session instead of
   inlining literals in config files.
