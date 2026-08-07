# Feature Specification: HUD three.js Modernization — 0.170 → 0.185.1, plus legibility and selection work

**Feature Branch**: `101-hud-threejs-modernization`
**Created**: 2026-08-06
**Status**: Draft — awaiting clarification on the renderer decision (see Clarifications)
**Input**: Operator request, 2026-08-06 — "I can't click on Nate / eN2N netclaws in the HUD for details, they are not clickable"; then "anything else you think the HUD needs work on especially using three.js latest and greatest stuff"; then "proceed with fix, and 2-5; and bring in some really showboat three.js stuff we couldn't do in .170 with .185.1".

## Problem Statement

Three separate things are wrong with the HUD, and only one of them is about three.js.

1. **A federated peer cannot be inspected.** Clicking "Nate" repaints the detail panel with
   the generic overview instead of peer detail, because the click path passes a `setDetail`
   kind that has no branch. Root-caused in [research.md](./research.md) R7.
2. **The HUD ignores data it already has.** `/api/n2n` carries `channel_state`, `stale`, and
   `inventory_received_at` per peer. Nate (live channel, fresh inventory) and Byrn (stale
   since 2026-07-25) render essentially alike. Selection is `emissiveIntensity = 1.8` plus a
   scale bump, which is easy to miss in a bloom-heavy scene — there is no `OutlinePass` at all.
3. **The renderer is eighteen months behind.** `three@^0.170.0` against a current `0.185.1`,
   fifteen releases. This is the *least* urgent of the three, and the research shows it is
   also the cheapest to fix.

The framing that matters: the two improvements with the highest payoff need **no upgrade at
all**, and the two most impressive capabilities need a **renderer migration** that the version
bump alone does not deliver. Conflating "upgrade three.js" with "get the new toys" is the main
way this work could go wrong.

## Measured state (2026-08-06, verified — see research.md)

| Quantity | Value |
|---|---|
Installed three.js | `0.170.0` |
Latest three.js | **`0.185.1`** (2026-07-01), 15 releases ahead |
r171–r185 breaking changes affecting this HUD | **0** (grepped every deprecated/removed API) |
Build at `0.185.1` with zero code changes | **passes** (exit 0) |
Bundle delta | 753.22 kB → 798.95 kB, **+45.73 kB (+6.1%)** |
Test files importing three.js | **0** — the 85 passing tests prove nothing about rendering |
Modules importing three.js | **7**, all with **zero** test coverage |
`ShaderMaterial` instances (GLSL, would need TSL port) | **4** |
`onBeforeCompile` hooks (worst part of a WebGPU port) | **0** |
`EffectComposer` passes in the chain | **7** |
Scene size | ~40 nodes (7 peers + 30 members + Border + edges) |

## Clarifications

### Needed before Phase 1 — the renderer decision

- **Q: Migrate to `WebGPURenderer`, or stay on `WebGLRenderer`?** → **[NEEDS CLARIFICATION]**

  This is the only genuinely open question and it gates User Stories 6–7 entirely.
  `WebGPURenderer` does **not** support `ShaderMaterial` with raw GLSL, and does **not**
  support `EffectComposer` — both must be ported (4 shaders, one 7-pass chain). In exchange it
  is the *only* way to get compute-shader particles, `ClusteredLighting`, and node-based
  post-processing. It falls back to WebGL 2 automatically, but the fallback does **not**
  restore the WebGPU-only capabilities, so anything built on them is a progressive
  enhancement that the HUD must look correct without.

  The spec is written so US1–US5 are renderer-agnostic and shippable either way, and US6–US7
  are explicitly gated on this answer.

### Decisions taken without asking (reasonable defaults, recorded)

- **The version bump is decoupled from the renderer choice.** Verified free at build level
  (research R2), so it lands first and alone regardless of how the renderer question resolves.
  Bundling them would make a zero-risk change hostage to a large one.
- **Verification is visual, via the already-integrated `chrome-devtools-mcp`** (feature 048),
  not a new headless-GL harness. The seven three.js modules have no tests and a rendering
  regression is visual by nature (research R6). No new dependency.
- **The peer inspector is written against the `/api/n2n` shape, not `/api/graph`.** It is the
  richer source and already carries the staleness fields US3 needs (research R7).
