#!/usr/bin/env python3
"""
parse_verdicts.py — verdict-aware criterion check for harness/done_gate.sh.

Frozen (spec 122-astra-live-digital-twin). Replaces a naive "does FR-001 appear anywhere in
verdicts.md" substring check (which cannot distinguish an ACCEPTed, evidenced criterion from
one merely *mentioned* inside a REJECT block) with an actual parse: a criterion only counts if
it is listed under "Criteria evidenced:" inside a block whose own "Verdict:" line is ACCEPT.

Usage: python3 harness/parse_verdicts.py <verdicts.md> <criterion-id> [<criterion-id> ...]
Prints, one per line, each id that is NOT satisfied. Exit 0 if all satisfied, 1 if some are
missing, 2 on any usage/parse error — done_gate.sh MUST treat exit 2 as a hard failure, not as
"nothing missing," since an uncaught Python exception also exits 1 by default and would otherwise
be silently indistinguishable from a legitimate "not yet done."
"""

import re
import sys


def satisfied_criteria(text: str) -> set[str]:
    blocks = re.split(r"(?=^## Iteration )", text, flags=re.MULTILINE)
    satisfied: set[str] = set()

    for block in blocks:
        verdict_match = re.search(r"^Verdict:\s*(ACCEPT|REJECT)", block, re.MULTILINE)
        if not verdict_match or verdict_match.group(1) != "ACCEPT":
            continue

        evidenced_match = re.search(
            r"^Criteria evidenced:\n(.*?)(?=^Criteria claimed but not evidenced:|^Concerns:|\Z)",
            block,
            re.MULTILINE | re.DOTALL,
        )
        if not evidenced_match:
            continue

        satisfied.update(
            m.group(0) for m in re.finditer(r"\b(?:FR|SC)-\d+\b", evidenced_match.group(1))
        )

    return satisfied


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: parse_verdicts.py <verdicts.md> <criterion-id> [...]", file=sys.stderr)
        return 2

    verdicts_path = sys.argv[1]
    criteria = sys.argv[2:]
    with open(verdicts_path) as fh:
        text = fh.read()

    satisfied = satisfied_criteria(text)
    missing = [c for c in criteria if c not in satisfied]

    for m in missing:
        print(m)

    return 1 if missing else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: parse_verdicts.py crashed: {exc}", file=sys.stderr)
        sys.exit(2)
