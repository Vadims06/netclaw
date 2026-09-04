#!/usr/bin/env python3
"""Fleet heartbeat health check via pyATS MCP server. Prints concise JSON summary."""
import json
import os
import subprocess
import sys

MCP_CALL = os.environ.get("MCP_CALL", "/home/johncapobianco/netclaw/scripts/mcp-call.py")
PYATS_PYTHON = os.environ.get("PYATS_PYTHON", "python3")
PYATS_MCP_SCRIPT = os.environ.get("PYATS_MCP_SCRIPT")
PYATS_TESTBED_PATH = os.environ.get("PYATS_TESTBED_PATH")

DEVICES = ["R1", "R2", "SW1", "SW2"]

def call(tool, args):
    cmd = [
        "python3", "-u", MCP_CALL,
        f"{PYATS_PYTHON} -u {PYATS_MCP_SCRIPT}",
        tool, json.dumps(args)
    ]
    env = os.environ.copy()
    env["PYATS_TESTBED_PATH"] = PYATS_TESTBED_PATH
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    try:
        raw = json.loads(out.stdout)
        text = raw["structuredContent"]["result"]
        return json.loads(text)
    except Exception as e:
        return {"error": f"parse_fail: {e}", "stdout": out.stdout[-500:], "stderr": out.stderr[-500:]}

def run_show(device, command):
    return call("pyats_run_show_command", {"device_name": device, "command": command})

def get_val(d, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d:
            d = d[k]
        else:
            return default
    return d

results = {}

for dev in DEVICES:
    entry = {"device": dev}

    # --- Reachability (via show version success = reachable) ---
    ver = run_show(dev, "show version")
    if ver.get("status") == "completed" or "parsed" in ver:
        entry["reachable"] = True
    else:
        entry["reachable"] = False
        entry["reach_error"] = ver.get("error") or ver.get("output", "")[:300]
        results[dev] = entry
        continue

    parsed = ver.get("parsed_output") or ver.get("output")
    # Try to extract uptime if parsed dict
    entry["uptime"] = None
    if isinstance(ver.get("output"), dict):
        pass

    # --- CPU ---
    cpu = run_show(dev, "show processes cpu sorted")
    entry["cpu_raw_ok"] = cpu.get("status") == "completed" or cpu.get("parsed") is not None
    cpu5min = None
    cpu_txt = cpu.get("output") if isinstance(cpu.get("output"), str) else json.dumps(cpu.get("output", ""))
    # Try parsed structured
    if isinstance(cpu.get("output"), dict):
        cpu5min = get_val(cpu, "output", "five_min_cpu_total")
    entry["cpu_5min"] = cpu5min
    entry["cpu_error"] = cpu.get("error")

    # --- Memory ---
    mem = run_show(dev, "show processes memory sorted")
    entry["mem_error"] = mem.get("error")

    plat = run_show(dev, "show platform resources")
    entry["platform_resources_error"] = plat.get("error")
    entry["platform_resources_raw"] = None
    if isinstance(plat.get("output"), str) and "Invalid input" not in plat.get("output", ""):
        entry["platform_resources_raw"] = plat.get("output")[:500]

    # --- Interfaces ---
    ipint = run_show(dev, "show ip interface brief")
    entry["ip_int_brief_ok"] = ipint.get("error") is None

    intf = run_show(dev, "show interfaces")
    entry["interfaces_ok"] = intf.get("error") is None
    entry["interfaces_raw_len"] = len(json.dumps(intf.get("output", "")))
    entry["_interfaces_full"] = intf

    entry["_ipint_full"] = ipint
    entry["_cpu_full"] = cpu
    entry["_mem_full"] = mem
    entry["_ver_full"] = ver

    # --- OSPF ---
    ospf = run_show(dev, "show ip ospf neighbor")
    entry["_ospf_full"] = ospf

    # --- BGP ---
    bgp = run_show(dev, "show ip bgp summary")
    entry["_bgp_full"] = bgp

    results[dev] = entry

# Dump everything to a file instead of stdout to avoid context flood; print a short pointer.
outpath = "/tmp/heartbeat_results.json"
with open(outpath, "w") as f:
    json.dump(results, f, indent=2, default=str)

print(f"WROTE {outpath}")
for dev, e in results.items():
    print(dev, "reachable=", e.get("reachable"))
