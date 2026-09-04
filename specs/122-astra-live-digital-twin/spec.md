# Feature Specification: Astra Live Digital Twin

**Feature Branch**: `122-astra-live-digital-twin`
**Created**: 2026-09-04
**Status**: Draft
**Input**: User description: "Astra Live Digital Twin: a live, continuously updated extension of the NetClaw Three.js network HUD (specs 101/102). Instead of a one-shot generated visualization, a collector continuously polls the state of a real lab network (via the existing pyATS/CML testbed integration) and streams topology, link-state, and device-status deltas into a persistent 3D scene that always reflects the current state of the live lab. The twin is read-only: it observes and renders the live network, it never writes configuration to any device. This feature is built by a new internal federation member (per the existing iN2N member/risk model, spec 056) named Astra Twin, an OpenAI-backed mesh participant distinct from the primary Claude-backed NetClaw agent. The feature is built by an autonomous Ralph loop with a maker/checker split, capped iterations, a lab-only testbed guard, and a frozen verification harness."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Watch the lab change live (Priority: P1)

An operator opens the digital twin and leaves it open while working in the lab. When they make a real change in the lab network — disable a link, reboot a device, bring up a new neighbor — the twin's 3D scene updates on its own to reflect that change, without the operator reloading the page or regenerating the visualization.

**Why this priority**: This is the entire premise of a "live" twin as opposed to the existing one-shot generated visualizations (specs 046/101/102). Without continuous, automatic sync to real lab state, this is not a different feature from what already exists — it is the MVP.

**Independent Test**: Open the twin against a running lab testbed, make one observable change on a lab device (e.g., shut an interface), and confirm the scene reflects that change without any manual refresh action.

**Acceptance Scenarios**:

1. **Given** the twin is open and showing the current lab topology, **When** a link between two lab devices goes down, **Then** the twin visually reflects that link as down within a bounded time window, with no manual reload.
2. **Given** the twin is open, **When** a new device joins the lab topology (e.g., a new CML node comes up and forms a neighbor relationship), **Then** the twin adds that device and its links to the scene without the operator restarting the visualization.
3. **Given** the twin has been running for an extended session, **When** several changes occur in sequence, **Then** each change appears as its own visible update rather than being silently dropped or coalesced into a stale final state.

---

### User Story 2 - Trust that the twin cannot touch the network (Priority: P2)

An operator (or a security reviewer) needs confidence that a tool which continuously talks to lab devices, and which was built by an autonomous, largely unattended process, cannot ever push a configuration change — only observe and render.

**Why this priority**: A live, always-on collector talking to network devices is exactly the kind of capability that must not silently gain write access, especially given it is built by an unattended loop. Trust in the read-only guarantee is a precondition for anyone actually leaving this running against a lab.

**Independent Test**: Inspect the twin's operating capability/audit trail and confirm no configuration-changing command is ever issued to any device across a full observation session, including one that includes device or topology changes.

**Acceptance Scenarios**:

1. **Given** the twin is actively collecting from the lab, **When** any device state changes for any reason, **Then** the only action taken by the twin is to read and render that state — never to write it.
2. **Given** an operator reviews what the twin is capable of, **When** they check its available operations, **Then** no configuration-write capability is present at all — not merely unused, but absent.

---

### User Story 3 - See who (and what) built and runs this (Priority: P3)

An operator or administrator wants to know that the Astra Live Digital Twin was built and is maintained by a distinct, identifiable participant in NetClaw's internal mesh — "Astra Twin" — and that this participant's own reasoning runs on a different AI provider than the primary NetClaw agent, not that it is an anonymous background script.

**Why this priority**: Provenance and identity matter for anything with standing access to live network state. Burying "this is a different, OpenAI-backed identity" inside a config file undermines the auditability the rest of NetClaw's mesh (iN2N) is built around.

**Independent Test**: Look up Astra Twin in the mesh's member/enrollment records and confirm it appears as its own named, enrolled participant with its model provider correctly attributed.

**Acceptance Scenarios**:

1. **Given** the mesh's member records, **When** an administrator looks up "Astra Twin," **Then** it appears as a distinct enrolled member, separate from the primary agent identity, with its AI provider identified.
2. **Given** the delivered twin visualization is running, **When** an operator checks where it came from, **Then** it is clear the twin was built and is maintained by Astra Twin rather than appearing to be an anonymous part of the primary agent.

---

### Edge Cases