- **Compute-shader particles are scoped to link flow only.** The >1M-unit headline is
  irrelevant at 40 nodes; as packet flow along federation links it is informative rather than
  decorative (research R5).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Inspect a federated peer (Priority: P1)

An operator clicks an eN2N peer in the org chart and sees that peer's federation detail:
identity, channel state, inventory freshness, chat enablement, and in-flight delegated tasks.

**Why this priority**: it is the reported defect, it is a genuine bug rather than an
enhancement, and it is currently misleading — the panel repaints with plausible-looking
content for a *different* subject, which is worse than doing nothing visible.

**Independent Test**: click each of the 7 peers; each shows its own detail. Fully testable
with no other story implemented.

**Acceptance Scenarios**:

1. **Given** the HUD is loaded with live `/api/n2n` data, **When** the operator clicks the
   peer node "Nate", **Then** the detail panel shows Nate's identity, state, channel state
   and inventory freshness — not the generic "This NetClaw" overview.
2. **Given** a peer with `stale: true` and an inventory from 12 days ago, **When** it is
   selected, **Then** the panel states the staleness explicitly rather than showing a bare
   timestamp the operator must date-arithmetic themselves.
3. **Given** a `severed` peer, **When** it is selected, **Then** the panel shows the severed
   state and does not present it as reachable.
4. **Given** keyboard navigation to a peer node, **When** it is activated, **Then** the same
   detail renders — both entry points are affected by the defect and both must be fixed.
5. **Given** a peer with in-flight delegated tasks, **When** it is selected, **Then** those
   tasks are listed.

---

### User Story 2 — Selection is unmistakable (Priority: P1)

An operator can always tell which node is currently selected, at any zoom, against a
bloom-heavy scene.

**Why this priority**: cheapest meaningful improvement in the whole feature, needs no upgrade
and no renderer decision, and it compounds with US1 — a detail panel is only useful if the
operator is confident *which* node it describes.

**Independent Test**: select nodes across bands and confirm the treatment is visible in a
screenshot without needing the panel to disambiguate.

**Acceptance Scenarios**:

1. **Given** any node is selected, **When** the operator looks at the scene, **Then** the
   selected node is distinguishable from every unselected node by a treatment that does not
   rely on emissive intensity alone.
2. **Given** a selected node in a cluster of cold members, **When** bloom is at its
   configured strength, **Then** the selection is still legible.
3. **Given** the selection changes, **Then** the previous node returns fully to its
   unselected appearance with no residue.
4. **Given** reduced-motion is preferred, **Then** the treatment is static rather than animated.

---

### User Story 3 — Liveness and staleness are readable from the scene (Priority: P1)

An operator can tell, without clicking anything, which peers and members are actually live and
which are stale or unreachable.

**Why this priority**: the biggest legibility win available, and it needs no upgrade. The data
is already fetched and already ignored. This is the difference between a topology picture and
an operational display.

**Independent Test**: with one live peer, one stale peer and one severed peer in the feed, all
three read differently in a screenshot.

**Acceptance Scenarios**:

1. **Given** Nate (`channel_state: "up"`, fresh inventory) and Byrn (`channel_state:
   "unknown"`, `stale: true`), **When** both render, **Then** they are visually distinct.
2. **Given** a peer whose inventory has never arrived (`inventory_received_at: null`),
   **Then** it is distinguishable from one with fresh inventory.
3. **Given** a member with `live: false` and `state: "provisioned"`, **Then** it is demoted
   relative to a live member, consistent with feature 072's existing visual-weight rules.
4. **Given** a peer transitions from live to stale while the HUD is open, **Then** the change
   is reflected on the next poll without a reload.
5. **Given** the encoding, **Then** it does not rely on color alone (accessibility — feature
   072 established an a11y tree that must stay coherent).

---

### User Story 4 — Federation links show flow (Priority: P2)

Links to live peers visibly carry traffic; links to stale or dead peers are visibly static.

**Why this priority**: this is where the "showboat" quality and genuine information coincide.
Deliberately P2 rather than P1 because it is an *addition* to US3's encoding rather than a
prerequisite for reading the scene. Achievable in the existing GLSL — no renderer decision.

