# Feature Specification: Generic Multivendor CLI Driver

**Feature Branch**: `076-multivendor-cli-driver`
**Created**: 2026-07-30
**Status**: Draft
**Roadmap item**: R1 in `docs/COVERAGE-ROADMAP.md` — highest coverage-per-line item on the roadmap
**Depends on**: R0 / spec 075 (this branch is stacked on it — R1 must follow `docs/ADDING-AN-MCP.md` and pass `scripts/reconcile-mcp.py`)
**Input**: User description: "Generic multivendor network CLI driver via Nornir, NAPALM and Netmiko. Roadmap item R1 — the largest coverage-per-line item on the roadmap. NetClaw's device reach today is pyATS (Cisco), junos-mcp (Juniper), gnmi-mcp (streaming telemetry) and radkit-mcp (cloud-relayed) — there is no general 'SSH to any platform' capability. One server adds MikroTik RouterOS, VyOS, SONiC, Nokia SR Linux, Extreme, Huawei, Dell, Ubiquiti EdgeOS and roughly ninety more platforms NetClaw cannot reach at all. […] Must be read-only first with writes explicitly gated. Must follow docs/ADDING-AN-MCP.md and pass scripts/reconcile-mcp.py, both established by spec 075."

---

## The problem

NetClaw can reach a network device four ways today, and every one of them is platform-bound:

| Existing server | Reaches | Skills |
|---|---|---|
| `pyATS` | Cisco IOS / IOS-XE / NX-OS / IOS-XR | 18 |
| `junos-mcp` | Juniper Junos (PyEZ/NETCONF) | 1 |
| `gnmi-mcp` | Any platform, but streaming telemetry only — not CLI |
| `radkit-mcp` | Cloud-relayed access, Cisco-oriented |

There is **no general "connect to this device and ask it something" capability.** A NetClaw operator with a MikroTik edge router, a VyOS lab firewall, a SONiC white-box switch, a Nokia SR Linux fabric, an Extreme campus stack, a Huawei core, a Dell OS10 leaf, or a Ubiquiti EdgeOS box cannot query any of them. None of `napalm`, `netmiko`, `nornir` or `scrapli` is installed, and no installer catalog entry exists for a generic driver.

This is the single largest reach gap in NetClaw, and it closes with one server.

## The layering decision (ratified 2026-07-30)

The four named libraries are frequently discussed as alternatives. They are not — they are four
different layers, and recognising that resolves the design:

| Layer | What it is | Platform breadth | Output shape |
|---|---|---|---|
| **Netmiko** | Transport: SSH sessions, prompt detection, paging quirks | ~100+ | Raw text |
| **NAPALM** | Normalization: vendor-neutral getters over a fixed API, often using Netmiko underneath | ~10 solid | Structured, **identical across vendors** |
| **Nornir** | Orchestration: inventory, concurrency, task composition. Talks to no device itself | inherits | inherits |
| **pyATS / Genie** | Parse and test framework: ~2000 parsers, state snapshot/diff, test harness | **Cisco-deep**, thin elsewhere | Structured, **shape varies per command** |

Nornir does not compete with Netmiko — it drives it. The genuine trade-off is **NAPALM
(normalized but narrow) versus Genie (rich but Cisco-centric)**.

### Ratified routing rule: platform-first, with one deliberate exception

| Situation | Server |
|---|---|
| Cisco IOS / IOS-XE / NX-OS / IOS-XR | `pyATS` (existing) |
| Juniper Junos | `junos-mcp` (existing) |
| Streaming telemetry, any vendor | `gnmi-mcp` (existing) |
| No direct reachability / cloud-relayed | `radkit-mcp` (existing) |
| **Any platform with no dedicated server** | **this server** |
| **Cross-vendor normalized comparison, even where a dedicated server exists** | **this server, via NAPALM getters (read-only)** |

The last row is the exception and the reason this rule must be written down: NAPALM also supports
IOS and Junos, so without an explicit rule two servers answer the same question in different shapes.

