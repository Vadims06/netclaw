# Implementation Plan: ComfyUI Network Topology Visualization

**Branch**: `120-comfyui-topology-viz` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)

## Summary

A new NetClaw skill (`workspace/skills/comfyui-topology-viz/`) that takes the same canonical
topology model spec 046's three.js skill already assembles (from any of NetClaw's live
topology-source integrations, or a freeform description) and, instead of a 3D scene, drives the
newly vendored community `comfyui-mcp` server to generate one stylized still image via a
user-managed ComfyUI instance. The image is saved to a persistent, timestamped workspace output
location, mirroring specs 046/082's delivery convention.

This feature is deliberately narrow (v1 = stills only, per Clarification session 2026-08-26) and
treats both the target ComfyUI endpoint's reachability and its installed models as things to
verify, not assume. Both were verified live during this planning session from inside NetClaw's own
WSL2 runtime: the configured instance (a ComfyUI Desktop install on a separate Windows host) is
reachable at `http://127.0.0.1:8000` with zero cross-host networking workaround needed, and it
currently has **zero installed image-generation checkpoints** — meaning FR-008's "no usable model"
path is this feature's actual first-use outcome today, not a hypothetical edge case.

## Technical Context

**Language/Version**: Python 3.10+ (skill logic, matching every other NetClaw skill); Node.js 18+
(the vendored `comfyui-mcp` community server, cloned and built at install time — not committed to
git, git-ignored under the existing `mcp-servers/*` pattern)

**Primary Dependencies**: The community `shawnrushefsky/comfyui-mcp` server (Node/TypeScript, MIT
license) cloned into `mcp-servers/comfyui-mcp/` at install time via the installer's existing
`clone_or_pull` helper — the exact same mechanism spec 046 used for `sketchfab-mcp-server`, **not**
a git-committed vendor tree (see research.md §1, which corrects the spec's initial assumption of a
`.gitignore` negation entry); registered as `comfyui-mcp` in `config/openclaw.json`. Ported (not
imported) copies of spec 046's `topology_model.py` and `sources.py` — this repo's skills are not
structured as an importable shared package (established precedent: 046 research.md §4), so the
canonical `TopologySnapshot`/`Device`/`Interface`/`Link`/`SourceKind` types and per-source adapters
are copied into this skill's own directory, trimmed of the 3D-specific `AssetKind`/`ProceduralShape`
concepts this feature does not need.

