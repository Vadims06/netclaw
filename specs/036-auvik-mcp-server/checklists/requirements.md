# Requirements & Coherence Checklist: Auvik MCP (036)

## A. Full-Stack Artifact Coherence (Constitution Principle XI)

Every box MUST be checked before merge. File locations/formats confirmed against the live repo.

- [ ] **mcp-servers/auvik-mcp/** created — server, `clients/`, `models/`, `tools/`, `utils/`, `requirements.txt`.
- [ ] **mcp-servers/auvik-mcp/README.md** — tool inventory (20), env vars, transport (stdio), install.
- [ ] **config/openclaw.json** — `"auvik-mcp"` registered inside `mcpServers` (command `python3` + `-u` + `mcp-servers/auvik-mcp/auvik_mcp_server.py`; `env` block `${AUVIK_USERNAME}`, `${AUVIK_API_KEY}`, `${AUVIK_BASE_URL:-https://auvikapi.us1.my.auvik.com}`, `${AUVIK_VERIFY_SSL:-true}`, `${AUVIK_TIMEOUT:-30}`, `${AUVIK_RATE_LIMIT:-600}`, `${AUVIK_MAX_PAGES:-50}`).
- [ ] **.env.example** — `AUVIK_*` block, descriptive comments, **no values** (Principle XIII).
- [ ] **scripts/install.sh** — new numbered step mirroring an existing Python-MCP block (venv + `pip install -r requirements.txt`).
- [ ] **ui/netclaw-visual/server.js** — (1) `INTEGRATION_CATALOG` entry `{ id:'auvik', name:'Auvik', category:'Observability', prefixes:['auvik-'], color:'<hex>', transport:'stdio', toolEstimate:20, description:'…' }`; (2) `ENV_MAP` entry `auvik:{ env:['AUVIK_USERNAME','AUVIK_API_KEY','AUVIK_BASE_URL'], files:[], notes:'…' }`.
- [ ] **README.md** — MCP-servers table row for Auvik; new "Auvik Network Intelligence Skills (4)" section listing the 4 skills; **bump** the MCP-server count + skills count in the section headers and intro line.
- [ ] **SOUL.md** — add `### Auvik … Skills (4)` line (skill names) ; bump skills + MCP-integration counts in the intro.
- [ ] **SOUL-SKILLS.md** — add a `### auvik-<skill>` procedure block for each of the 4 skills.
- [ ] **TOOLS.md** — Connection Details line: `- Auvik → AUVIK_USERNAME, AUVIK_API_KEY, AUVIK_BASE_URL (optional)`.
- [ ] **workspace/skills/auvik-inventory/SKILL.md** created.
- [ ] **workspace/skills/auvik-network-alerts/SKILL.md** created.
- [ ] **workspace/skills/auvik-lifecycle/SKILL.md** created.
- [ ] **workspace/skills/auvik-performance/SKILL.md** created.
- [ ] **CLAUDE.md / AGENTS.md** — append the `036-auvik-mcp-server` entry to "Active Technologies"/"Recent Changes" if that pattern is maintained.
- [ ] **specs/036-auvik-mcp-server/gait-session-log.md** — kept current; final summary commit (Principle IV).
- [ ] **Existing skills verified unbroken** (SC-004) — `python -m json.tool config/openclaw.json` valid; a representative existing server imports cleanly.
- [ ] **WordPress milestone blog drafted** (Principle XVII) — `docs/blog/2026-06-21-auvik-mcp.md`; if WordPress MCP unavailable, note milestone in the GAIT log.

## B. Requirement coverage (spec FR → plan task)

- [ ] FR-001..007 (inventory) → E1–E8 · FR-008/009 (alerts, read-only) → E9 + E20 assertion
- [ ] FR-010/011 (stats) → E13–E17 · FR-012/013 (SNMP poller) → E18/E19
- [ ] FR-014/015/016 (lifecycle) → E10–E12
- [ ] FR-017 (Basic auth) → B1 · FR-018 (base URL) → A2/B1 · FR-020 (rate limit/429) → A4/B2
- [ ] FR-019/019a (pagination) → A5/B3 · FR-021 (TOON) → A3/D1 · FR-022 (verify) → E8 · FR-023 (lifecycle/no-regress) → E20/H2
- [ ] FR-024/025/026 (resolution) → C1/C2 (+ used by E1–E19)

## C. Success-criteria verification (spec SC → step)

- [ ] SC-001 name/IP, ≤3 turns → quickstart smoke 3 (H3)
- [ ] SC-002 zero writes → E20 test + quickstart smoke 8 (grep)
- [ ] SC-003 rate limiting → A4/B2 tests
- [ ] SC-004 no regression → H2
- [ ] SC-005 coherence complete → Section A all checked
- [ ] SC-006 all 4 skills resolve tools + TOON output → H1/H3
- [ ] SC-007 resolution candidates on ambiguity → C1 tests + quickstart smoke 3
- [ ] SC-008 multi-page completeness → B3 test + quickstart smoke 4

## D. Constitution gates (re-checked post-design)
- [ ] Read-only confirmed (no POST/PUT/DELETE/PATCH tool or client method).
- [ ] Credentials only from env; `.env` git-ignored; `.env.example` value-free.
- [ ] FastMCP stdio lifecycle; stderr-only logging.
- [ ] Spec exists (XVI); GAIT logged (IV); milestone blog (XVII).
