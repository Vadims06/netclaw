# Feature Specification: ComfyUI Network Topology Visualization

**Feature Branch**: `119-comfyui-topology-viz`
**Created**: 2026-08-26
**Status**: Draft
**Input**: User description: "ComfyUI network topology visualization: a new NetClaw skill that takes topology data from NetClaw existing topology-source integrations (reusing the same canonical topology model that spec 046 threejs-network-viz skill assembles from CML, GNS3, containerlab, EVE-NG, Nautobot, NetBox, Infrahub, IP Fabric, Forward Networks, or a freeform description) and renders it as a stylized, flashy AI still image via ComfyUI, instead of or alongside the existing procedural/real-stencil 3D renders. Output is written to the same persistent workspace/output convention as specs 046 and 082 (timestamped, never overwritten). Vendor the community shawnrushefsky/comfyui-mcp server (Node/TypeScript, MIT license) under mcp-servers/comfyui-mcp/, following the exact vendoring pattern spec 046 established for sketchfab-mcp-server. Connectivity: the ComfyUI instance runs on a separate Windows host, currently observed listening on 127.0.0.1:8000, with models/checkpoints unknown. Scope for this v1 spec is topology stills only; video (traffic flybys, packet tracing animations) and flashy test-result cards are explicitly out of scope and noted as follow-on specs."

## Clarifications

### Session 2026-08-26

- Q: Which community MCP server should this feature vendor to talk to ComfyUI? → A: `shawnrushefsky/comfyui-mcp` (Node/TypeScript, MIT license) — chosen over alternatives (e.g. `joenorton/comfyui-mcp-server`) because it exposes a broad, workflow-capable tool surface rather than a narrow single-purpose "generate one image" wrapper, matching this feature's need for model discovery plus stylized generation.
- Q: What is this v1 spec's output scope? → A: Topology stills only — one generated image per request. Video (traffic flybys, packet-tracing animations) and flashy test-result cards are explicitly deferred to likely follow-on specs, mirroring how spec 046 shipped topology-only before spec 082 added a different output type later.
- Q: Should a generation request have a NetClaw-imposed maximum wait before it is reported as a timeout? → A: No fixed bound — NetClaw tracks the job to completion or failure using ComfyUI's own status signals, since real GPU image-generation time varies with model, workflow, and hardware and a fixed NetClaw-side cutoff would falsely report a slow-but-succeeding job as failed.
- Q: What happens if a second topology-image request arrives while one is already generating? → A: Reject the second request outright with a clear "a generation is already in progress" message; this feature does not queue or submit concurrent jobs against the shared ComfyUI worker.
- Q: When the model-availability check finds more than one usable image checkpoint, should NetClaw auto-select one or ask the engineer to choose? → A: Auto-select one deterministically and tell the engineer which checkpoint was used, so a normal request never stalls on a picker; this mirrors spec 046's automatic-fallback behavior rather than interrupting the flow with a choice.
- Q: How should the feature handle the fact that the target ComfyUI instance's installed checkpoints/models are unknown at spec time, and that ComfyUI runs on a separate Windows host from NetClaw's own WSL2/Linux runtime? → A: Treat both as things the feature must discover and verify, not assume. Model availability is checked at request time via a discovery step, with an explicit, clearly-worded failure/fallback when nothing usable is found; the endpoint is required external configuration, and Phase 0 research (in planning) must verify actual cross-host HTTP reachability before the plan assumes it works.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Turn a Live Topology Into a Stylized Still Image (Priority: P1)

A network engineer asks NetClaw to render a topology from a live source (for example, "give me a flashy AI image of the CML lab topology") and receives one generated, stylized image — created by ComfyUI from the topology's actual devices, roles, and connections — saved somewhere they can find and reopen it later.

**Why this priority**: This is the entire value of the feature. Without a correctly assembled prompt/description reaching ComfyUI and a real generated image coming back, nothing else here has value.

**Independent Test**: Ask NetClaw to render a topology from a reachable live source as a ComfyUI image. Confirm one image file is produced, is saved to a persistent, timestamped location, and visibly reflects the topology's device count/roles and connectivity (not a generic unrelated picture).

**Acceptance Scenarios**:

1. **Given** a reachable live topology source and a reachable ComfyUI backend with at least one usable image-generation checkpoint, **When** the engineer asks NetClaw for a stylized image of that topology, **Then** NetClaw assembles the topology's devices, roles, and connections into a generation request, sends it to ComfyUI, and returns one completed image.
2. **Given** a completed generation, **When** the engineer looks at the result, **Then** the image is saved as a distinctly-named, timestamped file in a persistent NetClaw workspace output location, and NetClaw tells the engineer where to find it.
3. **Given** the same topology is requested twice in a row, **When** each request completes, **Then** each produces its own independently saved image; an earlier result is never silently overwritten.
4. **Given** a topology with many devices of different roles (routers, switches, firewalls, etc.), **When** the image is generated, **Then** the composed input to ComfyUI (the prompt/description driving generation) reflects that variety rather than a flattened generic description of "a network."

---

### User Story 2 - Know Immediately When ComfyUI or a Usable Model Is Not Available (Priority: P2)

A network engineer who asks for a ComfyUI image gets a clear, specific explanation — not a hang, a generic error, or a silently wrong picture — whenever the ComfyUI backend cannot be reached, or can be reached but has no checkpoint suitable for image generation installed.

**Why this priority**: The target ComfyUI instance is a separate, user-managed host whose reachability and installed models are both unknowns at the time this feature ships. Silent or confusing failure here would make the feature untrustworthy from the first real use.

**Independent Test**: Point NetClaw at a ComfyUI endpoint that is unreachable (wrong host/port, or ComfyUI not running), and separately at a reachable one with zero image checkpoints installed. Confirm both produce a specific, actionable message rather than a hang, a stack trace, or a fabricated success.

**Acceptance Scenarios**:

1. **Given** the configured ComfyUI endpoint cannot be reached over the network, **When** the engineer requests a topology image, **Then** NetClaw reports that ComfyUI could not be reached at the configured endpoint, distinct from any other failure reason.
2. **Given** the ComfyUI endpoint is reachable, **When** NetClaw checks what is installed before generating, **Then** it enumerates the available checkpoints/models rather than assuming a specific one exists.
2a. **Given** the discovery step finds more than one checkpoint suitable for image generation, **When** NetClaw proceeds with the request, **Then** it selects one deterministically without stopping to ask the engineer to choose, and reports which checkpoint was used once the image completes.
3. **Given** the endpoint is reachable but no installed checkpoint is suitable for image generation, **When** the engineer requests a topology image, **Then** NetClaw reports that no usable model was found and states what kind of model needs to be installed, rather than attempting generation anyway or failing silently.
4. **Given** a generation request is sent and ComfyUI itself reports a job failure or error, **When** the engineer is waiting on the result, **Then** NetClaw reports that the generation itself failed (as distinct from a reachability or missing-model failure) as soon as ComfyUI reports it, without NetClaw imposing its own fixed cutoff on a job ComfyUI still reports as in progress.
5. **Given** a generation job is already in progress, **When** another topology-image request is made before it completes, **Then** NetClaw rejects the new request with a clear message that a generation is already running, rather than queuing it or submitting it to ComfyUI concurrently.

---

### User Story 3 - Render From Any Supported Topology Source, or a Freeform Description (Priority: P3)

A network engineer can request a ComfyUI-stylized image sourced from any of NetClaw's existing topology-of-record or lab-emulation integrations, or from a freeform plain-language description with no live source at all, and get the same kind of result either way.

**Why this priority**: This feature is explicitly a second rendering path over the same topology model spec 046 already assembles from these sources; it only delivers its stated value if it reuses that composability rather than hardcoding a single source.

**Independent Test**: Request a ComfyUI image sourced from at least one live integration and, separately, from a freeform plain-language topology description. Confirm both produce a completed image using the same generation and delivery conventions.

**Acceptance Scenarios**:

1. **Given** a topology available through any supported live source integration, **When** the engineer requests a ComfyUI image of it, **Then** NetClaw retrieves that source's topology data and drives generation from it the same way regardless of which source supplied the data.
2. **Given** a plain-language description of devices and how they connect with no live source referenced, **When** the engineer asks for a ComfyUI image of it, **Then** NetClaw generates an image from that description using the same delivery conventions as a live-sourced request.
3. **Given** a named live source is unreachable or returns an error, **When** the engineer requests a ComfyUI image from it, **Then** NetClaw reports that sourcing failure clearly, distinct from a ComfyUI-side failure, rather than attempting to generate from empty or partial data.

