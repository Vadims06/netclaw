# Feature Specification: HUD 2.0 — Top-Down Trust Org Chart

**Feature Branch**: `072-hud-2-org-chart`
**Created**: 2026-07-27
**Status**: Draft
**Input**: User description: "the orbiting space theme is clunky and hard to navigate — can we make an org-chart style top down, with external claws (eN2N) 'north' or clearly external to the org chart; mobile connections should look like iN2N but special; and then the member claws; the border in the center. DON'T touch the chat interface or the right-side info bar."

## Context: what the current HUD does and why it is hard to navigate

`ui/netclaw-visual/src/main.js` (132 KB) renders every entity as a core orbiting
a shared centroid: `CORE_CENTROID = (12, 0, 0)`, members fanned onto a ring of
radius `RISK_LAYOUT.tierRadius = 46`, edge nodes assigned one of three fixed
"close orbit" slots, peers on their own orbits. The camera is a
`PerspectiveCamera(48°)` driven by unconstrained `OrbitControls`.

Two things make it clunky, and only one of them is the theme:

1. **Free orbit destroys hierarchy.** With rotation unconstrained, any given
   frame shows the topology from an arbitrary angle. "External vs internal" and
   "who reports to whom" are relationships that only read if the viewer and the
   layout agree on which way is up. This is the dominant cause and it is a
   camera problem, not an aesthetic one.
2. **Every node is given equal visual weight** regardless of whether it matters.

### Measured state of the live data (2026-07-27, `GET /api/n2n`)

These numbers drive the layout and are not hypothetical:

| Quantity | Value |
|---|---|
| Members total | **29** |
| — `state=provisioned` (cold) | **22** |
| — `state=active` | 5 |
| — `state=unreachable` | 2 |
| — actually `live: true` | **4** (`cml`, `ipfabric`, `pyats`, `viz`) |
| `node_type=agent` / `edge` | 27 / 2 |
| eN2N peers | 5 rows (4 distinct — see FR-014) |
| Distinct `profile` values | **28 across 29 members** |

Three consequences:

- **A flat row of 29 members is unreadable at any zoom.** 25 of the 29 are cold
  or unreachable. The layout must demote them, not merely place them.
- **`profile` cannot be the org chart's middle tier.** It is effectively 1:1
  with the member (28 distinct values for 29 members) — grouping by it produces
  28 groups of one. A genuine middle tier has to come from somewhere else
  (FR-006), or the chart is a 29-wide flat fan with extra steps.
- **The chart is shallow.** Every member is depth-1 from the Border. This is a
  tiered band layout, not a general tree, so no Reingold–Tilford / tidy-tree
  algorithm is required. Row packing within bands is sufficient.

## Proposed layout

```
              ╔═ EXTERNAL — eN2N ═════════════════════════════════════╗
   NORTH      ║   ( AB )      ( Nicholas )    ( Byrn )     ( Hermes ) ║
              ║  federated     unreachable   unreachable    SEVERED   ║
              ╚═══╤═══════════════╤═══════════════╤═══════════╌╌╌╌════╝
                  │               ┊               ┊            ✂
        ══════════╪═══════════════╪═══════════════╪══════════════════════
         TRUST    │      B O R D E R   B O U N D A R Y
        ══════════╪═══════════════╪═══════════════╪══════════════════════
                  │               ┊               ┊
                       ╭──────────────────╮              ┌── EDGE LANE ──┐
   CENTRE            ╭─┤   B O R D E R    ├─╌╌╌╌╌╌╌╌╌╌╌╌►│  ( phone 1 )  │
                     │ │  johns-risk      │   push ch.   │  ( phone 2 )  │
                     │ ╰──────────────────╯              └───────────────┘
                     │
        ─────────────┴──── INTERNAL — iN2N ──────────────────────────────
                     │
        ┌────────────┼───────────┬──────────────┬───────────────┐
     [Lab&Emul]  [Assurance]  [Src of Truth] [Security]   [Controllers]
        │            │             │              │              │
   SOUTH ●cml      ●pyats       ●ipfabric     ·ise ·f5      ·aci ·nso
        ·clab      ·suzieq       ·netbox      ·palo ·nmap   ·sdwan ·aap
        ·gns3      ·batfish      ·infrahub    ·nvd  ·fwrule ·itential
                   ·forward      ·infoblox
        ● = live (4)      · = cold / provisioned (25, collapsed)
```

The Border reads as the centre of a vertical stack and as the root of the
internal chart at the same time — external above the boundary, internal below,
edges in their own lane at the boundary line.

## Clarifications

### Session 2026-07-27

- Q: Does "Border in the center" conflict with "org chart top down"? → A: No.
  The Border is the center of a three-band vertical stack: external above,
  Border in the middle, internal below. It is the root of the *internal* chart
  and the boundary node for the *external* one. Both readings hold.
- Q: Should this be true 3D or a flat diagram? → A: Planar layout on a single
  plane, with depth used only for band separation and hover lift. The 3D engine
  is retained for material quality, bloom, and link animation — not for
  free-form spatial arrangement.

### Open — needs the operator's decision