**Writes stay single-pathed per platform.** On Cisco and Juniper this server is read-only; the
dedicated servers own all configuration change. This is what keeps Constitution Principles I
("device state MUST be verified, not assumed") and VIII (verify after every change) enforceable —
"verified by which tool?" must have exactly one answer per platform.

The rejected alternative was **NAPALM-first for everything read-only**: conceptually cleaner, one
output shape everywhere, but it discards most of Genie's ~2000 parsers on NetClaw's most common
platform. Recorded here so it is not re-litigated.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reach a platform NetClaw cannot touch today (Priority: P1)

An operator runs a mixed network. They ask NetClaw about interface state on a MikroTik edge router,
a VyOS firewall, or a SONiC switch — platforms with no dedicated server — and get a real answer read
from the live device.

**Why this priority**: This is the entire point of R1. Today the answer is "NetClaw cannot reach that
device." One server changes that for roughly ninety platforms.

**Independent Test**: Point the server at a lab device of a platform no existing server supports
(containerlab can host SR Linux, VyOS and SONiC; GNS3/EVE-NG can host MikroTik) and retrieve
interface and version state. Delivers value with nothing else in this spec implemented.

**Acceptance Scenarios**:

1. **Given** a reachable device of a platform no existing NetClaw server supports, **When** the
   operator asks for its interface state, **Then** the live state is returned.
2. **Given** the same device, **When** the operator asks for a platform-specific `show` command,
   **Then** the raw output is returned without the server needing a parser for it.
3. **Given** an unreachable device, **When** a query is attempted, **Then** the operation halts and
   reports the failure rather than returning stale or assumed state (Principle I).
4. **Given** a platform the underlying driver does not support, **When** a connection is attempted,
   **Then** the unsupported platform is reported clearly rather than failing obscurely.

---

### User Story 2 - One question, one shape, across vendors (Priority: P1)

An operator asks a question that spans vendors — "show me BGP neighbours across the whole fabric" —
and receives one uniformly-shaped answer, rather than three differently-shaped ones they must
reconcile by hand.

**Why this priority**: Equal to US1 because it is the capability no existing server can provide at
all. `pyATS` and `junos-mcp` each answer well for their own platform, but their output shapes differ,
so cross-vendor questions currently require manual reconciliation. This is also the one case where
this server is the right tool even for Cisco and Juniper.

**Independent Test**: Query the same normalized fact across at least three different vendors' devices
and confirm the results share one shape and can be presented as a single table.

**Acceptance Scenarios**:

1. **Given** devices from three or more vendors, **When** a normalized fact is requested, **Then**
   every result shares one shape regardless of platform.
2. **Given** a device whose platform has a dedicated server, **When** a *normalized cross-vendor*
   fact is requested, **Then** this server answers it read-only.
3. **Given** a device whose platform has a dedicated server, **When** a *single-device deep* query is
   requested, **Then** the operator is directed to the dedicated server rather than served a shallower
   answer.
4. **Given** a platform for which a requested normalized fact is unavailable, **When** it is
   requested, **Then** the gap is reported explicitly rather than silently omitted from the results.

---

### User Story 3 - Ask many devices at once (Priority: P2)

An operator asks a question of an entire fleet — or a site, or a role — and gets per-device results
including per-device failures, without the whole operation collapsing because three devices were
unreachable.

**Why this priority**: P2 because US1 and US2 deliver value on single devices first. But fleet-wide
questions are the common real-world case, and doing them one device at a time does not scale to a
network.

**Independent Test**: Run one query against a lab of mixed-platform devices including at least one
deliberately unreachable, and confirm per-device results with the failure isolated.

**Acceptance Scenarios**:

1. **Given** a group of devices, **When** one query is issued to the group, **Then** results are
   returned per device.
2. **Given** a group in which some devices are unreachable, **When** the query runs, **Then**
   reachable devices return results and unreachable ones are reported individually as failures.
3. **Given** a large group, **When** the query runs, **Then** devices are contacted concurrently
   rather than strictly one at a time.

---

### User Story 4 - Inventory and credentials come from what NetClaw already has (Priority: P2)

