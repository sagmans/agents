#!/usr/bin/env bash
# Re-state the reply-form rule on every user turn.
#
# Claude Code adds UserPromptSubmit stdout to the model context right before it
# answers. The global instructions load once at session start, so standing
# brevity rules injected later can outweigh them; this short reminder gives the
# visual-first rule the same recency. Keep it brief: it costs tokens each turn.
set -euo pipefail

# Claude Code pipes the event JSON on stdin. Drain it so the writer never
# blocks on a full pipe; the reminder does not depend on the event content.
if [ ! -t 0 ]; then
	cat >/dev/null || true
fi

# Keep aligned with Visual-first communication in AGENTS.md.
REMINDER='Reply form: lead each substantive reply with a visual; choose its form, and prefer the richest form this surface renders inline. Brevity cuts words, never visuals. Prose alone only for a single fact or command, or when the user asks for plain text.'

printf '%s\n' "$REMINDER"
