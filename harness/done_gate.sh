#!/usr/bin/env bash
# done_gate.sh — passes only when every blocking FR/SC in spec.md has a corresponding entry
# in loop/state/verdicts.md (spec 122-astra-live-digital-twin, loop.md's "Done" stop condition).
#
# Frozen. This is a mechanical presence check, not a re-judgment of the checker's verdicts —
# it exists so "done" can never be asserted by a maker/checker pair simply forgetting to write
# an entry for a criterion. It is deliberately dumb: it does not evaluate whether the evidence
# a criterion cites is actually convincing, only that every criterion has SOME entry.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$REPO_ROOT/specs/122-astra-live-digital-twin/spec.md"
VERDICTS="$REPO_ROOT/loop/state/verdicts.md"

[[ -f "$SPEC" ]] || { echo "ERROR: spec.md not found at $SPEC" >&2; exit 1; }
[[ -f "$VERDICTS" ]] || { echo "ERROR: verdicts.md not found — no iteration has run yet" >&2; exit 1; }

# FR-### and SC-### ids as they appear in spec.md's own headings (e.g. "- **FR-001**: ...").
mapfile -t CRITERIA < <(grep -oE '\*\*(FR|SC)-[0-9]+\*\*' "$SPEC" | tr -d '*' | sort -u)

if [[ ${#CRITERIA[@]} -eq 0 ]]; then
  echo "ERROR: no FR-/SC- criteria found in spec.md — refusing to report done against nothing" >&2
  exit 1
fi

missing=()
for id in "${CRITERIA[@]}"; do
  if ! grep -q -- "$id" "$VERDICTS"; then
    missing+=("$id")
  fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "NOT DONE — missing evidence for: ${missing[*]}" >&2
  exit 1
fi

echo "DONE — all ${#CRITERIA[@]} criteria (${CRITERIA[*]}) have evidence in $VERDICTS"
exit 0