Devices and credentials are not re-entered. The device list comes from NetClaw's existing sources of
truth, and credentials come from the existing secret store — never from a plaintext inventory file.

**Why this priority**: P2 because US1 can be demonstrated against a small explicit target first. But
a second, hand-maintained inventory would immediately drift from NetBox/Nautobot/Infrahub, and a
plaintext credential file would violate Constitution Principle XIII outright.

**Independent Test**: Resolve a device from an existing source of truth and connect to it using a
credential retrieved from the secret store, with no device or secret written into a local file.

**Acceptance Scenarios**:

1. **Given** a device recorded in an existing source of truth, **When** it is referenced by name,
   **Then** its connection details are resolved from that source rather than a local inventory.
2. **Given** a device requiring credentials, **When** a connection is made, **Then** credentials come
   from the existing secret store.
3. **Given** any operation, **When** the configuration is inspected, **Then** no credential appears in
   any file on disk (Principle XIII).
4. **Given** a device absent from every source of truth, **When** it is referenced, **Then** the
   absence is reported rather than guessed at.

---

### User Story 5 - Configuration change is gated, staged and reversible (Priority: P3)

An operator changes configuration on a platform only this server can reach. The change is preceded by
a captured baseline, requires explicit human approval, and can be rolled back.

**Why this priority**: P3 deliberately. Read-only across ninety platforms is the valuable, safe
increment; writes are where this server could cause an outage. Shipping US1–US4 first means the
capability is useful long before it is dangerous. Genuinely gated writes need the approval path and
baseline capture working, which is why they come last rather than never.

**Independent Test**: Attempt a configuration change on a lab device and confirm it cannot proceed
without approval, that a baseline was captured first, and that it can be reverted.

**Acceptance Scenarios**:

1. **Given** a configuration change request, **When** it is issued, **Then** a baseline is captured
   before anything is modified (Principle II).
2. **Given** a configuration change request, **When** it is issued, **Then** it does not proceed
   without explicit human approval.
3. **Given** an applied change, **When** it completes, **Then** actual resulting state is compared
   against expected state, not merely that the command succeeded (Principle VIII).
4. **Given** a failed verification, **When** it is detected, **Then** rollback to the captured
   baseline is attempted and the outcome reported.
5. **Given** a Cisco or Juniper device, **When** a configuration change is requested through this
   server, **Then** it is refused and the dedicated server named instead — writes stay single-pathed.
6. **Given** any device interaction, **When** it completes, **Then** it is recorded in the audit
   trail (Principle IV).

---

### Edge Cases

- **A platform is supported by the transport layer but has no normalized getter.** Raw command
  execution must still work; the absence of normalization must be stated, not silently degraded.
- **A device is reachable but authentication fails.** Distinguishable from unreachable, because the
  remediation is entirely different.
- **A device's platform is misrecorded in the source of truth.** Connecting with the wrong driver
  produces confusing output; a platform mismatch should be detected and reported rather than guessed.
- **Two servers could answer the same question.** The routing rule decides, and the operator should be
  told which server answered, so results are attributable.
- **A command is destructive in a way the deny-list did not anticipate.** Constitution's forbidden
  operations (`write erase`, `reload`, `format flash:`) must be blocked regardless of platform
  syntax — and platform syntax varies, so a Cisco-shaped deny-list is insufficient.
- **A single device hangs.** One unresponsive device must not stall a fleet-wide query indefinitely.
- **Credentials differ per device, site, or platform.** A single global credential is not a realistic
  assumption for a mixed network.
- **The same device is queried through two servers and the answers disagree.** Should be surfaceable,
  since silent disagreement about device state is worse than a reported conflict.

## Requirements *(mandatory)*

### Functional Requirements

**Reach**

- **FR-001**: The server MUST connect to network devices over SSH across a broad set of platforms,
  including at minimum MikroTik RouterOS, VyOS, SONiC, Nokia SR Linux, Extreme, Huawei, Dell and
  Ubiquiti EdgeOS — none of which NetClaw can reach today.
