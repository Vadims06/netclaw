#!/usr/bin/env bash
# astra_agent.sh — AGENT_CMD for loop/ralph.sh (spec 122-astra-live-digital-twin).
#
# Wraps OpenAI's Codex CLI (`codex exec`) so ralph.sh's maker and checker processes run as
# Astra Twin, an OpenAI-backed identity, rather than Claude. Reads its prompt from stdin,
# exactly like the `claude -p` invocation this replaces — codex exec does the same when no
# [PROMPT] argument is given (research.md R1).
#
# Frozen (see specs/122-astra-live-digital-twin/plan.md, loop.md). Not run directly — ralph.sh
# invokes it as $AGENT_CMD.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Load OPENAI_API_KEY from .env without sourcing the whole file (which may contain other
# variables ralph.sh's preflight explicitly requires to be ABSENT, e.g. production creds —
# this only extracts the one line it needs).
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  if [[ -f "$REPO_ROOT/.env" ]]; then
    OPENAI_API_KEY="$(grep -E '^OPENAI_API_KEY=' "$REPO_ROOT/.env" | head -1 | cut -d= -f2-)"
  fi
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "FATAL: OPENAI_API_KEY not set and not found in .env — refusing to run Astra Twin unauthenticated." >&2
  exit 1
fi
export OPENAI_API_KEY

MODEL_ARGS=()
if [[ -n "${ASTRA_MODEL:-}" ]]; then
  MODEL_ARGS=(-m "$ASTRA_MODEL")
fi

exec codex exec \
  --full-auto \
  --sandbox workspace-write \
  -C "$REPO_ROOT" \
  "${MODEL_ARGS[@]}"
