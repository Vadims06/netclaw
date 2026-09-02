# Tasks: Federated AI-Augmented Network Topology Visualization

**Feature**: 121-federated-topology-viz
**Input**: Design documents from `/specs/121-federated-topology-viz/` (plan.md, research.md, data-model.md, contracts/, quickstart.md, spec.md)

**Tests**: Included — matches spec 120's own established convention (`tests/unit/`, `tests/integration/`, one genuinely-live integration test).

## Phase 1: Setup

- [X] T001 Create `mcp-servers/topology-diagram-mcp/` package: `server.py` (FastMCP scaffold with a stub `render_structural` tool), `requirements.txt` (`mcp>=1.0.0,<2`, `networkx`, `Pillow`) — research.md R3a: N2G/draw.io-CLI rejected, this reuses spec 120's proven networkx+Pillow stack
- [X] T002 [P] Create `mcp-servers/image-style-mcp/` package: `server.py` (FastMCP scaffold with a stub `style_image` tool), `requirements.txt` (`fastmcp`, `httpx`)
- [X] T003 Install dependencies for both new servers (`python3 -m pip install --user --break-system-packages -r mcp-servers/topology-diagram-mcp/requirements.txt`, same for `image-style-mcp` — this host's system `python3`/pip needs `--break-system-packages` per PEP 668, matching how `mcp`/`httpx` are already installed for `n2n-mcp`; confirmed no venv wrapper is used for existing Python MCP servers in the live config)
- [X] T004 [P] Register `topology-diagram-mcp` and `image-style-mcp` in `config/openclaw.json` (repo parity, Constitution XI) per quickstart.md step 2
- [X] T005 [P] Register `topology-diagram-mcp` and `image-style-mcp` in `~/.openclaw/openclaw.json` (live gateway config) via `openclaw mcp set` per quickstart.md step 2

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: Federation authorization, timeouts, and shared request/result shapes every user story's tests depend on.

- [X] T006 Grant `johns-risk/viz`'s `member.scope` in `federation.db` the two new tool entries — `{"name":"topology-diagram-mcp/render_structural","type":"tool","tier":"specialty"}` and `{"name":"image-style-mcp/style_image","type":"tool","tier":"specialty"}` — per quickstart.md step 3
- [X] T007 Verify `johns-risk/viz` is live via `n2n_member_health` (research.md R1); if not, `systemctl --user start netclaw-member-johns-risk-viz.service` and re-verify
- [X] T008 Set `N2N_TOOL_TIMEOUT_S=600` in `migration-staging/members/viz/.env` and in Border's own service environment (research.md R7); restart `netclaw-member-johns-risk-viz.service` and the Border daemon for both to take effect
- [X] T009 [P] Implement `StructuralRenderRequest`/`StructuralRenderResult` JSON shape handling (data-model.md) in `mcp-servers/topology-diagram-mcp/server.py`
- [X] T010 [P] Implement `StyleRequest`/`StyleResult` JSON shape handling (data-model.md) in `mcp-servers/image-style-mcp/server.py`

**Checkpoint**: Both new servers are registered and spawnable via stdio; `johns-risk/viz` is authorized to run both new tools. User story implementation can begin.

## Phase 3: User Story 1 - A Provably Accurate, Styled Topology Image (Priority: P1) 🎯 MVP

**Goal**: A request against a live topology integration returns a styled image whose devices, icons, connections, and labels are correct by construction, produced via the real federated (Stage A + Stage B) path.

**Independent Test**: Request a stylized image of a topology with real device data behind it; confirm the delivered image's devices/icons/connections/labels exactly match the source, and confirm via response metadata that both stages ran (not the fallback).

### Tests for User Story 1

- [X] T011 [P] [US1] Unit test: `render_structural` returns correct `device_count`, `positions`, role→stencil selection, **and that every link in the request appears as a rendered connection between its two endpoints** (FR-002) for a known snapshot, in `tests/unit/test_topology_diagram_mcp.py`
- [X] T012 [P] [US1] Unit test: `style_image` request/response shape, error propagation on ComfyUI failure, in `tests/unit/test_image_style_mcp.py`
- [X] T013 [P] [US1] Unit test: `federated_generation`'s success path (mocked `n2n_invoke` responses for both stages) returns `generation_path="federated"` with both member fields set, in `tests/unit/test_federated_generation_routing.py`

### Implementation for User Story 1

- [X] T014 [US1] Implement procedural per-role icon shapes with Pillow (circle=router, tick-marked rounded rect=switch, diamond=load_balancer, brick-hatched rect=firewall, monitor glyph=client, plain labeled rounded rect=unclassified — research.md R3a) and a networkx-Kamada-Kawai-layout-based diagram builder (Topology Snapshot devices/links → canvas positions + icon placement + link lines + hostname text), reusing spec 120's `topology_renderer.py`/`compute_positions()` approach, in `mcp-servers/topology-diagram-mcp/server.py`
- [X] T015 [US1] Implement PNG encoding (Pillow `Image.save()` to an in-memory buffer, base64-encode the result — no external CLI) and wire it into the `render_structural` tool in `mcp-servers/topology-diagram-mcp/server.py`
- [X] T016 [US1] Implement `device_count` validation and the transport-size ceiling check (post-render, data-model.md rule 1; contracts/topology-diagram-mcp.md failure shape) in `mcp-servers/topology-diagram-mcp/server.py`
- [X] T016a [US1] Implement the working-resolution density ceiling check (pre-render, data-model.md rule 2 — `device_count` vs. the fixed 1024×1024 canvas, distinct from T016's transport-size check per Edge Cases: "a topology so large it exceeds what the styling stage can process at its working resolution") in `mcp-servers/topology-diagram-mcp/server.py`
- [X] T017 [US1] Write `mcp-servers/topology-diagram-mcp/README.md` (tools, env vars, transport, install) per Constitution XII
- [ ] T018 [US1] Run the FR-015 research spike: feed 2-3 real spec 120 output images (`workspace/output/comfyui-topology-viz/`) as source input to a Qwen-Image-Edit-2509 GGUF image-edit workflow on the live ComfyUI instance; verify the real download size and license directly at the HuggingFace source before pulling anything (FR-016); score against the fixed bar (100% exact label reproduction, fully traceable lines); document the go/no-go finding in `specs/121-federated-topology-viz/spike-findings.md`
- [ ] T019 [US1] If T018 is a "no-go": repeat the identical protocol against FLUX.2 [klein] 4B (verifying its own real size/license first) and record that finding in the same `specs/121-federated-topology-viz/spike-findings.md`; if T018 is a "go", record the model selection there instead
- [X] T020 [US1] Implement a direct ComfyUI REST client (`/prompt`, `/history/{id}`, `/view`, `/upload/image`), ported from `workspace/skills/comfyui-topology-viz/comfyui_client.py`'s proven direct-REST approach, in `mcp-servers/image-style-mcp/server.py`
- [X] T021 [US1] Implement the image-edit workflow graph using the T018/T019-selected model (image-to-image, structure-preserving, `style_prompt`/`negative_prompt` passthrough per contracts/image-style-mcp.md) and wire it into the `style_image` tool in `mcp-servers/image-style-mcp/server.py`
- [X] T022 [US1] Write `mcp-servers/image-style-mcp/README.md` per Constitution XII
- [X] T023 [US1] Create `workspace/skills/comfyui-topology-viz/federated_generation.py` implementing the federated success path: reachability check, `render_structural` call via `n2n_invoke`, `style_image` call via `n2n_invoke` (both using the existing `n2n-mcp` stdio client pattern from `comfyui_client.py`), assembling the `GenerationPath("federated")` result (data-model.md)
- [X] T024 [US1] Edit `workspace/skills/comfyui-topology-viz/__init__.py`'s `visualize_topology_via_comfyui()` to call `federated_generation` instead of calling `generation.run_generation()` directly (research.md R8 — the one sanctioned call-site edit to existing spec 120 code; `generation.py` itself stays untouched)
- [X] T025 [US1] Live integration test: a real request routed through the live `johns-risk/viz` member end to end; assert device count, connections, and labels exactly match the source snapshot (SC-001), **plus a manual/visual check that each device's icon still depicts its original role after styling** (Acceptance Scenario 3 — not automatable via pixel diffing, same manual-but-rigorous verification spec 120 used to catch its own garbled-text regression), in `tests/integration/test_federated_topology_viz.py`
- [X] T026 [US1] Update `workspace/skills/comfyui-topology-viz/SKILL.md` to document the federated path and the `generation_path` response field (FR-004/FR-004a) — still one skill, no new entry point

**Checkpoint**: User Story 1 is independently functional and testable — a live-topology request produces a correct, styled image via the real federated path.

## Phase 4: User Story 2 - Uninterrupted Service When the Federated Path Isn't Available (Priority: P2)

**Goal**: When either federation member is unreachable, or the request is freeform, a real styled image is still produced via the existing fallback pipeline, with the engineer clearly told which path was used.

**Independent Test**: With one or both federation members deliberately unreachable, request a stylized image and confirm a real image is still produced with the fallback clearly indicated.

### Tests for User Story 2

- [X] T027 [P] [US2] Unit test: a freeform snapshot routes directly to fallback without attempting the federated path (FR-011), in `tests/unit/test_federated_generation_routing.py`
- [X] T028 [P] [US2] Unit test: structural member unreachable routes to fallback with `reason="johns-risk/viz unreachable"` (FR-009), in `tests/unit/test_federated_generation_routing.py`
- [X] T029 [P] [US2] Unit test: styling member unreachable after Stage A succeeds returns `generation_path="federated_partial"` with the unstyled diagram and a reason distinct from a structural-member failure (FR-010), in `tests/unit/test_federated_generation_routing.py`

### Implementation for User Story 2

- [X] T030 [US2] Implement the freeform-check and member-health-check routing logic (source_kind check, `n2n_member_health` calls before attempting Stage A) in `workspace/skills/comfyui-topology-viz/federated_generation.py`
- [X] T031 [US2] Implement the Stage-A-failure → fallback path, calling spec 120's unmodified `generation.run_generation()`, in `workspace/skills/comfyui-topology-viz/federated_generation.py`
- [X] T032 [US2] Implement the Stage-B-failure → `federated_partial` path (return Stage A's correct unstyled diagram plus reason, per FR-010/Edge Cases) in `workspace/skills/comfyui-topology-viz/federated_generation.py`
- [X] T033 [US2] Implement plain, clear reporting when either of Stage A's two ceiling checks fails (T016's transport-size check or T016a's working-resolution density check) — the reason surfaced to the engineer MUST distinguish which one was hit, not report both as one generic "too large" error, in `workspace/skills/comfyui-topology-viz/federated_generation.py`
- [X] T034 [US2] Implement mid-request-drop handling — a channel drop during Stage B after Stage A already succeeded is reported as a clear, immediate failure rather than an indefinite wait (Edge Cases), in `workspace/skills/comfyui-topology-viz/federated_generation.py`
- [X] T035 [US2] Extend spec 120's existing single-in-flight guard (`generation._job_in_flight`) to cover the `federated_generation.py` entry point too, so a federated request and a fallback request cannot race the same GPU (FR-013), in `workspace/skills/comfyui-topology-viz/federated_generation.py`
- [X] T036 [US2] Integration test: stop `netclaw-member-johns-risk-viz.service`, confirm a real image is still produced with `generation_path="fallback"` (quickstart.md step 6), in `tests/integration/test_federated_topology_viz.py`
- [X] T037 [US2] Integration test: a freeform request routes to fallback without attempting the federated path first (quickstart.md step 7), in `tests/integration/test_federated_topology_viz.py`

**Checkpoint**: User Stories 1 and 2 both work independently — federated path when available, fallback when not, correctly distinguished every time.

## Phase 5: User Story 3 - The Structural-Diagram Member Comes Online (Priority: P3)

**Goal**: `johns-risk/viz` is confirmed live and reachable from Border, independently of any specific image-generation request.

**Independent Test**: Bring the member online and confirm, via the existing federation member status/health mechanism, that it reports live and reachable.

- [X] T038 [US3] Verify via `n2n_member_list` — deliberately the member-*listing* API, not T007's `n2n_member_health` health-check API, to satisfy Acceptance Scenario 1's literal wording ("Border's member listing reports it as live") as its own independently-verifiable check rather than reusing T007's result — that Border's member listing reports `johns-risk/viz` as live and reachable (SC-004); record the confirmed output in `specs/121-federated-topology-viz/quickstart.md`'s step 1
- [X] T039 [US3] Integration test: call `render_structural` directly against `johns-risk/viz` (Stage A alone, no Stage B) and assert the returned image is a real diagram distinct from Border's own fallback rendering (acceptance scenario 2), in `tests/integration/test_federated_topology_viz.py`
- [X] T040 [US3] Document the "member is down → bring it up" runbook step (`systemctl --user start netclaw-member-johns-risk-viz.service`) in `workspace/skills/comfyui-topology-viz/SKILL.md`

**Checkpoint**: All three user stories are independently functional. Full feature works end to end.

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Constitution XI's Full-Stack Artifact Coherence Checklist — required before this feature can be merged.

- [X] T041 [P] Update `README.md`: capability description, MCP server count (+2), setup instructions for the federated path
- [X] T041a [P] Update `ui/netclaw-visual/server.js`: add HUD nodes/status for `topology-diagram-mcp` and `image-style-mcp` (Constitution X/XI — two new MCP server integrations, same treatment spec 120 gave its own one new server; see plan.md Constitution Check)
- [X] T041b [P] Verify neither new MCP server contains any device-credential handling or device-configuration code path (FR-014 — both are pure image/data transforms); note the confirmation in each server's README.md (`mcp-servers/topology-diagram-mcp/README.md`, `mcp-servers/image-style-mcp/README.md`)
- [X] T042 [P] Update `scripts/lib/catalog.sh`: add `topology-diagram-mcp` and `image-style-mcp` component entries
- [X] T043 [P] Update `scripts/lib/install-steps.sh`: add `component_install_topology_diagram_mcp()` and `component_install_image_style_mcp()`
- [X] T044 Run `python3 scripts/verify-catalog-coverage.py` and resolve any reported gap for the two new MCP servers
- [X] T045 [P] Update `SOUL.md`: capability summary for the federated topology visualization path
- [X] T046 [P] Update `.env.example`: confirm/annotate any env var the two new servers need (expected: `COMFYUI_URL` only, already documented by spec 120 — add a comment noting the new consumer if so)
- [X] T047 [P] Update `TOOLS.md`: infrastructure reference entries for `topology-diagram-mcp` and `image-style-mcp`
- [X] T048 Run the full existing spec 120 test suite (`tests/unit/test_comfyui_*.py`, `tests/integration/test_comfyui_topology_viz.py`) and confirm zero regressions (FR-012/Constitution XV)
- [ ] T049 Create `specs/121-federated-topology-viz/model-inventory.md` tracking any model weights downloaded during T018/T019, and delete any weights the spike rejected (mirrors spec 120's own cleanup precedent)
- [ ] T050 Record a GAIT session log entry for this feature's implementation (Constitution IV)
- [ ] T051 Draft a WordPress milestone blog post per Constitution XVII and present it to John for review before publishing

## Dependencies & Execution Order

- **Setup (T001-T005)** blocks everything.
- **Foundational (T006-T010)** blocks all user stories — no `n2n/tools/call` to either new tool can succeed until T006 (authorization) and T005 (registration) are done, and T008 (timeout) is needed before any real Stage B call, which runs long.
- **User Story 1 (T011-T026)**: T018/T019 (the FR-015 spike) must complete, with a documented finding, before T021 (the real Stage B workflow) is implemented — this is FR-015's own gate, not just a suggested order. T014-T017 (Stage A) has no dependency on the spike and can proceed in parallel with T018/T019.
- **User Story 2 (T027-T037)**: depends on `federated_generation.py` existing (T023, from US1) since it extends the same file — cannot start implementation (though tests T027-T029 can be written first, mocked) until T023 lands.
- **User Story 3 (T038-T040)**: depends on Foundational T006/T007 only — independently testable as soon as those land, doesn't require US1/US2's code.
- **Polish (T041-T051)**: after all user stories are complete.

## Parallel Example

```
# Setup phase — independent files:
T001 (topology-diagram-mcp scaffold) and T002 (image-style-mcp scaffold) in parallel.

# Foundational phase — independent files:
T009 (topology-diagram-mcp request/result shapes) and T010 (image-style-mcp request/result shapes) in parallel.

# User Story 1 tests — independent files, write before implementation:
T011, T012, T013 in parallel.

# User Story 2 tests — same file (test_federated_generation_routing.py), but independent test functions:
T027, T028, T029 can be drafted in parallel by different people, but land as one coordinated commit since they share a file.
```

## Implementation Strategy

**MVP = User Story 1 alone** (T001-T026): the federated pipeline working end to end against a live
topology is the entire reason this feature exists (spec.md: "the entire reason this feature exists").
User Story 2 (fallback correctness) and User Story 3 (member-liveness verification) are both
required for the feature to be considered complete and safe to merge, but User Story 1 is the
independently-demonstrable core.

Recommended order: Setup → Foundational → User Story 1 (including the FR-015 spike, which gates
Stage B) → User Story 2 → User Story 3 (largely verification, can run any time after Foundational,
but ordered last here since it has no downstream dependents) → Polish.
