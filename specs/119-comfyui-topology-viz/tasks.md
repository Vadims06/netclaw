# Tasks: ComfyUI Network Topology Visualization

**Input**: Design documents from `/specs/119-comfyui-topology-viz/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan.md's Testing Strategy explicitly calls for unit tests on prompt
composition/model-selection/failure-classification logic (mocked `comfyui-mcp`) and live
integration tests that assert on the actual, currently-verified state of the configured ComfyUI
instance (reachable, zero checkpoints — research.md §3), following the same "never mock the
dependency whose failure would matter most" convention established in specs 044/045/046.

**Organization**: Tasks are grouped by user story (spec.md's P1–P3) so each story is independently
implementable, testable, and demonstrable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependency)
- **[Story]**: US1–US3, mapping to spec.md's three prioritized user stories
- All file paths are exact and relative to the repo root

---

## Phase 1: Setup

**Purpose**: Vendor the community MCP server and wire it into the installer/config/docs surfaces
that don't depend on any of this feature's own code existing yet

- [X] T001 Create the skill package skeleton at `workspace/skills/comfyui-topology-viz/__init__.py` (empty package marker; the top-level entry point is added in Phase 4, T019)
- [X] T002 [P] Create the persistent output directory `workspace/output/comfyui-topology-viz/` (with a `.gitkeep`) that `output.py` will write timestamped images and sidecar JSON into (FR-003)
- [X] T003 [P] Add `component_install_comfyui_viz()` to `scripts/lib/install-steps.sh`: clone `https://github.com/shawnrushefsky/comfyui-mcp.git` into `mcp-servers/comfyui-mcp/` via the existing `clone_or_pull` helper, then `npm install && npm run build` (research.md §1 — matches the real, verified `sketchfab-mcp-server` precedent: cloned at install time, git-ignored, never committed)
- [X] T004 [P] Add a new catalog entry to `scripts/lib/catalog.sh`: `"comfyui-viz|Analysis & Diagrams|ComfyUI Topology Visualization|AI-generated stylized topology stills via a self-hosted ComfyUI instance"`
- [X] T005 [P] Register `comfyui-mcp` in `config/openclaw.json`: `"command": "node"`, `"args": ["mcp-servers/comfyui-mcp/dist/index.js"]`, `"env": {"COMFYUI_URL": "${COMFYUI_URL}"}` (repo-relative path, no hardcoded absolute path, per docs/ADDING-AN-MCP.md)
- [X] T006 [P] Add `COMFYUI_URL` to `.env.example` with a description (name only, no value) — the endpoint of the user's own ComfyUI instance, e.g. `http://127.0.0.1:8000` (FR-005 — required external config, no assumed default)
- [X] T007 [P] Add a `"comfyui-mcp": "comfyui-viz"` alias declaration to `scripts/verify-catalog-coverage.py`'s alias map (the server key does not reduce to the catalog id by stripping `-mcp`, same reason `sketchfab-mcp` needed an explicit alias)