**Independent Test**: one live and one stale peer; the live link animates, the stale one does not.

**Acceptance Scenarios**:

1. **Given** a peer with a live channel, **Then** its link to the Border shows directional flow.
2. **Given** a stale or severed peer, **Then** its link shows no flow.
3. **Given** reduced-motion is preferred, **Then** flow is conveyed without continuous animation.
4. **Given** ~40 nodes and their links, **Then** frame rate does not regress measurably.

---

### User Story 5 — Upgrade to 0.185.1 without regression (Priority: P2)

The HUD runs on `three@0.185.1` and looks and behaves exactly as it does today.

**Why this priority**: verified free at build level, so it is low-risk — but it delivers **no
visible operator value on its own**, which is precisely why it is P2 and not P1. It is
enabling work and honesty requires labelling it as such.

**Independent Test**: bump, build, load the HUD, confirm zero console errors and a visually
unchanged scene.

**Acceptance Scenarios**:

1. **Given** the dependency is `0.185.1`, **When** the project builds, **Then** it succeeds
   with no source change (already verified in an isolated probe — research R2).
2. **Given** the HUD is loaded in a browser, **Then** the console shows no errors and no
   three.js deprecation warnings.
3. **Given** the upgraded HUD, **Then** the org-chart bands, labels, links, selection and the
   full post-processing chain are visually intact.
4. **Given** the bundle grows ~6%, **Then** initial load remains acceptable on the operator's
   normal access path.
5. **Given** `THIRD_PARTY_NOTICES.md` or the HUD README cites a three.js version, **Then**
   they are updated (Principle XII).

---

### User Story 6 — Node-based post-processing on WebGPU (Priority: P3) 🔒

The post-processing chain runs on the modern node stack, enabling per-object selective bloom.

**Why this priority**: P3 and **gated on the renderer clarification**. It requires porting 4
`ShaderMaterial`s to TSL and rebuilding a 7-pass chain — bounded but real. Its main payoff is
making US2's selection treatment cleaner, which US2 already achieves acceptably without it.

**Independent Test**: the HUD renders identically on the node stack, and selective bloom
applies to one object without affecting its neighbours.

**Acceptance Scenarios**:

1. **Given** `WebGPURenderer`, **Then** the four custom materials render as they do today.
2. **Given** the node post-processing stack, **Then** bloom, SMAA, vignette, RGB-shift,
   afterimage, film and glitch equivalents are all present or a deliberate, recorded omission.
3. **Given** a WebGL-only browser, **Then** the HUD still renders correctly via fallback.
4. **Given** selective bloom, **Then** the selected node can bloom without its neighbours doing so.

---

### User Story 7 — Capabilities impossible at 0.170 (Priority: P3) 🔒

The HUD uses genuinely new r185 capabilities: `ClusteredLighting` for per-claw lighting, and
compute-shader particles for link flow.

**Why this priority**: P3, **gated on the renderer clarification**, and explicitly a
progressive enhancement — the WebGL fallback cannot provide these, so the HUD must be correct
without them. This is the most visually impressive story and the least operationally necessary,
and the priority reflects that honestly rather than rewarding novelty.

**Independent Test**: on a WebGPU browser, per-claw lights and particle flow are present; on a
WebGL-only browser, the HUD still reads correctly.

**Acceptance Scenarios**:

1. **Given** `ClusteredLighting` and one light per live claw, **Then** dozens of dynamic lights
   render without the frame-rate collapse this would cause at 0.170.
2. **Given** compute-shader particle flow on federation links, **Then** live links carry
   visible packet flow and dead links do not.
3. **Given** a WebGL-only browser, **Then** these degrade to US3/US4's non-WebGPU treatments
   with no broken or empty visuals.
4. **Given** either capability, **Then** it conveys real state — never decoration that could
   mislead an operator about liveness.

---

### Edge Cases

- What happens when `/api/n2n` returns zero peers (fresh install)? US3's encoding must have an
  empty state — feature 072 already defines first-run behavior that must not regress.
- What happens when two peers share a `display_name` (the live "Hermes" case, two identities)?
  Feature 072's `disambiguateLabels` handles the label; US1's inspector must show the
  *identity*, not just the label, or the panel is ambiguous.
