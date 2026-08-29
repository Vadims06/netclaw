"""
Topology-source adapters for the ComfyUI network topology visualization skill.

Ported from workspace/skills/threejs-network-viz/sources.py (spec 046) — same adapters, same
generic `{"devices": [...], "links": [...]}` input shape the conversational orchestration layer
already normalizes each source MCP's native response into before calling here, so this skill's
generation pipeline stays identical regardless of origin (FR-010, FR-011). See
specs/119-comfyui-topology-viz/research.md §5 and data-model.md.
"""

import re
from datetime import datetime, timezone

from materials import infer_device_role
from topology_model import (
    Device,
    DeviceRole,
    Interface,
    Link,
    LinkEndpoint,
    OperationalState,
    SourceKind,
    TopologySnapshot,
    sanitize_metadata,
)


class SourceUnreachableError(Exception):
    """Raised when a named topology source cannot be reached or errors (FR-012)."""

    def __init__(self, source_kind: str, detail: str):
        self.source_kind = source_kind
        self.detail = detail
        super().__init__(f"{source_kind} is unreachable or returned an error: {detail}")


class AmbiguousSourceError(Exception):
    """Raised when a request doesn't clearly name a source and more than one applies."""

    def __init__(self, candidates: list[str]):
        self.candidates = candidates
        super().__init__(
            "Multiple topology sources could satisfy this request: "
            + ", ".join(candidates)
        )


def _parse_state(value) -> OperationalState | None:
    if value is None:
        return None
    try:
        return OperationalState(str(value).lower())
    except ValueError:
        return OperationalState.UNKNOWN


def _new_snapshot_id(source_kind: SourceKind) -> str:
    return f"{source_kind.value}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}"


def _devices_from_raw(raw_devices: list[dict]) -> dict[str, Device]:
    devices: dict[str, Device] = {}
    for d in raw_devices:
        hostname = d.get("hostname") or d.get("name") or ""
        role_str = d.get("device_type") or d.get("role")
        role = DeviceRole(role_str) if role_str in DeviceRole._value2member_map_ else None
        if role is None:
            role = infer_device_role(hostname, d.get("model", ""))

        interfaces = []
        for iface in d.get("interfaces", []) or []:
            if isinstance(iface, str):
                interfaces.append(Interface(name=iface, parent_hostname=hostname))
            else:
                interfaces.append(
                    Interface(
                        name=iface.get("name", ""),
                        parent_hostname=hostname,
                        ip_address=iface.get("ip_address"),
                        state=_parse_state(iface.get("status")),
                        metadata=sanitize_metadata(iface.get("metadata")),
                    )
                )

        devices[hostname] = Device(
            hostname=hostname,
            role=role,
            state=_parse_state(d.get("status")),
            interfaces=interfaces,
            metadata=sanitize_metadata(
                {
                    k: v
                    for k, v in d.items()
                    if k
                    not in {
                        "hostname",
                        "name",
                        "device_type",
                        "role",
                        "status",
                        "interfaces",
                    }
                }
            ),
        )
    return devices


def _links_from_raw(raw_links: list[dict], devices: dict[str, Device]) -> list[Link]:
    links = []
    for idx, l in enumerate(raw_links):
        source_device = l.get("source_device") or l.get("source") or ""
        target_device = l.get("target_device") or l.get("target") or ""
        source_iface = l.get("source_interface") or None
        target_iface = l.get("target_interface") or None

        # Only reference an interface_name if that interface actually exists on the
        # endpoint device; otherwise fall back to device-level attachment rather than
        # fabricating one.
        if source_iface and source_device in devices:
            if source_iface not in {i.name for i in devices[source_device].interfaces}:
                source_iface = None
        if target_iface and target_device in devices:
            if target_iface not in {i.name for i in devices[target_device].interfaces}:
                target_iface = None

        links.append(
            Link(
                link_id=l.get("id") or f"link-{idx}",
                endpoint_a=LinkEndpoint(hostname=source_device, interface_name=source_iface),
                endpoint_b=LinkEndpoint(hostname=target_device, interface_name=target_iface),
                state=_parse_state(l.get("status")),
            )
        )
    return links


