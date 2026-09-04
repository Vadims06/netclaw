# Tasks: World Labs Fantastical Topology Visualization

**Input**: Design documents from `/specs/122-worldlabs-topology-viz/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/worldlabs-marble-mcp.md, quickstart.md

**Tests**: Included — plan.md's Technical Context explicitly commits to unit tests for
`fantastical_prompt_builder.py` and for the HTTP-status/guard-to-failure-category mapping, so those
are generated as real tasks below (not skipped as optional).

**Organization**: Tasks are grouped by user story (spec.md: US1/US2 are P1, US3 is P2) to enable
independent implementation and testing of each story.

**Revision note**: This task list was updated after `/speckit.analyze` surfaced seven findings
against the original `spec.md`/`plan.md`/`tasks.md` set (one CRITICAL constitutional conflict, two
HIGH, two MEDIUM, two LOW). All seven are addressed below and in the sibling documents; see each
affected task's note for which finding it resolves. Net effect: one new task (T018, GAIT logging —
finding C1), two tasks removed (former T020/T021, collapsed per finding D1), several existing task
descriptions strengthened (findings E1/E2/E3). Total task count: 32 (was 33).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are included in every description

## Path Conventions

Single project, matching every other NetClaw MCP server/skill pair:
- `mcp-servers/worldlabs-marble-mcp/` — new MCP server
- `workspace/skills/worldlabs-topology-viz/` — new skill
- `tests/unit/` — new unit tests

---

## Phase 1: Setup

**Purpose**: Scaffolding so both the new MCP server and the new skill exist as installable,
registered artifacts before any tool logic is written.

- [X] T001 Create `mcp-servers/worldlabs-marble-mcp/` with a minimal `server.py` (FastMCP app
  named `worldlabs-marble-mcp`, no tools yet) and `requirements.txt` (`mcp>=1.0.0,<2` — bounded
  per `docs/ADDING-AN-MCP.md`'s pinning rule since `server.py` imports
  `mcp.server.fastmcp`, plus `httpx`); add a `.gitignore` negation entry for the new directory
  (`docs/ADDING-AN-MCP.md` step 1)
- [X] T002 [P] Create `workspace/skills/worldlabs-topology-viz/` with a `SKILL.md` stub (YAML
  frontmatter only: `name`, `description`, `license`, `user-invocable: true`,
  `metadata.openclaw.requires.env: ["WLT_API_KEY"]` — matching
  `workspace/skills/comfyui-topology-viz/SKILL.md`'s frontmatter shape)
- [X] T003 [P] Register `worldlabs-marble-mcp` in `config/openclaw.json` with a repo-relative
  `command`/`args` (`python3`, `["-u", "mcp-servers/worldlabs-marble-mcp/server.py"]`) — no
  hardcoded absolute path (`docs/ADDING-AN-MCP.md` step 2)
- [X] T004 [P] Add `WLT_API_KEY` to `.env.example` with a descriptive comment and no value
  (Constitution Principle XIII). SC-005's "never in a committed file" clause is satisfied by the
  repo's existing, already-enforced `.env`-is-gitignored convention (Principle XIII) — no new
  mechanism needed here, this task only adds the *name*, never the value

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared code both P1 user stories (US1 preview, US2 generate) depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 [P] Port a trimmed `topology_model.py` into
  `workspace/skills/worldlabs-topology-viz/topology_model.py` — copy only `DeviceRole`,
  `OperationalState`, `TopologySnapshot` (devices/links), and `sanitize_metadata` /
  `FORBIDDEN_METADATA_KEYS` from `workspace/skills/comfyui-topology-viz/topology_model.py`; drop
  every 3D/ComfyUI-specific concept (data-model.md's Topology Snapshot section)
- [X] T006 [P] Add a `_map_failure(status_code, body) -> dict` helper to
  `mcp-servers/worldlabs-marble-mcp/server.py` implementing the failure-category table in
  `contracts/worldlabs-marble-mcp.md` (401→`authentication_failure` with a fixed message that
  never includes the key value, 402→`insufficient_credits` passing the provider message through
  verbatim, 429→`rate_limited` with a fixed "wait and retry" message, 404→`not_found_or_expired`,
  everything else→`generic_failure` passing the provider message through) — this is shared by
  every tool added in Phase 4. Also add a standalone `_confirmation_required_error()` helper for
  the `confirmation_required` category (research.md R8), which is raised before any HTTP call and
  so is not part of the HTTP-status mapping table itself
- [X] T007 Add the FR-009 decorative-interpretation label as a single exported constant,
  `DECORATIVE_LABEL`, in `workspace/skills/worldlabs-topology-viz/topology_model.py` (exact
  wording: states the result is an artistic/decorative interpretation, not an accurate
  representation of physical layout, cabling, or device state, and must be paired with a
  reference to the authoritative structural diagram)

**Checkpoint**: Topology model, shared failure-category mapping, and the decorative-label
constant all exist. US1 and US2 can now proceed independently.

---

## Phase 3: User Story 1 - Preview a fantastical prompt at no cost (Priority: P1) 🎯 MVP

**Goal**: Given a topology snapshot, produce the reference diagram plus a composed, themed text
prompt — instantly, with zero calls to World Labs and zero credits spent.

**Independent Test**: Supply a topology snapshot, request a preview, confirm the result contains
the reference diagram and a composed prompt reflecting real device roles/connectivity, and confirm
(by code inspection / mocking) that no HTTP call to `api.worldlabs.ai` occurs.

### Tests for User Story 1

- [X] T008 [P] [US1] Unit test in `tests/unit/test_fantastical_prompt_builder.py` covering:
  role-count summary for a known multi-role snapshot, connectivity-density summary at sparse/
  typical/dense link-to-device ratios, a theme string appearing in the output, the default theme
  applying when none is given, and the composed prompt staying under the length bound

### Implementation for User Story 1

- [X] T009 [US1] Implement `build_prompt(snapshot: TopologySnapshot, theme: str | None = None) ->
  str` in `workspace/skills/worldlabs-topology-viz/fantastical_prompt_builder.py`, porting the
  role-summary + connectivity-summary composition technique from
  `workspace/skills/comfyui-topology-viz/prompt_builder.py` (data-model.md's Fantastical Prompt
  section, research.md R5); bound total length the same way (~900 chars); apply a reasonable
  default theme when `theme` is `None` (depends on: T005, T008)
- [X] T010 [US1] Write the preview workflow section of
  `workspace/skills/worldlabs-topology-viz/SKILL.md`: call the existing
  `topology-diagram-mcp/render_structural` tool unmodified to get the reference diagram, call
  `build_prompt`, then present both **with `DECORATIVE_LABEL` included directly in the output
  template from the start** (not added later — finding D1) — explicitly document that this path
  makes no call to `worldlabs-marble-mcp` (FR-002/FR-005). **Also document both existing failure
  modes of the reused `render_structural` tool explicitly** (finding E2, plus a correction found
  during implementation): the working-resolution device-ceiling rejection (FR-012) AND the
  zero-device/empty-topology rejection (`"devices list is empty — nothing to render"`) MUST both
  be relayed with their specific reason (FR-012's spirit) rather than a generic "something went
  wrong" message — neither is new logic, but the preview workflow must name and handle both
  explicitly rather than let either fall through silently. The single-device (one device, zero
  links) case is different and MUST succeed normally — `render_structural` already supports it
  (depends on: T007, T009)
- [X] T011 [US1] Add a "Natural Language Commands" section to `SKILL.md` with example preview
  trigger phrases (e.g. "Give me a fantastical world preview of the CML lab topology,
  floating-islands theme"), matching the pattern in
  `workspace/skills/comfyui-topology-viz/SKILL.md` (depends on: T010)

**Checkpoint**: User Story 1 is fully functional and independently testable — free preview works
end-to-end with no World Labs calls, and the density-ceiling edge case is explicitly handled.

---

## Phase 4: User Story 2 - Generate a fantastical world from a real topology (Priority: P1)

**Goal**: After an explicit, separate, two-layer confirmation (conversational AND code-level),
spend credits to generate a real explorable world from the previewed reference diagram + prompt,
audit the attempt, report status on request, and fall back to a durable lookup if the operation
record expires.

**Independent Test**: Take a previewed reference diagram + prompt, explicitly confirm, verify a
world is produced with a working viewer link, a categorized failure with no silent/ambiguous
outcome, or a rejection when `user_confirmed` is not set; verify status-check, the expired-operation
fallback, and the GAIT record all work.

### Tests for User Story 2

- [X] T012 [P] [US2] Unit test in `tests/unit/test_worldlabs_marble_mcp.py` covering `_map_failure`
  (T006) against mocked httpx responses for 401, 402 (asserting the provider's message text is
  passed through), 429, 404, and a generic 500/400/422 — explicitly asserting the API key value
  never appears in any mapped output, **and asserting no `logging`/`print` call anywhere in
  `server.py` interpolates the raw `WLT_API_KEY` value** (finding E3 — a static source-inspection
  assertion, e.g. grepping the module source for the pattern, not just checking return values).
  Also cover the `confirmation_required` guard (finding E1, research.md R8): `generate_world`
  called with `user_confirmed` omitted, `false`, and a non-boolean truthy value MUST all be
  rejected with `confirmation_required` and MUST NOT result in any mocked HTTP call being made

### Implementation for User Story 2

- [X] T013 [US2] Implement the `generate_world` tool in
  `mcp-servers/worldlabs-marble-mcp/server.py`: **first validate `user_confirmed is True` and
  return `_confirmation_required_error()` immediately if not (finding E1, research.md R8, FR-016
  — before any other validation or HTTP call)**; then build the request with
  `world_prompt.type="image"`, `image_prompt={"source": "data_base64", "data_base64": ...,
  "extension": ...}`, `text_prompt`, `display_name` (max 64 chars), `model` (default
  `"marble-1.1"`); `POST https://api.worldlabs.ai/marble/v1/worlds:generate` with header
  `WLT-Api-Key` read from `os.environ["WLT_API_KEY"]` at call time; apply `_map_failure` on any
  non-200; never include the key in any log or returned value (contracts/worldlabs-marble-mcp.md,
  research.md R1/R8) (depends on: T006, T012)