- What happens on a browser with neither WebGPU nor adequate WebGL 2?
- What happens if `channel_state` is `"unknown"` — genuinely unknown, or not yet polled? US3
  must not render "unknown" as "dead".
- What happens to the CSS2D label layer under `WebGPURenderer`? Labels are DOM overlays and
  should be unaffected, but this is unverified.
- What happens when a peer is selected and then disappears from the feed?

## Requirements *(mandatory)*

### Peer inspection (US1)

- **FR-001**: Clicking or keyboard-activating any eN2N peer node MUST render that peer's own
  federation detail.
- **FR-002**: The inspector MUST be driven by the `/api/n2n` peer shape, and MUST NOT be
  implemented by routing peers to the existing BGP-session renderer, whose payload contract
  differs and would render undefined fields.
- **FR-003**: The inspector MUST show, at minimum: identity, display name, state, channel
  state, inventory freshness, chat enablement, and in-flight delegated tasks.
- **FR-004**: Inventory freshness MUST be expressed in operator terms (relative age and an
  explicit stale/fresh judgement), not as a raw timestamp alone.
- **FR-005**: Both the pointer and the keyboard/accessibility activation paths MUST be fixed.
- **FR-006**: No `setDetail` kind may fall through to the default overview branch. An
  unrecognised kind MUST fail loudly in development rather than silently rendering another
  subject's content — this silent fallthrough *is* the defect.

### Selection (US2)

- **FR-007**: The selected node MUST be distinguishable by a treatment that does not depend on
  emissive intensity alone.
- **FR-008**: Deselection MUST fully restore the prior appearance.
- **FR-009**: Exactly one node MUST read as selected at a time.
- **FR-010**: The selection treatment MUST respect reduced-motion preference.
- **FR-011**: Selection MUST remain legible at the extremes of the existing camera's
  configured zoom range.

### Liveness encoding (US3)

- **FR-012**: Peers MUST be visually differentiated by channel state and inventory staleness.
- **FR-013**: Members MUST be visually differentiated by `live` state, consistent with feature
  072's existing visual-weight rules rather than inventing a competing scheme.
- **FR-014**: The encoding MUST NOT rely on color alone, and MUST remain coherent with the
  existing a11y tree.
- **FR-015**: A state change MUST be reflected on the next poll without a reload.
- **FR-016**: `unknown` state MUST be rendered as distinct from both healthy and dead.
- **FR-017**: The encoding MUST NOT overstate confidence — a peer that is merely unpolled must
  not read as failed.

### Link flow (US4)

- **FR-018**: Links to live-channel peers MUST show directional flow; links to stale or severed
  peers MUST NOT.
- **FR-019**: Flow direction MUST correspond to something real, or MUST be non-directional.
- **FR-020**: Flow MUST respect reduced-motion preference.
- **FR-021**: Flow MUST NOT measurably regress frame rate at current scene scale.

### Version upgrade (US5)

