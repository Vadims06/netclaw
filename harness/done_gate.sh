#!/usr/bin/env bash
# done_gate.sh — passes only when every blocking FR/SC in spec.md has a corresponding entry
# in loop/state/verdicts.md (spec 122-astra-live-digital-twin, loop.md's "Done" stop condition).
#
# Frozen. This is a mechanical presence check, not a re-judgment of the checker's verdicts —
# it exists so "done" can never be asserted by a maker/checker pair simply forgetting to write
# an entry for a criterion. It is deliberately dumb about the QUALITY of evidence: it does not
# evaluate whether the evidence a criterion cites is actually convincing, only that every
# criterion appears under "Criteria evidenced:" inside a block whose own Verdict is ACCEPT (see
# harness/parse_verdicts.py) — it must NOT be dumb about ACCEPT vs REJECT: a criterion merely
# mentioned inside a rejected iteration's reasoning (e.g. "FR-006: not evidenced...") does not
# count. A bare substring search across the whole file cannot make that distinction and falsely
# reports done once every criterion has been mentioned anywhere, evidenced or not.

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

missing_output="$(python3 "$REPO_ROOT/harness/parse_verdicts.py" "$VERDICTS" "${CRITERIA[@]}")"
parser_exit=$?

# Exit 2 means the parser itself failed (usage error, crash) — this must NEVER be read as
# "nothing missing." Only 0 (all satisfied) and 1 (some missing, with names on stdout) are
# meaningful results.
if [[ $parser_exit -ge 2 ]]; then
  echo "ERROR: harness/parse_verdicts.py failed (exit $parser_exit) — refusing to report done:" >&2
  echo "$missing_output" >&2
  exit 1
fi

if [[ $parser_exit -eq 1 ]]; then
  mapfile -t missing <<< "$missing_output"
  echo "NOT DONE — missing ACCEPTed evidence for: ${missing[*]}" >&2
  exit 1
fi

echo "DONE — all ${#CRITERIA[@]} criteria (${CRITERIA[*]}) have evidence in $VERDICTS"
exit 0
