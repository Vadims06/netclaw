#!/usr/bin/env python3
"""Deterministic evidence checks for spec 122 safety criteria.

This script validates:
- FR-004: lab-only enforcement rejects a non-allowlisted testbed.
- FR-005: astra-twin-mcp registration requires only lab-testbed input, not production creds.
- SC-003: astra-twin paths expose read-only tooling with no config-write calls.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class CheckFailure(RuntimeError):
    pass


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def check_fr004() -> list[str]:
    lines: list[str] = []
    with tempfile.TemporaryDirectory(prefix="astra-twin-fr004-") as td:
        tmp = Path(td)
        testbed = tmp / "testbed.yaml"
        allowlist = tmp / "allowlist.yaml"

        testbed.write_text(
            """
            devices:
              rogue:
                os: iosxe
                type: router
                credentials:
                  default:
                    username: user
                    password: pass
                connections:
                  cli:
                    protocol: ssh
                    ip: 203.0.113.10
            """.strip()
            + "\n",
            encoding="utf-8",
        )
        allowlist.write_text("hosts: []\ncidrs:\n  - 198.51.100.0/24\n", encoding="utf-8")

        env = os.environ.copy()
        env["LAB_ALLOWLIST"] = str(allowlist)
        proc = subprocess.run(
            [sys.executable, str(ROOT / "harness" / "assert_lab_only.py"), str(testbed)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

        require(proc.returncode != 0, "FR-004: lab-only assertion unexpectedly accepted non-lab testbed")
        combined = f"{proc.stdout}\n{proc.stderr}".lower()
        require("outside the lab allowlist" in combined, "FR-004: rejection reason did not mention allowlist")

        lines.append("FR-004 OK: assert_lab_only rejects non-allowlisted testbed with explicit allowlist error")
    return lines


def check_fr005() -> list[str]:
    lines: list[str] = []

    config = json.loads(read("config/openclaw.json"))
    server = config["mcpServers"]["astra-twin-mcp"]
    env_map = server.get("env", {})
    env_keys = sorted(env_map.keys())
    allowed_env_keys = {
        "PYATS_TESTBED",
        "ASTRA_TWIN_POLL_INTERVAL_SECONDS",
        "LAB_ALLOWLIST",
        "PYATS_MCP_PYTHON",
        "PYATS_MCP_SERVER_PATH",
    }
    require(set(env_keys).issubset(allowed_env_keys), f"FR-005: unexpected astra-twin-mcp env keys in config/openclaw.json: {env_keys}")

    combined = "\n".join(
        [read("mcp-servers/astra-twin-mcp/server.py"), read("mcp-servers/astra-twin-mcp/collector.py")]
    )
    forbidden_vars = [
        "NETCLAW_USERNAME",
        "NETCLAW_PASSWORD",
        "NETCLAW_ENABLE_PASSWORD",
        "PROD",
        "PRODUCTION",
    ]
    unexpected = [v for v in forbidden_vars if v in combined]
    require(not unexpected, f"FR-005: astra-twin-mcp code references forbidden credential/production markers: {unexpected}")

    lines.append("FR-005 OK: astra-twin-mcp is configured with only PYATS_TESTBED and no production credential vars")
    return lines


def check_sc003() -> list[str]:
    lines: list[str] = []

    collector = read("mcp-servers/astra-twin-mcp/collector.py")
    server_py = read("mcp-servers/astra-twin-mcp/server.py")
    ui_server = read("ui/netclaw-visual/server.js")

    call_names = set(re.findall(r"call_tool\(\s*['\"]([^'\"]+)['\"]", collector))
    require(call_names, "SC-003: no pyATS tool calls found in collector.py")
    allowed_calls = {"pyats_list_devices", "pyats_run_show_command"}
    require(call_names.issubset(allowed_calls), f"SC-003: collector calls non-read pyATS tools: {sorted(call_names - allowed_calls)}")

    forbidden_tool_refs = {"pyats_configure_device", "pyats_run_linux_command", "pyats_run_dynamic_test"}
    all_call_names = set(re.findall(r"call_tool\(\s*['\"]([^'\"]+)['\"]", f"{collector}\n{server_py}\n{ui_server}"))
    bad_refs = sorted(all_call_names.intersection(forbidden_tool_refs))
    require(not bad_refs, f"SC-003: found write-capable/unsafe tool calls: {bad_refs}")

    tool_defs = set(re.findall(r"@mcp\.tool\(\)\s+async\s+def\s+(\w+)\(", server_py))
    require(tool_defs == {"get_snapshot", "get_deltas", "get_status"}, f"SC-003: unexpected MCP tool surface: {sorted(tool_defs)}")

    lines.append(
        "SC-003 OK: collector uses read-only pyATS calls only and astra-twin-mcp tool surface is snapshot/deltas/status"
    )
    return lines


def main() -> int:
    try:
        output: list[str] = []
        output.extend(check_fr004())
        output.extend(check_fr005())
        output.extend(check_sc003())
        for line in output:
            print(line)
        print("PASS: FR-004/FR-005/SC-003 evidence checks completed")
        return 0
    except CheckFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
