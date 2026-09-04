"""
Canonical topology data model for the World Labs fantastical topology visualization skill.

Ported from workspace/skills/comfyui-topology-viz/topology_model.py (spec 120), trimmed further
than that port trimmed spec 046's own model: this feature has no use for per-interface link
endpoints or source-provenance tracking either, since the only thing consumed downstream
(fantastical_prompt_builder.py, and the existing spec 121 topology-diagram-mcp/render_structural
tool this feature calls unmodified) needs just devices (hostname/role/state) and links (a/b/label)
— exactly the shape specs/121-federated-topology-viz/contracts/topology-diagram-mcp.md's
render_structural already accepts. See specs/122-worldlabs-topology-viz/data-model.md's Topology
Snapshot section and research.md R5.

Validation of the snapshot's structural correctness (duplicate hostnames, links referencing unknown
devices, the working-resolution density ceiling) is intentionally NOT duplicated here — it is
render_structural's job, reused as-is (FR-012). Re-implementing it here would risk the two copies
drifting apart.
"""

from dataclasses import dataclass, field
from typing import Optional


class DeviceRole(str):
    """Not an Enum on purpose: render_structural already treats any unrecognized role as
    'unclassified' rather than rejecting it (contracts/topology-diagram-mcp.md), so this feature
    only needs the canonical values as constants for building the Fantastical Prompt's role
    summary, not as a closed, validated set."""

    ROUTER = "router"
    SWITCH = "switch"
    FIREWALL = "firewall"
    LOAD_BALANCER = "load_balancer"
    CLIENT = "client"
    UNCLASSIFIED = "unclassified"


class OperationalState(str):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


# Forbidden metadata keys — a defensive denylist. Ported unchanged from spec 120's
# topology_model.py; matters more here than there, since the composed Fantastical Prompt is sent to
# a third party (World Labs), not just a locally-hosted ComfyUI instance.
FORBIDDEN_METADATA_KEYS = frozenset(
    {
        "password",
        "secret",
        "credential",
        "credentials",
        "api_key",
        "apikey",
        "token",
        "running_config",
        "startup_config",
        "config",
        "private_key",
    }
)


def sanitize_metadata(raw: Optional[dict]) -> dict:
    """Strip anything resembling a credential/secret/full-config blob before it can reach
    fantastical_prompt_builder.py."""
    if not raw:
        return {}
    return {
        str(k): str(v)
        for k, v in raw.items()
        if str(k).strip().lower() not in FORBIDDEN_METADATA_KEYS
    }


@dataclass
class Device:
    hostname: str
    role: str = DeviceRole.UNCLASSIFIED
    state: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Link:
    a: str
    b: str
    label: str = ""


@dataclass
class TopologySnapshot:
    snapshot_id: str
    devices: list[Device] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)

    def get_device(self, hostname: str) -> Optional[Device]:
        return next((d for d in self.devices if d.hostname == hostname), None)

    def is_empty(self) -> bool:
        return len(self.devices) == 0


# FR-009 — the decorative-interpretation statement every preview and generation result MUST carry,
# unconditionally, alongside a reference to the authoritative structural diagram it was derived
# from. Exported as a single constant so US1 (preview) and US2 (generate) compose it identically
# rather than two independently-worded copies drifting apart.
DECORATIVE_LABEL = (
    "This is an artistic, decorative interpretation of the topology's theme and connectivity "
    "pattern — it is NOT an accurate representation of physical device placement, cabling, or "
    "device state. The authoritative representation of this topology is the structural diagram "
    "above (produced by topology-diagram-mcp/render_structural), not this generated world."
)