def _build_snapshot(raw_topology: dict, source_kind: SourceKind) -> TopologySnapshot:
    devices = _devices_from_raw(raw_topology.get("devices", []))
    links = _links_from_raw(raw_topology.get("links", []), devices)
    snapshot = TopologySnapshot(
        snapshot_id=_new_snapshot_id(source_kind),
        source_kind=source_kind,
        source_label=raw_topology.get("source", source_kind.value),
        devices=list(devices.values()),
        links=links,
    )
    snapshot.validate()
    return snapshot


def from_cml(raw_topology: dict) -> TopologySnapshot:
    """Build a TopologySnapshot from a Cisco Modeling Labs topology export."""
    return _build_snapshot(raw_topology, SourceKind.CML)


def from_gns3(raw_topology: dict) -> TopologySnapshot:
    """Build a TopologySnapshot from a GNS3 project topology export."""
    return _build_snapshot(raw_topology, SourceKind.GNS3)


def from_containerlab(raw_topology: dict) -> TopologySnapshot:
    """Build a TopologySnapshot from a containerlab topology export."""
    return _build_snapshot(raw_topology, SourceKind.CONTAINERLAB)


def from_eve_ng(raw_topology: dict) -> TopologySnapshot:
    """Build a TopologySnapshot from an EVE-NG lab topology export."""
    return _build_snapshot(raw_topology, SourceKind.EVE_NG)


def from_nautobot(raw_topology: dict) -> TopologySnapshot:
    """Build a TopologySnapshot from a Nautobot source-of-truth export."""
    return _build_snapshot(raw_topology, SourceKind.NAUTOBOT)


def from_netbox_infrahub(raw_topology: dict) -> TopologySnapshot:
    """Build a TopologySnapshot from a NetBox or Infrahub source-of-truth export."""
    return _build_snapshot(raw_topology, SourceKind.NETBOX_INFRAHUB)


def from_ip_fabric(raw_topology: dict) -> TopologySnapshot:
    """Build a TopologySnapshot from an IP Fabric discovered-topology export."""
    return _build_snapshot(raw_topology, SourceKind.IP_FABRIC)


def from_forward_networks(raw_topology: dict) -> TopologySnapshot:
    """Build a TopologySnapshot from a Forward Networks discovered-topology export."""
    return _build_snapshot(raw_topology, SourceKind.FORWARD_NETWORKS)


_SOURCE_KIND_ADAPTERS = {
    SourceKind.CML.value: from_cml,
    SourceKind.GNS3.value: from_gns3,
    SourceKind.CONTAINERLAB.value: from_containerlab,
    SourceKind.EVE_NG.value: from_eve_ng,
    SourceKind.NAUTOBOT.value: from_nautobot,
    SourceKind.NETBOX_INFRAHUB.value: from_netbox_infrahub,
    SourceKind.IP_FABRIC.value: from_ip_fabric,
    SourceKind.FORWARD_NETWORKS.value: from_forward_networks,
}

# Keywords used to recognize a source by name in a natural-language request. Kept
# intentionally simple/explicit rather than fuzzy-matched, so disambiguation behavior
# stays predictable.
_SOURCE_NAME_HINTS: dict[str, str] = {
    "cml": SourceKind.CML.value,
    "modeling labs": SourceKind.CML.value,
    "gns3": SourceKind.GNS3.value,
    "containerlab": SourceKind.CONTAINERLAB.value,
    "clab": SourceKind.CONTAINERLAB.value,
    "eve-ng": SourceKind.EVE_NG.value,
    "eve ng": SourceKind.EVE_NG.value,
    "nautobot": SourceKind.NAUTOBOT.value,
    "netbox": SourceKind.NETBOX_INFRAHUB.value,
    "infrahub": SourceKind.NETBOX_INFRAHUB.value,
    "ip fabric": SourceKind.IP_FABRIC.value,
    "ipfabric": SourceKind.IP_FABRIC.value,
    "forward networks": SourceKind.FORWARD_NETWORKS.value,
    "forward": SourceKind.FORWARD_NETWORKS.value,
}


