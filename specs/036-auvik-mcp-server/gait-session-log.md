# GAIT Session Log — Auvik API MCP Server (036)

> **Audit trail maintained per Constitution Principle IV (Immutable Audit Trail).**
>
> The `gait-session-tracking` skill normally records turns live against the
> `gait_mcp` server. This session runs in a Claude Code shell where `gait_mcp`
> is not registered (identical to the 035-claroty-mcp session), so this
> document is the live, append-only audit trail kept in git. Each turn is
> appended, never overwritten; corrections are added as new turns referencing
> the original (Principle IV).

---

## Session metadata

| Field | Value |
|-------|-------|
| Session ID | `auvik-mcp` |
| Branch | `claude/epic-heyrovsky-5c9b55` (base: `main` @ `ad541cb`) |
| Start | 2026-06-20 (CDT) |
| Agent | Claude Opus 4.8 (Claude Code shell) |
| Operator | Ben / John (RedEye Networks) |
| Spec | `specs/036-auvik-mcp-server/` |
| Feature | 036 — Auvik API MCP Server (read-only network monitoring) |
| Status | IN PROGRESS — brainstorming/design |

---

## Turn 0 — Context exploration & constitution review

**Asked**

> Add an MCP to let NetClaw use the Auvik API. Skills/tools around network
> alerts, inventory, lifecycle, and performance. Follow the CONSTITUTION and
> all other documents. Start a GAIT audit. Ask clarifying questions. ULTRATHINK.

**Decided / Collected**

- Invoked `superpowers:brainstorming` (process skill) per session rules.
- Read `.specify/memory/constitution.md` (v1.1.0): SDD workflow mandatory
  (XVI), GAIT audit required (IV), MCP-native FastMCP (V), read-only preferred
  + gated writes, Full-Stack Artifact Coherence checklist (XI, NON-NEGOTIABLE),
  Credential Safety (XIII), Human-in-the-Loop for external comms (XIV).
- Identified gold-standard analog: **035-claroty-mcp** (built recently by same
  operator) — mirrors `azure-network-mcp` layout (`tools/`, `clients/`,
  `models/`, `utils/` with rate limiter + TOON shim + `itsm_gate.py`).
- Confirmed next free feature number = **036** (035-claroty-mcp exists in git
  history; specs/ on main goes to 034).
- GAIT: `gait_mcp` not registered in this shell → using file-based GAIT session
  log pattern (this file), same as the 035 session.
- Parsed attached Auvik OpenAPI (`auvikopenapi.txt`, 638 KB, OpenAPI 3.0.1):
  - 50 GET + 1 POST endpoint across 15 tags.
  - Auth: HTTP Basic (username + API key as password), `ApiKey` scheme.
  - Base URL region-specific (`https://auvikapi.us1.my.auvik.com`, also eu1/au1…).
  - Pagination: JSON:API cursor (`page[first]`, `page[after]`, `page[before]`).
  - Rich `filter[...]` params; MSP multi-tenant via `tenants` param.
  - Only write endpoint: `POST /v1/alert/dismiss/{id}`.

**Artifacts**: none (read-only exploration)

**Commit:** pending (will commit GAIT log + spec together)

---

## Turn 1 — Scope decisions (AskUserQuestion)

**Asked** — three scope questions via AskUserQuestion.

**Decided** (operator selections)

- **API scope** → *4 themes + Billing/Usage*. Cover Alerts, Inventory,
  Lifecycle, Performance, plus client/device Usage (billing). **Exclude** ASM
  (SaaS Management) tag from v1.
- **Alert dismiss** → *Read-only server*. Exclude `POST /v1/alert/dismiss/{id}`.
  No write tools at all → no `itsm_gate.py` needed; aligns with
  "read-only MCP servers are preferred" (Constitution, MCP Server Standards).
- **Skill split** → *4 skills, 1 per theme*: `auvik-network-alerts`,
  `auvik-inventory`, `auvik-lifecycle`, `auvik-performance`. Billing/Usage tools
  surfaced via the inventory skill (billing view of inventory).

**Artifacts**: none

**Commit:** pending

---

## Turn 2 — Design presented, approved, and spec authored

**Asked**

> [design presented] ~20 consolidated read-only tools across 4 theme modules,
> mirroring the azure/claroty layout. Operator reply: "Yes it looks right, proceed."

**Decided**

- Tool granularity: "list multiple" + "get single" merged into one tool per
  resource via optional `id` (≈20 tools total, matching the claroty footprint).
- Billing/Usage tools placed in the `auvik-inventory` skill (billing view of
  inventory) — no 5th skill, honoring the 4-skill decision.
- Configuration-backup history grouped under `auvik-lifecycle`.
- Env vars: `AUVIK_USERNAME`, `AUVIK_API_KEY`, `AUVIK_BASE_URL`
  (default us1), `AUVIK_RATE_LIMIT`, `AUVIK_VERIFY_SSL`. No write/ITSM env
  (read-only server).
- Wrote `specs/036-auvik-mcp-server/spec.md`: 4 prioritized user stories
  (Inventory P1, Alerts P2, Performance P3, Lifecycle P4), 23 functional
  requirements, key entities, 6 success criteria, assumptions.
- Spec self-review passed (no placeholders; FR-009 ↔ SC-002 both assert zero
  writes; billing→inventory and config→lifecycle consistent throughout).

**Created/Modified**

- `specs/036-auvik-mcp-server/spec.md` (new)
- `specs/036-auvik-mcp-server/gait-session-log.md` (this file, updated)

**Commit:** `docs(036): add Auvik MCP spec + GAIT session log`

---

<!-- Subsequent turns (plan/research, implementation, coherence,
     verification) appended below as the session progresses. -->
