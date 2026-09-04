# Implementation Plan: World Labs Fantastical Topology Visualization

**Branch**: `122-worldlabs-topology-viz` | **Date**: 2026-09-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/122-worldlabs-topology-viz/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add one new MCP server, `worldlabs-marble-mcp`, that is a thin, fully stateless proxy to three World
Labs Marble REST endpoints (`worlds:generate`, `operations/get`, `worlds/get`), plus one new
orchestrating skill, `worldlabs-topology-viz`, that reuses the existing spec 121
`topology-diagram-mcp/render_structural` tool unmodified to get the authoritative reference diagram,
composes a bounded, deterministic "fantastical" text prompt from the same Topology Snapshot shape
spec 120/121 already use (role-count + connectivity-density summarization, the same technique as
spec 120's `prompt_builder.py`, themed instead of styled), and gates the one credit-spending call
(`generate_world`) behind both an explicit conversational confirmation and a code-level required
confirmation argument the tool itself validates (FR-004/FR-016 — strengthened during
`/speckit.analyze`, finding E1). No new persistent storage and no in-memory session cache — the
operation id / world id returned by World Labs is the only handle to a generation, and the calling
conversation is responsible for retaining it (Clarifications session 2026-09-03, Q1). Every
confirmed generation attempt IS recorded, via the repo's existing GAIT audit trail
(`gait_record_turn`) — not a new store, and not optional (Constitution Principle IV; corrected
during `/speckit.analyze`, finding C1, after the original Q2 answer of "no audit logging at all"
was found to directly conflict with the constitution).

## Technical Context

**Language/Version**: Python 3.10+ (matches every existing NetClaw MCP server and skill; no new
language)
**Primary Dependencies**: FastMCP (`worldlabs-marble-mcp`, matching repo convention), `httpx`
(outbound HTTPS calls to `api.worldlabs.ai` — no other NetClaw MCP server needs a new HTTP client
library beyond what's already vendored per-server, e.g. `mcp-servers/gitlab-mcp`'s pattern). The
skill reuses the existing, unmodified `topology-diagram-mcp/render_structural` tool (spec 121) for
the reference diagram and ports a trimmed copy of spec 120's `topology_model.py` (just
`DeviceRole`/`OperationalState`/`TopologySnapshot`/`sanitize_metadata` — no 3D or ComfyUI-specific
concepts) plus a new `fantastical_prompt_builder.py` module following the exact
role-summary/connectivity-summary composition pattern already proven in spec 120's
`prompt_builder.py`.
**Storage**: N/A — no new persistent storage of any kind (spec Clarifications Q1/Q2, FR-013,
FR-015). The reference PNG passes in-process as base64, directly into the `generate_world` request
body via Marble's `data_base64` image-reference source (research.md R1) — no upload/asset-management
round trip, no intermediate file.
**Testing**: pytest (matches repo convention); unit tests for `fantastical_prompt_builder.py`
(deterministic output for known snapshots) and for `worldlabs-marble-mcp`'s HTTP-status-to-failure-
category mapping (mocked httpx responses covering 401/402/429/404/generic — research.md R3); one
manual/documented live verification (already performed this session, not a mock — research.md R2)
satisfying spec FR-014/SC-006, since this is real money and not something to re-run on every test
pass.
**Target Platform**: Linux (WSL2) — same single-host deployment as every other NetClaw MCP server
**Project Type**: Single project — one new MCP server package under `mcp-servers/`, one new skill
directory under `workspace/skills/`, no frontend/backend split
**Performance Goals**: No fixed latency target for `generate_world` itself (the provider's own ~5
minute generation time, outside NetClaw's control); the free preview path (FR-002) MUST NOT add any
wait beyond what `render_structural` already takes (SC-001) — no additional processing between the
reference diagram and the composed prompt.
**Constraints**: Every code path that can reach `generate_world` MUST first pass through an explicit,
distinct user-confirmation step (FR-004/FR-005, SC-002) — enforced in the skill's documented workflow
AND by `generate_world` itself requiring a `user_confirmed: true` argument it validates before making
any outbound call (FR-016). The MCP server otherwise remains a thin, largely unconditional proxy,
consistent with every other MCP server in this repo, but this one specific safety property is not left
to convention alone (finding E1 — a purely conversational guarantee was judged insufficient for a
money-spending operation). The WLT-Api-Key value MUST never appear in a log, error message, or
response body (FR-010/SC-005). Every confirmed `generate_world` attempt MUST produce a `gait_record_turn`
entry (FR-015, Constitution Principle IV) — the skill layer's responsibility, not the MCP server's,
keeping the credential and the audit-recording concern in separate places.
**Scale/Scope**: One new MCP server (three tools: `generate_world`, `check_generation_status`,
`get_world`), one new skill (topology model port + prompt builder + workflow docs), no new
federation member, no new database

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I/II/VIII (Safety-First, Read-Before-Write, Verify After Every Change)**: N/A to device state —
  this feature never touches a network device; it only reads an already-assembled Topology Snapshot
  and calls an external image-generation API.
- **III (ITSM-Gated Changes)**: N/A — this feature makes no production network/device change of any
  kind; there is nothing for a ServiceNow CR to gate. (Omitted from the original Constitution Check
  entirely — gap found during `/speckit.analyze`, finding C2 — not previously mis-evaluated, simply
  absent.)
- **IV (Immutable Audit Trail)**: Satisfied, after correction — see Clarifications session
  2026-09-03's correction note and FR-015. Every confirmed `generate_world` attempt produces a
  `gait_record_turn` entry (topology identity/theme, operation id, cost once known, outcome — never
  the credential, never raw device data). This is the repo's existing, pre-mandated audit substrate,
  not a new store, so it does not conflict with FR-013's "no new persistent storage." (The original
  Clarifications Q2 answer — "no audit logging at all" — directly violated this principle's "no
  operation MAY execute silently" clause and the Forbidden Operations list; found and corrected
  during `/speckit.analyze`, finding C1. Also omitted from the original Constitution Check entirely,
  which is how C1 went undetected until the cross-artifact analysis pass — finding C2.)
