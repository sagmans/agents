"""Shared constants and client layout definitions for catalog management."""

from __future__ import annotations

import re

SUPPORTED_CLIENTS: tuple[str, ...] = (
    "pi",
    "opencode",
    "claude",
    "codex",
    "cursor",
    "gemini",
)

MANIFEST_FILENAME = ".agents-manifest.json"
MANIFEST_VERSION = 1

REG_FILE_MODE = 0o644
EXEC_FILE_MODE = 0o755
DIR_MODE = 0o755

MAX_ID_LENGTH = 64
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
SAFE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.*-]+$")

REQUIRED_ROLE_SECTIONS: tuple[str, ...] = (
    "Mission",
    "Use When",
    "Do Not Use When",
    "Required Inputs",
    "Preconditions and Blockers",
    "Workflow",
    "Evidence Requirements",
    "Decision Rules",
    "Security and Mutation Guardrails",
    "Handoff Contract",
    "Output Format",
    "Completion Criteria",
)

# Roles authorized to edit code directly without read-only OpenCode guardrails.
MUTATING_ENGINEER_ROLES: frozenset[str] = frozenset(
    {
        "bug-fix-engineer",
        "build-config-engineer",
        "data-migration-engineer",
        "documentation-engineer",
        "end-to-end-test-engineer",
        "feature-implementer",
        "integration-test-engineer",
        "observability-engineer",
        "performance-engineer",
        "refactoring-engineer",
        "security-test-engineer",
        "smoke-test-engineer",
        "static-analysis-engineer",
        "unit-test-engineer",
        "visual-regression-engineer",
    }
)

# Model fields are omitted from tracked role metadata so users bind models via `--model-map`.
PI_ALLOWED_METADATA_FIELDS: frozenset[str] = frozenset(
    {
        "tools",
        "skills",
        "color",
        "prompt_mode",
        "thinking",
        "max_turns",
        "isolation",
        "memory",
        "allowed_subagents",
        "session_dir",
        "disallowed_tools",
        "inherit_context",
    }
)

OPENCODE_ALLOWED_METADATA_FIELDS: frozenset[str] = frozenset(
    {
        "mode",
        "permissions",
        "tools",
        "temperature",
        "max_steps",
    }
)

VALID_PI_PROMPT_MODES: frozenset[str] = frozenset({"append", "replace"})
VALID_PI_THINKING_LEVELS: frozenset[str] = frozenset(
    {"off", "minimal", "low", "medium", "high", "xhigh", "max"}
)
VALID_PI_ISOLATIONS: frozenset[str] = frozenset({"off", "worktree"})
VALID_PI_MEMORY_SCOPES: frozenset[str] = frozenset({"project", "local", "user"})
VALID_OPENCODE_MODES: frozenset[str] = frozenset({"subagent", "primary", "all"})
VALID_PERMISSION_EFFECTS: frozenset[str] = frozenset({"allow", "ask", "deny"})

# Subdirectories relative to `--home` where each client expects catalog assets.
CLIENT_SUBPATHS: dict[str, dict[str, str]] = {
    "pi": {
        "skills": ".pi/agent/skills",
        "roles": ".pi/agent/agents",
        "prompts": ".pi/agent/prompts",
        "themes": ".pi/agent/themes",
    },
    "opencode": {
        "skills": ".config/opencode/skills",
        "roles": ".config/opencode/agents",
        "commands": ".config/opencode/commands",
    },
    "claude": {
        "skills": ".claude/skills",
        "roles": ".claude/agents",
        "styles": ".claude/output-styles",
        "hooks": ".claude/hooks",
    },
    "codex": {
        "skills": ".codex/skills",
        "roles": ".codex/agents",
    },
    "cursor": {
        "skills": ".cursor/skills",
        "roles": ".cursor/agents",
    },
    "gemini": {
        "skills": ".gemini/skills",
        "roles": ".gemini/agents",
    },
}

DEFAULT_OPENCODE_DENY_RULE: dict[str, str] = {
    "action": "edit",
    "resource": "*",
    "effect": "deny",
}
