# Feature Specification: HUD WebGPU Showcase + Interactive Layout

**Feature Branch**: `102-hud-webgpu-interactive-layout`
**Created**: 2026-08-07
**Status**: Draft — two blocking clarifications (see Clarifications)
**Input**: Operator request, 2026-08-07 — "work on 102 - the amazing show off polish - also for 102 ADD the ability to click / drag / reposition the layouts maybe offer a drop down default layout; some layout options; free-form; SAVE layout?"

## Problem Statement

Two things, and they pull in different directions — which is the interesting part of this feature.

1. **The HUD can't do the impressive things r185 makes possible.** Spec 101 landed the version bump but stayed on `WebGLRenderer`, deferring `ClusteredLighting`, compute-shader particles and node-based post-processing here. These need `WebGPURenderer`, which supports neither raw-GLSL `ShaderMaterial` nor `EffectComposer` — so it is an either/or migration, not an upgrade.
2. **The layout is fixed and the operator wants to arrange it.** Nodes sit exactly where `computeLayout()` puts them, with no way to drag, rearrange, choose a different arrangement, or keep one.

**The tension worth naming up front**: feature 072's core premise is that *fixed* positions build spatial memory, and its FR-022/FR-038 explicitly guarantee no node ever moves as a result of selection or expansion — "a claw that fails changes how it looks, never where it is." Spec 101 carried that guarantee forward. Free-form dragging deliberately moves nodes.

That is not a contradiction to wave away. The resolution this spec proposes: **072 forbade the *system* moving nodes behind the operator's back; it did not forbid the operator moving them deliberately.** Spatial memory is preserved when position changes are operator-initiated, persistent, and reversible — and destroyed when they are algorithmic and surprising. Every layout requirement below is written to keep that distinction intact, and FR-038's original guarantee survives verbatim for system-initiated changes.

## Inherited from spec 101 (measured, not re-derived)

| Fact | Value |
|---|---|
`three` version | `0.185.1` (already landed) |
`ShaderMaterial` instances needing TSL port | **4** |
`onBeforeCompile` hooks | **0** — the usual worst part of a WebGPU port is absent |
`EffectComposer` passes to rebuild on the node stack | **7** |
WebGL fallback | automatic, but does **not** restore WebGPU-only capabilities |
Scene scale | ~40 nodes (7 peers + 30 members + Border + edges) |
Visual baseline to preserve | 101's six peer states, selection ring, link flow |
Test split | `src/orgchart/` pure and tested; `src/orgchart-render/` has no coverage |

`ClusteredLighting` overrides the WebGPU lighting system rather than layering on it.

## Clarifications

### Needed before Phase 1

- **Q1: Where do saved layouts persist?** → **[NEEDS CLARIFICATION]**
  Spec 101's FR-039 forbade touching `server.js` or the `/api/n2n` contract, and 072 did the same.
  Saving a layout breaks that unless it stays client-side. Options: browser `localStorage`
  (no server change, per-browser, lost on cache clear); a new `server.js` endpoint plus on-disk
  file (shared across browsers, but widens the API surface two specs deliberately kept closed);
  or export/import a JSON file the operator manages. This decides whether 102 is still a
  client-only feature.

- **Q2: Does the WebGPU migration ship as a hard switch or a runtime toggle?** → **[NEEDS CLARIFICATION]**
  A toggle means both renderers must be maintained — 4 shaders in *both* GLSL and TSL, and *two*
  post-processing chains — roughly doubling the surface. A hard switch means WebGL-only browsers
  lose the showcase features permanently and there is no fallback to compare against when a
  visual regression appears.

### Decisions taken without asking (reasonable defaults, recorded)

- **Dragging moves a node, never its band membership or its edges.** A peer dragged below the
  trust boundary is still a peer. Position is presentation; topology is data.
- **Layout changes never alter `/api/n2n` state.** Nothing an operator does to the arrangement
  can affect federation, and nothing about the arrangement is reported as network state.
- **The computed layout stays the default.** Presets and free-form are opt-in; a fresh browser
  sees exactly what 072/101 produce today.
- **Showcase features remain progressive enhancements** (carried from 101): the HUD must be fully
  correct and readable without them, because the WebGL fallback cannot provide them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Drag a node and have it stay put (Priority: P1)

An operator drags a node to a position that suits how they think about the topology, and it stays
there — through selection, expansion, poll refreshes and member enrollment.

**Why this priority**: it is the concrete request, it is independently useful with nothing else
built, and it is where the 072 tension is resolved or broken. Getting this right makes the rest
safe; getting it wrong quietly destroys the spatial-memory property two specs paid for.

**Independent Test**: drag three nodes, then select, expand, wait out a poll, and confirm all
three are still exactly where they were put.

**Acceptance Scenarios**:

1. **Given** the operator drags a member node, **When** released, **Then** it stays at the new
   position and its links follow it.
2. **Given** a node has been moved, **When** the 30-second poll refreshes, **Then** it does not
   snap back — and this is the case most likely to regress, because `updateOrgChart` repaints on
   every poll.
