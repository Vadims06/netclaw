# Feature Specification: Federated AI-Augmented Network Topology Visualization

**Feature Branch**: `121-federated-topology-viz`
**Created**: 2026-08-30
**Status**: Draft
**Input**: User description: "Federated AI-augmented network topology visualization: a new capability that replaces the Canny-edge-reconstruction approach spec 120 (comfyui-topology-viz) had to build workarounds for, with a two-stage pipeline where structural correctness comes entirely from deterministic diagram generation and the diffusion model only ever restyles an already-correct image, never reconstructs one from an edge map. Stage A (structural, no diffusion involved): generate an accurate network diagram with real vendor iconography from actual topology data, using NetClaw's existing drawio-diagram skill (or a new N2G-based adapter if the freeform-only case needs it) rather than the plain box-and-line renderer spec 120 built. Stage B (presentation, diffusion involved): take Stage A's rendered image and apply a true image-editing model (Qwen-Image-Edit-2509, GGUF-quantized, Apache-2.0) to restyle it while preserving every line, icon, and label. This must be built as a real internal federation (iN2N) delegation flow: Border calls Stage A on the existing `johns-risk/viz` member (already has drawio-diagram, currently not live), gets an image back, calls Stage B on a ComfyUI-capable member, gets the final styled image back — Border performs no diffusion or diagram-rendering work itself. Spec 120's existing structural (Flux+ControlNet+Canny) pipeline becomes this architecture's explicit fallback tier, used unchanged, when either federation member is unreachable or the request is freeform-only. A research spike must verify empirically whether GGUF-quantized Qwen-Image-Edit preserves line-work/text legibility before any models are downloaded, falling back to evaluating FLUX.2 [klein] 4B if it doesn't. Read-only with respect to network devices throughout; follows the full SDD workflow per Constitution Principle XVI."

## Clarifications

### Session 2026-08-30

- Q: How does the new federated pipeline relate to spec 120's existing conversational skill (`comfyui-topology-viz`)? → A: Same existing skill/invocation stays the single entry point; it internally chooses the federated path vs. the fallback path per FR-009/FR-011's existing routing rules, so the engineer's request phrasing never changes and "which path was used" is metadata on the same response.
- Q: What is the measurable pass/fail bar for the pre-build research spike (FR-015) on the candidate styling model's line-work/text fidelity? → A: 100% of device labels in the test image(s) must be reproduced exactly, character-for-character, and every connection line must remain traceable without gaps — a soft/subjective "looks usable" bar would let the same class of failure spec 120 already hit (illegible AI-reconstructed text) back in through the spike itself.
- Q: Should the spec mandate a payload-size bound or transport mechanism for passing Stage A's rendered image to Stage B over the internal federation channel? → A: Deferred entirely to planning — not a spec-level concern; the existing internal channel already carries arbitrary JSON-RPC payloads in production, and if a real size limit turns out to matter, `/speckit.plan`'s research phase investigates and designs around the actual constraint rather than the spec guessing at one.
- Q: Does this feature need new connection-health monitoring/reconnection for `johns-risk/viz` beyond bringing it online once, in case it drops mid-operation later? → A: No — rely entirely on NetClaw's existing per-request member reachability check (the same mechanism FR-009 already uses); a mid-operation drop is simply caught the next time the member is called, with no new persistent-monitoring capability in scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A Provably Accurate, Styled Topology Image (Priority: P1)

A network engineer asks for a stylized image of a real topology (from any of NetClaw's existing
topology-of-record integrations) and receives an image whose devices, icons, connections, and
labels are correct — not because an AI model successfully reconstructed them from a lossy edge
map, but because they were never at risk of being wrong in the first place. The diffusion step
only ever changes how the already-correct diagram *looks*.

**Why this priority**: This is the entire reason this feature exists. Spec 120's Canny+ControlNet
pipeline proved, through real testing, that asking a diffusion model to reconstruct structure from
an edge map produces real correctness failures (a phantom device, illegible labels) that had to be
patched around after the fact. This feature removes that failure class by construction instead of
patching it.

**Independent Test**: Request a stylized image of a topology with real device data behind it (a
live source, not freeform). Confirm the delivered image's devices, icons, connections, and text
labels exactly match the source topology, and confirm (via logs/response metadata) that the image
passed through both the structural stage and the styling stage — not the fallback path.

