# Implementation Plan: Astra Live Digital Twin

**Branch**: `122-astra-live-digital-twin` | **Date**: 2026-09-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/122-astra-live-digital-twin/spec.md`

## Summary

Extend NetClaw's existing Three.js HUD (specs 101/102) with a continuously-updating "live twin" of a
lab network: a read-only collector polls the existing pyATS/CML MCP tooling on a fixed interval,
diffs against its last known state, and streams the resulting deltas to the HUD over the browser's
already-present WebSocket dependency, so the 3D scene updates itself within seconds of a real lab
change instead of requiring regeneration. The feature is built — not run — by "Astra Twin," a new,
OpenAI-backed iN2N mesh member distinct from the primary Claude-backed agent, using an unattended
Ralph-loop build process with an independent maker/checker split. **This plan governs both the
delivered twin and the loop that builds it; `/speckit.implement` for this feature builds the loop
harness only (see `loop.md`), never the twin's application code directly — the loop builds that.**

## Technical Context

**Language/Version**: Python 3.10+ (`astra-twin-mcp` collector server, matching every existing NetClaw
MCP server); Node.js 18+ / ES2022 (HUD extension in `ui/netclaw-visual/`, matching specs 101/102);
Bash (`loop/ralph.sh` driver, matching every existing NetClaw install/enable script)
**Primary Dependencies**: FastMCP (new `astra-twin-mcp` server — read-only, wraps existing pyATS MCP
and CML/GNS3 MCP tool calls, does not talk to devices directly); the existing `ws` npm dependency
already present in `ui/netclaw-visual/package.json` (delta streaming to the browser — no new runtime
dependency for this half); `@openai/codex` (already installed, `codex exec`, drives Astra Twin's
maker/checker agent processes via `OPENAI_API_KEY`); Playwright (new — headless-browser screenshot,
console-error, and element-count capture for the frozen `harness/`, since prior HUD specs 101/102
relied on a human manually taking screenshots, which an unattended loop cannot do); existing
`bgp/federation/manager.py` / `risk.py` / `scripts/in2n-member.py` (iN2N member enrollment, consumed
and minimally extended, not rebuilt)
**Storage**: In-memory current-state snapshot + a bounded ring buffer of the last 500 deltas inside
the `astra-twin-mcp` process (no database — deltas older than the buffer require a fresh snapshot,
which is cheap at lab scale); the existing iN2N SQLite at `~/.openclaw/n2n/federation.db` gains one
nullable column (`model_provider`) on the existing `member` table — no new store
**Testing**: pytest (contract tests for the twin schema and MCP tool responses, frozen); `npm test`
(existing HUD test convention, extended for the new scene-delta application logic); the frozen
Playwright harness (`harness/`) for automated visual verification, since this loop runs unattended
**Target Platform**: Linux server (NetClaw host, collector + HUD backend); any modern browser (HUD
frontend) — same platforms as specs 101/102, nothing new
**Project Type**: Extension of an existing web-service + CLI hybrid (MCP server, Node HUD backend,
browser frontend), delivered through a new autonomous build-loop tool (Bash driver + Python harness)
**Performance Goals**: A real lab change is visible in the twin within 30 seconds (SC-001); the HUD
stays interactive while receiving live deltas, inheriting the 60fps target already established by
specs 101/102 — delta application must not cause a full scene rebuild
**Constraints**: Zero configuration-write capability anywhere in the delivered feature (FR-003,
FR-005); the collector MUST refuse to start against anything but the allowlisted lab testbed
(FR-004); the loop itself MUST hold no config-write MCP capability during the build (safety envelope,
loop.md) — this is enforced at the environment level, not just by policy
**Scale/Scope**: A single lab topology of realistic lab size (tens of devices/links) — this is not a
production-scale monitoring system

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — see below.*

| Principle | Status | Notes |
|---|---|---|
| I. Safety-First Operations | PASS | The twin only ever issues `show`-equivalent reads through existing pyATS/CML MCP tools; FR-003 makes this a hard requirement, not a convention, and `harness/assert_lab_only.py` (frozen) enforces the testbed allowlist before the loop is even allowed to start. |
| II. Read-Before-Write | PASS (N/A for writes) | The collector never writes; there is no baseline/modify/verify cycle to satisfy because there is no modify step. |
| III. ITSM-Gated Changes | PASS (N/A) | No configuration changes are ever made, in lab or production, so no CR is required. If this changes in a future spec, that spec — not this one — takes on the CR requirement. |
| IV. Immutable Audit Trail | PASS | Every loop iteration commits to git with a task description (`loop/state/iterations.md`); the checker's verdicts are a second, independent written record (`loop/state/verdicts.md`); Astra Twin's iN2N enrollment and every delegated build action are recorded in the existing `remote_invocation_record` audit table (spec 056/057 pattern) — this is a *stronger* audit trail than a single human session would leave, not a weaker one. |
| V. MCP-Native Integration | PASS | The collector is delivered as `astra-twin-mcp`, a proper FastMCP server, not a bespoke script bolted onto the HUD. |
| VI. Multi-Vendor Neutrality | PASS | `astra-twin-mcp` holds no vendor-specific logic itself — it delegates every device read to the existing pyATS MCP server, which already owns multi-vendor neutrality. |
| VII. Skill Modularity | PASS | This feature does not introduce an operator-facing skill; it extends the HUD and adds one focused MCP server. No skill scope creep. |
| VIII. Verify After Every Change | PASS | Every loop iteration runs the frozen gate (`harness/run_gates.sh`) before a commit is even attempted, and a second independent process re-verifies against the spec before acceptance — stronger than the baseline→apply→verify cycle this principle describes. |
| IX. Security by Default | PASS | `astra-twin-mcp` requests read-only MCP tool access only; this is documented and justified in its `README.md` (task-generated) per the MCP Server Standards section. |
| X. Observability | PASS | FR-010's freshness indicator and the collector's `get_status()` tool are exactly the "health/status" surface this principle requires; the Three.js HUD is the integration being extended, not bypassed. |
| XI. Full-Stack Artifact Coherence | GATED — see Pass Schedule | This is the principle most at risk from an unattended loop, precisely because it is boilerplate an agent is likely to skip under time pressure. It is made an explicit, checker-graded phase (Phase D below) rather than left implicit. |
| XIII. Credential Safety | PASS | `OPENAI_API_KEY` is already in `.env` (confirmed present, not committed); `.env.example` gains a description-only entry as part of Phase D; the loop's `preflight()` explicitly asserts production credentials are *absent* from its environment, which is stricter than this principle requires. |
| XVI. Spec-Driven Development | PASS | This plan is itself the artifact this principle mandates; `/speckit.implement` builds the loop harness, and the loop's own `IMPLEMENTATION_PLAN.md` (derived from `tasks.md`) is the record that no work happened outside this SDD chain. |
| XVII. Milestone Documentation via WordPress | DEFERRED, not skipped | Drafting a blog post is a human-facing, judgment-heavy writing task, not a mechanically checkable one — it is explicitly kept **outside** the loop (see loop.md's non-goals) and left as a follow-up for the primary Claude-backed agent once the loop reports done, not something Astra Twin's build loop is asked to do. |

No violations require entries in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/122-astra-live-digital-twin/
├── plan.md              # This file
├── loop.md              # The Loop Contract — frozen, read by /speckit.implement and by ralph.sh
├── research.md           # Phase 0 output
├── data-model.md          # Phase 1 output
├── quickstart.md          # Phase 1 output
├── contracts/             # Phase 1 output — MCP tool contract + WS delta-message contract
└── tasks.md               # Phase 2 output (/speckit.tasks) — generates the loop scaffold, not the twin
```