- [X] T014 [US2] Implement the `check_generation_status` tool in
  `mcp-servers/worldlabs-marble-mcp/server.py`: `GET
  https://api.worldlabs.ai/marble/v1/operations/{operation_id}`; pass through `done`, `error`,
  `response`, `cost`, and `metadata` (including `metadata.world_id` when present, per research.md
  R4); apply `_map_failure` on any non-200, including 404→`not_found_or_expired` (depends on:
  T006)
- [X] T015 [US2] Implement the `get_world` tool in `mcp-servers/worldlabs-marble-mcp/server.py`:
  `GET https://api.worldlabs.ai/marble/v1/worlds/{world_id}`; pass through `world_id`,
  `display_name`, `world_marble_url`, `assets`; apply `_map_failure` on any non-200, including
  404→`not_found` (research.md R4) (depends on: T006)
- [X] T016 [US2] Write `mcp-servers/worldlabs-marble-mcp/README.md` documenting all three tools
  (including the `user_confirmed` guard and `confirmation_required` category), the required
  `WLT_API_KEY` environment variable, stdio transport, and install command (matching
  `mcp-servers/topology-diagram-mcp/README.md`'s structure) (depends on: T013, T014, T015)
- [X] T017 [US2] Write the generate/confirm/poll workflow section of
  `workspace/skills/worldlabs-topology-viz/SKILL.md`: require an explicit, separate user
  confirmation stating credits will be spent and generation takes ~5 minutes before calling
  `generate_world` with `user_confirmed=true`; document polling via `check_generation_status`;
  document falling back to `get_world` using a `world_id` observed in an earlier poll's `metadata`
  if status-checking returns `not_found_or_expired`; every completed/failed result must include
  `DECORATIVE_LABEL` **from the start of this section's output template** (finding D1 — not added
  in a later pass) (FR-004/FR-005/FR-007/FR-008/FR-009/FR-016) (depends on: T010, T013, T014, T015)
