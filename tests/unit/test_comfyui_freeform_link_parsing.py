"""
Regression test for a real bug found live during implementation: sources.from_freeform()
mis-parsed a clause like "core1 connects to a switch called sw1" — the connector-split
grabbed the article "a" as the device name (b.split()[0]) instead of the actual hostname
"sw1", creating a phantom "a" device and leaving the intended real device unconnected.

Found by generating a real topology_renderer.py structure image from a live freeform request
and visually inspecting it (workspace/output/comfyui-topology-viz/...-structure.png) — the
rendered diagram showed a nonsense 4th node "a" and an orphaned fw1, exposing a bug the
plain-text SDXL prompt path never surfaced (prompt_builder only summarizes role counts, never
exact hostnames/links, so this bug was invisible until the structural ControlNet pipeline
made the actual parsed graph visible).
"""

import sys
from pathlib import Path

skill_path = Path(__file__).parent.parent.parent / "workspace" / "skills" / "comfyui-topology-viz"
sys.path.insert(0, str(skill_path))

from sources import from_freeform  # noqa: E402


def test_connects_to_a_role_called_name_uses_the_real_hostname():
    snapshot = from_freeform(
        "a router called core1, core1 connects to a switch called sw1, "
        "sw1 connects to a firewall called fw1"
    )
    hostnames = {d.hostname for d in snapshot.devices}
    assert hostnames == {"core1", "sw1", "fw1"}
    assert "a" not in hostnames

    link_pairs = {frozenset((l.endpoint_a.hostname, l.endpoint_b.hostname)) for l in snapshot.links}
    assert frozenset({"core1", "sw1"}) in link_pairs
    assert frozenset({"sw1", "fw1"}) in link_pairs
    # The original bug left fw1 completely disconnected (linked to a phantom "a" node
    # instead) — confirm every device has at least one real link.
    linked_hosts = set()
    for link in snapshot.links:
        linked_hosts.add(link.endpoint_a.hostname)
        linked_hosts.add(link.endpoint_b.hostname)
    assert linked_hosts == {"core1", "sw1", "fw1"}


def test_bare_hostnames_still_work():
    """The fix must not regress the simple bare-hostname case."""
    snapshot = from_freeform("r1 connects to sw1, sw1 connects to fw1")
    hostnames = {d.hostname for d in snapshot.devices}
    assert hostnames == {"r1", "sw1", "fw1"}
