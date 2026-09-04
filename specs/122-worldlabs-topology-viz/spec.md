# Feature Specification: World Labs Fantastical Topology Visualization

**Feature Branch**: `122-worldlabs-topology-viz`
**Created**: 2026-09-03
**Status**: Draft
**Input**: User description: "Add a new worldlabs-marble-mcp MCP server plus an orchestrating skill that produces an AI-augmented, explorable 3D world visualization of a real network topology, built on top of the existing spec 121 pipeline. The World Labs Marble API is a generative world model that does not accept structured or graph input and has no mechanism for precise node placement, so this feature is explicitly a decorative or companion visualization, not a replacement for accurate topology diagrams. The real structurally-correct diagram, produced by the existing spec 121 topology-diagram-mcp render_structural tool from real devices and links pulled from CML or pyATS, remains the authoritative artifact. This new feature takes that already-correct PNG and uses it as the reference image for Marble image-conditioned world generation, paired with a generated text prompt translating the topology role and connectivity structure into descriptive language for a fantastical scene while preserving the connectivity pattern shown. Poll for completion then surface the resulting world viewer URL and or exported assets. Marble generation costs real credits and takes about 5 minutes per world, so the feature must require explicit per-invocation user confirmation before any credits spending call, and must support a no-cost prompt preview or dry-run mode. API key handling must read from an environment variable, never hardcoded, logged, or committed. Must follow docs/ADDING-AN-MCP.md and pass scripts/reconcile-mcp.py, matching the existing FastMCP server convention used by every other NetClaw MCP. No new persistent storage; only in-memory or response-level correlation between a topology snapshot and its generated world id and viewer URL."

## Clarifications

### Session 2026-09-03

- Q: When multiple generations might be in flight, or a generation was started in a previous session, how should the system let a user check status later — should it track state at all, or be a stateless pass-through? → A: Fully stateless — the system only wraps World Labs calls 1:1; whoever starts a generation must hold onto the returned operation/world id themselves to check status later. No state kept anywhere in NetClaw.
- Q: Should confirmed (credit-spending) generation attempts be recorded in this repo's existing GAIT audit trail for accountability? → A: No audit logging — rely entirely on World Labs' own account/billing history to see what was spent; NetClaw records nothing.
  - **Correction (same session, found during `/speckit.analyze`)**: The above answer directly conflicts with Constitution Principle IV ("No operation MAY execute silently — all actions MUST produce an audit record") and the Forbidden Operations list ("Silent operations without GAIT logging"). Constitution conflicts are not diluted or reinterpreted. Revised decision: each confirmed generation attempt MUST produce a GAIT record via the existing `gait_record_turn` mechanism (the same one every other consequential NetClaw operation already uses — see `workspace/skills/atlassian-itsm/SKILL.md` for the established pattern). This is **not** a new audit-logging mechanism and does not conflict with FR-013's "no new persistent storage" — GAIT is the repo's pre-existing, already-mandated, Git-based audit substrate, not a new database or file store. What survives from the original answer: no *new* store of any kind is introduced, and the record is minimal (topology identity, operation id, cost if known, outcome) — never the API key, never raw device data.
- Q: The World Labs dashboard mentions request-start rate limits — should hitting one be its own distinct failure category, separate from generic failure? → A: Yes, add rate-limiting as a fourth distinct failure category (alongside auth failure, insufficient-credits, and generic failure) with its own clear "wait and retry" message.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Preview a fantastical prompt at no cost (Priority: P1)

A network engineer has a real topology snapshot (from a CML lab, a pyATS run, or any other existing topology source already normalized into the devices/links shape used by spec 121) and wants to see what an AI-augmented "explorable world" version of it would look like conceptually, without spending any credits or waiting for generation.

**Why this priority**: This is the only part of the feature that is free and instant, and it is the safety valve that keeps a person from accidentally starting an expensive, five-minute generation they did not mean to start. It must exist before any credit-spending path is built.

**Independent Test**: Can be fully tested by supplying a topology snapshot and requesting a preview, and confirming the system returns the reference image and the composed text prompt without contacting World Labs or spending any credits.

**Acceptance Scenarios**:

