#!/usr/bin/env python3
"""Enroll Astra Twin into a worktree-local test federation DB for spec 122 D1.

This script intentionally avoids ~/.openclaw and writes only inside the worktree
(or another caller-provided path) so loop runners with restricted writable roots
can still produce deterministic enrollment evidence.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_MCP = ROOT / "mcp-servers" / "protocol-mcp"
if str(PROTOCOL_MCP) not in sys.path:
    sys.path.insert(0, str(PROTOCOL_MCP))

from bgp.federation.manager import FederationManager  # noqa: E402
from bgp.federation.risk import RiskManager  # noqa: E402


def run(db_path: Path, base_dir: Path, risk_name: str, member_name: str) -> dict:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    base_dir.mkdir(parents=True, exist_ok=True)

    manager = FederationManager(db_path=str(db_path), base_dir=str(base_dir))
    risk = RiskManager(manager)

    risk.set_role("border", risk_name=risk_name, description="Astra Twin test federation")
    token = risk.issue_token(label=f"{risk_name}/{member_name}")

    cert_pem, _ = RiskManager._generate_self_signed("astra-twin")
    member_id = f"{risk_name}/{member_name}"
    risk.consume_token(
        token["token"],
        member_id=member_id,
        cert_pem=cert_pem,
        display_name="Astra Twin",
        node_type="agent",
        model_provider="openai",
    )

    row = manager._conn.execute(
        "SELECT member_id, display_name, node_type, model_provider, state "
        "FROM member WHERE member_id=?",
        (member_id,),
    ).fetchone()
    manager.close()
    if row is None:
        raise RuntimeError(f"member row missing after enrollment: {member_id}")

    result = dict(row)
    if result.get("model_provider") != "openai":
        raise RuntimeError(f"expected model_provider='openai', got {result.get('model_provider')!r}")

    return {
        "db_path": str(db_path),
        "base_dir": str(base_dir),
        "risk_name": risk_name,
        "member": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Enroll Astra Twin into a test federation DB")
    parser.add_argument(
        "--db-path",
        default="loop/state/astra-twin-test-federation.db",
        help="SQLite federation DB path (default: loop/state/astra-twin-test-federation.db)",
    )
    parser.add_argument(
        "--base-dir",
        default="/tmp/astra-twin-test-federation-home",
        help="Base directory for n2n auxiliary files (default: /tmp/astra-twin-test-federation-home)",
    )
    parser.add_argument("--risk-name", default="astra-test-risk")
    parser.add_argument("--member-name", default="astra-twin")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove existing DB file and base_dir before enrollment",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    base_dir = Path(args.base_dir)

    if args.reset:
        if db_path.exists():
            db_path.unlink()
        if base_dir.exists():
            shutil.rmtree(base_dir)

    result = run(db_path, base_dir, args.risk_name, args.member_name)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