**Checkpoint**: `comfyui-mcp` is installable, configured, and discoverable by the coverage checker. No feature code exists yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Canonical data types and the ComfyUI MCP client wrapper every user story depends on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T008 [P] Port the trimmed canonical types from `workspace/skills/threejs-network-viz/topology_model.py` into `workspace/skills/comfyui-topology-viz/topology_model.py`: `Device`, `Interface`, `Link`, `TopologySnapshot`, `SourceKind`, `OperationalState`, `sanitize_metadata`, `SourceUnreachableError`, `AmbiguousSourceError` — omitting the 3D-only `AssetKind`/`ProceduralShape`/`ModelSource`/`DeviceAsset` (data-model.md, research.md §5)
- [X] T009 Port the source adapters from `workspace/skills/threejs-network-viz/sources.py` into `workspace/skills/comfyui-topology-viz/sources.py` (all 8 live-source adapters, the freeform adapter, and `resolve_source`/disambiguation), re-pointed at this skill's own `topology_model.py` (T008) — depends on T008
- [X] T010 [P] Implement `GenerationRequest`, `ModelAvailabilityCheck`, `GeneratedImage`, and the `GenerationFailure` typed-error taxonomy (six `kind` values) dataclasses/enums in `workspace/skills/comfyui-topology-viz/generation_model.py`, matching data-model.md's fields exactly
- [X] T011 Implement `workspace/skills/comfyui-topology-viz/comfyui_client.py`: an MCP stdio client (using the `mcp` SDK's `ClientSession`/`stdio_client`/`StdioServerParameters`, the same pattern `threejs-network-viz/assets.py` already uses for `sketchfab-mcp-server`) that spawns `node mcp-servers/comfyui-mcp/dist/index.js` with `COMFYUI_URL` read from the environment (erroring clearly if unset — never silently falling back to `comfyui-mcp`'s own built-in `8000`/`8188` default, per FR-005), exposing `get_status()` (which MUST verify the response's `comfyuiUrl`/`discoverySource` actually match the configured `COMFYUI_URL` rather than trusting `comfyuiConnected` alone — `comfyui-mcp` was found live to silently port-scan and substitute a different local ComfyUI instance when the configured one is unreachable, research.md §8), `list_models(type="checkpoints")`, `search_templates(model_type, task_type)`, `get_template(template_id, parameters)`, `run_workflow(workflow, sync=False, ...)`, and `poll_task_result(task_id)` — the last with **no maximum attempt count or wall-clock cutoff**, looping until `comfyui-mcp` itself reports a terminal status (contracts/comfyui-generation-contract.md steps 1–6; research.md §4) — depends on T010
- [X] T012 Implement `check_model_availability() -> ModelAvailabilityCheck` in `comfyui_client.py`, calling `list_models()` and applying deterministic selection over checkpoint-type entries (FR-006, FR-006a) — depends on T011

**Checkpoint**: Canonical topology types, all source adapters, and the full `comfyui-mcp` client wrapper exist and are independently unit-testable. User story implementation can now begin.

---

## Phase 3: User Story 1 - Turn a Live Topology Into a Stylized Still Image (Priority: P1) 🎯 MVP

**Goal**: Given a reachable topology source and a ComfyUI backend with at least one usable
checkpoint, produce one generated image reflecting that topology's devices/roles/connections, saved
to a persistent, timestamped location.

**Independent Test**: With `comfyui-mcp` mocked to report a usable checkpoint and a successful
generation, request a stylized image of a topology and confirm one image + sidecar JSON is written
under `workspace/output/comfyui-topology-viz/` with a distinct filename, and NetClaw reports the
file path and which checkpoint was used.

**Note**: Per research.md §3, the actually-configured ComfyUI instance currently has zero installed
checkpoints — so this story's happy path cannot be live-verified end-to-end today. It is fully
covered by mocked unit/contract tests here; the live check against the real instance (which today
correctly reports "no usable model") belongs to User Story 2 (T023).

### Tests for User Story 1

- [X] T013 [P] [US1] Unit test `prompt_builder.py`'s composition/summarization across small and large synthetic `TopologySnapshot` fixtures (bounded length, role/count summarization, no per-interface exhaustive enumeration) in `tests/unit/test_comfyui_prompt_builder.py`
- [X] T014 [P] [US1] Unit test deterministic model selection (FR-006a) over zero/one/multiple mocked checkpoint lists in `tests/unit/test_comfyui_model_selection.py`
- [X] T015 [P] [US1] Contract test: with every `comfyui-mcp` tool call mocked, assert `generation.py`'s happy-path call order matches contracts/comfyui-generation-contract.md steps 1–7 exactly (`get_status` → `list_models` → `search_templates` → `get_template` → `run_workflow(sync=False)` → `poll_task_result` → image write) in `tests/unit/test_comfyui_generation_contract.py`

### Implementation for User Story 1

- [X] T016 [US1] Implement `build_prompt(snapshot: TopologySnapshot) -> str` in `workspace/skills/comfyui-topology-viz/prompt_builder.py` — a bounded-length natural-language description of device roles/counts/connectivity (research.md §6); relies on `topology_model.py`'s `sanitize_metadata` (T008) so credentials/secrets/config content can never reach the prompt (FR-015) — depends on T008
- [X] T017 [US1] Implement `write_image(image_bytes, request: GenerationRequest) -> GeneratedImage` and its sidecar-JSON writer in `workspace/skills/comfyui-topology-viz/output.py`: a timestamped, uniquely-named file under `workspace/output/comfyui-topology-viz/`, never overwriting an existing file (FR-003, FR-004) — depends on T002, T010
- [X] T018 [US1] Implement the happy-path orchestrator `run_generation(snapshot: TopologySnapshot) -> GeneratedImage` in `workspace/skills/comfyui-topology-viz/generation.py`: calls `comfyui_client.check_model_availability()`, `prompt_builder.build_prompt()`, submits via `search_templates`/`get_template`/`run_workflow`, polls to a ComfyUI-reported terminal state, and calls `output.write_image()` on success, reporting the checkpoint used (FR-001, FR-002, FR-006a) — depends on T011, T012, T016, T017
- [X] T019 [US1] Implement the top-level entry point `visualize_topology_via_comfyui(topology_input: dict) -> GeneratedImage` in `workspace/skills/comfyui-topology-viz/__init__.py`, accepting the same normalized `{"devices": [...], "links": [...]}` shape the conversational orchestration layer already produces for spec 046, calling `sources.py` (T009) to build a `TopologySnapshot` and then `generation.run_generation()` (T018) — depends on T009, T018, T001
- [X] T020 [US1] Draft the initial `workspace/skills/comfyui-topology-viz/SKILL.md` covering Story 1's invocation and happy-path workflow (finalized with all stories and known limitations in Phase 6, T033) — depends on T019

**Checkpoint**: User Story 1 is fully functional against a mocked `comfyui-mcp` backend and independently testable.

---

## Phase 4: User Story 2 - Know Immediately When ComfyUI or a Usable Model Is Not Available (Priority: P2)

**Goal**: An unreachable ComfyUI backend, a reachable backend with no usable checkpoint, and a
failed/never-resolving generation job each produce a specific, distinguishable message — never a
hang, a generic error, or a silently wrong result. A second request while one is in flight is
rejected outright.

**Independent Test**: Point the skill at an unreachable endpoint and confirm a `backend_unreachable`
message; separately, run it against the actually-configured (reachable, zero-checkpoint) ComfyUI
instance and confirm a `no_usable_model` message naming what to install; separately, submit a second
request while one is in flight and confirm `generation_already_in_progress`.

### Tests for User Story 2

- [X] T021 [P] [US2] Unit test each of the four distinct failure classifications (`backend_unreachable`, `no_usable_model`, `generation_job_failed`, `generation_already_in_progress`) produces a distinct, correctly-worded message under mocked `comfyui-mcp` conditions, in `tests/unit/test_comfyui_failure_classification.py`
- [X] T022 [P] [US2] Unit test the single-in-flight-job guard: a second call to `run_generation()` while the first is still `submitted` is rejected without ever calling `comfyui_client` again, in `tests/unit/test_comfyui_concurrency_guard.py`
- [X] T023 [US2] Live integration test against the actually-configured `COMFYUI_URL`: assert `check_model_availability()` reports `status == "no_usable_model"` with an empty `available_checkpoints` list — today's real, verified environment state (research.md §3) — in `tests/integration/test_comfyui_topology_viz.py` — depends on T012

### Implementation for User Story 2

- [X] T024 [US2] Implement `backend_unreachable` (FR-007) and `no_usable_model` (FR-008) classification in `generation.py`, wired to `comfyui_client.get_status()` and `check_model_availability()`, with the FR-008-required "what to install" message (a Stable Diffusion 1.5, SDXL, or Flux checkpoint into ComfyUI's `models/checkpoints`); `backend_unreachable` MUST also fire when `get_status()`'s config-fidelity check fails (research.md §8), not only on an outright connection error — depends on T011, T012, T018
- [X] T025 [US2] Implement `generation_job_failed` classification in `generation.py`, sourced from `comfyui_client.poll_task_result()`'s terminal ComfyUI-reported failure state, kept distinct from the two conditions above (FR-009) — depends on T018
- [X] T026 [US2] Implement the in-memory single-in-flight-job guard in `generation.py` — a module-level flag set when a job reaches `submitted` and cleared on any terminal state — and the `generation_already_in_progress` classification (FR-009a, research.md §7) — depends on T018
- [X] T027 [US2] Extend `SKILL.md` with the four failure/fallback behaviors and their exact operator-facing messages — depends on T024, T025, T026

**Checkpoint**: User Stories 1 and 2 both work independently — the feature behaves correctly whether or not the ComfyUI backend currently has a usable model, exactly matching this environment's real state.

---

## Phase 5: User Story 3 - Render From Any Supported Topology Source, or a Freeform Description (Priority: P3)

**Goal**: The same generation pipeline works identically regardless of which live topology source
(or no live source at all — a freeform description) supplied the input, with sourcing failures
reported distinctly from any ComfyUI-side failure.

**Independent Test**: Request a ComfyUI image from a freeform plain-language topology description
(no live source) and confirm it completes using the same pipeline as a live-sourced request;
separately, request one from an unreachable named source and confirm a `source_unreachable` message
distinct from any ComfyUI failure; separately, request one for a zero-device topology and confirm
`empty_topology` fires before any `comfyui-mcp` call is made.

### Tests for User Story 3

- [X] T028 [P] [US3] Unit test that a `SourceUnreachableError` from `sources.py` produces the distinct `source_unreachable` message (never a ComfyUI-side message) in `tests/unit/test_comfyui_source_failures.py`
- [X] T029 [P] [US3] Unit test that a zero-device `TopologySnapshot` produces `empty_topology` and that `comfyui_client` is never invoked (assert the mock has zero calls) in `tests/unit/test_comfyui_empty_topology.py`

### Implementation for User Story 3

- [X] T030 [US3] Wire `source_unreachable` (FR-012) and `empty_topology` (FR-013) classification into `generation.py`/`__init__.py`'s entry point, reusing `sources.py`'s `SourceUnreachableError` (T009) and a `TopologySnapshot.devices` emptiness check performed before `comfyui_client` is ever called — depends on T009, T019
- [X] T031 [P] [US3] Freeform end-to-end test: a real freeform-description request parsed through `sources.py`'s freeform adapter, with `comfyui-mcp` mocked, in `tests/integration/test_comfyui_topology_viz.py` — depends on T030
- [X] T032 [US3] Live-source integration test: retrieve a real topology from at least one already-configured live source integration (topology retrieval only; `comfyui-mcp` mocked for the generation half) and confirm it produces the same request shape as the freeform path (FR-010, FR-011) in `tests/integration/test_comfyui_topology_viz.py` — depends on T030
- [X] T033 [US3] Finalize `SKILL.md`: all three user stories, the full composed-sources list, freeform examples, the `COMFYUI_URL` environment variable, and a Known Limitations section (stills-only scope, single-in-flight, no fixed timeout, today's zero-checkpoint state) mirroring `threejs-network-viz/SKILL.md`'s structure — depends on T027, T030

**Checkpoint**: All three user stories are independently functional — full spec.md coverage.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Constitution Principle XI (Full-Stack Artifact Coherence) and XVII (Milestone
Documentation) requirements flagged as REQUIRED in plan.md's Constitution Check

- [X] T034 [P] Update `README.md` (description, architecture note, and capability/tool counts for the new skill and `comfyui-mcp`)
- [X] T035 [P] Update `SOUL.md` (skill definition and capability summary for `comfyui-topology-viz`)
- [X] T036 [P] Update `TOOLS.md` (infrastructure reference entry for `comfyui-mcp`)
- [X] T037 [P] Add a status node for `comfyui-mcp` to `ui/netclaw-visual/` (Constitution X — Observability)
- [X] T038 [P] Add an index row for `comfyui-mcp` to `mcp-servers/README.md` (`| comfyui-mcp | AI image generation backend for topology stills | Community |`), matching the existing `sketchfab-mcp-server` row's pattern for a git-ignored, install-time-cloned server
- [X] T039 Run `python3 scripts/reconcile-mcp.py` and `python3 scripts/verify-catalog-coverage.py`; fix any reported gaps before considering Setup (Phase 1) complete, per `docs/ADDING-AN-MCP.md` and `CLAUDE.md`
- [X] T040 [P] Note `comfyui-mcp`'s own `npm audit` findings (once built via T003) as a tracked, non-blocking Polish-phase follow-up in `SKILL.md`'s Known Limitations, mirroring the same tracked-not-blocking treatment `sketchfab-mcp-server` received in spec 046
- [X] T041 Re-run quickstart.md's two verification `curl` commands against the real, currently-configured `COMFYUI_URL` and confirm the documented outcomes (reachable; zero checkpoints) still hold, or update quickstart.md/research.md if the environment has changed since planning
- [X] T042 Run the full test suite (`pytest tests/unit/ tests/integration/`) and confirm all pass with the expected real-environment outcomes (T023's live "no usable model" assertion, not a fabricated success); confirm zero modifications were made to `mcp-servers/sketchfab-mcp-server/`, `workspace/skills/threejs-network-viz/`, `workspace/skills/ue5-network-viz/`, or `workspace/skills/blender-3d-viz/` (FR-014)
- [X] T043 Draft the WordPress milestone blog post per Constitution Principle XVII and present it to John for review before publishing

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - US1 has no dependency on US2/US3
  - US2 extends the same `generation.py`/`comfyui_client.py` modules US1 creates — depends on US1's T018 existing, but is independently testable once it does
  - US3 extends the same entry point US1 creates (T019) and reuses `sources.py` from Foundational — independently testable once US1's T019 exists
- **Polish (Phase 6)**: Depends on all three user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) — no dependency on other stories
- **User Story 2 (P2)**: Builds on US1's `generation.py`/`__init__.py` (T018/T019) rather than duplicating them, but is independently testable per its own Independent Test criteria once wired
- **User Story 3 (P3)**: Builds on US1's entry point (T019) and Foundational's `sources.py` (T009), independently testable per its own Independent Test criteria once wired

### Within Each User Story

- Tests are written before their corresponding implementation task and MUST fail first
- Data/prompt composition before orchestration
- Orchestration before the top-level entry point
- Story complete before moving to the next priority

### Parallel Opportunities

- All Setup tasks marked [P] (T002–T007) can run in parallel once T001 exists
- T008 and T010 (Foundational, different files) can run in parallel; T009, T011, T012 are sequential on their listed dependencies
- All [P]-marked tests within a story phase can run in parallel
- T034–T038, T040 (Polish) can all run in parallel; T039, T041, T042, T043 are sequential (each depends on prior Polish work or all stories being done)

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Unit test prompt_builder.py composition/summarization in tests/unit/test_comfyui_prompt_builder.py"
Task: "Unit test deterministic model selection in tests/unit/test_comfyui_model_selection.py"
Task: "Contract test for the happy-path call sequence in tests/unit/test_comfyui_generation_contract.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Confirm US1's mocked unit/contract tests pass; a genuine live happy-path
   demo requires the user to first install a ComfyUI checkpoint (see quickstart.md)
5. Demo the mocked happy path and the SKILL.md workflow

### Incremental Delivery

1. Complete Setup + Foundational → foundation ready
2. Add User Story 1 → validate against mocks (MVP, pending a real checkpoint for a live demo)
3. Add User Story 2 → validate against the real, currently-reachable-but-modelless ComfyUI instance (this is the story that can be live-demoed today)
4. Add User Story 3 → validate freeform + at least one live topology source
5. Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- This feature's honest, verified starting condition (research.md §3) is that US2's "no usable
  model" path is what a real end-to-end run produces today — treat that as the meaningful live
  demo for this feature until a checkpoint is installed, not as a blocked or degraded outcome
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same-file conflicts, cross-story dependencies that break independence

## Post-completion live-verification fix (2026-08-27)

After all 43 tasks above were marked complete, a checkpoint (`sd_xl_base_1.0.safetensors`) was
installed and the happy path was run live for the first time — surfacing two real bugs mocks
could never have caught (research.md §9): `comfyui-mcp`'s own task tracker gets permanently stuck
reporting "working" for jobs ComfyUI itself already completed, and a stdio teardown race in our
own client code turned successful `run_workflow` calls into spurious exceptions. Both were fixed
(`comfyui_client.py`, `generation.py`, `output.py` now poll/download via ComfyUI's own
`/history`/`/view` endpoints directly rather than trusting `comfyui-mcp`'s task/file reporting),
all affected tests updated (23/23 passing), and a real end-to-end run confirmed: one genuine
512×512 PNG generated from a freeform topology in ~21.5s, correctly attributing
`sd_xl_base_1.0.safetensors`. See research.md §9 and `SKILL.md`'s Known Limitations for details.