- **FR-022**: The HUD MUST run on `three@0.185.1`.
- **FR-023**: The upgrade MUST NOT require changes to HUD source (verified at build level;
  runtime is what US5's acceptance covers).
- **FR-024**: After upgrade the HUD MUST load with zero console errors and zero three.js
  deprecation warnings.
- **FR-025**: All existing visual behavior MUST be preserved — bands, labels, links,
  selection, camera, and every post-processing pass.
- **FR-026**: Documentation citing a three.js version MUST be updated (Principle XII).
- **FR-027**: `scripts/reconcile-mcp.py` MUST exit 0 (CLAUDE.md; CI gate).
- **FR-028**: The upgrade MUST be verifiable without disturbing the running
  `netclaw-hud.service`, or the disruption MUST be an explicit confirmed step.

### Renderer migration (US6/US7) — gated

- **FR-029**: If `WebGPURenderer` is adopted, all four `ShaderMaterial`s MUST be ported to node
  materials/TSL with no visual regression.
- **FR-030**: If adopted, the 7-pass `EffectComposer` chain MUST be rebuilt on the node stack,
  and any effect deliberately dropped MUST be recorded as a decision rather than silently lost.
- **FR-031**: If adopted, the HUD MUST render correctly on a WebGL-only browser via fallback.
- **FR-032**: WebGPU-only capabilities MUST be progressive enhancements. The HUD MUST NOT
  depend on them for conveying any operational state.
- **FR-033**: Any new visual channel MUST encode real state, never decoration that could be
  misread as liveness.

### Verification

- **FR-034**: Runtime verification MUST be visual, using the existing `chrome-devtools-mcp`
  integration, and MUST NOT introduce a new test dependency.
- **FR-035**: Verification MUST cover zero console errors plus a screenshot confirming the
  scene renders.
- **FR-036**: Any new pure logic MUST be unit-tested on the `src/orgchart/` side of feature
  072's pure/render split, which forbids importing three.js.

### Preservation

- **FR-037**: The chat interface and the right-hand information bar MUST NOT be altered —
  carried forward from feature 072's explicit operator constraint.
- **FR-038**: Feature 072's layout stability guarantees MUST hold: no sibling node moves as a
  result of selection or expansion.
- **FR-039**: `server.js` and the `/api/n2n` contract MUST NOT change. This is a client-side feature.
- **FR-040**: The existing a11y tree and keyboard navigation MUST remain functional.

## Success Criteria *(mandatory)*

- **SC-001**: An operator can click any of the 7 peers and see that peer's own detail — 7/7,
  where today it is 0/7.
- **SC-002**: In a screenshot with no panel visible, an observer can correctly identify which
  node is selected.
- **SC-003**: In a screenshot, an observer can correctly sort peers into live / stale /
  severed without clicking.
- **SC-004**: The HUD runs on `0.185.1` with zero console errors and no visual regression.
- **SC-005**: Frame rate at current scene scale is no worse than before, measured the same way
  before and after.
- **SC-006**: No `setDetail` call can silently render the wrong subject — an unhandled kind is
  detectable rather than plausible.
- **SC-007**: Bundle growth from the upgrade stays within ~10% of today's 753 kB.
- **SC-008**: If WebGPU is adopted, the HUD renders correctly on a WebGL-only browser, with
  the WebGPU-only capabilities absent rather than broken.
- **SC-009**: Every claim of "verified" in this feature is backed by a build result, a
  screenshot, or a test — not by inspection alone.

## Assumptions

- The operator's browser supports WebGL 2 today; WebGPU availability is not assumed.
- `/api/n2n` remains the source of truth for federation state, unchanged by this work.
- Feature 072's pure/render split, band layout, camera constraints and a11y tree are the
  foundation to build on, not to revisit.
- The ~40-node scale holds. Nothing here is designed for thousands of nodes, and the research
  explicitly rejects capabilities justified only at that scale.
- `chrome-devtools-mcp` (feature 048) is installed and usable against `localhost:3000`.
- `netclaw-hud.service` runs a live Vite dev server from the working tree, so dependency
  changes are operationally visible and must be sequenced deliberately.
- The 4 `ShaderMaterial`s and 0 `onBeforeCompile` hooks measured in research R4 are the
  complete custom-shader surface.

## Out of Scope

- **WebXR / VR walkthrough of the mesh.** Newly possible with WebGPU in r185 and genuinely
  interesting, but a distinct feature with its own interaction design.
- **Rendering thousands of nodes.** Compute particles and instancing headlines target a scale
  this HUD does not have; scoped in R5 to link flow only.
- **Replacing CSS2D labels with SDF text** (`troika-three-text`). Current labels are crisp and
  selectable; the only gain is depth-correct occlusion, which has not been reported as a problem.
- **Changing `server.js`, `/api/n2n`, or any MCP server.** Client-side only.
- **The chat interface and right-hand info bar** (FR-037).
- **Revisiting feature 072's layout algorithm.**
- **Upgrading to r186+.** Unreleased at spec time; its `Object3D.dispose()` change is noted in
  research R3 as a future consideration.

## Dependencies

- `three@0.185.1` from npm.
- Feature 072's org-chart modules (`src/orgchart/`, `src/orgchart-render/`).
- Feature 048's `chrome-devtools-mcp` for runtime verification.
- The `/api/n2n` endpoint as it exists today.