def resolve_source(request_text: str, available_sources: list[str]) -> str:
    """
    Determine which topology source a natural-language request refers to. Raises
    AmbiguousSourceError when the request doesn't name a recognizable source and more
    than one is available (never guesses), and SourceUnreachableError when none are
    available at all.

    Args:
        request_text: the engineer's natural-language visualization request
        available_sources: source_kind values NetClaw currently has a working
            integration for (i.e., is actually configured/reachable)

    Returns:
        The resolved source_kind string.
    """
    text = request_text.lower()
    matches = {
        kind for hint, kind in _SOURCE_NAME_HINTS.items() if hint in text and kind in available_sources
    }

    if len(matches) == 1:
        return next(iter(matches))
    if len(matches) > 1:
        raise AmbiguousSourceError(sorted(matches))

    # No recognizable source named in the request text.
    if len(available_sources) == 1:
        return available_sources[0]
    if len(available_sources) == 0:
        raise SourceUnreachableError("any", "no topology sources are currently configured/reachable")
    raise AmbiguousSourceError(sorted(available_sources))


# =============================================================================
# Freeform (no live source) topology description parsing — User Story 3 (FR-011)
# =============================================================================

_ROLE_WORDS: dict[str, DeviceRole] = {
    "router": DeviceRole.ROUTER,
    "routers": DeviceRole.ROUTER,
    "switch": DeviceRole.SWITCH,
    "switches": DeviceRole.SWITCH,
    "firewall": DeviceRole.FIREWALL,
    "firewalls": DeviceRole.FIREWALL,
    "load balancer": DeviceRole.LOAD_BALANCER,
    "load balancers": DeviceRole.LOAD_BALANCER,
    "client": DeviceRole.CLIENT,
    "clients": DeviceRole.CLIENT,
    "endpoint": DeviceRole.CLIENT,
    "endpoints": DeviceRole.CLIENT,
    "pc": DeviceRole.CLIENT,
    "server": DeviceRole.CLIENT,
}

_NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

_CONNECTOR_PATTERN = re.compile(
    # Word-based connectors need surrounding whitespace, not \b, since "-" has no
    # \w/\W transition when surrounded by spaces (\b-\b never matches " - "). The
    # bare-hyphen alternative REQUIRES whitespace on both sides so it never splits a
    # hyphenated hostname like "core-rtr".
    r"(?:\s+connects?\s+to\s+|\s+connected\s+to\s+|\s+connecting\s+to\s+|\s*<->\s*|\s*->\s*|\s+-\s+)",
    re.IGNORECASE,
)

_NAMED_ROLE_PATTERN = re.compile(
    r"\b(?P<name>[A-Za-z0-9_.\-]+)\s+is\s+an?\s+(?P<role>router|switch|firewall|load balancer|client|endpoint)\b",
    re.IGNORECASE,
)
_ROLE_NAMED_PATTERN = re.compile(
    r"\b(?:a|an)\s+(?P<role>router|switch|firewall|load balancer|client|endpoint)\s+"
    r"(?:called|named)\s+(?P<name>[A-Za-z0-9_.\-]+)\b",
    re.IGNORECASE,
)
_QUANTITY_PATTERN = re.compile(
    r"\b(?P<count>a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+"
    r"(?P<role>routers?|switch(?:es)?|firewalls?|load balancers?|clients?|endpoints?)\b",
    re.IGNORECASE,
)


