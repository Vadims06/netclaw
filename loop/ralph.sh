#!/usr/bin/env bash
# ralph.sh — autonomous build loop for specs/122-astra-live-digital-twin
#
#   ./loop/ralph.sh              run to completion or budget
#   MAX_ITER=5 ./loop/ralph.sh   short run
#   DRY_RUN=1 ./loop/ralph.sh    preflight checks only, no agent calls
#
# One iteration = fresh agent process (Astra Twin, OpenAI-backed — see astra_agent.sh), one
# task, gates, independent check, commit. Context never accumulates. State lives in loop/state/
# and git. See specs/122-astra-live-digital-twin/loop.md for the full contract this implements.

set -uo pipefail

SPEC_DIR="specs/122-astra-live-digital-twin"
LOOP_DIR="loop"
STATE_DIR="$LOOP_DIR/state"
RUNS_DIR="$LOOP_DIR/runs"

MAX_ITER="${MAX_ITER:-30}"
STALL_LIMIT="${STALL_LIMIT:-3}"
DIFF_CAP="${DIFF_CAP:-400}"
DRY_RUN="${DRY_RUN:-0}"

# Astra Twin's own agent runtime — OpenAI's Codex CLI, not Claude (research.md R1).
AGENT_CMD="${AGENT_CMD:-$LOOP_DIR/astra_agent.sh}"

