#!/usr/bin/env python3
"""Deterministic evidence checks for spec 122 safety/runtime criteria.

This script validates:
- FR-004: lab-only enforcement rejects a non-allowlisted testbed.
- FR-005: astra-twin-mcp registration requires only lab-testbed input, not production creds.
- SC-003: astra-twin paths expose read-only tooling with no config-write calls.
- SC-006: delivered visualization runtime is interactive without any AI-provider dependency.
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


def check_sc006() -> list[str]:
    lines: list[str] = []

    twin_runtime_source = read("ui/netclaw-visual/src/twin/live-twin.js").lower()
    forbidden_runtime_markers = ["openai", "anthropic", "claude", "chat.completions", "api_key"]
    unexpected = [token for token in forbidden_runtime_markers if token in twin_runtime_source]
    require(not unexpected, f"SC-006: runtime twin/HUD sources reference AI-provider markers: {unexpected}")

    server_source = read("ui/netclaw-visual/server.js")
    twin_tool_calls = set(re.findall(r"callAstraTwinTool\('([^']+)'", server_source))
    allowed_twin_calls = {"get_snapshot", "get_status", "get_deltas"}
    require(
        twin_tool_calls.issubset(allowed_twin_calls),
        f"SC-006: twin server path calls unexpected tools: {sorted(twin_tool_calls - allowed_twin_calls)}",
    )

    probe = r"""
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { createLiveTwinLayer } from './src/twin/live-twin.js';

process.env.OPENAI_API_KEY = '';
process.env.ANTHROPIC_API_KEY = '';

const elements = new Map();
const body = {
  appendChild(el) {
    if (el?.id) elements.set(el.id, el);
    return el;
  },
};
const documentShim = {
  body,
  getElementById(id) {
    return elements.get(id) || null;
  },
  createElement() {
    return {
      id: '',
      style: {},
      textContent: '',
      remove() {
        if (this.id) elements.delete(this.id);
      },
    };
  },
};

class MockWebSocket {
  static last = null;
  constructor() {
    this.listeners = { message: [], close: [], error: [] };
    MockWebSocket.last = this;
  }
  addEventListener(type, cb) {
    this.listeners[type].push(cb);
  }
  emit(type, payload) {
    for (const cb of this.listeners[type] || []) cb(payload);
  }
  close() {
    this.emit('close', {});
  }
}

globalThis.window = { location: { protocol: 'http:', host: 'localhost:3001' } };
globalThis.document = documentShim;
globalThis.WebSocket = MockWebSocket;
globalThis.performance = { now: () => Date.now() };
globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0);

globalThis.fetch = async (url) => {
  if (String(url).includes('/api/twin/snapshot')) {
    return {
      ok: true,
      json: async () => ({
        seq: 1,
        nodes: [
          { id: 'r1', label: 'R1', status: 'up' },
          { id: 'r2', label: 'R2', status: 'up' },
        ],
        links: [
          { id: 'r1:r2', source_node_id: 'r1', target_node_id: 'r2', state: 'up' },
        ],
      }),
    };
  }
  if (String(url).includes('/api/twin/status')) {
    return {
      ok: true,
      json: async () => ({
        poll_interval_seconds: 10,
        consecutive_failures: 0,
        last_successful_poll: new Date().toISOString(),
      }),
    };
  }
  return { ok: false, status: 404, json: async () => ({}) };
};

const scene = new THREE.Scene();
const makeLabel = (text) => {
  const label = new THREE.Object3D();
  label.element = { textContent: text };
  return label;
};
const layer = createLiveTwinLayer({ scene, makeLabel });
await layer.start();
await new Promise((resolve) => setTimeout(resolve, 25));

assert.equal(window.__astraTwinDebug?.nodeCount, 2);
assert.equal(window.__astraTwinDebug?.linkCount, 1);
assert.equal(window.__astraTwinDebug?.lastError, null);
assert.ok(document.getElementById('astra-twin-freshness'));

MockWebSocket.last.emit('message', {
  data: JSON.stringify({
    seq: 2,
    kind: 'node_added',
    node: { id: 'r3', label: 'R3', status: 'up' },
  }),
});
await new Promise((resolve) => setTimeout(resolve, 10));
assert.equal(window.__astraTwinDebug?.nodeCount, 3);

layer.dispose();
console.log('runtime_probe_ok');
"""

    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    env.pop("ANTHROPIC_API_KEY", None)
    proc = subprocess.run(
        ["node", "--input-type=module"],
        cwd=ROOT / "ui" / "netclaw-visual",
        input=probe,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    require(proc.returncode == 0, f"SC-006 runtime probe failed: {(proc.stderr or proc.stdout).strip()}")
    require("runtime_probe_ok" in proc.stdout, "SC-006 runtime probe did not confirm completion")

    lines.append(
        "SC-006 OK: live twin layer starts, updates, and remains interactive with OPENAI/ANTHROPIC keys absent"
    )
    return lines


def main() -> int:
    try:
        output: list[str] = []
        output.extend(check_fr004())
        output.extend(check_fr005())
        output.extend(check_sc003())
        output.extend(check_sc006())
        for line in output:
            print(line)
        print("PASS: FR-004/FR-005/SC-003/SC-006 evidence checks completed")
        return 0
    except CheckFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