### Source Code (repository root)

```text
mcp-servers/astra-twin-mcp/        # FROZEN once written — the collector, read-only
├── server.py                       # FastMCP server: get_snapshot, get_deltas, get_status tools
├── collector.py                    # asyncio polling loop against existing pyATS/CML MCP tools
├── README.md                       # tool inventory, env vars, transport, install (constitution XI/XII)
└── requirements.txt

models/
└── twin_schema.py                  # FROZEN — TwinNode/TwinLink/TwinDelta/TwinSnapshot, shared by
                                     #   the collector and the HUD-facing server code

harness/                            # FROZEN — the loop's automated back pressure
├── assert_lab_only.py              # refuses to run if PYATS_TESTBED resolves outside the lab allowlist
├── run_gates.sh                    # build + pytest + npm test + console-error check + visual verify
├── visual_verify.py                # Playwright: screenshot, non-blank check, element-count assertions
└── done_gate.sh                    # every blocking FR/SC in spec.md has evidence in verdicts.md

tests/contract/                     # FROZEN — pytest contract tests against models/twin_schema.py
└── test_twin_schema.py             #   and astra-twin-mcp's tool responses

ui/netclaw-visual/                  # extended, not replaced — specs 101/102's stack
├── server.js                       # +GET /api/twin/snapshot, +WS /ws/twin (proxies astra-twin-mcp)
└── src/twin/                       # new: delta-application layer over the existing scene primitives

bgp/federation/                     # extended, not rebuilt — spec 056's iN2N member model
├── manager.py                      # +model_provider column/handling on `member`
└── risk.py

scripts/
└── in2n-member.py                  # reused as-is to enroll Astra Twin with model_provider=openai

loop/                                # generated by /speckit.implement for THIS spec — see loop.md
├── ralph.sh
├── astra_agent.sh                  # AGENT_CMD wrapper: codex exec, sourcing OPENAI_API_KEY
├── PROMPT.md
├── CHECK.md
├── IMPLEMENTATION_PLAN.md          # derived from tasks.md
└── state/
```