- **Q1 (blocking for FR-006): what is the member category taxonomy?** `profile`
  is 1:1 with the member, so the middle tier must be a category map. A proposed
  default is in FR-006; it is a starting point written by inspection of member
  names, not domain truth. Confirm or replace it.
- **Q2 (FR-009): should cold members be visible by default?** The spec assumes
  collapsed-but-present. The alternative is hidden behind a toggle.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read the trust topology at a glance (Priority: P1)

An operator opens the HUD and, without rotating, panning, or clicking anything,
can immediately answer: who is outside my organisation, who is inside it, which
of them are alive right now, and where is the boundary between the two.

**Why this priority**: This is the entire point of the redesign. Every other
story is refinement. If the first frame does not answer those four questions,
the rebuild has failed and the orbit version was no worse.

**Independent Test**: Load the HUD on a clean session. Without any input,
confirm the external peers, the Border, and the internal members are each
identifiable, and the trust boundary between external and internal is visible
as an explicit graphic element rather than implied by distance.

**Acceptance Scenarios**:

1. **Given** a loaded HUD at default camera, **When** the operator looks at the
   scene without interacting, **Then** eN2N peers appear in a band above an
   explicitly drawn trust boundary, the Border sits on the centre line, and
   iN2N members occupy the band below it.
2. **Given** 4 live members among 29 total, **When** the scene renders, **Then**
   the 4 live members are visually dominant and the 25 cold/unreachable ones are
   demoted, so live capacity is legible without counting.
3. **Given** the operator drags the mouse, **When** they attempt to orbit,
   **Then** the camera pans within the layout plane and does not rotate out of
   the top-down orientation.
4. **Given** a severed peer, **When** the scene renders, **Then** its link to the
   Border is drawn as broken//severed and is distinguishable from a merely
   unreachable peer at a glance.

---

### User Story 2 - Distinguish mobile edges from member claws (Priority: P2)

An operator can spot their enrolled phones instantly and tell them apart from
server-side member claws, without hunting through the member band.

**Why this priority**: Edge nodes are internal (enrolled members, `node_type=edge`)
but behave nothing like member claws — they are user-carried, intermittently
connected, and receive pushes rather than serving delegations. The current HUD
already special-cases them into close-orbit slots for exactly this reason; that
intent must survive the redesign.

**Independent Test**: With at least one edge node enrolled, confirm it renders in
its own lane, is not mixed into the member rows, and its link to the Border is
visually distinct from a member link.

**Acceptance Scenarios**:

1. **Given** 2 enrolled edge nodes, **When** the scene renders, **Then** they
   appear in a dedicated lane flanking the Border, inside the trust boundary but
   outside the member chart.
2. **Given** an edge node that is unreachable, **When** the scene renders,
   **Then** its last-seen age is legible without opening the detail panel.
3. **Given** an edge node with a null `display_name`, **When** the scene renders,
   **Then** a stable fallback label derived from `member_id` is shown rather
   than a blank (see FR-015).

---

### User Story 3 - Drill into any node without losing the map (Priority: P2)

Clicking any node populates the existing right-hand detail panel while the
overall chart stays in place and oriented.

**Why this priority**: The operator explicitly wants the chat interface and the
right-hand info bar kept as-is. This story exists to guarantee the redesign is
additive to them and does not change their contract.

**Independent Test**: Click a peer, a member, and an edge node in turn; confirm
the right-hand panel updates exactly as it does today and the camera does not
jump or reframe.

**Acceptance Scenarios**:

1. **Given** any node, **When** the operator clicks it, **Then** the existing
   `setDetail(kind, payload, related)` contract is invoked unchanged.
2. **Given** a selected node, **When** the detail panel is open, **Then** the
   chart remains fully visible and does not reflow.

---

### Edge Cases

- **Zero members / zero peers** (fresh Border): bands must render with an empty
  state, not collapse into an unlabelled void.
- **A member enrolling while the HUD is open**: must appear on the next poll
  without a reload, preserving the existing `refreshRiskMembers()` behaviour.
- **More edge nodes than lane slots**: must wrap or scroll, not overlap. The
  current implementation stacks a 4th phone onto the last slot; that regression
  must not be carried forward.
- **Very long display names**: must truncate with the full value available in
  the detail panel.
- **A member that is both `active` and not `live`**: state and liveness are
  distinct fields and disagree in the live data (5 active vs 4 live). The
  visual must encode `live`, not `state`, for the dominance rule in FR-008.

## Requirements *(mandatory)*

### Layout

- **FR-001**: The scene MUST be laid out as three horizontal bands on a single
  plane: external (north), Border (centre), internal (south).
- **FR-002**: An explicit trust boundary MUST be drawn between the external band
  and the Border — a visible graphic element, not implied whitespace.
- **FR-003**: eN2N peers MUST occupy the external band, above the boundary, and
  MUST NOT be rendered as children of the Border in the org chart sense.
- **FR-004**: The Border MUST sit on the centre line, and MUST be the visual
  root of the internal chart and the attachment point for external links.
- **FR-005**: iN2N member claws MUST occupy the internal band below the Border,
  arranged as a top-down chart.
