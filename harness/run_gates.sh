#!/usr/bin/env bash
# run_gates.sh — deterministic, no-model back pressure for one loop iteration
# (spec 122-astra-live-digital-twin, loop.md).
#
# Frozen. Runs: Python import/compile check -> pytest tests/contract -> npm test (HUD) ->
# visual_verify.py (Playwright, only if the HUD is actually reachable — see below).
#
# Usage: harness/run_gates.sh <out-dir>
# Exit 0 = every applicable gate passed. Non-zero = at least one failed; see <out-dir>/*.log.

set -uo pipefail

OUT_DIR="${1:?Usage: run_gates.sh <out-dir>}"
mkdir -p "$OUT_DIR"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PLAYWRIGHT_PYTHON="${PLAYWRIGHT_PYTHON:-}"
if [[ -z "$PLAYWRIGHT_PYTHON" ]]; then
  if command -v python3.13 >/dev/null 2>&1 && python3.13 -c "import playwright" >/dev/null 2>&1; then
    PLAYWRIGHT_PYTHON="python3.13"
  else
    PLAYWRIGHT_PYTHON="python3"
  fi
fi

fail=0

echo "== Python import/compile check ==" | tee "$OUT_DIR/gates.log"
if ! python3 -m py_compile models/twin_schema.py mcp-servers/astra-twin-mcp/*.py harness/*.py \
    >>"$OUT_DIR/gates.log" 2>&1; then
  echo "FAIL: python compile check" | tee -a "$OUT_DIR/gates.log"
  fail=1
fi

echo "== pytest tests/contract ==" | tee -a "$OUT_DIR/gates.log"
if ! python3 -m pytest tests/contract -q >>"$OUT_DIR/gates.log" 2>&1; then
  echo "FAIL: pytest tests/contract" | tee -a "$OUT_DIR/gates.log"
  fail=1
fi

if [[ -f ui/netclaw-visual/package.json ]]; then
  echo "== npm test (ui/netclaw-visual) ==" | tee -a "$OUT_DIR/gates.log"
  if ! (cd ui/netclaw-visual && npm test) >>"$OUT_DIR/gates.log" 2>&1; then
    echo "FAIL: npm test" | tee -a "$OUT_DIR/gates.log"
    fail=1
  fi
fi

# visual_verify.py needs a running HUD to point at. Phase A/B iterations (no HUD twin routes
# yet) legitimately have nothing to screenshot — this gate is a no-op skip, not a failure,
# until Phase C's task first stands up /api/twin and /ws/twin. Once ASTRA_TWIN_HUD_URL (or the
# default localhost:$HUD_PORT) actually answers, this gate becomes mandatory again.
HUD_URL="${ASTRA_TWIN_HUD_URL:-http://localhost:${HUD_PORT:-3001}/}"
if curl -sf -o /dev/null --max-time 3 "$HUD_URL" 2>/dev/null; then
  echo "== visual_verify.py ($PLAYWRIGHT_PYTHON) ==" | tee -a "$OUT_DIR/gates.log"
  if ! "$PLAYWRIGHT_PYTHON" harness/visual_verify.py --out-dir "$OUT_DIR" --url "$HUD_URL" \
      >>"$OUT_DIR/gates.log" 2>&1; then
    echo "FAIL: visual_verify.py" | tee -a "$OUT_DIR/gates.log"
    fail=1
  fi
else
  echo "SKIP: visual_verify.py — $HUD_URL not reachable yet (expected before Phase C's HUD routes exist)" \
    | tee -a "$OUT_DIR/gates.log"
fi

exit $fail