**Structure Decision**: Single-repo extension, not a new project. Four things are frozen the moment
the harness generation phase writes them (`mcp-servers/astra-twin-mcp/`, `models/twin_schema.py`,
`harness/`, `tests/contract/`) — the loop may read them but any diff touching them halts the run.
Everything else under `ui/netclaw-visual/`, `bgp/federation/`, and the constitution's Full-Stack
Artifact Coherence surface (README.md, catalog.sh, install-steps.sh, SOUL.md, SKILL.md, .env.example,
TOOLS.md, config/openclaw.json) is the loop's actual task queue.

## Pass Schedule

*Human checkpoint after each phase, per loop.md. Phases sort the task queue; they are not a second
task list.*

- **Phase A — Collector & schema** (frozen once done): `astra-twin-mcp` server, `models/twin_schema.py`,
  read-only tool wiring against existing pyATS/CML MCP servers, `harness/assert_lab_only.py`.
- **Phase B — Verification harness** (frozen once done): `harness/run_gates.sh`, `harness/visual_verify.py`
  (Playwright), `tests/contract/`, `harness/done_gate.sh`. *Checkpoint: iteration 0 must prove these
  gates actually catch an injected regression before Phase C starts (loop.md's mandatory first
  checkpoint).*
- **Phase C — Live HUD integration**: `/api/twin/snapshot`, `/ws/twin`, the delta-application scene
  layer, freshness indicator (FR-010), delta highlighting (FR-009), camera-state preservation (FR-008).
- **Phase D — Astra Twin enrollment & constitution coherence**: `model_provider` column, iN2N
  enrollment of Astra Twin, and the full Artifact Coherence Checklist (README.md, catalog.sh,
  install-steps.sh, verify-catalog-coverage.py, SOUL.md, `workspace/skills/` docs if any operator-
  facing surface is added, `.env.example`, TOOLS.md, config/openclaw.json, `astra-twin-mcp/README.md`).
  *This phase exists because Principle XI is exactly the kind of boilerplate an unattended loop skips
  under budget pressure — it is not allowed to be an afterthought of Phase C.*

## Complexity Tracking

*No entries — no constitution violations require justification.*