3. **Given** a node has been moved, **When** a new member enrolls, **Then** the moved node does
   not shift and the new member is appended without disturbing it (072's FR-034b).
4. **Given** a node is dragged, **When** the pointer moves, **Then** the camera does not orbit —
   drag and orbit must not fight over the same gesture.
5. **Given** a node is dragged onto another node, **Then** nothing merges, snaps or reorders;
   overlap is the operator's business.
6. **Given** a moved node, **When** it is selected, **Then** 101's selection ring appears at its
   *current* position, not its computed one.

---

### User Story 2 — Choose a layout preset (Priority: P1)

An operator picks from a small set of named arrangements — the current top-down org chart plus
alternatives — and the scene rearranges to it.

**Why this priority**: the operator asked for a dropdown, and presets are what make free-form
recoverable. Without "reset to computed", a dragged-apart scene is unrecoverable, which would
make US1 dangerous rather than useful.

**Independent Test**: switch between every preset and back to the default; each produces a
distinct, readable arrangement and the default is byte-identical to today's.

**Acceptance Scenarios**:

1. **Given** the preset dropdown, **When** the operator selects the default, **Then** the scene
   is identical to what 072/101 compute today.
2. **Given** any preset, **Then** band membership, health treatments, peer states and link
   topology are unchanged — only positions differ.
3. **Given** nodes have been dragged, **When** a preset is chosen, **Then** the manual positions
   are replaced, and the operator was warned first or can undo it.
4. **Given** a preset, **Then** labels do not collide at the default zoom. (Spec 101 shipped a
   label-collision regression that only a screenshot caught; presets multiply that risk.)
5. **Given** ~40 nodes, **When** switching presets, **Then** the transition does not drop frames
   below the established budget.

---

### User Story 3 — Save and restore a layout (Priority: P2)

An operator keeps an arrangement they like and returns to it later.

**Why this priority**: P2 because US1 and US2 are useful without it — but it is what makes the
effort of arranging worth spending. Gated on Q1.

**Acceptance Scenarios**:

1. **Given** an arrangement, **When** saved and the page reloaded, **Then** it is restored.
2. **Given** a saved layout, **When** a member that did not exist at save time has enrolled,
   **Then** it appears at its computed position rather than being hidden or crashing the restore.
3. **Given** a saved layout, **When** a member in it no longer exists, **Then** the stale entry
   is ignored silently.
4. **Given** a saved layout, **Then** the operator can discard it and return to computed.
5. **Given** saved layout data, **Then** it contains only node identifiers and positions — never
   federation state, never credentials.

---

### User Story 4 — Node-based post-processing on WebGPU (Priority: P2)

The post-processing chain runs on the modern node stack, enabling per-object selective bloom.

**Why this priority**: enabling work for US5 and a real improvement to 101's selection ring
(which currently has to avoid additive blending precisely because `UnrealBloomPass` washes it
out). Ships little visible value alone.

**Acceptance Scenarios**:

1. **Given** `WebGPURenderer`, **Then** all four ported materials render as they do today.
2. **Given** the node stack, **Then** every one of the 7 current effects is present or its
   omission is a recorded decision.
3. **Given** selective bloom, **Then** a selected node can bloom without its neighbours doing so.
4. **Given** a WebGL-only browser, **Then** the HUD still renders correctly.

---

### User Story 5 — The showcase (Priority: P3)

Capabilities impossible at 0.170: a light per live claw via `ClusteredLighting`, and
compute-shader particle flow on federation links.

**Why this priority**: P3 and honest about it. Most visually impressive, least operationally
necessary, and unavailable to any WebGL fallback viewer.

**Acceptance Scenarios**:

1. **Given** `ClusteredLighting` with one light per live claw, **Then** dozens of dynamic lights
   render without the frame collapse this would cause at 0.170.
2. **Given** compute-shader flow, **Then** it replaces 101's three-dot approximation with real
   particle density on live links only.
3. **Given** a WebGL-only browser, **Then** these degrade to 101's treatments with nothing broken
   or empty.
4. **Given** any showcase channel, **Then** it encodes real state — never decoration that could
   be misread as liveness.

---

### Edge Cases

- What happens when a node is dragged outside the camera's constrained pan/zoom range?
- What happens to a moved node when the operator switches to a preset and back — is the manual
  position remembered or gone?
- What happens on a touch device, where drag and pan are the same gesture?
- What happens if a saved layout was produced by an older version with different node ids?
- What happens to `mountA11y`'s keyboard tree when positions become arbitrary? Its ordering
  currently derives from computed layout order.
- What happens when a peer is dragged across the trust boundary line — does the boundary still
  mean anything visually?
- What happens if WebGPU is available but the driver crashes mid-session?

## Requirements *(mandatory)*

### Dragging (US1)

- **FR-001**: Any node MUST be draggable to a new position with a pointer.
- **FR-002**: A moved node MUST retain its position across poll refreshes, selection, expansion,
  search and member enrollment.
- **FR-003**: Dragging MUST NOT alter band membership, category, health, peer state, or link
  topology. Position is presentation only.
- **FR-004**: Dragging MUST NOT orbit or pan the camera, and camera control MUST remain available
  when not dragging a node.
- **FR-005**: Links MUST follow a moved node, including the member elbow routing through category
  headers.
- **FR-006**: 101's selection ring and label MUST track the node's current position.
- **FR-007**: Overlapping nodes MUST NOT snap, merge, or reorder.
- **FR-008**: A drag MUST be distinguishable from a click, so dragging does not also select.

### Presets (US2)

- **FR-009**: The HUD MUST offer a named set of layout presets, including the current computed
  layout as the default.
- **FR-010**: The default preset MUST reproduce today's computed layout exactly.
- **FR-011**: Switching presets MUST NOT change any data-derived property — only positions.
- **FR-012**: There MUST be a way back to the computed layout from any arranged state.
- **FR-013**: No preset may produce colliding labels at the default zoom.
- **FR-014**: Replacing manual positions MUST be either warned about or undoable.

### Save / restore (US3)

- **FR-015**: An operator MUST be able to save the current arrangement and have it restored later.
- **FR-016**: A saved layout MUST tolerate nodes added since it was saved (place at computed
  position) and nodes removed since (ignore silently). It MUST NOT fail closed on either.
- **FR-017**: A saved layout MUST be discardable.
- **FR-018**: Saved data MUST contain only node identifiers and positions — no federation state,
  no credentials, no inventory.
- **FR-019**: A corrupt or unreadable saved layout MUST fall back to computed and say so, never
  render a broken scene.

### WebGPU migration (US4)

- **FR-020**: All four `ShaderMaterial`s MUST be ported to node materials/TSL with no visual
  regression against 101's baseline screenshots.
- **FR-021**: The 7-pass chain MUST be rebuilt on the node stack; any effect dropped MUST be a
  recorded decision, not a silent loss.
- **FR-022**: The HUD MUST render correctly on a WebGL-only browser.
- **FR-023**: 101's six peer states, selection ring and link-flow gating MUST be preserved
  exactly — they are the visual baseline this migration must not disturb.

### Showcase (US5)

- **FR-024**: WebGPU-only capabilities MUST be progressive enhancements. The HUD MUST NOT depend
  on them to convey any operational state.
- **FR-025**: Every new visual channel MUST encode real state.
- **FR-026**: A WebGPU driver failure mid-session MUST degrade rather than blank the scene.

### Preservation

- **FR-027**: 072's FR-038 guarantee survives **for system-initiated changes**: no node moves as
  a result of selection, expansion, search, poll refresh or enrollment. Only the operator moves
  nodes.
- **FR-028**: The chat interface and right-hand information bar MUST NOT be altered.
- **FR-029**: The a11y tree and keyboard navigation MUST remain functional with arbitrary
  positions.
- **FR-030**: `scripts/reconcile-mcp.py` MUST exit 0.
- **FR-031**: Any new pure logic MUST be unit-tested under `src/orgchart/`, which must never
  import three.js.

## Success Criteria *(mandatory)*

- **SC-001**: Three dragged nodes remain exactly where placed after selection, expansion, a poll
  refresh, and a member enrollment.
- **SC-002**: The default preset is visually identical to the pre-102 HUD.
- **SC-003**: A saved layout survives a page reload, and survives one member being added and one
  removed.
- **SC-004**: On a WebGL-only browser the HUD renders correctly with showcase features absent
  rather than broken.
- **SC-005**: Median frame time stays within 110% of 101's recorded post-bump baseline, measured
  the same way on the same host.
- **SC-006**: 101's six peer states remain mutually distinguishable after the renderer migration,
  checked against the same declared-channel table.
- **SC-007**: No preset or dragged arrangement produces colliding labels at default zoom.
- **SC-008**: Saved layout data contains no federation state or credentials, verified by
  inspecting what is written.
- **SC-009**: Every requirement has evidence — a test, a build result, or a screenshot.

## Assumptions

- The operator's browser supports WebGL 2; WebGPU availability is not assumed.
- 101's `evidence/` baselines and probe script are the comparison point for SC-005/SC-006.
- Chrome DevTools (spec 048) is now provisioned, so visual verification is available — it was not
  when 101 began.
- ~40 nodes remains the scale. Nothing here targets thousands.
- `/api/n2n` remains unchanged as the source of topology and state.

## Out of Scope

- **WebXR / VR walkthrough.** Newly possible with WebGPU in r185, but a distinct feature.
- **Automatic layout algorithms** (force-directed, hierarchical solvers). Presets are a fixed
  named set; solving layout is its own problem.
- **Collaborative or shared layouts** — multiple operators seeing each other's arrangements.
- **Changing `/api/n2n`, `server.js`** — unless Q1 resolves toward a server-side store, in which
  case that becomes an explicit, scoped exception rather than a quiet drift.
- **Rendering thousands of nodes.**
- **The chat interface and right-hand info bar.**

## Dependencies

- Spec 101 (merged): `three@0.185.1`, the six-state peer encoding, the selection channel, link
  flow, and the recorded baselines.
- Spec 072: band layout, camera constraints, pure/render split, a11y tree.
- Spec 048 (now provisioned): Chrome DevTools for visual verification.
