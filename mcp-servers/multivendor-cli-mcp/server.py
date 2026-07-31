#!/usr/bin/env python3
"""Multivendor CLI Driver — MCP server entry point.

Spec 076 (roadmap R1). Contract:
specs/076-multivendor-cli-driver/contracts/mcp-tools.md

Gives NetClaw a general "connect to this device and ask it something" capability.
Before this server, all four device-facing servers were platform-bound — pyATS
(Cisco), junos-mcp (Juniper), gnmi-mcp (telemetry only), radkit-mcp
(cloud-relayed) — leaving ~90 platform families unreachable: MikroTik, VyOS,
SONiC, Nokia SR Linux, Extreme, Huawei, Dell, Ubiquiti EdgeOS.

ROUTING — this server is NOT a replacement for pyATS or junos-mcp:

  Cisco IOS/XE/NXOS/XR ......... pyATS       (far richer, ~2000 Genie parsers)
  Juniper Junos ................ junos-mcp   (PyEZ/NETCONF)
  Streaming telemetry .......... gnmi-mcp
  No direct reachability ....... radkit-mcp
  Everything else .............. THIS SERVER
  Cross-vendor normalized reads. THIS SERVER (read-only, even on the above)

Writes stay single-pathed per platform: this server REFUSES configuration change
on platforms owned by another server (FR-010). That is what keeps Principles I
and VIII enforceable — "verified by which tool?" must have one answer.

MUST run from this server's dedicated virtualenv. `napalm`/`netmiko` resolve
cryptography 49.x while the system interpreter carries 46.x, which NetClaw's
NCFED federation stack uses for X.509 issuance (spec 060). Running this outside
its venv risks the certificate stack, not this server (FR-030a, research R7).

STATUS: stub. Created early per analyze finding O1 — the tool implementations
land in later phases, but without an entry point none of them would be reachable
over MCP, so no story phase would be independently testable as an MCP capability.
Tools are registered here as they are implemented.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from policy.filter import Mode, evaluate  # noqa: E402
from policy.platform_deny import (  # noqa: E402
    PLATFORM_DENY,
    READ_ONLY_PREFIXES,
    is_modelled,
)

SERVER_NAME = "multivendor-cli"          # the `server` field in every result (FR-011)
SERVER_VERSION = "0.1.0"

mcp = FastMCP("multivendor-cli-mcp")


def write_enabled() -> bool:
    """Whether write tools are exposed at all (FR-022).

    Default is read-only. Write tools are ABSENT from tools/list rather than
    present-and-refusing, so an agent cannot even attempt a change unless an
    operator has deliberately opted in.
    """
    return os.environ.get("MULTIVENDOR_WRITE_ENABLED", "").lower() in ("1", "true", "yes")


def current_mode() -> Mode:
    return Mode.WRITE_ENABLED if write_enabled() else Mode.READ_ONLY


@mcp.tool()
def server_info() -> dict:
    """Report this server's identity, mode, and platform-policy coverage.

    Deliberately the first tool implemented: it lets an operator confirm the
    safety posture (read-only vs write-enabled) and see which platforms have
    explicit destructive-syntax modelling, before trusting it with a device.
    """
    return {
        "server": SERVER_NAME,
        "version": SERVER_VERSION,
        "mode": current_mode().value,
        "write_enabled": write_enabled(),
        "modelled_platforms": sorted(PLATFORM_DENY),
        "read_only_prefixes": sorted(READ_ONLY_PREFIXES),
        "routing": {
            "owned_elsewhere": {
                "cisco_ios": "pyats", "cisco_xe": "pyats",
                "cisco_nxos": "pyats", "cisco_xr": "pyats",
                "juniper_junos": "junos-mcp",
            },
            "note": (
                "Reads may overlap with the owning server; writes may not. "
                "Cross-vendor normalized reads are permitted everywhere, read-only."
            ),
        },
        "status": "stub — tool surface lands in spec 076 Phases 3-6",
    }


@mcp.tool()
def check_command_policy(command: str, platform: str | None = None) -> dict:
    """Evaluate a command against policy WITHOUT contacting any device.

    Lets an operator (or the agent) find out whether a command would be permitted
    before anything is attempted, and see which rule would reject it. Enforcement
    itself is server-side and unavoidable (FR-029); this only makes it inspectable.
    """
    verdict = evaluate(command, platform, current_mode())
    return {
        "server": SERVER_NAME,
        "command": command,
        "platform": platform,
        "mode": current_mode().value,
        "allowed": verdict.allowed,
        "rule": verdict.rule.value if verdict.rule else None,
        "denied_reason": verdict.denied_reason,
        "platform_modelled": is_modelled(platform),
        "note": (
            None if is_modelled(platform)
            else "platform has no explicit destructive-syntax model; "
                 "universal denylist still applies"
        ),
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
