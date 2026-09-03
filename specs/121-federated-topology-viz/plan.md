# Implementation Plan: Federated AI-Augmented Network Topology Visualization

**Branch**: `121-federated-topology-viz` | **Date**: 2026-08-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/121-federated-topology-viz/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Replace spec 120's Canny-edge-reconstruction pipeline's structural-correctness risk with a two-stage
federated (iN2N) pipeline: Stage A deterministically renders a topology-accurate, real-icon,
correctly-labeled diagram (new `topology-diagram-mcp` tool, N2G + draw.io CLI, executed on the
`johns-risk/viz` federation member), Stage B restyles that already-correct image with an image-edit
diffusion model without altering its structure (new `image-style-mcp` tool, Qwen-Image-Edit-2509 or
FLUX.2 [klein] pending a research spike, executed on the same member). Border orchestrates both
stages purely via the existing `n2n/tools/call` federation mechanism (`n2n-mcp`'s `n2n_invoke`/
`n2n_member_health`) and never renders or diffuses in-process itself. Spec 120's existing pipeline
becomes the unmodified fallback tier for freeform requests or member unreachability, wrapped by a new
`federated_generation.py` orchestrator that is the only change to the existing skill's call graph.

## Technical Context

**Language/Version**: Python 3.10+ (matches every existing NetClaw MCP server and skill; no new
language)
**Primary Dependencies**: FastMCP (both new MCP servers, matching repo convention), networkx +
Pillow (Stage A rendering — reused from spec 120's `topology_renderer.py`, no new system binary;
research.md R3a corrects the original N2G/draw.io-CLI decision after finding neither is available
headlessly on this host), the existing `mcp` Python SDK stdio client pattern (already proven in
spec 120's `comfyui_client.py`, reused to call `n2n-mcp`), direct ComfyUI REST calls (ported from
spec 120's `comfyui_client.py`, not the `comfyui-mcp` Node server's known-broken task tracker —
research.md R5)
**Storage**: N/A — no new persistent storage; images pass inline (base64) over the existing
federation channel (research.md R6) and land in spec 120's existing
`workspace/output/comfyui-topology-viz/` output directory
**Testing**: pytest (matches spec 120's `tests/unit/` and `tests/integration/` convention); new unit
tests for `federated_generation.py`'s routing logic (mockable member-health/tool-call responses) and
for each new MCP server's tool logic; one live integration test against the real `johns-risk/viz`
member, mirroring spec 120's one genuinely-live integration test
**Target Platform**: Linux (WSL2) — same single-host deployment as Border and every other member in
this "3 rings" environment (research.md R1/R2)
**Project Type**: Single project — two new MCP server packages under `mcp-servers/`, new modules
added to the existing `workspace/skills/comfyui-topology-viz/` skill (spec 120's own files
untouched — FR-012), no frontend/backend split
**Performance Goals**: No fixed latency target (spec's own Assumptions: no fixed timeout at either
stage, consistent with spec 120); `N2N_TOOL_TIMEOUT_S` raised to 600s on both sides so the federation
layer itself doesn't impose an accidental ceiling (research.md R7)
**Constraints**: Images must fit the existing federation channel's 16 MB aggregate message cap
(research.md R6); at most one federated-or-fallback generation in flight at a time (FR-013, reusing
spec 120's existing single-in-flight guard); zero device-configuration actions at any stage (FR-014)
**Scale/Scope**: Two new MCP servers (one tool each), one new orchestrator module, no new federation
member (reuses already-live `johns-risk/viz`, research.md R1/R5), no new persistent schema

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I/II/VIII (Safety-First, Read-Before-Write, Verify After Every Change)**: N/A to device state —
  this feature is read-only visualization throughout (FR-014), identical in this respect to spec 120,
  which already satisfied these principles. Not applicable to image-generation pipeline internals.
- **V (MCP-Native Integration)**: Satisfied — both new capabilities (`topology-diagram-mcp`,
  `image-style-mcp`) are built as proper MCP servers (FastMCP) with declared stdio transport, not a
  bespoke integration pattern. Federation orchestration itself reuses the existing, already-compliant
  `n2n/tools/call` JSON-RPC mechanism (research.md R4) rather than inventing a new one.
- **VI (Multi-Vendor Neutrality)**: N/A — no vendor-specific device logic anywhere in this feature.
- **VII (Skill Modularity)**: Satisfied — `federated_generation.py` is a new, single-purpose module
  (routing/orchestration only); it delegates rendering and styling entirely to the two new MCP
  servers rather than duplicating spec 120's logic in-process.
- **IX (Security by Default)**: N/A — no new privileged access; both new MCP servers request no
  elevated permissions (they read a snapshot / an image, produce an image).
- **X (Observability)**: `ui/netclaw-visual/server.js` MUST be updated for the two new MCP server
  integrations (`topology-diagram-mcp`, `image-style-mcp`) themselves, exactly as spec 120 updated it
  for its own one new MCP server — "no new HUD node" would only apply if no new integration existed;
  two new MCP servers is two new integrations, regardless of whether a new federation *member* was
  also added. Tracked as a Polish-phase task (T041a).
- **XI (Full-Stack Artifact Coherence)** — NON-NEGOTIABLE, full checklist tracked at implementation
  time: `README.md`, `scripts/lib/catalog.sh`, `scripts/lib/install-steps.sh`,
  `scripts/verify-catalog-coverage.py`, `SOUL.md`, two new `workspace/skills/.../SKILL.md`-equivalent
  docs are N/A (these are MCP servers, not skills — but each needs its own `mcp-servers/<name>/README.md`
  per XII), `.env.example`, `TOOLS.md`, `config/openclaw.json` — for **both** new MCP servers.
- **XII (Documentation-as-Code)**: Each new MCP server gets a `README.md` (tools, env vars, transport,
  install). No new skill is created (FR-004a: same existing skill entry point), so no new
  `SKILL.md` — the existing `comfyui-topology-viz/SKILL.md` gets an update describing the federated
  path, not a new skill directory.
- **XIII (Credential Safety)**: `COMFYUI_URL` is the only env var either new server needs (already
  documented in `.env.example` per spec 120); no new secrets introduced.
- **XIV (Human-in-the-Loop)**: N/A — no external communication (Slack/ServiceNow/GitHub) in this
  feature's scope.
- **XV (Backwards Compatibility)**: Directly enforced by FR-012 — spec 120's fallback pipeline is
  reused unmodified; the only change to existing code is one call-site in `__init__.py`
  (research.md R8).
- **XVI (Spec-Driven Development)**: This plan is itself the compliance mechanism — spec → clarify →
  plan → tasks → implement, no ad-hoc work.
- **XVII (Milestone Documentation)**: A WordPress blog post draft is owed at completion (post-merge),
  consistent with spec 120's own precedent.

**Result**: No violations requiring justification in Complexity Tracking. The two new MCP servers are
the minimum needed to satisfy FR-005/FR-006 (deterministic tool-call execution on a member, not
Border in-process) — see research.md R3 for why the existing `drawio-diagram` skill could not be
reused as-is.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
mcp-servers/
├── topology-diagram-mcp/        # NEW — Stage A: render_structural tool
│   ├── server.py
│   ├── requirements.txt         # adds N2G
│   └── README.md
├── image-style-mcp/             # NEW — Stage B: style_image tool
│   ├── server.py
│   ├── requirements.txt
│   └── README.md
└── n2n-mcp/                     # EXISTING — n2n_invoke / n2n_member_health, unmodified

workspace/skills/comfyui-topology-viz/    # EXISTING (spec 120) — extended, not modified in place
├── federated_generation.py      # NEW — routing orchestrator (research.md R8)
├── __init__.py                  # ONE call-site edit: calls federated_generation, not generation directly
├── generation.py                # UNCHANGED (FR-012) — the fallback path
├── topology_model.py            # UNCHANGED — shared Topology Snapshot
├── prompt_builder.py            # UNCHANGED — reused by image-style-mcp's caller-side prompt build
└── SKILL.md                     # UPDATED — documents the federated path, still one skill

tests/
├── unit/
│   ├── test_federated_generation_routing.py   # NEW
│   ├── test_topology_diagram_mcp.py            # NEW
│   └── test_image_style_mcp.py                 # NEW
└── integration/
    └── test_federated_topology_viz.py          # NEW — one genuinely-live test, mirrors spec 120's
```

**Structure Decision**: Single project, no frontend/backend split. This feature is additive
alongside spec 120's existing skill directory (never editing spec 120's own files, per FR-012) plus
two new, small, single-tool MCP server packages under `mcp-servers/`, matching the exact layout every
other NetClaw MCP server in this repo already uses.

## Complexity Tracking

*No violations — Constitution Check above found none requiring justification. Two new MCP servers
are the minimum surface FR-005/FR-006 require (research.md R3); no simpler alternative preserves
"deterministic tool execution on a member, not Border in-process."*
