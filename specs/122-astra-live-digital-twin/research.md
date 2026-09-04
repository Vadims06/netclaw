# Phase 0 Research: Astra Live Digital Twin

## R1 — Astra Twin's agent runtime for the build loop

**Decision**: `AGENT_CMD` in `loop/ralph.sh` wraps OpenAI's own Codex CLI: `codex exec --full-auto
--sandbox workspace-write -m "$ASTRA_MODEL" [PROMPT is piped via stdin]`. Confirmed installed on this
host: `@openai/codex@0.114.0` at `~/.nvm/versions/node/v25.1.0/bin/codex`. Confirmed via `codex exec
--help` that `codex exec` reads its initial instructions from stdin when no `[PROMPT]` argument is
given — this is a drop-in replacement for the `claude -p < PROMPT.md` shape the driver already uses;
no change to `ralph.sh`'s piping is needed, only to `AGENT_CMD` itself. `--full-auto` is Codex's own
alias for `-a on-request --sandbox workspace-write` — low-friction unattended execution with the
sandbox still on, which layers a second, independent enforcement of "no writes outside the worktree"
underneath the loop's own frozen-path check. `ASTRA_MODEL` is left as an operator-settable env var
(default: whatever `codex exec` resolves without `-m`, i.e. the account's configured default) rather
than a hardcoded model ID, since pinning an exact OpenAI model string here would go stale independent
of anything in this repo.

**Rationale**: The loop's maker and checker must actually edit files and run shell commands, not just
return chat text — a raw Chat Completions call has no tool-use loop of its own. Building a bespoke
agentic wrapper around the OpenAI API would reimplement what Codex CLI already is, and would need its
own security review for shell/file access. Reusing Codex CLI keeps the loop's shape (`AGENT_CMD <
PROMPT.md > log`) unchanged from the Claude-based original, and its sandbox is a second safety layer.

**Alternatives considered**: A custom Python wrapper using OpenAI's function-calling for read/write/
bash — rejected as unnecessary reimplementation and additional attack surface for no benefit, since
Codex CLI is already installed and already does this. Using `claude -p` for Astra Twin's own loop
(i.e., not actually OpenAI-backed) — rejected outright: the spec's FR-006/FR-007 require Astra Twin's
identity to be genuinely, verifiably a different AI provider, not merely labeled as one.

## R2 — Automated visual verification for an unattended loop

**Decision**: Add Playwright (new dependency, `harness/` only) to drive a headless browser against the
running HUD, take a screenshot, assert it isn't blank, assert expected node/link element counts, and
capture console errors — `harness/visual_verify.py`.

**Rationale**: Specs 101 and 102 both relied on a human manually taking and comparing screenshots
("committed baseline screenshots are the substitute... weaker than a live comparison," per spec 102's
own plan.md). That is exactly the "unattended verification" failure mode loop.md warns about — there
is no human in the loop to take the screenshot. An automated headless-browser check is the only way
the gate step can independently confirm the scene actually rendered, not merely that the server
process didn't crash.

**Alternatives considered**: Puppeteer — functionally similar; Playwright chosen for built-in
auto-waiting and a more ergonomic Python binding, matching the harness being Python (frozen alongside
`assert_lab_only.py` and the pytest contract tests). Skipping visual verification and trusting
`npm test` alone — rejected: unit tests on the delta-application logic cannot catch a scene that
renders nothing, which is the actual failure mode FR-002/FR-009 exist to prevent.

## R3 — Delta transport from collector to browser

**Decision**: Reuse the `ws` npm package already present in `ui/netclaw-visual/package.json` — no new
frontend dependency. `server.js` gains a WebSocket endpoint `/ws/twin` that subscribes to
`astra-twin-mcp`'s `get_deltas` tool on an interval and forwards new deltas to connected browser
clients; `/api/twin/snapshot` (plain REST) serves the full current state for first load or reconnect.

**Rationale**: Spec 116 already established the precedent of adding a persistent WS connection
(Border-side) for exactly this "don't wait on the next full poll" latency reason; the browser side of
that pattern (`ws`) is already a dependency here, so no new package is needed at all on the HUD side.

**Alternatives considered**: Server-Sent Events — simpler, but the HUD already has a WS dependency and
prior art (spec 116) in this exact shape; introducing a second streaming transport for one feature
would be inconsistent for no benefit. Polling `/api/twin/snapshot` from the browser on a timer —
rejected: cannot meet SC-001's "within 30 seconds, no manual reload" goal without either a very tight
poll interval (wasteful) or an unacceptably loose one (fails the success criterion).

## R4 — Collector talks to devices only through existing MCP servers

**Decision**: `astra-twin-mcp`'s `collector.py` never opens a device connection itself. It calls the
existing pyATS MCP server's (and, where relevant, CML/GNS3 MCP servers') already-registered read-only
tools on a fixed poll interval, and computes deltas by diffing the parsed result against its last
in-memory snapshot.

**Rationale**: Constitution Principle VI (Multi-Vendor Neutrality) already assigns vendor-specific
device logic to vendor-specific MCP servers; re-implementing device polling inside `astra-twin-mcp`
would duplicate that logic and create a second place vendor bugs could live. It also makes the
read-only guarantee (FR-003, FR-005) structural rather than promised: `astra-twin-mcp` simply has no
code path that can issue a write, because it never holds a device credential or session at all — only
MCP tool-call results.

**Alternatives considered**: Direct pyATS testbed access inside the collector — rejected: this is
exactly the kind of "config-write capability held even though unused" pattern loop.md's safety
envelope explicitly forbids (FR-005's "not merely unused, but absent").

## R5 — iN2N member model gains a provider attribute

**Decision**: Add one nullable column, `model_provider`, to the existing `member` table in
`~/.openclaw/n2n/federation.db` (extending the schema spec 056/066 already established, the same way
spec 066 added `node_type` to that same table). Default `NULL`/`"claude"` for every existing member;
Astra Twin is enrolled with `model_provider="openai"` via the existing `scripts/in2n-member.py`
enrollment flow, unmodified except for accepting this new field.

**Rationale**: FR-006/FR-007 require Astra Twin's distinct identity and AI-provider attribution to be
visible in actual mesh membership records, not just in documentation prose. Reusing the existing
member/enrollment machinery (rather than inventing a parallel "AI-provider registry") keeps one source
of truth for "who is a mesh participant," consistent with how every other member-model extension in
this repo (066, 067, 068) has been additive, not a fork.

**Alternatives considered**: A separate JSON file or config entry documenting Astra Twin's provider —
rejected: this is exactly the "buried in a script" outcome the spec's User Story 3 explicitly rejects.