- What happens when the lab testbed becomes unreachable mid-session (network blip, CML restart)? The twin must show its data as stale rather than silently freezing on outdated state or crashing.
- What happens when a device is removed from the lab (decommissioned, node deleted) and later reappears under the same identity? The twin must reconcile this as a real removal followed by a real return, not leave a stale ghost node.
- What happens when the lab topology is larger than usual (many devices/links at once)? The twin must keep rendering and updating rather than silently dropping devices past some undocumented limit.
- What happens if Astra Twin's own AI backend (OpenAI) is unreachable or rate-limited? The already-delivered twin visualization must keep working for the operator — its runtime has no dependency on any AI provider being available; only Astra Twin's own build/maintenance activity is affected.
- What happens if the collector is pointed at something other than the designated lab testbed? The system must refuse to collect from it rather than silently rendering non-lab state.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The twin MUST render a 3D visualization of the current topology, link state, and device status of a live lab network, extending the existing Three.js HUD presentation (specs 101/102) rather than replacing it.
- **FR-002**: The twin MUST update its visualization to reflect real changes observed in the lab network (link state changes, device reachability changes, topology/neighbor changes) without requiring the operator to reload or regenerate the scene.
- **FR-003**: The twin MUST NOT issue any configuration-changing command to any network device, under any circumstance — it is read-only by design, not merely by convention.
- **FR-004**: The twin's live data collection MUST be restricted exclusively to a designated lab/test network; it MUST refuse to run if the resolved network target is not confirmed to be that lab environment.
- **FR-005**: The twin MUST NOT require, hold, or have access to production network credentials at any point in its operation.
- **FR-006**: "Astra Twin" MUST exist as a distinctly identified, enrolled participant in NetClaw's internal mesh (iN2N member model), separate from the primary NetClaw agent identity.
- **FR-007**: Astra Twin's enrollment/identity record MUST correctly attribute that its own reasoning is powered by a different AI model provider (OpenAI) than the primary agent (Claude), visible to anyone inspecting mesh membership.
- **FR-008**: The twin MUST preserve the operator's current view (camera position/orientation, any manual zoom or grouping) across live updates — a background data change must never reset what the operator is looking at.
- **FR-009**: The twin MUST visually distinguish what just changed (e.g., a link that just went down, a device that just appeared) from state that has been stable, so an operator can tell deltas apart from steady-state.
- **FR-010**: The twin MUST show an operator-visible indicator of data freshness (e.g., how recently the shown state was confirmed against the lab), including clearly indicating when that data has gone stale.
- **FR-011**: The delivered twin visualization MUST function and remain interactive with no runtime dependency on any AI/LLM provider being reachable — AI involvement (Astra Twin) is limited to building and maintaining the feature, not to serving it.

### Key Entities

- **Live Twin Scene**: The persistent 3D representation of the lab network that the operator views; carries forward across updates rather than being regenerated from scratch each time.
- **Collector**: The continuously running process that observes the lab network's real state and produces the deltas the scene applies; read-only against the network by construction.
- **Device/Link Delta**: A single observed change (a device's status, a link's state, a topology/neighbor change) since the twin's last known state, used to update the scene incrementally.
- **Lab Testbed**: The bounded, explicitly non-production network environment that is the only permitted source of live data for the twin.
- **Astra Twin (mesh member)**: A distinct, enrolled iN2N mesh participant, attributed to the OpenAI AI provider, responsible for building and maintaining this feature. Not part of the twin's runtime data path.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can observe a real change made in the lab (e.g., a link taken down) reflected in the twin within 30 seconds, with no manual reload or regeneration step.
- **SC-002**: 100% of the twin's live data originates from the designated lab testbed across its operating lifetime; zero production devices are ever observed as a data source.
- **SC-003**: The twin issues zero configuration-changing commands to any device across its entire operating history, verifiable via audit review.
- **SC-004**: Astra Twin is found as a distinct, correctly AI-provider-attributed member in 100% of mesh membership lookups performed by an administrator.
- **SC-005**: An operator can determine, within 5 seconds of looking at the screen, whether the twin's displayed state is current or stale.
- **SC-006**: The delivered visualization remains fully interactive and functional through a full session with zero dependency on any AI provider's availability.

## Assumptions

- The existing pyATS/CML lab testbed integration and Three.js HUD stack (specs 101/102) are reused as-is; this feature extends them rather than replacing them.
- "Live" means near-real-time polling/delta-streaming within a bounded latency window (target: within 30 seconds per SC-001), not literally instantaneous push updates.
- Astra Twin's OpenAI-backed reasoning is used only during this feature's build and ongoing maintenance (the autonomous build loop); it is not a runtime dependency of the delivered visualization (see FR-011, SC-006).
- The iN2N internal federation member/enrollment model (spec 056) is extended, not replaced, to carry an AI-provider attribute per member so Astra Twin's OpenAI backing is visible in enrollment records (FR-007).
- Scale is bounded to a single lab topology of realistic lab size (on the order of tens of devices/links), not a production-scale network.
- This feature carries no user-facing authentication/authorization requirements beyond what already gates access to the existing NetClaw HUD; it does not introduce a new access-control surface.