**Acceptance Scenarios**:

1. **Given** a topology available through a live source integration, **When** the engineer
   requests a stylized image, **Then** the delivered image shows the correct number of devices,
   the correct connections between them, and legible, correct hostname/label text, matching the
   source topology exactly.
2. **Given** a completed request, **When** the engineer asks how it was produced, **Then** NetClaw
   can state whether the structural+styling pipeline was used or the fallback was used, so the
   engineer knows which correctness guarantee applies to what they received.
3. **Given** a topology whose devices have recognizable roles (router, switch, firewall, etc.),
   **When** the image is generated, **Then** each device is rendered with icon styling
   appropriate to a real diagramming convention (not a generic, unlabeled shape), and that
   rendering is not altered by the styling stage in a way that changes what role it depicts.

---

### User Story 2 - Uninterrupted Service When the Federated Path Isn't Available (Priority: P2)

A network engineer asks for a stylized topology image at a time when the structural-diagram
member or the styling member is unreachable, or when the request is a freeform description with
no real device data behind it. They still get a real, stylized image back — using the same
generation capability NetClaw already shipped — rather than an error or a degraded experience.

**Why this priority**: The federated pipeline depends on two additional moving parts (two
federation members) beyond what already works today. Losing image generation entirely whenever
either one is briefly unavailable would be a regression from what NetClaw can already do.

**Independent Test**: With one (or both) of the federation members deliberately unreachable,
request a stylized topology image and confirm a real image is still produced, and that NetClaw
tells the engineer it used the fallback path rather than silently pretending the primary path
succeeded.

**Acceptance Scenarios**:

1. **Given** the structural-diagram member is unreachable, **When** the engineer requests a
   stylized image, **Then** NetClaw falls back to the existing structural (Flux+ControlNet)
   pipeline and still delivers a real image, clearly indicating the fallback was used.
2. **Given** both federation members are reachable but the request is a freeform description with
   no real device data behind it, **When** the engineer requests a stylized image, **Then**
   NetClaw uses the fallback pipeline directly (there is no real device data for the
   structural-diagram member to work from) rather than attempting and failing the federated path
   first.
3. **Given** the styling member specifically (not the structural-diagram member) is unreachable,
   **When** the engineer requests a stylized image, **Then** NetClaw reports that distinctly from
   "structural member unreachable" — the engineer should be able to tell which half of the
   pipeline had the problem.

---

### User Story 3 - The Structural-Diagram Member Comes Online (Priority: P3)

The existing `johns-risk/viz` federation member — already carrying the diagram-generation
capability this feature depends on — is provisioned but not currently connected. An operator
needs it brought up and verified reachable before the federated pipeline can do any real work.

**Why this priority**: Without this, User Stories 1 and 2's "primary path" literally cannot run —
it's a prerequisite, not a nice-to-have, but it's scoped as its own story because "bring a
provisioned member online" is a distinct, independently-verifiable unit of work from anything
about image generation itself.

**Independent Test**: Bring the member online and confirm, via the existing federation member
status/health mechanism, that it reports live and reachable from Border.

**Acceptance Scenarios**:

1. **Given** the `johns-risk/viz` member is provisioned but not live, **When** it is brought
   online, **Then** Border's member listing reports it as live and reachable.
2. **Given** the member is live, **When** Border calls its diagram-generation capability with a
   real topology, **Then** a real diagram image is returned over the internal channel, distinct
   from Border's own fallback rendering.

---

### Edge Cases

- What happens when Stage A succeeds (a correct diagram comes back) but Stage B fails (the
  styling member errors or times out)? The engineer should still be offered the correct,
  un-styled Stage A diagram rather than nothing, with a clear note that styling failed — a
  correct plain diagram is more useful than no diagram at all.
