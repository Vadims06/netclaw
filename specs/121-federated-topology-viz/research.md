# Phase 0 Research: Federated AI-Augmented Network Topology Visualization

**Feature**: 121-federated-topology-viz | **Date**: 2026-08-30

All findings below come from reading the live `bgp/federation/*` source, querying the live
`~/.openclaw/n2n/federation.db`, and checking the live systemd member service — not from the prior
spec 120 session's assumptions. Two things assumed true when spec 121 was written turned out to be
stale; both are called out explicitly (R1, R2).

## R1: `johns-risk/viz` is already live, not offline

**Finding**: Spec 121's Assumptions/User Story 3 describe `johns-risk/viz` as "provisioned but not
currently connected." That was true when spec 120 was written. It is no longer true now:

```
$ systemctl --user status netclaw-member-johns-risk-viz.service
Active: active (running) since Sun 2026-08-30 11:27:08 EDT
...dialed Border 127.0.0.1:11790 as johns-risk/viz ({'risk': 'johns-risk', 'trusted': True,
'member_state': 'active'})
```

`federation.db`'s `member` row for `johns-risk/viz` shows `state=active`, `scope` includes
`drawio-diagram`, `threejs-network-viz`, `uml-diagram`, `aws-architecture-diagram`,
`canvas-network-viz`, `markmap-viz`, `blender-3d-viz`, `ue5-network-viz` (all as bare-string skill
entries, no `tool` entries yet — see R3).

**Decision**: User Story 3 / FR-007's "bring online" work is scoped down to *verify and keep live*,
not *provision from scratch*. Implementation MUST NOT assume this persists — a later systemd
restart, host reboot, or manual stop could take it back down before implementation runs — so tasks
still include a live `n2n_member_health("johns-risk/viz")` check as the actual acceptance gate for
FR-007/SC-004, not a status read from this document. If it is down at implementation time, bringing
it back up is `systemctl --user start netclaw-member-johns-risk-viz.service` (already `enabled`),
not a new-member provisioning flow.

**Rationale**: SC-004 says "confirmed live and reachable, verified independently of any specific
image-generation request" — the verification step is required regardless of whether it happens to
already be up.

## R2: `comfyui-mcp` is registered on Border, not on any member

**Finding**: `~/.openclaw/openclaw.json`'s `mcpServers.comfyui-mcp` entry (added by spec 120) is
Border's own local MCP config. `johns-risk/viz` (and every member) is a lightweight process launched
by `scripts/in2n-member.py` — it shares the **same `$HOME`** as Border in this single-host "3 rings"
deployment (see project memory: members currently run uncontainerized, same machine, same repo
checkout), so it can reach `http://127.0.0.1:8000` (ComfyUI on the Windows host, already verified
reachable from WSL2 in spec 120) exactly as Border can.

**Decision**: No member relocation is needed for Stage B to reach ComfyUI. See R5.

## R3: `n2n/tools/call` requires a real MCP tool — drawio-diagram, as it exists, is not one

This is the load-bearing finding for FR-001/FR-005/FR-006.

`invocation.py`'s `_exec_tool_stdio(tool, arguments)` (used by both the inbound `handle_tools_call`
and, symmetrically, by whichever process receives the call) requires `tool` in the form
`"server_id/tool_name"`, looks up `server_id` in that process's own `openclaw.json` →
`mcpServers`, spawns it via stdio, and does `initialize` → `tools/call`. This is a deterministic,
schema'd function call — there is no LLM in this path (that's the whole point of `tools/call` vs.
`tasks/submit`, and exactly why the spec's Clarification chose it).

`workspace/skills/drawio-diagram/SKILL.md` exposes two modes, neither of which fits:

- **Mode 1 (native file)**: the *calling agent* writes mxGraphModel XML itself with the Write tool,
  then shells out to the draw.io desktop CLI to export. This requires agentic reasoning to produce
  the XML — it is not a callable MCP tool with a JSON schema at all.
