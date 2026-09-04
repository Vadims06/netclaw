"""
Unit tests for fantastical_prompt_builder.py's composition (spec 122 FR-002/FR-003,
research.md R9/R10) — per-device and per-link description, theming, default theme, the length
bound, and the deliberate no-legible-text instruction.

Rewritten alongside the module itself after live evidence (2026-09-03): the original aggregate
role-count/connectivity-density summary produced a coherent but completely untraceable-to-real-data
result. The replacement describes each device and each real link individually instead.
"""

import importlib.util
import sys
from pathlib import Path

# Loaded by explicit file path under temporarily-reserved bare names, NOT a bare `sys.path.insert +
# import` — workspace/skills/comfyui-topology-viz/, workspace/skills/threejs-network-viz/, and this
# skill's own directory all happen to define a same-named topology_model.py with different, mutually
# incompatible shapes. Nine existing test files already bare-import "topology_model", so whichever
# one Python's import cache resolves first in a shared pytest session would otherwise silently win
# for every other file too. This loader briefly occupies sys.modules["topology_model"] only long
# enough for fantastical_prompt_builder.py's own internal `from topology_model import
# TopologySnapshot` to resolve correctly at exec time, then restores whatever was there before —
# leaving no permanent global state for any other test file, regardless of collection order.
_skill_path = Path(__file__).parent.parent.parent / "workspace" / "skills" / "worldlabs-topology-viz"


def _load_worldlabs_topology_viz_modules():
    plan = [("topology_model", "topology_model.py"), ("fantastical_prompt_builder", "fantastical_prompt_builder.py")]
    previous = {name: sys.modules.get(name) for name, _ in plan}
    loaded = {}
    try:
        for name, filename in plan:
            spec = importlib.util.spec_from_file_location(name, _skill_path / filename)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            loaded[name] = module
    finally:
        for name, _ in plan:
            if previous[name] is not None:
                sys.modules[name] = previous[name]
            else:
                sys.modules.pop(name, None)
    return loaded


_modules = _load_worldlabs_topology_viz_modules()
topology_model = _modules["topology_model"]
fantastical_prompt_builder = _modules["fantastical_prompt_builder"]

Device = topology_model.Device
Link = topology_model.Link
TopologySnapshot = topology_model.TopologySnapshot
DEFAULT_THEME = fantastical_prompt_builder.DEFAULT_THEME
_MAX_PROMPT_CHARS = fantastical_prompt_builder._MAX_PROMPT_CHARS
build_prompt = fantastical_prompt_builder.build_prompt


def _snapshot(devices, links):
    return TopologySnapshot(snapshot_id="snap-1", devices=devices, links=links)


def test_prompt_names_each_real_device_by_hostname():
    snapshot = _snapshot(
        devices=[
            Device(hostname="R1", role="router"),
            Device(hostname="R2", role="router"),
            Device(hostname="SW1", role="switch"),
        ],
        links=[Link(a="R1", b="R2"), Link(a="R1", b="SW1")],
    )
    prompt = build_prompt(snapshot, theme="an underwater city")

    assert "R1" in prompt
    assert "R2" in prompt
    assert "SW1" in prompt
    assert "an underwater city" in prompt


def test_prompt_describes_each_real_link_individually():
    snapshot = _snapshot(
        devices=[Device(hostname="R1", role="router"), Device(hostname="SW1", role="switch")],
        links=[Link(a="R1", b="SW1")],
    )
    prompt = build_prompt(snapshot)
    assert "R1" in prompt and "SW1" in prompt
    # The specific real edge must appear as its own clause, not just both hostnames anywhere.
    assert "connects R1 down to SW1" in prompt


def test_routers_and_firewalls_assigned_top_tier():
    snapshot = _snapshot(devices=[Device(hostname="R1", role="router"), Device(hostname="FW1", role="firewall")], links=[])
    prompt = build_prompt(snapshot)
    assert prompt.count("At the top tier") == 2


def test_switches_and_load_balancers_assigned_middle_tier():
    snapshot = _snapshot(
        devices=[Device(hostname="SW1", role="switch"), Device(hostname="LB1", role="load_balancer")], links=[]
    )
    prompt = build_prompt(snapshot)
    assert prompt.count("At the middle tier") == 2


def test_clients_and_unclassified_assigned_ground_tier():
    snapshot = _snapshot(
        devices=[Device(hostname="PC1", role="client"), Device(hostname="X1", role="unclassified")], links=[]
    )
    prompt = build_prompt(snapshot)
    assert prompt.count("At the ground tier") == 2


def test_prompt_never_asks_for_legible_text():
    """Deliberate design choice (research.md R10): text rendering is unreliable, so the prompt
    must never ask Marble to inscribe hostnames as legible text/sigils."""
    snapshot = _snapshot(devices=[Device(hostname="R1", role="router")], links=[])
    prompt = build_prompt(snapshot)
    assert "no readable text" in prompt


def test_empty_snapshot_is_handled_gracefully():
    """Reachable only via direct unit test — the real workflow stops before this, since
    render_structural rejects an empty snapshot first (spec.md Edge Cases correction)."""
    snapshot = _snapshot(devices=[], links=[])
    prompt = build_prompt(snapshot, theme="a mystical forest")
    assert "a mystical forest" in prompt
    assert "no locations to place yet" in prompt


def test_default_theme_applies_when_none_given():
    snapshot = _snapshot(devices=[Device(hostname="R1", role="router")], links=[])
    assert DEFAULT_THEME in build_prompt(snapshot, theme=None)
    assert DEFAULT_THEME in build_prompt(snapshot)


def test_prompt_stays_within_length_bound():
    devices = [Device(hostname=f"d{i}", role="router") for i in range(60)]
    links = [Link(a=f"d{i}", b=f"d{i+1}") for i in range(59)]
    prompt = build_prompt(_snapshot(devices, links), theme="x" * 2000)
    assert len(prompt) <= _MAX_PROMPT_CHARS


def test_same_snapshot_different_theme_changes_only_theme_language():
    snapshot = _snapshot(
        devices=[Device(hostname="R1", role="router"), Device(hostname="SW1", role="switch")],
        links=[Link(a="R1", b="SW1")],
    )
    prompt_a = build_prompt(snapshot, theme="a mystical forest")
    prompt_b = build_prompt(snapshot, theme="a cyberpunk metropolis")

    assert "a mystical forest" in prompt_a and "a mystical forest" not in prompt_b
    assert "a cyberpunk metropolis" in prompt_b and "a cyberpunk metropolis" not in prompt_a
    assert "R1" in prompt_a and "R1" in prompt_b
    assert "SW1" in prompt_a and "SW1" in prompt_b