- What happens when the styling stage's model can't reliably preserve fine line-work or text at
  working resolution (the research spike's own risk)? This must be caught by the pre-build
  research spike, not discovered live in production — see Assumptions.
- What happens when a request arrives while a previous federated request is still in flight? The
  system must not allow two overlapping requests to race against the same downstream ComfyUI GPU
  resource, mirroring the single-in-flight constraint spec 120 already established for its own
  pipeline.
- What happens when the structural-diagram member returns a diagram for a topology so large it
  exceeds what the styling stage can process at its working resolution? The engineer is told this
  plainly rather than receiving a corrupted or silently-truncated result.
- What happens when a member connection drops mid-request (after Stage A succeeds, during Stage
  B)? This is distinct from "member unreachable at request start" — the engineer must get a clear
  report of a mid-request failure, not an indefinite wait.

## Requirements *(mandatory)*

### Functional Requirements

**Structural correctness by construction (Story 1)**

- **FR-001**: System MUST generate the structural diagram for a request from actual topology
  device/connection data via a deterministic diagram-generation capability — never from a
  diffusion model reconstructing structure from an image or edge map.
- **FR-002**: The structural diagram MUST render each device with role-appropriate iconography
  (not a generic, unlabeled shape) and a legible, correct label, and MUST render every real
  connection between devices.
- **FR-003**: The styling stage MUST be constrained to preserve the structural diagram's lines,
  icons, and labels — its only permitted effect is visual/stylistic (color, texture, lighting,
  background), never adding, removing, or relabeling a device or connection.
- **FR-004**: System MUST make it possible for the engineer to determine, per completed request,
  whether the structural+styling (federated) path or the fallback path produced the delivered
  image.
- **FR-004a**: This capability MUST be invoked through spec 120's existing conversational skill —
  the engineer's request phrasing does not change; the choice between the federated path and the
  fallback path (per FR-009/FR-011) is made internally, and the path used (FR-004) is surfaced as
  part of that same skill's response, not through a separate command.

**Federated delegation (Stories 1, 3)**

- **FR-005**: The structural-diagram step and the styling step MUST run as separate internal
  federation member capabilities, invoked from Border, rather than as in-process code on Border
  itself. Border MUST NOT perform diagram rendering or diffusion generation directly for this
  path.
- **FR-006**: System MUST use NetClaw's existing internal federation member-invocation mechanism
  to call each stage and receive its result, consistent with how NetClaw already delegates
  deterministic tool executions to specific-purpose members elsewhere.
- **FR-007**: The existing `johns-risk/viz` federation member (already provisioned with a
  diagram-generation capability) MUST be brought online and verified reachable as part of this
  feature — a new member is not required for the structural stage. Ongoing connection-health
  monitoring or automatic reconnection is explicitly out of scope: a later mid-operation drop is
  handled entirely by the existing per-request reachability check (FR-009), not a new persistent
  monitoring capability.
- **FR-008**: System MUST determine, as part of this feature's design work, whether the styling
  stage runs on the same member as the structural stage or a separate dedicated member; either
  is acceptable so long as the choice is deliberate and documented, not incidental.

**Fallback behavior (Story 2)**

- **FR-009**: When the structural-diagram member is unreachable, System MUST fall back to NetClaw's
  existing structural image-generation pipeline (already shipped) and clearly indicate to the
  engineer that the fallback was used.
- **FR-010**: When the styling member is unreachable but the structural-diagram member succeeded,
  System MUST report that distinctly from a structural-member failure — the engineer must be able
  to tell which stage had the problem — and MUST still offer the correctly-structured, unstyled
  diagram rather than nothing (Edge Cases).
- **FR-011**: When a request has no real device data behind it (a freeform description), System
  MUST route directly to the existing fallback pipeline rather than attempting the federated path
  and failing.
- **FR-012**: The existing fallback pipeline (spec 120's structural Flux+ControlNet+Canny
  generation) MUST be reused exactly as it already exists — this feature MUST NOT modify it.
- **FR-013**: System MUST allow at most one federated (or fallback) generation request in flight
  at a time, consistent with the existing single-in-flight constraint (Edge Cases).

**Cross-cutting**

- **FR-014**: This feature MUST NOT make, or enable making, any configuration change to a network
  device at any point in either the structural or styling stage — it is read-only visualization,
  identical in this respect to spec 120.
- **FR-015**: Before any new model weights for the styling stage are downloaded, a research spike
  MUST empirically verify — using real, already-existing generated images as test input — that the
  candidate styling model preserves fine line-work and text legibility against a fixed, measurable
  bar: 100% of device labels in the test image(s) reproduced exactly, character-for-character, and
  every connection line remaining traceable without gaps. If the candidate model does not meet
  this bar, System's design MUST document that finding and identify a fallback model candidate
  rather than proceeding on an unverified assumption.
- **FR-016**: System MUST verify the real, exact download size and licensing/access terms of any
  new model file directly against its source before downloading it, rather than relying on an
  estimate or an unverified assumption — a prior feature's own experience found both an incorrect
  size estimate and a silently-gated download that produced a corrupt file when this check was
  skipped.

### Key Entities

- **Topology Snapshot**: The same complete set of devices, roles, and connections already defined
  by spec 120 (and, before that, spec 046) — this feature's structural stage consumes it, it does
  not redefine it.
- **Structural Diagram**: The deterministic, correct-by-construction rendered image (real device
  iconography, real labels, real connections) produced by the structural-diagram federation member
  from a Topology Snapshot — the input to the styling stage.
- **Styled Image**: The final delivered image — the Structural Diagram after the styling stage has
  altered its visual appearance without altering its structural content.
- **Federation Member**: An addressable, independently-connected NetClaw participant (already an
  existing NetClaw concept) that exposes a specific capability Border can invoke and receive a
  result from — this feature uses one for the structural stage and one (possibly the same one) for
  the styling stage.
- **Generation Path**: Which route produced a given delivered image — the federated
  (structural-diagram-member + styling-member) path, or the existing fallback path — recorded per
  request so the engineer can know which correctness guarantee applies.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 100% of requests sourced from a live topology integration and successfully
  completed via the federated path, every device, connection, and label in the delivered image
  matches the source topology exactly — zero phantom devices, zero dropped connections, zero
  illegible or incorrect labels.
- **SC-002**: 100% of requests that cannot use the federated path (member unreachable, or
  freeform-only) still produce a real delivered image via the fallback path, with zero silent
  failures.
- **SC-003**: An engineer can determine which generation path (federated vs. fallback) produced
  any given delivered image, for 100% of completed requests.
- **SC-004**: The previously-provisioned-but-offline structural-diagram federation member is
  confirmed live and reachable, verified independently of any specific image-generation request.
- **SC-005**: The pre-build research spike produces a documented go/no-go finding — measured
  against 100% exact label reproduction and fully traceable connection lines on the test image(s)
  — on the primary styling-model candidate's line-work/text fidelity before any styling-stage
  model weights are downloaded — this feature is not considered ready for its styling-stage
  implementation until that finding exists.

## Assumptions

- This feature builds directly on spec 120 (`comfyui-topology-viz`): it reuses spec 120's
  Topology Snapshot data model and its existing fallback generation pipeline unchanged, and does
  not modify any of spec 120's shipped code.
- "Real vendor iconography" means diagram-convention device icons (router/switch/firewall/etc.
  shapes recognizable in standard network-diagramming tools), not photorealistic hardware
  renders — this is a diagramming-tool-quality bar, not a photorealism bar.
- The structural-diagram generation capability is exposed by NetClaw's existing diagramming
  skill(s), already present on the `johns-risk/viz` federation member; this feature does not need
  to build new diagram-rendering logic from scratch, only bring the existing capability online and
  reachable, and adapt its output for the styling stage's input needs if necessary.
- The styling stage requires new model weights not currently installed anywhere in this
  environment; exactly which model (subject to the research spike's finding, FR-015) and exactly
  which federation member hosts it are implementation decisions for the planning phase, not fixed
  by this specification.
- Both federation stages are deterministic tool executions (a rendering step, a generation step)
  with clear inputs and outputs — neither requires agentic judgment or reasoning at the member
  side, which is why this feature uses NetClaw's existing tool-style member invocation mechanism
  rather than its agentic/skill-delegation mechanism.
- "Read-only with respect to network devices" carries over unchanged from spec 120: nothing in
  this feature's structural or styling stage ever issues a configuration command to any network
  device.
- A single generation request is expected to involve real, non-trivial processing time at each
  stage (structural rendering, then GPU-bound diffusion styling); this feature does not introduce
  a fixed timeout at either stage, consistent with spec 120's own decision on this point.
- The exact mechanism and any size bound for passing Stage A's rendered image to Stage B over the
  internal federation channel is deliberately left open here — a planning-phase decision, informed
  by the existing internal channel's real, already-production behavior, not a spec-level
  requirement (Clarification session 2026-08-30).