- **Mode 2 (browser mode, `@drawio/mcp`)**: **is** a real MCP server (`open_drawio_xml`,
  `open_drawio_mermaid`, `open_drawio_csv`), but it opens the diagram in a browser editor and
  returns a URL — never image bytes. Wrong output shape for a pipeline stage that must hand a
  rendered image to Stage B.

**Decision**: Build one new, small, deterministic MCP server —
`mcp-servers/topology-diagram-mcp/` (Python, FastMCP, matching repo convention) — exposing exactly
one tool, `render_structural`, that takes a Topology Snapshot (spec 120/046's existing shape) and
returns rendered image bytes (base64) plus the per-device canvas position map.

**R3a — corrected during implementation (2026-08-30)**: The original decision below this line named
N2G (`pip install n2g`) → draw.io XML → the draw.io desktop CLI for PNG export. That does not work on
this host: `drawio` is not on PATH, not installable via `apt-cache policy drawio` (no candidate), not
present via snap or flatpak, and nothing under `/` matches `*drawio*` outside this repo's own working
copy. N2G's `drawio_diagram` class was installed and inspected directly
(`N2G.drawio_diagram`, methods: `add_node`/`add_link`/`layout`/`dump_xml`/`dump_file` only) — it has
**no rasterization method of its own**; every draw.io export path assumes the Electron desktop app or
a browser, neither available headlessly here without a new, heavier dependency (a `docker pull` of a
drawio-export image, or an xvfb-wrapped Electron CLI) that needs root/interactive setup this session
cannot perform (`sudo apt-get install graphviz` itself failed non-interactively: "sudo: interactive
authentication is required").

**Revised decision**: Render with the same dependency-free stack spec 120's `topology_renderer.py`
already uses successfully in this exact environment — **networkx** (layout) + **Pillow** (drawing),
both already installed, zero new system binaries. The only real change from spec 120's renderer is
that this one draws a small, fixed set of **procedurally-generated per-role icon shapes** (a filled
circle for `router`, a rounded rectangle with tick marks for `switch`, a diamond for
`load_balancer`, a rectangle with a brick hatch for `firewall`, a simple monitor glyph for `client`,
a plain labeled rounded rectangle for `unclassified`) drawn once with Pillow primitives — not
generic unlabeled boxes — satisfying FR-002's "role-appropriate iconography... diagramming-tool-
quality bar, not photorealism" (spec.md Assumptions) without sourcing any external icon set or
introducing a licensing question. Real hostname labels are burned in directly as legible text (no
Canny detection is involved anywhere in this feature, so spec 120's label-legibility workaround does
not apply here — text can be drawn directly and stays legible into Stage B).

**Alternatives considered**:
- `graphviz`/`dot` + custom node images — a real, headless-friendly, lightweight option (the `python
  graphviz` binding is already installed); rejected only because the `graphviz` **system package**
  providing the `dot` binary needs `sudo apt-get install graphviz` and this session has no
  interactive sudo. Recorded here because it is the better long-term choice if/when the package is
  installed — a future revision could swap the Pillow drawing step for `dot` without changing the
  tool's contract (same request/result shapes), and this is worth revisiting rather than being
  considered closed.
- Force draw.io Mode 2 (`@drawio/mcp`) to work by screenshotting its browser-editor URL headlessly —
  rejected: adds a heavy, flaky browser-automation dependency to replace something a proven
  in-repo renderer already does cleanly.
- Hand-rolling mxGraphModel XML directly (still via N2G or otherwise) — moot once rasterization
  itself has no headless path on this host; there is no XML format worth producing if nothing here
  can turn it into pixels.

## R4: No existing skill in this repo issues an outbound `n2n/tools/call` from Python

**Finding**: grepping the whole repo for `n2n/tools/call` / `invoke_remote_tool` from `workspace/skills/`
or `scripts/` returns nothing — every prior federation feature (052-072) either drives federation
through the CLI/HUD or is the daemon's own internal code. This feature is the first Border-side
*skill* to actually call out over `n2n/tools/call`.

**Decision**: Call it the same way `comfyui_client.py` already calls the `comfyui-mcp` server — spawn
`n2n-mcp` (already an installed MCP server, `mcp-servers/n2n-mcp/server.py`) via stdio, using the
identical MCP client pattern already proven in spec 120's `comfyui_client.py`
(`stdio_client`/`ClientSession`/`_call_tool_async`) — no new client code shape, just a new target
server. The exact tool is `n2n_invoke(peer, target_type="tool", target_name="<server>/<tool>",
arguments=<json string>)` (`mcp-servers/n2n-mcp/server.py:298`), which POSTs to the daemon's
`/n2n/invoke` HTTP API → `Invoker.invoke_remote_tool` → outbound `n2n/tools/call`. Reachability
checks (FR-009/FR-011 routing, SC-004) use the sibling tool `n2n_member_health(member_id)`
(`server.py:646`), which reads `/n2n/members/health` — the same status surface the HUD/CLI already
use, so this feature adds no new reachability mechanism, just a new caller of an existing one.

## R4a: federated_generation.py calls the daemon HTTP API directly, not n2n-mcp over stdio (correction)

**Finding**: R4's decision to spawn `n2n-mcp` via stdio and call its `n2n_invoke` tool hit a real,
reproducible client-side bug live-tested during implementation: the `mcp` Python SDK's
`ClientSession.call_tool()` silently re-parses a string argument that looks like JSON back into a
dict before sending it over the wire — confirmed by printing the exact dict handed to `call_tool()`
(showing `arguments` as a proper JSON *string*) immediately before the call, then observing the
*server* receive it as a dict, failing `n2n_invoke`'s own pydantic validation
(`arguments: Optional[str]`) with `"Input should be a valid string ... input_type=dict"`. Calling
the daemon's `/n2n/invoke` and `/n2n/members/health` HTTP endpoints directly via `curl` (bypassing
the MCP-stdio hop entirely) worked correctly and repeatably on the first and every subsequent try.

**Revised decision**: `federated_generation.py` calls the daemon's HTTP API directly with `httpx`
(`http://127.0.0.1:8179`, matching `n2n-mcp`'s own `BGP_DAEMON_API` default and its exact
`_get`/`_post` timeout pattern — 610s client timeout on POST, wider than the 600s tool timeout
R7 configures, so the client never gives up before the daemon returns) — `/n2n/invoke` for both
stages, `/n2n/members/health` for the reachability check. This is still literally the same
`n2n/tools/call` wire method FR-006 requires; `n2n-mcp` is only a thin MCP-tool wrapper around this
exact HTTP API for LLM-agent callers, and this feature's caller is a deterministic Python skill
module, not an LLM agent turn, so there is no reason to route through the MCP-stdio hop (and its
now-confirmed argument-coercion bug) at all.

## R5: Stage B (styling) runs on the same member as Stage A — FR-008 resolved

**Decision**: `johns-risk/viz` hosts *both* stages. A second new small server,
`mcp-servers/image-style-mcp/` (Python, FastMCP), exposes one tool, `style_image(image_base64,
style_prompt) -> {styled_image_base64}`. It talks to ComfyUI **directly via REST** (`/prompt`,
`/history/{id}`, `/view`, `/upload/image`) — porting the already-proven direct-REST approach from
spec 120's `comfyui_client.py`, not routing through the `comfyui-mcp` Node server's own task
tracker, which spec 120 already found to be permanently broken (research.md §"task tracker stuck
bug"). Re-introducing a known-broken dependency into new code would be a regression, not reuse.

**Rationale**: `johns-risk/viz` is already live (R1), already reachable to ComfyUI at
`127.0.0.1:8000` (R2), and adding a second tool to an already-connected member is strictly simpler
than provisioning, enrolling, and pinning a brand-new dedicated member for a single capability.
FR-008 explicitly allows either; nothing about GPU/process isolation is required by the spec.

**Alternative considered**: A dedicated `johns-risk/comfyui` member. Rejected for v1 — no isolation
requirement exists today; if resource contention between diagram rendering and GPU diffusion becomes
a real problem later, splitting the member is a small, independent follow-up.

## R6: Image handoff mechanism and size bound — Clarification Q3 resolved

**Finding**: The internal channel already chunks and reassembles arbitrary-size JSON-RPC payloads in
production (`bgp/constants.py`): `NCFED_MAX_PAYLOAD = 65536` (64 KB per wire frame, transparently
chunked), `NCFED_MAX_MESSAGE = 16 * 1024 * 1024` (16 MB aggregate reassembled-message cap). This is
the same mechanism spec 065's Chroma-to-Chroma replication already relies on in production.

**Decision**: Pass images as base64 strings directly inside the `arguments`/result payload of the
`n2n/tools/call` JSON-RPC calls — no new transport, no file-path handoff, no separate upload step.
A base64'd PNG at spec 120's proven working resolution (1024×1024, typically 1-3 MB raw) sits
comfortably under the 16 MB cap. If a future topology's rendered image would exceed it, the correct
behavior (per the spec's Edge Cases bullet on oversized topologies) is to fail with a clear message
from `render_structural`, not to silently truncate — implemented as a size check before the base64
result is returned.

## R7: Federation tool-call timeout must be raised for both sides

**Finding**: `Invoker.__init__` reads `N2N_TOOL_TIMEOUT_S` (default `120`) from the *process's own*
environment. This value governs two separate waits: the receiving side's
`asyncio.wait_for(run(), timeout=self.tool_timeout)` inside `_exec_tool_stdio`, and the calling
side's `_outbound_call(..., timeout=self.tool_timeout + 5)`. Spec 120's real end-to-end generation
took ~42s for a small topology; Stage B's edit-model pass is comparable-to-longer, and large
topologies will be slower still. The spec's own Assumptions state this feature "does not introduce
a fixed timeout at either stage," consistent with spec 120's decision — but the *federation layer*
would silently impose one anyway at the default.

**Decision**: Raise `N2N_TOOL_TIMEOUT_S` in **both** Border's own environment and
`migration-staging/members/viz/.env` to `600` (matching the existing `N2N_SKILL_TIMEOUT_S` default
already used elsewhere for long-running delegated work) — a config change, not a code change, and
each side's env is independent so this doesn't affect other members' unrelated tool calls.

## R8: Routing/fallback lives in a new orchestrator module, not by editing spec 120's files

**Finding**: FR-012 forbids modifying spec 120's shipped fallback pipeline; FR-004/FR-004a require
the *same* skill entry point to report which path (federated vs. fallback) produced a given result.
These two requirements together mean the "which path, and was it federated" decision must wrap
spec 120's existing `generation.run_generation()` from the outside, not be spliced into it.

**Decision**: Add a new module, `workspace/skills/comfyui-topology-viz/federated_generation.py`,
that:
1. Checks `snapshot.source_kind != SourceKind.FREEFORM` (FR-011).
2. If non-freeform, checks `n2n_member_health("johns-risk/viz")` for both the diagram and styling
   capabilities (same member, R5) (FR-009/FR-010).
3. On both checks passing, calls `render_structural` then `style_image` via `n2n_invoke` (R4), and
   returns the styled image plus `generation_path="federated"`.
4. On any failure/unreachability, or a freeform request, calls spec 120's existing
   `generation.run_generation(snapshot)` **unchanged** and returns its result plus
   `generation_path="fallback"` and the specific reason (which stage/check failed).
5. On Stage A success + Stage B failure specifically, returns the correct unstyled Stage A diagram
   (FR-010/Edge Cases) rather than falling all the way back to spec 120's pipeline — this is a third
   outcome, not just "federated" or "fallback."

`__init__.py`'s `visualize_topology_via_comfyui()` entry point calls this new module instead of
calling `generation.run_generation()` directly — the one necessary edit to existing spec 120 code,
and it is a call-site change, not a modification of `generation.py`'s own logic (FR-012 intact).

## R9: FR-015 research spike — methodology (to run before Stage B implementation, not before planning)

**Decision**: Use 2-3 of spec 120's own already-generated, already-labeled real output images
(`workspace/output/comfyui-topology-viz/`) as the *source image* input to a Qwen-Image-Edit-2509
(GGUF-quantized) image-edit workflow — the ComfyUI instance already has the required nodes live
(`TextEncodeQwenImageEdit`, `ReferenceLatent`, `UnetLoaderGGUF`/`CLIPLoaderGGUF`, confirmed in spec
120's research). Score the result against the spec's fixed bar: 100% of visible device labels
reproduced character-for-character, every connection line traceable without gaps — via direct visual
inspection, the same rigor that caught spec 120's garbled-text regression. If it fails, run the same
protocol against FLUX.2 [klein] 4B (Apache-2.0) before finalizing. Per FR-016, verify the real
download size and license terms directly at the HuggingFace source immediately before pulling either
model — do not reuse spec 120's earlier size estimates for a *different* model file.

This spike is implementation work (a `/speckit.tasks`-generated task), not a planning-phase
deliverable — it produces its own dated finding note under this feature's directory once it runs,
gating Stage B's implementation tasks specifically (SC-005).

## R10: n2n/tools/call had no working path from Border to an internal member at all (found + fixed during implementation)

**Finding**: R4's decision assumed calling `n2n_invoke(peer="johns-risk/viz", target_type="tool", ...)` would work because the wire method (`n2n/tools/call`) and the sending-side plumbing (`Invoker.invoke_remote_tool`, `n2n-mcp`'s `n2n_invoke` tool) both existed. Live testing against the real, running `johns-risk/viz` member found **four separate, previously-unexercised gaps** — every one of `tools/call`'s prior uses in this codebase was eN2N (external peer) only; nothing had ever called it Border→internal-member before this feature:

1. `InternalChannel`'s member-side dispatch table (`_in2n_member_handlers` in `service.py`) had no entry for `n2n/tools/call` at all — only `n2n/tasks/submit` (agentic delegation). An inbound call hit `ERR_METHOD_NOT_FOUND` before any auth check ran.
2. `InternalChannel.attestation` was never elevated from `FederationChannel`'s default `"self-asserted"` to `"possession"`, even after a full iN2N pinned-key/signed-nonce handshake succeeded — so `negotiate.allows()`'s tier-0 gate denied `tools/call` unconditionally on every internal channel regardless of trust state.
3. `Invoker._channel()` (used to establish/reuse a channel for an *outbound* call) only ever checked `service.channels` (the eN2N dict) via `ensure_channel()`, which requires an eN2N `federation_peer` row and fails with `"peer_unreachable: not federated"` for any identity it doesn't recognize as a BGP peer — including a live, connected internal member, which lives in `service.member_channels` and is brought up via the already-existing `ensure_member_up()` instead.
4. `Authorizer.authorize()`'s `is_federated()` pre-check has no concept of an iN2N member's *self-referential* `peer_identity` (a member's one channel to Border is recorded with `peer_identity == that member's own member_id`, confirmed by `_in2n_member_submit`'s own comment) — there is no `federation_peer` row for "myself," so this always returned `Decision(False, "severed", "peer not federated")` even for an already fully-authenticated internal channel.

**Fix** (all four, additive/backward-compatible — no existing eN2N behavior changed):
1. `service.py`: added `"n2n/tools/call": self.invoker.handle_tools_call` to `_in2n_member_handlers`.
2. `service.py`'s `dial_border()`: set `ch.attestation = "possession"` right after the iN2N handshake (enroll/hello signature + optional hub-attestation verification) succeeds — the same semantic eN2N's TLS-cert-binding path already establishes for its own channels, just via iN2N's own proof mechanism.
3. `invocation.py`'s `Invoker._channel()`: branch on `self.service.is_member_task(ident)` (an existing helper) to call `ensure_member_up()` instead of `ensure_channel()` for an internal-member identity.
4. `authorization.py`'s `authorize()`: added an `already_trusted: bool = False` keyword; when `True`, skips only the `is_federated()` sub-check (grant/rate/budget checks still run unconditionally). `invocation.py`'s `handle_tools_call` sets it via `isinstance(channel, InternalChannel)` — the one call site this feature actually exercises; `handle_task_submit`/`handle_knowledge_query`/`_replicate_gate` are unaffected (confirmed they're eN2N-only in current usage — iN2N's own task delegation goes through the separate, `member_scope`-gated `_in2n_member_submit`, never through `Invoker.handle_task_submit`).

Also seeded the two required `invocation_grant` rows directly in `johns-risk/viz`'s own local federation.db (`migration-staging/members/viz/n2n/federation.db`), `peer_identity='johns-risk/viz'` (matching the self-referential identity pattern above), one per new tool.

**Live-verified** (2026-08-30, after restarting `netclaw-mesh.service` and `netclaw-member-johns-risk-viz.service` to pick up the code changes): `curl -X POST http://127.0.0.1:8179/n2n/invoke` with `peer=johns-risk/viz, target_type=tool, target_name=topology-diagram-mcp/render_structural` returned a real, correct, base64-encoded PNG — the member actually spawned `topology-diagram-mcp/server.py` via `_exec_tool_stdio` and returned its result over the live iN2N channel. This is the first working end-to-end internal `n2n/tools/call` in this codebase.

**Why fix the shared mechanism instead of switching to `tasks/submit`**: the spec's Clarification session explicitly chose deterministic tool execution over agentic skill delegation *because* neither stage needs judgment at the member side (Assumptions). Switching to `tasks/submit` would mean the member's own LLM invokes the rendering/styling tools itself — reintroducing exactly the kind of non-determinism the spec deliberately avoided. All four gaps found here are narrow, additive completions of infrastructure the spec's own clarification already assumed existed, not new capability — confirmed with the user before making any of these changes to shared code (2026-08-30).

## Technology Decisions Summary

| Area | Decision |
|---|---|
| Language | Python 3.10+ for both new MCP servers and the new skill module, matching repo convention |
| Structural diagram generation | networkx + Pillow (both already spec 120 dependencies) with procedural per-role icon shapes — no new system binary (R3a correction) |
| New MCP server (Stage A) | `mcp-servers/topology-diagram-mcp/` — one tool, `render_structural` |
| New MCP server (Stage B) | `mcp-servers/image-style-mcp/` — one tool, `style_image`, direct ComfyUI REST (no comfyui-mcp Node hop) |
| Styling model (pending R9 spike) | Qwen-Image-Edit-2509 GGUF-quantized (primary candidate), FLUX.2 [klein] 4B (documented fallback) |
| Federation call mechanism | `n2n-mcp`'s `n2n_invoke`/`n2n_member_health` tools, stdio MCP client (same pattern as `comfyui_client.py`) |
| Both stages' host member | `johns-risk/viz` (already live, R1) |
| Image transport | base64 inline in `n2n/tools/call` JSON-RPC payload, existing 16 MB channel cap, no new transport |
| Timeout | `N2N_TOOL_TIMEOUT_S=600` in Border's env and `migration-staging/members/viz/.env` |
| Routing/fallback | New `federated_generation.py` wraps unmodified spec 120 `generation.run_generation()` |