def from_freeform(description: str) -> TopologySnapshot:
    """
    Build a TopologySnapshot from a plain-language topology description (FR-011).
    Recognizes explicit "<name> is a <role>" / "a <role> called <name>" role
    declarations, "<A> connects to <B>" / "<A> - <B>" / "<A> -> <B>" connections, and
    bare "<count> <role>s" quantity phrases for devices with no explicit connection.
    Any detail that can't be determined gets a clearly-indicated default: an
    unrecognized role becomes DeviceRole.UNCLASSIFIED, and a quantity-only device gets
    a generated name recorded in its metadata as `"name_source": "generated"`.
    """
    devices: dict[str, Device] = {}
    order: list[str] = []

    def _get_or_create(name: str, role: DeviceRole | None = None) -> Device:
        if name not in devices:
            resolved_role = role or infer_device_role(name)
            devices[name] = Device(hostname=name, role=resolved_role)
            order.append(name)
        elif role is not None and devices[name].role == DeviceRole.UNCLASSIFIED:
            devices[name].role = role
        return devices[name]

    # Mask out spans already consumed by an explicit named-role declaration so the
    # quantity scan below never double-counts e.g. "sw1 IS A SWITCH" as ALSO meaning
    # "one more, unnamed switch".
    masked_description = list(description)

    def _mask(span: tuple[int, int]) -> None:
        for i in range(*span):
            masked_description[i] = " "

    for match in _NAMED_ROLE_PATTERN.finditer(description):
        role = _ROLE_WORDS.get(match.group("role").lower(), DeviceRole.UNCLASSIFIED)
        _get_or_create(match.group("name"), role)
        _mask(match.span())

    for match in _ROLE_NAMED_PATTERN.finditer(description):
        role = _ROLE_WORDS.get(match.group("role").lower(), DeviceRole.UNCLASSIFIED)
        _get_or_create(match.group("name"), role)
        _mask(match.span())

    masked_description = "".join(masked_description)

    def _extract_device_name(part: str) -> str | None:
        """A connector-split segment may be a bare hostname ("core1") or an inline role
        declaration ("a switch called sw1" / "sw1 is a switch") — naively taking the
        first/last word of the latter grabs the article "a" instead of the real hostname.
        Prefer an explicit role-declaration match, then a name already known from the
        role-declaration pass above, before falling back to the bare first/last-word
        heuristic for genuinely bare hostnames."""
        role_named = _ROLE_NAMED_PATTERN.search(part)
        if role_named:
            return role_named.group("name")
        named_role = _NAMED_ROLE_PATTERN.search(part)
        if named_role:
            return named_role.group("name")
        tokens = re.findall(r"[A-Za-z0-9_.\-]+", part)
        for token in tokens:
            if token in devices:
                return token
        return tokens[-1] if tokens else None

    links: list[Link] = []
    for clause in re.split(r"[,;\n]|(?:\band\b)", description, flags=re.IGNORECASE):
        clause = clause.strip()
        if not _CONNECTOR_PATTERN.search(clause):
            continue
        parts = _CONNECTOR_PATTERN.split(clause)
        parts = [p.strip(" .") for p in parts if p.strip(" .")]
        for a, b in zip(parts, parts[1:]):
            name_a = _extract_device_name(a)
            name_b = _extract_device_name(b)
            if not name_a or not name_b:
                continue
            device_a = _get_or_create(name_a)
            device_b = _get_or_create(name_b)
            links.append(
                Link(
                    link_id=f"freeform-link-{len(links)}",
                    endpoint_a=LinkEndpoint(hostname=device_a.hostname),
                    endpoint_b=LinkEndpoint(hostname=device_b.hostname),
                )
            )

    # Quantity phrases ("two routers") for devices with no explicit name or connection
    # — generated names, clearly marked as such. Scanned against the MASKED text so an
    # already-handled "X is a router"/"a router called X" declaration is never also
    # read as a quantity phrase.
    for match in _QUANTITY_PATTERN.finditer(masked_description):
        count_word = match.group("count").lower()
        count = _NUMBER_WORDS.get(count_word) or (int(count_word) if count_word.isdigit() else 1)
        role_word = match.group("role").lower()
        role = _ROLE_WORDS.get(role_word, _ROLE_WORDS.get(role_word.rstrip("s"), DeviceRole.UNCLASSIFIED))
        existing_of_role = sum(1 for d in devices.values() if d.role == role)
        for i in range(count):
            generated_name = f"{role.value}-{existing_of_role + i + 1}"
            if generated_name in devices:
                continue
            device = Device(
                hostname=generated_name,
                role=role,
                metadata={"name_source": "generated"},
            )
            devices[generated_name] = device
            order.append(generated_name)

    snapshot = TopologySnapshot(
        snapshot_id=_new_snapshot_id(SourceKind.FREEFORM),
        source_kind=SourceKind.FREEFORM,
        source_label="freeform description",
        devices=[devices[name] for name in order],
        links=links,
    )
    snapshot.validate()
    return snapshot