1. **Given** a valid topology snapshot with devices and links, **When** the user requests a preview, **Then** the system returns the structurally-correct reference diagram and a generated descriptive text prompt that reflects each device's role and how devices are connected, with no external API call made and no credits spent.
2. **Given** a topology snapshot that has already been rendered once, **When** the user requests another preview with a different theme (e.g., "underwater city" vs. "floating islands"), **Then** the system returns a new text prompt reflecting the new theme while still describing the same real connectivity pattern, again at no cost.

---

### User Story 2 - Generate a fantastical world from a real topology (Priority: P1)

Having reviewed a preview, the network engineer confirms they want to actually spend credits to generate the explorable 3D world, and receives a link they can open to explore it once it is ready.

**Why this priority**: This is the actual value the user asked for — a real, explorable, AI-generated world inspired by their real topology. It depends on Story 1 existing first (the confirmation gate), so it is P1 but sequenced after the preview capability.

**Independent Test**: Can be fully tested by taking a previewed prompt, explicitly confirming generation, and verifying that a world is produced and a working viewer link (or exported asset reference) is returned once generation completes.

**Acceptance Scenarios**:

1. **Given** a previewed reference image and text prompt, **When** the user explicitly confirms they want to generate, **Then** the system starts generation, reports that credits will be spent and generation will take roughly five minutes, and does not start generation without that explicit confirmation.
2. **Given** a generation has been started, **When** the user checks on it later, **Then** the system reports whether it is still in progress, has completed (with a viewer link and/or exported asset reference), or has failed (with a clear reason).
3. **Given** a completed generation, **When** the user opens the returned link, **Then** they can explore a 3D world that is thematically recognizable as inspired by the original topology's structure (e.g., the same number of major "hubs" connected in a similar pattern), while understanding this world is not a substitute for the accurate diagram.

---

### User Story 3 - Understand this is not the source of truth (Priority: P2)

A user who has not used this feature before, or who is looking at a generated world without context, needs to clearly understand that the fantastical world is a decorative companion piece and that the accurate topology diagram (from the existing spec 121 pipeline) remains the authoritative representation of the real network.

**Why this priority**: Without this, a generated world could be mistaken for an accurate representation of network structure, which is actively misleading for operational decisions. This is a safety/clarity requirement rather than new functionality, so it is P2.

**Independent Test**: Can be fully tested by inspecting any preview or generation result and confirming it is labeled as a decorative/companion visualization alongside a reference to (or copy of) the authoritative structural diagram it was derived from.

**Acceptance Scenarios**:

1. **Given** any preview or completed generation result, **When** the user views it, **Then** the result clearly states it is an artistic/decorative interpretation and is not a precise representation of device placement, cabling, or state, and includes or references the authoritative structural diagram it was generated from.

---

### Edge Cases