- [X] T018 [US2] **(New — resolves finding C1 / Constitution Principle IV)** Add a GAIT audit
  instruction to the same workflow section of `SKILL.md`: immediately after every `generate_world`
  call (success, failure, or `confirmation_required` rejection), call `gait_record_turn` with
  `user_text` (topology snapshot identity/theme, confirmation given), `assistant_text` (outcome —
  `operation_id`, `world_id`/`world_marble_url` and `cost.total_credits` once known, or the
  failure category), and empty/identity-only `artifacts` — matching the pattern documented in
  `workspace/skills/atlassian-itsm/SKILL.md`. Explicitly document that this is required for every
  confirmed attempt, not optional, and that it MUST NOT include the API key or raw device data
  beyond hostname/role identity (data-model.md's GAIT Audit Entry section, research.md R7)
  (depends on: T017)
- [X] T019 [US2] Add generate/status-check example trigger phrases to `SKILL.md`'s "Natural
  Language Commands" section (depends on: T017)

**Checkpoint**: User Stories 1 AND 2 both work independently — preview is free, generation is
gated at two independent layers, every confirmed attempt is GAIT-audited, and status-check plus
the expired-operation fallback both work.

---

## Phase 5: User Story 3 - Understand this is not the source of truth (Priority: P2)

**Goal**: Every preview and every generation result visibly carries the decorative-interpretation
statement and a reference to the authoritative structural diagram it was derived from.

**Independent Test**: Inspect any preview result (US1) and any completed/failed generation result
(US2) and confirm both carry `DECORATIVE_LABEL`'s statement and reference the reference diagram.

**Note (finding D1 — collapsed during `/speckit.analyze`)**: The original task list had separate
"wire the label in" implementation tasks here. Since `DECORATIVE_LABEL` (T007) exists before T010
and T017 are written, those two tasks now include it directly from the start — there is nothing
left to retrofit. This phase is now purely a verification test confirming that discipline holds.

### Tests for User Story 3

- [X] T020 [P] [US3] Unit test in `tests/unit/test_decorative_labeling.py` asserting
  `DECORATIVE_LABEL` (T007) is referenced by name in both the preview workflow section (T010) and
  the generate/status-check workflow section (T017) of `SKILL.md` — including specifically the
  completed-generation and `get_world`-fallback cases within T017's section, not just the section
  as a whole (**correction found during implementation**: there is no Python function that
  composes the final human-facing chat response — that composition happens conversationally,
  following `SKILL.md`, so this is a documentation-content check, not a function-return-value
  check like T008/T012) (depends on: T007, T010, T017)

**Checkpoint**: All three user stories are independently functional; every user-facing output is
correctly labeled.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Constitution Principle XI (Full-Stack Artifact Coherence) and Principle XVII
(Milestone Documentation) — required before this feature is considered complete, per
`docs/ADDING-AN-MCP.md`'s checklist.

- [X] T021 [P] Update `README.md` — description, architecture note, and tool/capability counts
  including `worldlabs-marble-mcp`
- [X] T022 [P] Update `SOUL.md` — capability summary and counts for the new skill and MCP server
- [X] T023 [P] Add a `worldlabs-marble-mcp` entry to `scripts/lib/catalog.sh`
  (`"id|Category|Name|Description"`)
- [X] T024 [P] Add `component_install_worldlabs_marble_mcp()` to `scripts/lib/install-steps.sh`
- [X] T025 Run `scripts/verify-catalog-coverage.py` and resolve any reported gap for the new
  server/catalog id (depends on: T023, T024)
- [X] T026 [P] Update `TOOLS.md` — infrastructure reference entry for `worldlabs-marble-mcp`
- [X] T027 [P] Add `worldlabs-marble-mcp` to `ui/netclaw-visual/server.js` — both the node-list
  entry and the annotation-map entry (`docs/ADDING-AN-MCP.md`'s "two artifacts, not one" note)
- [X] T028 Run `scripts/check-server-startup.py --only worldlabs-marble-mcp` and resolve any fatal
  startup finding (a timeout is success) (depends on: T001, T013, T014, T015)
- [X] T029 Run `scripts/reconcile-mcp.py` and resolve any non-zero finding across all surfaces
  (depends on: T003, T021, T022, T023, T024, T025, T026, T027, T028)
- [X] T030 Run `quickstart.md`'s free-preview flow (User Story 1) manually as final validation and
  confirm no World Labs API call occurs (depends on: T010, T011)
- [ ] T031 Record the end-of-session GAIT summary commit (Constitution Principle IV) for this
  feature's development work — distinct from T018's per-generation GAIT record, which audits the
  *feature's own runtime operation*; this task is the ordinary session-level wrap-up GAIT already
  requires for every NetClaw session
- [ ] T032 Draft the WordPress milestone blog post per Constitution Principle XVII and present it
  to John for review before publishing (depends on: T029)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS User Stories 1 and 2
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational only (independently testable from US1, though
  its SKILL.md section builds on US1's preview section already existing in the same file — T017
  depends on T010 for that reason, not a functional dependency)
- **User Story 3 (Phase 5)**: Depends on both US1 (T010) and US2 (T017) already existing, since it
  verifies labeling in both of their outputs — this is the one story that is not fully independent
  of the others, by its own nature (it is a cross-cutting correctness check on the other two)
- **Polish (Phase 6)**: Depends on all three user stories being complete

### Parallel Opportunities

- T002, T003, T004 (Setup) — different files, run together
- T005, T006 (Foundational) — different files, run together
- T008 (US1 test) can be written in parallel with T005/T006, before T009 exists (test-first)
- T012 (US2 test) can be written in parallel with T005/T006, before T013 exists (test-first)
- T020 (US3 test) can be written as soon as T007 exists, in parallel with US1/US2 implementation
- T021, T022, T023, T024, T026, T027 (Polish) — different files, run together

---

## Parallel Example: Foundational + User Story 1 test-first start

```bash
# After Setup (Phase 1) completes, launch together:
Task: "Port trimmed topology_model.py in workspace/skills/worldlabs-topology-viz/topology_model.py"
Task: "Add _map_failure and _confirmation_required_error helpers in mcp-servers/worldlabs-marble-mcp/server.py"

# Then, in parallel with each other (both are test-first, before their implementations exist):
Task: "Unit test for fantastical_prompt_builder in tests/unit/test_fantastical_prompt_builder.py"
Task: "Unit test for _map_failure and the confirmation guard in tests/unit/test_worldlabs_marble_mcp.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run `quickstart.md`'s preview flow, confirm zero World Labs calls
5. This is a real, demoable MVP on its own — a free preview feature with no credit-spending
   capability yet

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. User Story 1 → validate independently → demo the free preview (MVP)
3. User Story 2 → validate independently (this is where real credits get spent for the first
   time, and where the GAIT audit record first gets written — do this deliberately, not casually)
   → demo end-to-end generation
4. User Story 3 → validate independently → confirm labeling discipline holds everywhere
5. Polish (Phase 6) → full Constitution Principle XI artifact coherence, then
   `scripts/reconcile-mcp.py` must exit 0 before this feature is considered mergeable

---

## Notes

- [P] tasks touch different files with no incomplete-task dependency between them
- [Story] labels map every Phase 3+ task to spec.md's US1/US2/US3
- Verify T008/T012/T020 fail before their corresponding implementation tasks are done
  (test-first, per plan.md's Testing strategy)
- T013 (`generate_world`) is the only task in this entire feature that, once merged and invoked
  for real, spends real money — treat manual verification of it with the same care given to
  the live test already performed and documented in research.md R2, and confirm T018's GAIT
  recording actually fires on that first real call
- Commit after each task or logical group