---

### Edge Cases

- What happens when the topology has zero devices (e.g., an empty or misidentified source)? NetClaw reports that there is nothing to visualize rather than sending an empty request to ComfyUI.
- What happens when ComfyUI accepts the generation job but it never completes (stuck queue, crashed worker)? NetClaw keeps tracking the job using ComfyUI's own status signals rather than applying its own fixed timeout; if ComfyUI itself reports an error or failure, NetClaw reports that immediately. If ComfyUI's own queue/job status never resolves at all (for example, the ComfyUI process crashes mid-job with no error surfaced), the engineer can cancel and re-ask — this is an accepted limit of relying on ComfyUI as the source of truth for job completion rather than a NetClaw-side cutoff.
- What happens when the topology is very large (dozens of devices, hundreds of interfaces)? NetClaw still composes a request and generates an image; extreme device-level detail may be summarized rather than exhaustively enumerated in the generation input, since image generation cannot render arbitrarily dense text.
- What happens when the engineer requests both a ComfyUI image and a three.js 3D scene (spec 046) for the same topology in one ask? Each is generated independently through its own existing path; this feature does not merge or replace the other.
- What happens when the ComfyUI host is reachable but returns models/checkpoints meant for something other than image generation (e.g., only audio or video models installed)? NetClaw treats that the same as "no usable model found" for this feature's purposes and reports it as such.
- What happens when a second topology-image request arrives while one is already generating? NetClaw rejects the new request with a clear "a generation is already in progress" message rather than queuing it or submitting it to ComfyUI alongside the in-flight job.

## Requirements *(mandatory)*

### Functional Requirements

**Core generation and delivery (Story 1)**

- **FR-001**: System MUST accept a request to render a given topology as a stylized image via ComfyUI, triggerable through natural-language conversation with NetClaw.
- **FR-002**: System MUST compose a generation input for ComfyUI from the topology's actual devices, roles, and connections, so the resulting image is recognizably driven by that specific topology rather than a generic placeholder description.
- **FR-003**: System MUST deliver each completed generation as a distinctly-named, timestamped image file saved to a persistent NetClaw workspace output location, and MUST tell the engineer where the file is; System MUST NOT overwrite a previously saved result.
- **FR-004**: Each request MUST produce its own independent generation; requesting the same topology twice MUST NOT reuse or silently return a prior result.

**Explicit failure and fallback behavior (Story 2)**

- **FR-005**: System MUST treat the ComfyUI backend endpoint (host and port) as required external configuration; it MUST NOT assume a fixed default that matches the community MCP server's own built-in default, since the target instance is independently configured.
- **FR-006**: Before attempting generation, system MUST query the ComfyUI backend for its currently installed checkpoints/models rather than assuming any specific one is present.
- **FR-006a**: When more than one installed checkpoint is suitable for image generation, system MUST select one deterministically without prompting the engineer to choose, and MUST tell the engineer which checkpoint was used for the completed generation.
- **FR-007**: When the ComfyUI backend cannot be reached at the configured endpoint, system MUST report that specific failure to the engineer, distinguishable from a missing-model or generation-failure report.
- **FR-008**: When the ComfyUI backend is reachable but no installed model is suitable for image generation, system MUST report that specific condition to the engineer, including what kind of model needs to be installed, rather than attempting generation or failing silently.
- **FR-009**: System MUST track a submitted generation job to completion or failure using ComfyUI's own job status signals, and MUST NOT impose a fixed NetClaw-side timeout on a job ComfyUI still reports as in progress, since real generation time varies with model, workflow, and hardware; when ComfyUI itself reports the job failed or errored, system MUST report that outcome to the engineer as distinct from a reachability or missing-model failure.
- **FR-009a**: System MUST allow at most one generation job in flight at a time; when a new topology-image request arrives while a prior one is still in progress, system MUST reject the new request with a clear message that a generation is already running, rather than queuing it or submitting it to ComfyUI concurrently.

**Composable topology sourcing (Story 3)**