FROZEN_PATHS=(
  "mcp-servers/astra-twin-mcp/"
  "models/twin_schema.py"
  "harness/"
  "tests/contract/"
  "$SPEC_DIR/spec.md"
  "$SPEC_DIR/plan.md"
  "$SPEC_DIR/loop.md"
  "$LOOP_DIR/PROMPT.md"
  "$LOOP_DIR/CHECK.md"
  "$LOOP_DIR/ralph.sh"
  "$LOOP_DIR/astra_agent.sh"
  "$STATE_DIR/verdicts.md"
)

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
die() { printf '\n!! HALT: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- preflight --

preflight() {
  log "preflight"

  [[ -f "$SPEC_DIR/spec.md" ]] || die "spec not found at $SPEC_DIR"
  [[ -f "$LOOP_DIR/PROMPT.md" && -f "$LOOP_DIR/CHECK.md" ]] || die "prompt files missing"
  [[ -d harness && -d tests/contract ]] || die "back-pressure harness missing — generate it before looping"
  [[ -x "$AGENT_CMD" || "$AGENT_CMD" == codex* ]] || die "AGENT_CMD ($AGENT_CMD) not found/executable"

  # Never run in the primary checkout.
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not a git repo"
  if [[ "$(git rev-parse --git-dir)" == ".git" ]]; then
    die "refusing to run in the primary checkout — use a dedicated worktree (loop.md Safety Envelope)"
  fi

  # Lab-only testbed. This is the guard that keeps an unattended loop off production gear.
  [[ -n "${PYATS_TESTBED:-}" ]] || die "PYATS_TESTBED unset"
  [[ -f "$PYATS_TESTBED" ]] || die "PYATS_TESTBED does not exist: $PYATS_TESTBED"
  if ! python3 harness/assert_lab_only.py "$PYATS_TESTBED"; then
    die "testbed contains devices outside the lab allowlist (see harness/lab_allowlist.yaml)"
  fi

  # Production credentials must be absent, not merely unused.
  for v in NETCLAW_PROD_TOKEN PROD_DEVICE_PASSWORD NETBOX_TOKEN SERVICENOW_PASSWORD; do
    [[ -z "${!v:-}" ]] || die "$v is set — clear production credentials before looping"
  done

  # Astra Twin's own credential must be present — see astra_agent.sh.
  if [[ -z "${OPENAI_API_KEY:-}" ]] && ! grep -qE '^OPENAI_API_KEY=' .env 2>/dev/null; then
    die "OPENAI_API_KEY not set and not found in .env — Astra Twin cannot run unauthenticated"
  fi

  mkdir -p "$STATE_DIR" "$RUNS_DIR"
  for f in iterations.md verdicts.md debt.md memory.md; do
    [[ -f "$STATE_DIR/$f" ]] || echo "# ${f%.md}" > "$STATE_DIR/$f"
  done
  [[ -f "$LOOP_DIR/IMPLEMENTATION_PLAN.md" ]] || die "IMPLEMENTATION_PLAN.md missing — derive it from tasks.md first"

  log "preflight ok — testbed $(basename "$PYATS_TESTBED"), budget $MAX_ITER, agent $AGENT_CMD"
}

# -------------------------------------------------------------------- guards --

frozen_touched() {
  local changed; changed="$(git diff --name-only; git diff --cached --name-only)"
  for p in "${FROZEN_PATHS[@]}"; do
    if grep -qF -- "$p" <<<"$changed"; then echo "$p"; return 0; fi
  done
  return 1
}

diff_size() { git diff --numstat | awk '{a+=$1+$2} END {print a+0}'; }

# --------------------------------------------------------------------- steps --

run_maker() {
  local n="$1" out="$RUNS_DIR/$n/maker.log"
  log "iteration $n — maker (Astra Twin)"
  ITERATION="$n" $AGENT_CMD < "$LOOP_DIR/PROMPT.md" > "$out" 2>&1
  return $?
}

run_gates() {
  local n="$1" out="$RUNS_DIR/$n/gates.log"
  log "iteration $n — gates"
  ./harness/run_gates.sh "$RUNS_DIR/$n" > "$out" 2>&1
  return $?
}

run_checker() {
  # Separate process, fresh context, no sight of the maker's reasoning.
  local n="$1" out="$RUNS_DIR/$n/check.log"
  log "iteration $n — checker (Astra Twin)"
  ITERATION="$n" $AGENT_CMD < "$LOOP_DIR/CHECK.md" > "$out" 2>&1
  grep -qE '^VERDICT:[[:space:]]*ACCEPT' "$out"
}

done_check() {
  ./harness/done_gate.sh >/dev/null 2>&1
}

# ---------------------------------------------------------------------- main --

preflight
[[ "$DRY_RUN" == "1" ]] && { log "dry run complete"; exit 0; }

stall=0
start_head="$(git rev-parse HEAD)"

for (( n=0; n<MAX_ITER; n++ )); do
  mkdir -p "$RUNS_DIR/$n"
  before="$(git rev-parse HEAD)"
  iter_start=$SECONDS

  if ! run_maker "$n"; then
    log "iteration $n — maker exited non-zero"
  fi

  if bad="$(frozen_touched)"; then
    git checkout -- . ; git clean -fd
    die "iteration $n attempted to modify frozen path: $bad"
  fi

  lines="$(diff_size)"
  if (( lines > DIFF_CAP )); then
    log "iteration $n — diff $lines lines exceeds cap $DIFF_CAP, reverting"
    git checkout -- . ; git clean -fd
    echo "- iter $n: REJECT (diff cap: $lines lines)" >> "$STATE_DIR/iterations.md"
    (( ++stall >= STALL_LIMIT )) && die "stalled after $stall non-productive iterations"
    continue
  fi

  git diff > "$RUNS_DIR/$n/diff.patch"

  if ! run_gates "$n"; then
    log "iteration $n — gates failed, reverting"
    git checkout -- . ; git clean -fd
    echo "- iter $n: REJECT (gates) — see runs/$n/gates.log" >> "$STATE_DIR/iterations.md"
    (( ++stall >= STALL_LIMIT )) && die "stalled after $stall non-productive iterations"
    continue
  fi

  if ! run_checker "$n"; then
    log "iteration $n — checker rejected, reverting"
    git checkout -- . ; git clean -fd
    echo "- iter $n: REJECT (checker) — see runs/$n/check.log" >> "$STATE_DIR/iterations.md"
    (( ++stall >= STALL_LIMIT )) && die "stalled after $stall non-productive iterations"
    continue
  fi

  git add -A
  git commit -q -m "loop($n): $(head -1 "$RUNS_DIR/$n/task.txt" 2>/dev/null || echo 'iteration')"
  after="$(git rev-parse HEAD)"

  if [[ "$before" == "$after" ]]; then
    log "iteration $n — no net change"
    (( ++stall >= STALL_LIMIT )) && die "stalled after $stall non-productive iterations"
  else
    stall=0
    echo "- iter $n: ACCEPT ${after:0:8} ($(( SECONDS - iter_start ))s)" >> "$STATE_DIR/iterations.md"
  fi

  if done_check; then
    log "done gate passed at iteration $n"
    echo "- DONE at iteration $n" >> "$STATE_DIR/iterations.md"
    break
  fi
done

echo
log "loop finished"
git --no-pager log --oneline "$start_head..HEAD" | sed 's/^/  /'
echo
if done_check; then
  log "STATUS: complete — every blocking criterion has evidence in $STATE_DIR/verdicts.md"
else
  log "STATUS: incomplete — budget exhausted. Review $STATE_DIR/debt.md and $STATE_DIR/verdicts.md"
fi