- **FR-006**: Members MUST be grouped into a middle tier by category. `profile`
  MUST NOT be used as the grouping key (it is 1:1 with the member).
  Proposed default taxonomy — **pending operator confirmation (Q1)**:

  | Category | Members |
  |---|---|
  | Lab & Emulation | `cml`, `containerlab`, `gns3` |
  | Assurance & Test | `pyats`, `suzieq`, `batfish`, `forward`, `gtrace`, `packet` |
  | Source of Truth | `netbox`, `nautobot`, `infrahub`, `infoblox`, `ipfabric` |
  | Security | `ise`, `f5`, `paloalto`, `fortimanager`, `fwrule`, `nmap`, `nvd` |
  | Controllers & Fabric | `aci`, `catalyst-center`, `sdwan`, `nso`, `aap`, `itential` |
  | Cloud & Platform | `azure`, `github` |
  | Visualisation | `viz` |

  Any member not in the map MUST fall into an explicit "Uncategorised" group
  rather than being dropped.
- **FR-007**: Mobile edge nodes MUST render in a dedicated lane flanking the
  Border — inside the trust boundary, outside the member chart — and MUST NOT be
  interleaved with member claws.

### Visual weight

- **FR-008**: Live members (`live: true`) MUST be visually dominant over
  cold/unreachable ones. Dominance MUST key off `live`, not `state`.
- **FR-009**: Cold members MUST be collapsed into a compact, dimmed
  representation that is expandable on demand, so 25 inactive nodes cannot
  crowd out 4 active ones. *(Default-visible per Q2 assumption.)*
- **FR-010**: Link styling MUST distinguish, at a glance: healthy eN2N,
  unreachable eN2N, severed eN2N, healthy iN2N, cold iN2N, and the edge/push
  channel.
- **FR-011**: The edge/push link MUST be visually distinct from a member
  delegation link, reflecting that it is asymmetric (Border → device).

### Camera and interaction

- **FR-012**: The camera MUST be constrained so the top-down orientation cannot
  be lost. Free rotation MUST be disabled; pan and zoom MUST remain.
- **FR-013**: An orthographic projection SHOULD be used so that sibling nodes at
  equal tier render at equal size, which is what makes a chart readable as a
  chart. If perspective is retained for material reasons, tier scaling MUST be
  compensated so equal-tier nodes appear equal.

### Data correctness (defects surfaced by this work)

- **FR-014**: Peers MUST be de-duplicated by identity before rendering. The live
  feed currently returns `Hermes` twice with conflicting states (`severed` and
  `federated`). The existing `deduplicatePeers()` MUST be applied to this feed,
  and where states conflict the more restrictive one MUST win.
- **FR-015**: A node with a null `display_name` MUST fall back to a label
  derived from `member_id`. Both live edge nodes currently have
  `display_name: null` and would otherwise render blank.

### Preservation (explicit non-goals)

- **FR-016**: The chat interface MUST NOT be modified.
- **FR-017**: The right-hand detail/info panel MUST NOT be modified. Its
  `setDetail()` contract MUST be honoured unchanged.
- **FR-018**: All existing detail-panel renderers — `renderRiskSection`,
  `renderFederationSection`, `renderEdgeNodes`, `renderPostureBadge`,
  `renderGaitTrail`, `renderChannelSecurity`, `renderReplicationJobs`,
  `renderRecentPushes` — MUST continue to work against the same data.

### Security constraint

- **FR-019**: This feature MUST NOT widen the HUD's existing unauthenticated
  API surface, and MUST NOT introduce any new endpoint that returns credential
  values. (See `~/netclaw-reports/SECURITY-hud-credential-exposure.md`: the
  HUD already serves the credential store in plaintext over an unauthenticated,
  CORS-open, `0.0.0.0`-bound API. That defect is out of scope here and is being
  tracked separately, but this work must not compound it.)

## Success Criteria *(mandatory)*

- **SC-001**: An operator who has never seen the HUD can correctly identify
  which claws are external and which are internal, on first view, without
  interacting.
- **SC-002**: The 4 live members are identifiable within 2 seconds of load,
  without counting or zooming.
- **SC-003**: No camera input can produce a view in which the external band is
  not above the internal band.
- **SC-004**: All 29 members, 4 peers, and 2 edge nodes render without label
  collision or node overlap at default zoom.
- **SC-005**: Chat and the right-hand panel behave identically to HUD 1.0 —
  verified by diffing their behaviour, not by inspection.

## Assumptions

- Three.js is retained (r0.170, already vendored with `OrbitControls`,
  `CSS2DRenderer`, and the postprocessing chain). No new rendering dependency
  is required. `CSS2DRenderer` is the intended label mechanism — at ~40 nodes
  the DOM cost is immaterial and the crispness matters for a chart.
- No new layout library is required. Bands + row packing within a band is
  sufficient for a depth-2 chart; a general tidy-tree algorithm would be
  over-engineering here.
- The existing `/api/n2n` payload is sufficient. The only additions this spec
  implies are client-side (the category map in FR-006); no server change is
  required, and none should be made to satisfy FR-019.