- **V (MCP-Native Integration)**: Satisfied — `worldlabs-marble-mcp` is a proper FastMCP server with
  declared stdio transport, not a bespoke integration. The skill calls it and the existing
  `topology-diagram-mcp` the same way every other skill calls a registered MCP tool.
- **VI (Multi-Vendor Neutrality)**: N/A — no network-vendor logic anywhere in this feature.
- **VII (Skill Modularity)**: Satisfied — `worldlabs-topology-viz` performs one function (compose a
  themed prompt from a real topology and drive Marble generation) and delegates rendering entirely to
  the existing `topology-diagram-mcp`, never re-implementing it.
- **IX (Security by Default)**: N/A — no elevated device permissions; the only credential is the
  World Labs API key, handled per Principle XIII below.
- **X (Observability)**: `ui/netclaw-visual/server.js` MUST gain a node for `worldlabs-marble-mcp`
  (one new MCP server integration, same as every prior spec that added one — see spec 121's own
  precedent for `topology-diagram-mcp`/`image-style-mcp`). Tracked as a Polish-phase task.
- **XI (Full-Stack Artifact Coherence)** — NON-NEGOTIABLE: `README.md`, `scripts/lib/catalog.sh`,
  `scripts/lib/install-steps.sh`, `scripts/verify-catalog-coverage.py`, `ui/netclaw-visual/`,
  `SOUL.md`, `workspace/skills/worldlabs-topology-viz/SKILL.md`, `.env.example` (new `WLT_API_KEY`
  variable name only, no value — Principle XIII), `TOOLS.md`, `config/openclaw.json`, and
  `mcp-servers/worldlabs-marble-mcp/README.md` — full checklist tracked at implementation time
  (`docs/ADDING-AN-MCP.md` is the authoritative procedure and gate).
- **XII (Documentation-as-Code)**: New MCP server gets a `README.md` (tools, env vars, transport,
  install); new skill gets a `SKILL.md` (purpose, tools used, workflow, required env vars, example
  usage) documenting the mandatory preview-then-confirm-then-generate sequence.
- **XIII (Credential Safety)**: `WLT_API_KEY` is the only new env var. Read from the environment at
  runtime by `worldlabs-marble-mcp` only; never logged, never echoed in a tool result, never written
  to any file the system controls (FR-010). `.env.example` documents the name only.
- **XIV (Human-in-the-Loop for External Communications)**: This feature's credit-spending call is
  treated with the same discipline this principle already establishes for external-facing actions —
  explicit human approval is required before `generate_world` runs, even though Marble itself is not
  one of the principle's enumerated channels (Slack/ServiceNow/GitHub); the spirit applies directly
  since real money and an external third party are both involved.
- **XV (Backwards Compatibility)**: Purely additive — `topology-diagram-mcp` and every existing skill
  are unmodified. No shared interface changes.
- **XVI (Spec-Driven Development)**: This plan is itself the compliance mechanism —
  specify → clarify → plan → tasks → implement.
- **XVII (Milestone Documentation)**: A WordPress blog post draft is owed at completion, consistent
  with spec 120/121 precedent.

**Result**: No violations requiring justification in Complexity Tracking. One new MCP server is the
minimum surface needed to keep the WLT-Api-Key out of the skill layer entirely (Principle XIII) while
still exposing the three Marble endpoints this feature actually needs — no simpler alternative avoids
either a second credential-holding location or an unused fourth tool. Principle IV's audit-trail
requirement is satisfied by reusing the existing GAIT mechanism (no new store introduced) after the
`/speckit.analyze` correction described above.

## Project Structure

### Documentation (this feature)

```text
specs/122-worldlabs-topology-viz/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── worldlabs-marble-mcp.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
mcp-servers/
├── worldlabs-marble-mcp/        # NEW — generate_world / check_generation_status / get_world
│   ├── server.py
│   ├── requirements.txt         # mcp>=1.0.0,<2 ; httpx
│   └── README.md
└── topology-diagram-mcp/        # EXISTING (spec 121) — reused unmodified

workspace/skills/worldlabs-topology-viz/    # NEW
├── SKILL.md                     # Preview → confirm → generate → poll workflow
├── topology_model.py            # Ported/trimmed from spec 120's topology_model.py
└── fantastical_prompt_builder.py  # Role-summary + connectivity-summary → themed text prompt

tests/
└── unit/
    ├── test_fantastical_prompt_builder.py   # NEW
    └── test_worldlabs_marble_mcp.py         # NEW — mocked httpx, covers 401/402/429/404/generic
```

**Structure Decision**: Single project, no frontend/backend split. One new, small, single-purpose MCP
server package under `mcp-servers/` (matching every other NetClaw MCP server's layout) and one new
skill directory under `workspace/skills/`, additive alongside spec 120/121's existing directories
(never editing their files).

## Complexity Tracking

*No violations — Constitution Check above found none requiring justification. Three tools on one MCP
server is the minimum surface FR-006/FR-007/FR-008 require while keeping the credential isolated to
that one server (research.md R1 explains why `generate_world` alone, using Marble's `data_base64`
image-reference source, replaces what was originally assumed to be a two-call upload-then-generate
flow).*