**Storage**: N/A — stateless skill; each completed generation is written as an image file plus a
small sidecar JSON (prompt used, model used, source snapshot summary) for traceability, matching
spec 082's provenance-stamping discipline at a much lighter weight. Output lands in
`workspace/output/comfyui-topology-viz/` (git-ignored, matching 046/082's convention).

**Testing**: pytest — unit tests for prompt composition from a `TopologySnapshot`, deterministic
model selection when multiple checkpoints are usable (FR-006a), the single-in-flight-job guard
(FR-009a), and the three distinct failure classifications (FR-007/FR-008/FR-009), with `comfyui-mcp`
tool calls mocked. One live integration test against whatever ComfyUI instance is actually
configured — today that test correctly exercises and asserts the real, verified "no usable model
found" path (FR-008), not a fabricated success, following the "never mock the dependency whose
failure would matter most" rule already established in 044/045/046.

**Target Platform**: NetClaw's own runtime (WSL2/Linux) driving a ComfyUI backend reachable over
HTTP at a user-configured endpoint. Confirmed live during Phase 0 research: the currently configured
instance is a ComfyUI Desktop install on a separate Windows host, reachable at `127.0.0.1:8000` from
this WSL2 session with no NAT/port-forward workaround required (see research.md §2).

**Project Type**: Single new skill + one newly vendored community MCP server (`comfyui-mcp`); no new
NetClaw-authored MCP server — the same shape as spec 046 (skill + `sketchfab-mcp-server`).

**Performance Goals**: Not latency-bound by NetClaw's own code. Per Clarification session
2026-08-26, real GPU image-generation time is explicitly **not** subject to a NetClaw-imposed
timeout — a submitted job is tracked to completion or failure using ComfyUI's own status signals
(FR-009), since generation time varies with model, workflow, and hardware.

**Constraints**: At most one generation job in flight at a time (FR-009a — reject, don't queue);
generation inputs (prompts) MUST NOT include credentials, secrets, or full running-config content
(FR-015); this feature MUST NOT modify `comfyui-mcp`, any topology-source MCP, or any existing
visualization skill (three.js/Blender/UE5) (FR-014).

**Scale/Scope**: One generated still image per request; video/animation generation and stylized
test-result cards are explicitly out of scope for this spec (FR-016).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Safety-First Operations | PASS | Purely read-only visualization; no device configuration is ever changed |
| II. Read-Before-Write | N/A | No device writes occur anywhere in this feature |
| III. ITSM-Gated Changes | N/A | No production device changes; visualization only |
| IV. Immutable Audit Trail | PASS | Reuses existing GAIT logging for skill invocations; no new audit mechanism needed |
| V. MCP-Native Integration | PASS | All new capability is delivered through the newly-registered `comfyui-mcp` MCP server (proper `config/openclaw.json` registration), not a bespoke HTTP client |
| VI. Multi-Vendor Neutrality | PASS | Prompt-composition/generation logic is topology-source-agnostic; each source's retrieval logic stays inside its own existing MCP server, untouched |
| VII. Skill Modularity | PASS | One new skill (`comfyui-topology-viz`) that composes existing topology-source skills and the new `comfyui-mcp` server rather than duplicating retrieval or generation logic |
| VIII. Verify After Every Change | N/A | No device changes to verify; acceptance is via spec.md's scenarios |
| IX. Security by Default | PASS (flagged) | `COMFYUI_URL` points at a user-managed local/LAN endpoint, not a credential; `comfyui-mcp` requires no API key of its own (research.md §3). Flagged: `comfyui-mcp`'s own `npm audit` has not yet been checked — tracked for the Polish phase, matching how spec 046 tracked the same open item for `sketchfab-mcp-server` |
| X. Observability | **REQUIRED** | Every failure/fallback condition (unreachable ComfyUI, no usable model, job failure, concurrent-request rejection, unreachable topology source, empty topology) MUST be explicitly and distinguishably reported (FR-007/008/009/009a/012/013) rather than silent; `ui/netclaw-visual/` MUST gain a status node for the new `comfyui-mcp` integration |
| XI. Full-Stack Artifact Coherence | **REQUIRED** | `README.md`, `SOUL.md`, `TOOLS.md`, `scripts/lib/catalog.sh` + `scripts/lib/install-steps.sh` (clone+build step for `comfyui-mcp`), `scripts/verify-catalog-coverage.py`, `ui/netclaw-visual/` HUD node, and `workspace/skills/comfyui-topology-viz/SKILL.md` all need updates — see checklist below |
| XII. Documentation-as-Code | **REQUIRED** | New `SKILL.md` must document purpose, composed topology sources, the generation flow, and the `COMFYUI_URL` environment variable |
| XIII. Credential Safety | PASS | `COMFYUI_URL` is not a secret, but is still documented (name only, no value) in `.env.example` and read from `.env` at runtime, matching repo convention even for non-secret configuration |
| XIV. Human-in-the-Loop | N/A | No external communications (Slack/ServiceNow/GitHub/etc.) triggered by this feature |
| XV. Backwards Compatibility | PASS | New, purely additive skill; existing `threejs-network-viz`, `ue5-network-viz`, and `blender-3d-viz` skills are untouched and remain available |
| XVI. Spec-Driven Development | PASS | Following the full specify → clarify → plan → tasks → implement workflow |
| XVII. Milestone Documentation | **REQUIRED** | WordPress blog post after implementation, per constitution and prior practice (046/082) |

**Gate Status**: PASS — no violations requiring justification. Observability (X), Artifact Coherence
(XI), Documentation (XII), and Milestone Documentation (XVII) requirements are tracked for the
Polish phase, matching how 046 handled the same conditional-pass pattern.

## Project Structure

### Documentation (this feature)

```text
specs/120-comfyui-topology-viz/
├── plan.md               # This file (/speckit.plan command output)
├── research.md           # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md         # Phase 1 output (/speckit.plan command)
├── contracts/
│   └── comfyui-generation-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md               # /speckit.tasks output (not created by this command)
```

### Source Code (repository root)

```text
workspace/skills/comfyui-topology-viz/
├── SKILL.md
├── __init__.py
├── topology_model.py      # Ported from 046: Device/Interface/Link/TopologySnapshot/SourceKind/
│                           # OperationalState + SourceUnreachableError/AmbiguousSourceError,
│                           # trimmed of 3D-only concepts (AssetKind/ProceduralShape/ModelSource)
├── sources.py              # Ported from 046: one adapter per topology source + disambiguation,
│                           # consuming the same generic {"devices": [...], "links": [...]} shape
│                           # the conversational orchestration layer already normalizes to
├── generation_model.py     # NEW: GenerationRequest/ModelAvailabilityCheck/GeneratedImage/
│                           # GenerationFailure — see data-model.md
├── prompt_builder.py       # NEW: TopologySnapshot -> a bounded-length ComfyUI generation prompt
│                           # (device roles/counts/connectivity, summarized for large topologies)
├── comfyui_client.py       # NEW: get_status/list_models discovery, search_templates/get_template
│                           # selection, run_workflow submission (sync:false), get_task_result
│                           # polling to a ComfyUI-reported terminal state
├── generation.py           # NEW: orchestrates prompt_builder + comfyui_client, enforces the
│                           # single-in-flight-job guard (FR-009a), classifies failures into the
│                           # distinct categories FR-007/008/009/012/013 require
└── output.py                # NEW: writes the timestamped image + sidecar JSON to
                              # workspace/output/comfyui-topology-viz/, mirroring 046's output.py

mcp-servers/comfyui-mcp/     # Vendored community server (shawnrushefsky/comfyui-mcp), cloned and
                              # built (npm install && npm run build) at install time — git-ignored,
                              # not committed, matching the sketchfab-mcp-server precedent

workspace/output/comfyui-topology-viz/   # Persistent, timestamped image output (git-ignored)
```

**Structure Decision**: One new skill plus one newly vendored community MCP server, no new
NetClaw-authored MCP server — mirroring spec 046's shape exactly (skill + `sketchfab-mcp-server`).
Topology retrieval itself is reused, not reimplemented: the conversational orchestration layer
(NetClaw itself, mid-conversation) calls the same existing topology-source MCP tools spec 046 already
uses and normalizes their output the same way before invoking this skill — this skill's `sources.py`
adapts that same normalized shape into `TopologySnapshot` objects, exactly as 046's does today.

## Complexity Tracking

*No Constitution Check violations require justification — this section is intentionally empty.*