- **FR-010**: System MUST accept topology data sourced from any of NetClaw's existing topology-of-record and lab-emulation integrations already supported by spec 046 (at minimum Cisco Modeling Labs, GNS3, containerlab, EVE-NG, Nautobot, NetBox/Infrahub, IP Fabric, and Forward Networks), reusing that same assembled topology model rather than re-implementing topology retrieval.
- **FR-011**: System MUST also accept a plain-language, freeform description of devices and their connections as an alternative to a live source, using the same generation and delivery conventions as a live-sourced request.
- **FR-012**: If a named live topology source is unreachable or returns an error, system MUST report that sourcing failure clearly and distinctly from any ComfyUI-side failure, rather than attempting to generate from empty or partial topology data.
- **FR-013**: When a topology has zero devices to render, system MUST report that there is nothing to visualize rather than submitting an empty or meaningless generation request.

**Cross-cutting**

- **FR-014**: System MUST NOT modify any device configuration, topology-source integration, or existing visualization skill (including spec 046's three.js skill) as part of this feature; it is a read-only, additive visualization path.
- **FR-015**: System MUST NOT embed credentials, secrets, or full running-configuration content in any generation input sent to ComfyUI, consistent with the same restriction spec 046 applies to its own rendered labels.
- **FR-016**: Video output (traffic flybys, packet-tracing animations, or any moving-image generation) and stylized test-result "cards" are explicitly out of scope for this feature; System MUST NOT be built to attempt either in this iteration.

### Key Entities

- **Topology Snapshot**: The same complete set of devices, roles, and connections defined and assembled by spec 046, reused here as the input driving image generation rather than a 3D scene.
- **Generation Request**: The composed description/prompt (and any generation parameters) sent to ComfyUI for a single visualization ask, derived from one Topology Snapshot.
- **Generated Image**: The completed still image returned by ComfyUI for one Generation Request; saved as a distinct, timestamped artifact in the persistent workspace output location.
- **Model Availability Check**: The result of querying the ComfyUI backend for installed checkpoints/models before generation is attempted, used to decide whether to proceed or report a missing-model condition.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A network engineer can go from asking for a ComfyUI topology image to having a completed, saved image in hand, for a typical lab-sized topology, without performing any manual setup step beyond having already configured the ComfyUI endpoint once.
- **SC-002**: 100% of completed generations are saved as distinctly-named files in the persistent workspace output location, with zero instances of one result silently overwriting another.
- **SC-003**: 100% of unreachable-backend, missing-model, and generation-failure conditions produce a specific, distinguishable message to the engineer — zero instances of an indefinite hang or a silently wrong/placeholder result standing in for a real failure.
- **SC-004**: Across topologies sourced from at least two different supported live integrations plus a freeform description, all three successfully produce a completed image using the same request/delivery conventions.
- **SC-005**: When the model-availability check finds no usable image-generation checkpoint, 100% of those requests stop and report the condition before ever submitting a generation job, rather than submitting one that predictably cannot succeed.

## Assumptions

- The vendored community MCP server for this feature is `shawnrushefsky/comfyui-mcp` (Node/TypeScript, MIT license), consumed as-is per the same vendoring pattern spec 046 established for `sketchfab-mcp-server` — not modified, not forked.
- The target ComfyUI instance runs on a separate host from NetClaw's own runtime (observed: a native Windows install, reachable at `127.0.0.1:8000` from the Windows side) and is entirely user-managed — this feature neither installs nor configures ComfyUI itself, only connects to an already-running instance via configuration.
- Actual network reachability from NetClaw's runtime environment to the configured ComfyUI endpoint is unverified at spec time and must be confirmed during planning's research phase before implementation proceeds; if unreachable as configured, the manual remediation (e.g., starting ComfyUI with a listen/bind flag reachable beyond host-local loopback) is a documented operator step, not something this feature automates.
- Installed checkpoints/models on the target ComfyUI instance are unknown at spec time; this feature assumes nothing is pre-installed and treats "which models exist" as something to discover per request, per Clarification session 2026-08-26.
- Each generated image is a one-off still snapshot of the topology at request time; there is no live-updating or streaming generation in this feature.
- This feature is strictly additive: NetClaw's existing three.js (046), Blender (024), and UE5 (044/045) visualization skills are untouched and remain available as separate rendering paths.
- Video generation (traffic flybys, packet-tracing animations) and stylized test-result cards are known, desired future directions but are explicitly out of scope for this v1 spec and are expected to become their own follow-on spec(s), mirroring how spec 082 followed spec 046 for a different output type.
