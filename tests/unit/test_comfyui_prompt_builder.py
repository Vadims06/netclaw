"""
Unit tests for prompt_builder.py's composition/summarization (spec 119 FR-002, Edge Cases,
research.md §6) — bounded length, role/count summarization, no per-interface exhaustive
enumeration.
"""

import sys
from pathlib import Path

skill_path = Path(__file__).parent.parent.parent / "workspace" / "skills" / "comfyui-topology-viz"
sys.path.insert(0, str(skill_path))

from prompt_builder import _MAX_PROMPT_CHARS, build_prompt  # noqa: E402
from topology_model import (  # noqa: E402
    Device,
    DeviceRole,
    Interface,
    Link,
    LinkEndpoint,
    SourceKind,
    TopologySnapshot,
)


def _snapshot(devices, links, source_kind=SourceKind.CML, source_label="test-lab"):
    return TopologySnapshot(
        snapshot_id="snap-1",
        source_kind=source_kind,
        source_label=source_label,
        devices=devices,
        links=links,
    )


def test_prompt_reflects_actual_device_roles_and_counts():
    devices = [
        Device(hostname="r1", role=DeviceRole.ROUTER),
        Device(hostname="r2", role=DeviceRole.ROUTER),
        Device(hostname="sw1", role=DeviceRole.SWITCH),
    ]
    snapshot = _snapshot(devices, [])
    prompt = build_prompt(snapshot)
    assert "2 routers" in prompt
    assert "1 switch" in prompt
    assert "test-lab" in prompt


def test_prompt_reflects_source_label():
    devices = [Device(hostname="fw1", role=DeviceRole.FIREWALL)]
    snapshot = _snapshot(devices, [], source_label="acme-nautobot")
    prompt = build_prompt(snapshot)
    assert "acme-nautobot" in prompt


def test_prompt_is_bounded_for_a_very_large_topology():
    devices = [Device(hostname=f"d{i}", role=DeviceRole.ROUTER) for i in range(500)]
    links = [
        Link(link_id=f"l{i}", endpoint_a=LinkEndpoint(f"d{i}"), endpoint_b=LinkEndpoint(f"d{i+1}"))
        for i in range(499)
    ]
    snapshot = _snapshot(devices, links)
    prompt = build_prompt(snapshot)
    assert len(prompt) <= _MAX_PROMPT_CHARS
    # Summarized as a count, never one line per device (interfaces aren't enumerated at all).
    assert "500 routers" in prompt
    assert "d499" not in prompt


def test_prompt_never_enumerates_interfaces():
    devices = [
        Device(
            hostname="r1",
            role=DeviceRole.ROUTER,
            interfaces=[Interface(name="GigabitEthernet0/1", parent_hostname="r1", ip_address="10.0.0.1")],
        )
    ]
    snapshot = _snapshot(devices, [])
    prompt = build_prompt(snapshot)
    assert "GigabitEthernet0/1" not in prompt
    assert "10.0.0.1" not in prompt


def test_connectivity_summary_distinguishes_unconnected_devices():
    devices = [Device(hostname="d1", role=DeviceRole.CLIENT), Device(hostname="d2", role=DeviceRole.CLIENT)]
    snapshot = _snapshot(devices, [])
    prompt = build_prompt(snapshot)
    assert "unconnected" in prompt
