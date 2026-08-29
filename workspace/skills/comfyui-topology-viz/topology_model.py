"""
Canonical topology data model for the ComfyUI network topology visualization skill.

Ported from workspace/skills/threejs-network-viz/topology_model.py (spec 046), trimmed of the
3D-only asset-resolution concepts (AssetKind, ProceduralShape, ModelSource, FallbackReason,
DeviceAsset, FallbackNote) and spatial-layout concepts (Vector3, Device.position) that this
feature has no use for — a generated still image has no per-device asset-selection or 3D-placement
step; the whole snapshot is summarized into one text prompt instead. See
specs/120-comfyui-topology-viz/data-model.md and research.md §5.

Every topology-source adapter in sources.py (live source or freeform) MUST produce these types,
and prompt_builder.py consumes only these types — never a source-specific shape.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class DeviceRole(str, Enum):
    ROUTER = "router"
    SWITCH = "switch"
    FIREWALL = "firewall"
    LOAD_BALANCER = "load_balancer"
    CLIENT = "client"
    UNCLASSIFIED = "unclassified"


class OperationalState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class SourceKind(str, Enum):
    CML = "cml"
    GNS3 = "gns3"
    CONTAINERLAB = "containerlab"
    EVE_NG = "eve_ng"
    NAUTOBOT = "nautobot"
    NETBOX_INFRAHUB = "netbox_infrahub"
    IP_FABRIC = "ip_fabric"
    FORWARD_NETWORKS = "forward_networks"
    FREEFORM = "freeform"


# Forbidden metadata keys — a defensive denylist enforced at assembly time (FR-015). Adapters
# MUST NOT copy anything matching these into Device.metadata / Interface.metadata, and
# prompt_builder.py MUST NOT compose a prompt from anything bypassing this sanitizer.
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
    """Strip anything resembling a credential/secret/full-config blob (FR-015)."""
    if not raw:
        return {}
    return {
        str(k): str(v)
        for k, v in raw.items()
        if str(k).strip().lower() not in FORBIDDEN_METADATA_KEYS
    }


@dataclass
class Interface:
    name: str
    parent_hostname: str
    ip_address: Optional[str] = None
    state: Optional[OperationalState] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Device:
    hostname: str
    role: DeviceRole = DeviceRole.UNCLASSIFIED
    state: Optional[OperationalState] = None
    interfaces: list[Interface] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class LinkEndpoint:
    hostname: str
    interface_name: Optional[str] = None


@dataclass
class Link:
    link_id: str
    endpoint_a: LinkEndpoint
    endpoint_b: LinkEndpoint
    state: Optional[OperationalState] = None
    label: str = ""

    def __post_init__(self):
        if not self.label:
            a = self.endpoint_a
            b = self.endpoint_b
            a_label = f"{a.hostname}:{a.interface_name}" if a.interface_name else a.hostname
            b_label = f"{b.hostname}:{b.interface_name}" if b.interface_name else b.hostname
            self.label = f"{a_label} <-> {b_label}"


@dataclass
class TopologySnapshot:
    snapshot_id: str
    source_kind: SourceKind
    source_label: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    devices: list[Device] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)

    def get_device(self, hostname: str) -> Optional[Device]:
        return next((d for d in self.devices if d.hostname == hostname), None)

    def is_empty(self) -> bool:
        """FR-013: a snapshot with zero devices has nothing to visualize."""
        return len(self.devices) == 0

    def validate(self) -> None:
        """Enforce data-model.md's validation rules; raises ValueError on violation."""
        hostnames = {d.hostname for d in self.devices}
        for device in self.devices:
            for iface in device.interfaces:
                if iface.parent_hostname != device.hostname:
                    raise ValueError(
                        f"Interface {iface.name!r} parent_hostname {iface.parent_hostname!r} "
                        f"does not match owning Device {device.hostname!r}"
                    )
        for link in self.links:
            for endpoint in (link.endpoint_a, link.endpoint_b):
                if endpoint.hostname not in hostnames:
                    raise ValueError(
                        f"Link {link.link_id!r} references unknown device {endpoint.hostname!r}"
                    )
                if endpoint.interface_name is not None:
                    device = self.get_device(endpoint.hostname)
                    iface_names = {i.name for i in device.interfaces} if device else set()
                    if endpoint.interface_name not in iface_names:
                        raise ValueError(
                            f"Link {link.link_id!r} references unknown interface "
                            f"{endpoint.interface_name!r} on {endpoint.hostname!r}"
                        )
