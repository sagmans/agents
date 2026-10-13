# agents
Agents, skills, plugins, configurations and more

## Git hooks

Checks run in tracked local Git hooks instead of push/PR CI. Enable them once per clone:

```sh
sh scripts/setup-hooks.sh
```

Each hook runs your global Git hook of the same name first (if any), then this repository's checks:

- `pre-commit`: staged whitespace and conflict-marker check.
- `pre-push`: global hook only (no project checks yet).
