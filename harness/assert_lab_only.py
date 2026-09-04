#!/usr/bin/env python3
"""
assert_lab_only.py — refuse to proceed against anything but an explicitly allowlisted lab
testbed (spec 122-astra-live-digital-twin, loop.md Safety Envelope).

Frozen (see specs/122-astra-live-digital-twin/plan.md). Called two independent ways:
  1. loop/ralph.sh's preflight, against $PYATS_TESTBED, before any iteration is allowed to run.
  2. mcp-servers/astra-twin-mcp/server.py's own startup, so the deployed twin refuses to serve
     against a non-lab testbed even outside the build loop's lifetime (spec FR-004).

Usage: python3 harness/assert_lab_only.py <testbed.yaml>
Exit 0 = every device in the testbed is on the allowlist. Exit 1 = refused, reason on stderr.

Deliberately fails CLOSED: an empty or missing allowlist means nothing is permitted, not
everything.
"""

import ipaddress
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ALLOWLIST = os.path.join(HERE, "lab_allowlist.yaml")


def load_allowlist(path: str) -> tuple[set[str], list[ipaddress.IPv4Network | ipaddress.IPv6Network]]:
    if not os.path.isfile(path):
        return set(), []
    with open(path) as fh:
        data = yaml.safe_load(fh) or {}
    hosts = set(str(h).strip() for h in (data.get("hosts") or []))
    cidrs = []
    for c in data.get("cidrs") or []:
        try:
            cidrs.append(ipaddress.ip_network(str(c).strip(), strict=False))
        except ValueError as exc:
            print(f"ERROR: invalid CIDR in allowlist: {c!r} ({exc})", file=sys.stderr)
            sys.exit(1)
    return hosts, cidrs


def extract_device_hosts(testbed_path: str) -> dict[str, str]:
    """Returns {device_name: connection_host_or_ip}. Looks under every connection block
    (testbeds in this repo use varying connection key names: ssh, cli, defaults, ...) for the
    first 'ip' field found, since that's what pyATS actually dials."""
    with open(testbed_path) as fh:
        data = yaml.safe_load(fh) or {}

    devices = data.get("devices") or {}
    result: dict[str, str] = {}
    for name, cfg in devices.items():
        connections = cfg.get("connections") or {}
        host = None
        for _conn_name, conn_cfg in connections.items():
            if isinstance(conn_cfg, dict) and "ip" in conn_cfg:
                host = str(conn_cfg["ip"])
                break
        if host is None:
            print(f"ERROR: device {name!r} in {testbed_path} has no resolvable connection ip", file=sys.stderr)
            sys.exit(1)
        result[name] = host
    return result


def is_allowed(host: str, hosts: set[str], cidrs: list) -> bool:
    if host in hosts:
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False  # hostnames never match a CIDR
    return any(addr in net for net in cidrs)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: assert_lab_only.py <testbed.yaml>", file=sys.stderr)
        return 1

    testbed_path = sys.argv[1]
    if not os.path.isfile(testbed_path):
        print(f"ERROR: testbed file not found: {testbed_path}", file=sys.stderr)
        return 1

    allowlist_path = os.environ.get("LAB_ALLOWLIST", DEFAULT_ALLOWLIST)
    hosts, cidrs = load_allowlist(allowlist_path)

    if not hosts and not cidrs:
        print(
            f"ERROR: lab allowlist at {allowlist_path} is empty — refusing to resolve any "
            "testbed. Populate it with your actual CML lab devices before running the loop.",
            file=sys.stderr,
        )
        return 1

    device_hosts = extract_device_hosts(testbed_path)
    violations = {
        name: host for name, host in device_hosts.items() if not is_allowed(host, hosts, cidrs)
    }

    if violations:
        print(f"ERROR: testbed {testbed_path} contains devices outside the lab allowlist:", file=sys.stderr)
        for name, host in violations.items():
            print(f"  - {name} -> {host}", file=sys.stderr)
        return 1

    print(f"OK: all {len(device_hosts)} device(s) in {testbed_path} are lab-allowlisted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