- **FR-002**: The server MUST execute an arbitrary read-only command on a device and return its
  output, without requiring a parser for that specific command.
- **FR-003**: The server MUST report an unsupported platform explicitly rather than failing obscurely.
- **FR-004**: The server MUST halt and report when a device is unreachable, never returning assumed or
  cached state as if live (Principle I).
- **FR-005**: The server MUST distinguish "unreachable" from "authentication failed" from "platform
  mismatch", since each has a different remediation.

**Normalization**

- **FR-006**: The server MUST return a set of common operational facts in one shape that is identical
  across platforms.
- **FR-007**: Where a normalized fact is unavailable for a platform, the server MUST report that gap
  explicitly rather than omitting it silently.
- **FR-008**: Normalized cross-vendor reads MUST be available even for platforms that have a
  dedicated server, and MUST be read-only there.

**Routing and boundaries**

- **FR-009**: The server MUST NOT be the route for single-device Cisco or Juniper work; `pyATS` and
  `junos-mcp` remain authoritative for their platforms.
- **FR-010**: The server MUST refuse configuration changes on platforms owned by a dedicated server,
  naming the correct server, so every platform has exactly one write path.
- **FR-011**: Results MUST identify which server produced them, so answers are attributable when more
  than one server could have answered.
- **FR-012**: The routing rule MUST be documented in the accompanying skills so an operator and the
  agent select consistently.

**Fleet operations**

- **FR-013**: The server MUST execute one query against a group of devices and return per-device
  results.
- **FR-014**: A failure on one device MUST NOT abort the operation for others; per-device failures
  MUST be reported individually.
- **FR-015**: Devices MUST be contacted concurrently, with a bound on concurrency.
- **FR-016**: An unresponsive device MUST time out rather than stalling the operation indefinitely.

**Inventory and credentials**

- **FR-017**: Device inventory MUST be resolved from NetClaw's existing sources of truth rather than a
  new hand-maintained inventory file.
- **FR-018**: Credentials MUST come from NetClaw's existing secret store.
- **FR-019**: No credential may be written to any file on disk, in any form (Principle XIII).
- **FR-020**: Per-device, per-site or per-platform credential differences MUST be supported; a single
  global credential is not sufficient.
- **FR-021**: A device absent from every source of truth MUST be reported as absent rather than
  guessed at.

**Safety**

- **FR-022**: The server MUST default to read-only. Any write capability MUST be explicitly enabled
  rather than available by default.
- **FR-023**: The Constitution's forbidden operations MUST be blocked on every platform, accounting
  for the fact that destructive command syntax differs per vendor.
- **FR-024**: Configuration changes MUST capture a baseline before modifying anything (Principle II).
- **FR-025**: Configuration changes MUST require explicit human approval through NetClaw's existing
  approval path (Principle I).
- **FR-026**: After a change, actual state MUST be compared against expected state — not merely that
  the command returned successfully (Principle VIII).
- **FR-027**: On failed verification, rollback to the captured baseline MUST be attempted and the
  outcome reported.
- **FR-028**: Every device interaction MUST be recorded in the audit trail (Principle IV).
- **FR-029**: Command filtering MUST be enforced server-side, not merely advertised in skill
  documentation, so it cannot be bypassed by phrasing a request differently.

**Integration**

- **FR-030**: The server MUST be registered and installable per `docs/ADDING-AN-MCP.md`, and
  `scripts/reconcile-mcp.py` MUST pass — including a catalog entry and install function, since no
  generic-driver catalog id exists today.
- **FR-031**: Accompanying skills MUST cover, at minimum: normalized fact retrieval, safe raw command
  execution, and fleet-wide fan-out.
- **FR-032**: Existing device-facing capability MUST NOT regress; all 18 pyATS skills and the Junos
  skill MUST continue to work unchanged.

### Key Entities

- **Device**: A reachable network element. Has a name, an address, a platform identifier, and a
  credential reference. Resolved from a source of truth, never defined locally.
- **Platform**: The OS family determining which driver and command syntax apply. Mismatch between the
  recorded and actual platform is a detectable error condition.