- What happens when the topology snapshot has more devices than the underlying structural renderer can legibly draw (the existing spec 121 density ceiling)? The system MUST surface that same limitation before attempting any World Labs call, since no reference image can be produced.
- What happens when the World Labs account has insufficient credits at the moment generation is confirmed? The system MUST report this clearly and MUST NOT retry automatically or silently fall back to a degraded mode.
- What happens when authentication to World Labs fails (invalid/expired/misconfigured API key)? The system MUST report a clear authentication failure distinct from a credits or quota failure, and MUST NOT leak the key value in any error message, log, or response.
- What happens when starting a generation is rejected due to World Labs' own rate limiting? The system MUST report this as a distinct failure from authentication or insufficient-credits failures, with guidance to wait and retry, and MUST NOT automatically retry a paid operation on the user's behalf.
- What happens when a generation request times out or fails on World Labs' side after credits may have already been spent? The system MUST report the failure and MUST NOT silently retry a paid operation without new explicit confirmation.
- What happens if the user asks for a preview or generation with a **single-device** topology (one device, zero links)? The system MUST still produce a coherent result (a "preview" of a single-location scene) rather than erroring, since the underlying structural renderer already supports exactly this case. **Correction (found during implementation, `/speckit.implement`)**: a truly **empty** topology (zero devices) is different — `render_structural` explicitly rejects it (`"devices list is empty — nothing to render"`), it does not render a blank/empty result. The system MUST surface that specific, existing rejection clearly (same treatment as the density-ceiling case, FR-012's spirit) rather than attempting to fabricate a "coherent result" that cannot exist for zero devices.
- What happens if a user tries to reuse a previous generation's world for a topology snapshot that has since changed? The system MUST treat each generation as tied to the specific snapshot it was created from and MUST NOT imply a stale world reflects a topology's current state.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept a topology snapshot (the same devices/links shape already used by the existing spec 121 structural rendering pipeline) as the input for both preview and generation.
- **FR-002**: System MUST produce, at no cost and without any external network call to World Labs, a preview consisting of (a) the structurally-correct reference diagram for the given topology snapshot and (b) a generated descriptive text prompt that translates each device's role and the real connectivity pattern into thematic/fantastical language.
- **FR-003**: System MUST allow the user to request different thematic styles for the same topology snapshot at preview time (e.g., different fantastical settings), without requiring a new topology snapshot.
- **FR-004**: System MUST require an explicit, separate user confirmation before performing any operation that spends World Labs credits, and MUST clearly state before that confirmation that credits will be spent and generation typically takes several minutes. This is enforced at two levels: the orchestrating workflow never issues the credit-spending call without first obtaining that confirmation in conversation, AND the credit-spending call itself requires an explicit confirmation flag it validates before proceeding (so the call cannot succeed by omission or default — found underspecified during `/speckit.analyze`; a purely conversational guarantee was judged insufficient for a safety-critical, money-spending operation).
- **FR-005**: System MUST NOT start a credit-spending generation automatically as a side effect of a preview request.
- **FR-006**: System MUST derive the generation prompt from the real topology's actual devices and links — describing each device and each real connection individually in the composed text — so that the resulting world is thematically derived from the real topology rather than from an unrelated or purely imaginative prompt. **Corrected 2026-09-03 after live evidence** (six real production generations, research.md R9/R10): the reference diagram MUST NOT be passed as image input to generation by default — doing so gets pasted flat and unchanged into the generated scene rather than used as structural guidance, and is also measurably less reliable than text-only generation. The reference diagram remains the authoritative visual artifact shown to the user (FR-009); it is not sent to World Labs as part of the default generation path. Passing it as an opt-in image input remains technically possible for a caller who has accepted that known tradeoff, but is not the recommended or default behavior.
- **FR-007**: System MUST be able to report the status of a started generation (in progress, completed, or failed) on request, given the operation/world identifier that was returned when generation was started; the system MUST NOT require any server-side state to answer this, since the caller is responsible for retaining that identifier.
- **FR-008**: System MUST, upon successful completion, surface a way for the user to access the resulting world (a viewer link and/or a reference to exported world assets).
- **FR-009**: System MUST clearly label every preview and every generation result as a decorative/artistic interpretation of the topology, not an accurate representation of physical layout, cabling, or device state, and MUST associate each result with the authoritative structural diagram it was derived from.
- **FR-010**: System MUST read the World Labs API credential from an environment variable at runtime and MUST NOT hardcode it, write it to any log, persist it to any file the system controls, or include it in any error message or response.
- **FR-011**: System MUST distinguish, in whatever it reports back for a failure, between an authentication failure, an insufficient-credits/quota failure, a rate-limit/throttling failure, and a generic/unknown failure, so the user knows what action (if any) is needed — a rate-limit failure MUST be reported with guidance to wait and retry rather than to check credentials or billing.
- **FR-012**: System MUST check the existing structural-rendering density limit (from the spec 121 pipeline) before attempting to produce a reference image, and MUST report that limit clearly if a topology snapshot exceeds it, rather than attempting a degraded or partial reference image.
- **FR-013**: System MUST NOT persist generated world assets, viewer links, or the correlation between a topology snapshot and a generated world beyond the lifetime of a single request/response — no new database, file store, or in-memory session cache is introduced by this feature. The system is a fully stateless pass-through to the external provider's own operation tracking.
- **FR-014**: System MUST be independently verifiable that basic connectivity and authentication to the World Labs API works (a minimal, low/no-cost round trip) before any broader capability of this feature is considered usable, since API access was not yet confirmed working as of this feature's creation.
- **FR-015**: System MUST record every confirmed generation attempt (success or failure) in the existing GAIT audit trail (`gait_record_turn`), capturing the topology snapshot's identity/theme, the operation id, the cost once known, and the outcome — never the API key, never raw device data beyond identity. This uses the repo's pre-existing, already-mandated audit substrate (Constitution Principle IV) and MUST NOT introduce any *new* audit-logging mechanism or persistent store of its own (revised during `/speckit.analyze` — see Clarifications correction above; the original "no audit logging at all" answer conflicted with Constitution Principle IV).
- **FR-016**: The credit-spending operation MUST require an explicit confirmation argument that must be affirmatively set to proceed — an omitted, missing, or false value MUST be rejected before any call to World Labs is made, with a distinct, reportable reason (`confirmation_required`). This is a code-level safeguard in addition to, not instead of, the conversational confirmation in FR-004 (added during `/speckit.analyze`: SC-002's "verified by inspection" guarantee had no code-level or testable mechanism behind it).

### Key Entities

- **Topology Snapshot**: The same real-world devices-and-links data already used by the existing spec 121 pipeline (hostnames, roles, states, and link pairs). Not owned by this feature — this feature only consumes it.
- **Reference Diagram**: The structurally-correct, deterministically-rendered image of a Topology Snapshot, produced by the existing spec 121 structural renderer. Serves as the authoritative artifact and as the image input to world generation.
- **Fantastical Prompt**: A generated, human-readable description that translates a Topology Snapshot's device roles and connectivity pattern into thematic/fantastical scene language, used together with the Reference Diagram to condition world generation. Exists only for the duration of a preview or generation request.
- **Generated World**: The explorable 3D result produced by the external world-generation provider from a Reference Diagram and a Fantastical Prompt, identified by a provider-issued world identifier and accessible via a viewer link and/or exported asset references. Explicitly decorative, never authoritative, and not persisted by this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can obtain a free preview (reference diagram plus fantastical prompt) for a given topology snapshot without any wait beyond the time the existing structural renderer already takes, and without spending any credits.
- **SC-002**: No credit-spending generation ever starts without a distinct, explicit confirmation step separate from the preview request — verified both by inspection of every code path that can reach the paid operation, and by the paid operation's own required confirmation argument (FR-016) making an unconfirmed call fail by construction rather than by convention alone.
- **SC-003**: A user who confirms generation receives either a working viewer link/asset reference or a clearly-explained failure reason, with no case producing a silent or ambiguous outcome.
- **SC-004**: 100% of preview and generation results presented to a user carry a visible statement that the world is a decorative interpretation and a link to or copy of the authoritative structural diagram.
- **SC-005**: No API credential value ever appears in a log, error message, response body, or committed file, verified by review of every place this feature emits output.
- **SC-006**: Before this feature is considered ready for broader use, a documented, successful minimal round trip to the World Labs API (proving the credential and basic connectivity work) exists and is reproducible.

## Assumptions

- The existing spec 121 `topology-diagram-mcp` structural renderer (and the Topology Snapshot shape it consumes) is reused as-is for producing the Reference Diagram; this feature does not modify that renderer's rendering logic or its density ceiling.
- "Fantastical" or thematic style is a user-selectable input at preview time (e.g., a short style label or free-text theme), defaulting to a reasonable generic theme (e.g., a stylized landscape) when the user does not specify one.
- Generation is a single-shot operation per confirmation: one confirmed request produces one Generated World from one Reference Diagram plus one Fantastical Prompt. Batch or multi-world generation from a single topology snapshot is out of scope for this feature.
- The World Labs API's documented behavior (image-conditioned generation via an uploaded reference image plus a text prompt, followed by polling an operation until it completes) is assumed to remain stable; this feature does not attempt to compensate for undocumented provider-side behavior changes.
- Because API authentication was not yet confirmed working at the time this specification was written, this feature's rollout explicitly includes a standalone verification step (SC-006) that must succeed before the preview/generation user stories are exercised against the live provider.
- No *new* persistent storage or historical record of generated worlds is required by this feature — the existing GAIT audit trail (FR-015) is reused as-is, not a new store. If the user later wants generated worlds queryable/tracked beyond what a GAIT record captures, that would be a separate, future enhancement.
