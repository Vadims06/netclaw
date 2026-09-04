#!/usr/bin/env bash
# astra_agent.sh — AGENT_CMD for loop/ralph.sh (spec 122-astra-live-digital-twin).
#
# Wraps OpenAI's Codex CLI (`codex exec`) so ralph.sh's maker and checker processes run as
# Astra Twin, an OpenAI-backed identity, rather than Claude. Reads its prompt from stdin,
# exactly like the `claude -p` invocation this replaces — codex exec does the same when no
# [PROMPT] argument is given (research.md R1).
#
# IMPORTANT (discovered running iteration 0): codex exec does NOT authenticate from an
# OPENAI_API_KEY env var at invocation time. It needs a one-time `codex login --with-api-key`
# that persists a session under $CODEX_HOME/auth.json; absent that, it falls back to whatever
# ChatGPT-account login already exists in $CODEX_HOME (default ~/.codex/), which on this host is
# the OPERATOR's own personal login used across other, unrelated projects — reusing it here is
# both wrong (a "distinct OpenAI-backed identity," spec.md User Story 3, should not literally be
# the operator's own account) and fragile (that session's refresh token had already gone stale
# from unrelated use elsewhere, which is what actually broke iteration 0). Astra Twin gets its
# own isolated CODEX_HOME, logged in once with the API key from .env, completely separate from
# the operator's ~/.codex/.
#
# Frozen (see specs/122-astra-live-digital-twin/plan.md, loop.md). Not run directly — ralph.sh
# invokes it as $AGENT_CMD.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export CODEX_HOME="${CODEX_HOME:-$HOME/.openclaw/astra-twin/codex-home}"

if [[ ! -f "$CODEX_HOME/auth.json" ]]; then
  echo "FATAL: no Astra Twin codex session at \$CODEX_HOME/auth.json ($CODEX_HOME)." >&2
  echo "  One-time setup: grep -E '^OPENAI_API_KEY=' $REPO_ROOT/.env | cut -d= -f2- | \\" >&2
  echo "    CODEX_HOME=\"$CODEX_HOME\" codex login --with-api-key" >&2
  exit 1
fi

MODEL_ARGS=()
if [[ -n "${ASTRA_MODEL:-}" ]]; then
  MODEL_ARGS=(-m "$ASTRA_MODEL")
fi

exec codex exec \
  --full-auto \
  --sandbox workspace-write \
  -C "$REPO_ROOT" \
  "${MODEL_ARGS[@]}"