- **Device group**: A named set of devices — by site, role, platform, or tag — that one query can
  target.
- **Normalized fact**: An operational datum whose shape is identical across platforms. The unit of
  cross-vendor comparison.
- **Raw command result**: Unparsed device output, for anything no normalized fact covers.
- **Command policy**: The server-side allow and deny rules, including the Constitution's forbidden
  operations expressed per platform syntax.
- **Change transaction**: A configuration change bundling baseline, approval, application,
  verification and rollback.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: NetClaw can retrieve live state from at least **five platform families it cannot reach
  today**, demonstrated against real devices or lab instances.
- **SC-002**: Total reachable platform families increase from **4 to 90+**.
- **SC-003**: A normalized fact requested across at least three vendors returns one shape, presentable
  as a single table without per-vendor special-casing.
- **SC-004**: A fleet query against a mixed group including at least one unreachable device returns
  results for every reachable device and isolates the failure.
- **SC-005**: A fleet query of N devices completes substantially faster than N sequential queries.
- **SC-006**: Zero credentials appear in any file on disk, verified by inspection.
- **SC-007**: Zero devices are defined in a local inventory file; every device resolves from a source
  of truth.
- **SC-008**: Every Constitution-forbidden operation is blocked on every supported platform, verified
  per platform rather than assumed from one.
- **SC-009**: No configuration change can be applied without a captured baseline and explicit
  approval, verified by attempting to bypass both.
- **SC-010**: A configuration change on a Cisco or Juniper device through this server is refused and
  names the correct server.
- **SC-011**: All 18 pyATS skills and the Junos skill remain functional (SC verified against the
  pre-change baseline).
- **SC-012**: `scripts/reconcile-mcp.py` exits zero with the new server registered.
- **SC-013**: An operator can determine which server should answer a given device question from the
  skill documentation alone, without reading source.

## Assumptions

- **The layering and routing decision is settled**, per the ratified rule above: platform-first with a
  cross-vendor read-only exception, writes single-pathed per platform. This was confirmed with the
  maintainer on 2026-07-30 and should not be reopened during planning.
- **A community server will be adopted rather than written from scratch.** Two candidates were
  identified in the landscape scan — one combining normalized getters with raw CLI execution and
  shipping command blacklisting plus input validation, the other adding connection pooling and
  concurrency. Candidate selection, and whether to adopt one, both, or fork, is a Phase 0 research
  decision, not a spec decision.
- **Read-only first is not negotiable.** US5 is P3 specifically so the safe increment ships first.
- **Lab platforms are available for testing.** NetClaw already integrates containerlab, GNS3 and
  EVE-NG, which between them host SR Linux, VyOS, SONiC and MikroTik — so SC-001 is testable without
  buying hardware.
- **None of the underlying libraries is currently installed** (`napalm`, `netmiko`, `nornir`,
  `scrapli` all absent), so dependency isolation per Principle XV needs real attention — these pull a
  substantial transitive tree.
- **No generic-driver catalog id exists**, so unlike R0 this feature genuinely does add a catalog
  entry and install function.
- **This branch is stacked on R0 (spec 075), which is not yet merged to `main`.** R1 inherits
  `docs/ADDING-AN-MCP.md` and `scripts/reconcile-mcp.py` from it. If R0 changes during review, R1
  rebases.

## Dependencies

- **Spec 075 / R0** — the add-an-MCP procedure and the reconciliation gate this feature must satisfy.
- Existing sources of truth — NetBox, Nautobot, Infrahub — for device inventory (FR-017).
- Existing secret store — Vault MCP — for credentials (FR-018).
- Existing approval path — HumanRail / the established gating mechanism — for writes (FR-025).
- GAIT — audit trail for every device interaction (FR-028).
- `pyATS` and `junos-mcp` — not modified, but their boundaries are defined against this server.
- Lab infrastructure — containerlab, GNS3, EVE-NG — for multi-platform testing.
- `scripts/lib/catalog.sh` and `scripts/lib/install-steps.sh` — a new component entry and install
  function (FR-030).
