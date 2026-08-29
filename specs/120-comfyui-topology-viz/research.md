# Phase 0 Research: ComfyUI Network Topology Visualization

## 1. Correcting the vendoring pattern assumption

**Decision**: `comfyui-mcp` is cloned and built **at install time** by a new
`component_install_comfyui_viz()` function in `scripts/lib/install-steps.sh`, using the installer's
existing `clone_or_pull` helper — the same mechanism that already vendors `sketchfab-mcp-server`. It
is **not** committed to the NetClaw git repository and needs **no** `.gitignore` negation entry.

**Rationale**: The spec's Assumptions section (written before this research) described following
"the exact vendoring pattern spec 046 established for `sketchfab-mcp-server`" and specifically named
a `.gitignore` negation entry as part of that pattern. Direct inspection during this planning session
showed that description was wrong: `git ls-files mcp-servers/sketchfab-mcp-server` returns nothing
(untracked), `git check-ignore -v` confirms it matches the blanket `mcp-servers/*` ignore rule with
**no** negation line for it anywhere in `.gitignore`, and `scripts/lib/install-steps.sh`'s
`component_install_threejs_viz()` clones it fresh from `https://github.com/gregkop/sketchfab-mcp-server.git`
via `clone_or_pull` on every install, applying a repo-local patch file
(`scripts/patches/sketchfab-mcp-license-fix.patch`) before `npm install && npm run build`. The real
pattern is "clone a third-party repo into `mcp-servers/<name>/` at install time, leave it git-ignored,
patch it locally if a real defect is found" — not "vendor a copy into the NetClaw repo itself."
`comfyui-mcp` follows the identical real pattern.

**Alternatives considered**: Committing a vendored copy of `comfyui-mcp` into the repo (as the spec's
Assumptions originally implied) — rejected; it contradicts the actual, working precedent this feature
is supposed to mirror and would add an unnecessary maintenance burden (keeping a committed copy in
sync with upstream) that the real sketchfab-mcp-server precedent deliberately avoids.

## 2. Live-verified: WSL2-to-Windows-host reachability

**Decision**: No manual `--listen`/bind-address change, port-forward, or NAT workaround is needed.
The feature can treat the configured `COMFYUI_URL` as directly reachable over plain HTTP from
NetClaw's WSL2 runtime.

**Rationale**: This planning session ran directly inside the user's actual NetClaw WSL2 environment.
`curl http://127.0.0.1:8000/system_stats` was executed live and returned a genuine ComfyUI response
(`"comfyui_version": "0.34.0"`, `"os": "win32"`, real PyTorch/frontend package versions) — confirming
both that the endpoint is reachable and that it is genuinely ComfyUI, not a coincidental listener.
`ip route show default` confirms this WSL2 instance's default gateway is `192.168.2.1` (a real
NAT-mode gateway address), yet `127.0.0.1:8000` still resolved directly — consistent with WSL2's
mirrored networking mode being active on this host, which shares the Windows loopback namespace with
WSL2. The spec's Assumption that this needed verification, not assumption, was correct to flag; the
verified answer is that it already works with zero operator action required.

**Alternatives considered**: Building a documented manual remediation step (start ComfyUI with a
bind address reachable outside Windows loopback, e.g. `--listen 0.0.0.0`) was planned as a fallback
per the spec's Assumptions — not needed given the live result, but retained as a documented
contingency in quickstart.md in case a future user's WSL2 is in NAT (non-mirrored) mode instead,
where this same test would fail and that remediation would become necessary.

## 3. Live-verified: current model availability is the "no usable model" case

**Decision**: `comfyui_client.py`'s discovery step must be built and tested against the real
"zero usable checkpoints" outcome as the primary case to get right, not an edge case to defer.

**Rationale**: `curl http://127.0.0.1:8000/models/checkpoints` was executed live against the same
verified-reachable instance and returned `[]` — zero checkpoints installed. `object_info` for
`CheckpointLoaderSimple` confirms the node exists (ComfyUI itself is fully functional) but has no
values to offer for `ckpt_name`. This means FR-008's "no installed checkpoint is suitable for image
generation" condition is this feature's actual, current, real first-use outcome — not a theoretical
edge case exercised only by a deliberately-misconfigured test. The exact operator-facing message this
produces (FR-008 requires stating "what kind of model needs to be installed") should point at
installing at least one Stable Diffusion 1.5, SDXL, or Flux checkpoint into ComfyUI's
`models/checkpoints` directory — the three model families `comfyui-mcp`'s built-in template system
recognizes (research.md §4).

**Alternatives considered**: None — this is an observed fact about the live environment, not a
design choice.

## 4. `comfyui-mcp` tool surface and the generation flow

**Decision**: Drive generation through `comfyui-mcp`'s built-in template system rather than
hand-authoring a raw ComfyUI workflow graph. The call sequence is:

1. `get_status` (or `get_capabilities`) — confirm the backend is reachable before anything else (FR-007's distinct "unreachable" report hinges on this failing cleanly and early).
2. `list_models` — enumerate installed checkpoints (FR-006); if none are suitable for image generation, stop here and report per FR-008/FR-006's discovery-before-generation requirement.
3. `search_templates` with `taskType: "txt2img"` and a `modelType` matching the selected checkpoint's family (`sd15`/`sdxl`/`flux`/`any`) — find a built-in text-to-image template.
4. `get_template` with the chosen `templateId` and a `parameters` object carrying the composed prompt text and the selected model name — returns a populated, ready-to-run workflow JSON.
5. `run_workflow` with that workflow, `sync: false` — submits the job and returns immediately with a task identifier, rather than blocking NetClaw's own request/response cycle on GPU-bound generation time.
6. `get_task_result` (polled, alongside `get_queue`/`get_history` as needed) until ComfyUI itself reports a terminal status (completed or failed) — this is the mechanism FR-009's "no NetClaw-imposed timeout, tracked via ComfyUI's own status signals" is implemented with.
7. On success, the resolved image (`outputMode`/`get_image`) is written to `workspace/output/comfyui-topology-viz/` via `output.py`.

**Rationale**: `run_workflow`'s own documented contract requires a full ComfyUI workflow JSON object
and explicitly does **not** accept a bare text prompt — attempting to skip straight to `run_workflow`
with just a prompt string would fail outright. `comfyui-mcp` exists specifically to make raw
workflow-graph authorship unnecessary for a straightforward text-to-image ask: `search_templates` →
`get_template(..., parameters={prompt, model, ...})` is the documented, intended path to a valid
workflow without this feature needing to understand ComfyUI's node graph format at all. Choosing
`sync: false` plus explicit polling (rather than `sync: true`, which would block inside the tool call
for however long generation takes) is what makes FR-009's "no fixed NetClaw-side timeout" honest in
implementation, not just in wording — a synchronous call would still be bounded by whatever timeout
NetClaw's own MCP tool-call layer imposes, silently reintroducing the fixed cutoff the spec
explicitly rejected.

**Alternatives considered**: Hand-authoring a minimal raw text-to-image workflow JSON directly
(bypassing the template tools) — rejected; it would require this feature to embed and maintain
ComfyUI node-graph knowledge (node types, required fields, version drift across ComfyUI releases)
that `comfyui-mcp`'s own template system already owns and keeps current via its "70+ example
workflows from official ComfyUI docs." Using `sync: true` — rejected per the timeout-honesty
rationale above.

## 5. Reuse vs. re-derivation of topology data

**Decision**: `topology_model.py` and `sources.py` are ported (copied and trimmed) from
`workspace/skills/threejs-network-viz/`, not imported cross-package, and not reimplemented from
scratch.

**Rationale**: `threejs-network-viz/sources.py`'s own docstring establishes that topology retrieval
from each of the eight live sources happens at the conversational orchestration layer (NetClaw itself,
mid-conversation, calling each source's existing MCP tools) which normalizes results into a generic
`{"devices": [...], "links": [...]}` shape **before** any skill-local code runs; `sources.py`'s
adapters only turn that already-normalized shape into typed `TopologySnapshot` objects. This feature
needs exactly the same typed shape as its input to `prompt_builder.py`, so porting the already-correct
canonical types and adapters (trimmed of the 3D-only `AssetKind`/`ProceduralShape`/`ModelSource`
concepts this feature has no use for) avoids re-deriving source-parsing logic from zero, while
respecting the same architectural constraint 046 already documented: this repo's skills use relative
imports with `sys.path` fallbacks, not a shared installable package, so a live cross-skill-directory
import would be fragile.

**Alternatives considered**: Extracting a genuinely shared `netclaw_topology` library now — correct
long-term direction (046's research.md already flagged this as a reasonable future follow-up), but a
larger refactor touching multiple existing skills, out of scope for this feature.

## 6. Prompt composition and topology-size summarization

**Decision**: `prompt_builder.py` renders a bounded-length natural-language description from a
`TopologySnapshot` — device counts by role, notable role diversity, and a summarized description of
connectivity (not an exhaustive per-interface enumeration) — rather than attempting to serialize the
full topology model into the generation prompt.

**Rationale**: Unlike 046's 3D scene (which can render arbitrarily many labeled objects), a ComfyUI
text prompt is a natural-language string with practical length and usefulness limits — an image
model cannot meaningfully render hundreds of individually-labeled interfaces, and an overlong prompt
degrades generation quality more than it improves fidelity. This directly implements the spec's Edge
Cases entry: "extreme device-level detail may be summarized rather than exhaustively enumerated in
the generation input, since image generation cannot render arbitrarily dense text."

**Alternatives considered**: Passing the full topology JSON as generation metadata — ComfyUI's
text-to-image templates have no mechanism to consume structured JSON as anything other than a string
in the prompt field, so this would only produce a worse, unbounded prompt with no offsetting benefit.

## 7. Single-in-flight-job guard implementation

**Decision**: An in-memory flag/lock scoped to the skill's own process lifetime (set when a job is
submitted, cleared when it resolves) is sufficient to implement FR-009a. No new persistent store is
needed.

**Rationale**: NetClaw runs as a single gateway process per user installation (consistent with how
several other in-flight NetClaw features — e.g. subscription state in the gNMI MCP server, or
in-memory session ledgers elsewhere in this codebase — already treat single-process runtime state as
sufficient without a database). A generation job's in-flight status only needs to survive for the
duration of one job (tracked to a ComfyUI-reported terminal state per §4 above), not across NetClaw
restarts.

**Alternatives considered**: A file-based or SQLite-backed lock — rejected as unnecessary durability
for a condition that is, by definition, only meaningful while the owning process is running; if
NetClaw restarts mid-generation, the in-flight ComfyUI job itself is orphaned regardless of how
NetClaw tracked it, so persisting the lock across restarts would not actually recover anything.

## 8. Implementation-time finding: `comfyui-mcp` silently port-scans past a misconfigured `COMFYUI_URL`

**Finding**: With the real vendored server built and running against this environment's actual
ComfyUI instance, `get_status()` was called with `COMFYUI_URL` set to a completely non-routable IP
(`http://10.255.255.1:9999`) and, separately, to an unused local port (`http://127.0.0.1:59999`). In
both cases `comfyui-mcp` did **not** report a failure — it returned `comfyuiConnected: true`,
`discoverySource: "port-scan"`, and `comfyuiUrl: "http://127.0.0.1:8000"` (the real instance,
discovered by scanning common local ports), silently substituting a different backend than the one
configured. A response with `comfyuiConnected: true` is therefore **not sufficient** to confirm the
*configured* endpoint is what generation will actually run against.

**Decision**: `comfyui_client.py`'s reachability check does not stop at `comfyuiConnected` — it also
compares `get_status()`'s returned `comfyuiUrl` against the `COMFYUI_URL` this feature configured,
and requires `discoverySource == "environment"` (meaning `comfyui-mcp` actually honored the
configured value rather than falling back to port-scanning). Either mismatch is classified as
`backend_unreachable` (FR-007), even though the underlying tool call itself succeeded and even
though *some* ComfyUI is technically reachable — because FR-005 requires the configured endpoint be
what's actually used, not whatever `comfyui-mcp`'s own fallback discovery happens to find.

**Rationale**: This is exactly the kind of gap a misconfigured `.env` would hide silently — worse,
in a shared-network environment with more than one ComfyUI instance running (e.g., two engineers on
the same LAN), this fallback could cause a generation request to silently run against a *different
person's* ComfyUI instance rather than failing loudly. Treating a discovery-source/URL mismatch as
`backend_unreachable` turns that into the same clean, reported failure FR-007 already requires for
outright unreachability, rather than a new, unaccounted-for silent-substitution failure mode.

**Alternatives considered**: Trusting `comfyuiConnected` alone (the original, pre-implementation
design) — rejected once this behavior was found live; it would have violated FR-005 and FR-007 in
exactly the scenario those requirements exist to prevent. Passing a `comfyui-mcp` configuration flag
to disable its port-scan fallback — no such flag exists in this server's `get_status`/init tool
surface (confirmed by inspecting its full tool schema); the response-comparison approach works
without needing one.

## 9. Implementation-time finding: `comfyui-mcp`'s own task tracker gets permanently stuck, and a stdio teardown race in our own client

**Finding A — comfyui-mcp's task tracker is unreliable.** After a checkpoint was installed and a
real end-to-end generation was run for the first time, `comfyui_client.get_task_result()` /
`get_task()` / `list_tasks()` reported `{"status": "working", "statusMessage": "Queued for
generation"}` **permanently** — even minutes after ComfyUI's own `/history/{promptId}` endpoint
showed the job had completed successfully (`status_str: "success"`) in about 19 seconds.
`comfyui-mcp`'s WebSocket listener, meant to catch ComfyUI's own completion events and update its
task registry, silently failed to do so for this job. Under the original design (§4 above, "loop
`get_task_result` until it reports a terminal status"), this would poll forever — a real, silent
hang, discovered live by the user noticing no GPU activity in Task Manager despite the process
still running.

**Decision A**: `_submit_and_poll()` in `generation.py` polls ComfyUI's own `/history/{promptId}`
REST endpoint directly via a new `comfyui_client.get_prompt_history()` (plain `httpx` GET,
bypassing `comfyui-mcp` entirely for this check), confirmed live to be reliable and to return `{}`
(HTTP 200) rather than erroring when a prompt isn't in history yet. `comfyui-mcp`'s own
`run_workflow`-returned `taskId` was confirmed live to equal ComfyUI's own `promptId` (via
`get_task`'s response), making this a valid substitution. `comfyui_client.get_task_result()` is
retained only for diagnostics, explicitly documented as unreliable for polling. The completed
image is now downloaded directly from ComfyUI's own `/view` endpoint using the `filename`/
`subfolder`/`type` reference in the `/history` entry's `outputs` — not from any path `comfyui-mcp`
reports — which also makes `output.py`'s original defensive multi-candidate path-guessing (§3's
documented uncertainty) moot; it was replaced entirely rather than kept as a fallback.

**Finding B — a stdio teardown race in our own client, not comfyui-mcp.** After Decision A was
implemented, `run_workflow` calls started intermittently raising `anyio.BrokenResourceError`
(wrapped in a `BaseExceptionGroup`) from inside `comfyui_client._call_tool_async`'s `async with`
teardown. Cross-checking ComfyUI's own `/history` after each "failed" call showed the job had, in
every case, actually been submitted and completed successfully — the exception was purely a
client-side artifact of `_call_tool_async` `return`ing from inside the nested `async with
stdio_client(...): async with ClientSession(...):` blocks, which races trailing stdio traffic
`comfyui-mcp` sends after a tool's JSON-RPC response (plausibly async-job progress/logging
notifications on the same channel) against session teardown.

**Decision B**: `_call_tool_async` now captures its result into a local dict *before* the `async
with` blocks close, and re-raises a teardown-phase exception only if no result was captured — a
genuine failure (nothing received) still propagates correctly, but the confirmed-benign race no
longer masks a real, successful result as a hard failure.

**Rationale**: Both findings follow the same pattern established in spec 046 with
`sketchfab-mcp-server`'s dropped license field — trust nothing about a third-party MCP server's
task-lifecycle or transport behavior until it's been exercised against a real backend end-to-end.
Neither finding was reachable during planning (research.md §3 — no checkpoint was installed yet)
or even during the first implementation pass (mocked tests can't reproduce a stdio timing race or
a stuck upstream task tracker); both only surfaced once a real checkpoint existed and a real
generation was actually run to completion, live, with the user watching for GPU activity as an
independent cross-check.

**Verified end-to-end**: with both fixes applied, a real freeform topology ("a router called
core1, core1 connects to a switch called sw1, sw1 connects to a firewall called fw1") produced a
genuine 512×512 PNG in 21.5 seconds, correctly attributing `sd_xl_base_1.0.safetensors` as the
checkpoint used, written to `workspace/output/comfyui-topology-viz/` with its sidecar JSON.

**Alternatives considered**: Reintroducing a NetClaw-side timeout to bound Finding A's hang —
rejected; it would silently reintroduce the fixed cutoff Clarification session 2026-08-26
explicitly rejected, and the real fix (poll a source that's actually reliable) is strictly better
than bounding an unreliable one. Blanket-catching all exceptions around every `_call_tool` call to
paper over Finding B — rejected in favor of the narrower, result-aware catch actually implemented,
since a blanket catch would also hide genuine connection failures that happen before any result is
received.

## 10. Post-implementation: the ControlNet structural pipeline (Flux + Canny), live-verified

**Context**: SDXL's plain txt2img output (§3's verified example) was visually confirmed by the
user to be unusable — abstract neon line-art with no recognizable device/connection structure at
all. Following the user's own architecture proposal, a second generation pipeline was added:
`topology_renderer.py` deterministically renders the topology as a plain black-on-white box/line
diagram (networkx layout + Pillow drawing, NOT AI-generated), which is fed to ComfyUI's `Canny`
node as ControlNet conditioning for a Flux generation — forcing the diffusion model to paint over
real structural edges instead of inventing structure from text alone.

**Decision**: `generation.py` prefers this structural path whenever
`comfyui_client.controlnet_available()` reports all required models present (Flux UNET, its two
CLIP text encoders, its VAE, and a ControlNet), falling back to the plain txt2img path otherwise
— preserving FR-008's graceful-degradation behavior rather than making the ControlNet models a
hard requirement.

**Two real bugs found and fixed during the first live end-to-end run** (not caught by any mocked
test, since mocks can't expose structural/visual correctness issues):

1. **`sources.from_freeform()` mis-parsed inline role declarations combined with connector
   syntax.** A description like `"core1 connects to a switch called sw1"` split on "connects to"
   and took the *first word* of the second half ("a") as the device name instead of the real
   hostname ("sw1") — creating a phantom `"a"` device and leaving the intended device
   disconnected. This bug is inherited (via the port, research.md §5) from spec 046's
   `threejs-network-viz/sources.py`, which has the identical bug — per FR-014 only
   `comfyui-topology-viz`'s copy was fixed, `threejs-network-viz` was left untouched. The bug was
   invisible in the plain txt2img path because `prompt_builder.py` only summarizes role *counts*,
   never exact hostnames or link structure — it only became visible once the structural renderer
   made the actual parsed graph directly observable in the generated image. Fixed with a new
   `_extract_device_name()` helper in `sources.py` that prefers an explicit role-declaration match
   or an already-known device name over the old naive first/last-word heuristic.
2. **Canny-edge-conditioned text is unreliable.** With hostnames drawn directly into
   `topology_renderer.py`'s structure image, Flux could not reliably reconstruct exact letters
   from the Canny edge map alone — a live run produced garbled nonsense ("fret", "svitch",
   "evrit") instead of the real hostnames. This is a fundamentally different mechanism from
   Flux's genuinely strong *prompt-driven* text rendering the user's proposed architecture
   correctly credited it with — that strength doesn't transfer to reproducing arbitrary text from
   a lossy edge map. Fixed by removing all text from the structure image (`topology_renderer.py`
   now draws box/line geometry only) and burning real, correct hostname labels onto the
   *completed* generation afterward, deterministically, via a new `label_overlay.py` using the
   same canvas positions (`topology_renderer.compute_positions()`) the structure image used.

**Verified end-to-end after both fixes** (2026-08-28): the same freeform topology
(`"a router called core1, core1 connects to a switch called sw1, sw1 connects to a firewall
called fw1"`) produced a genuinely correct diagram in 41.9s — exactly 3 devices, the real
`core1↔sw1↔fw1` chain, and legible correct labels. Remaining imperfections are cosmetic
(generic device iconography rather than role-specific icons, decorative hallucinated background
clutter, thin/dashed rather than "glowing" connection lines per the prompt) — real prompt-tuning
opportunities, not correctness bugs.

**Model inventory**: see `specs/120-comfyui-topology-viz/model-inventory.md` for the full
Flux+ControlNet model set installed (~25GB) and cleanup guidance.

## 11. Negative prompting and aesthetic direction

**Finding**: The first structural-path generation (§10) left `ControlNetApplySD3`'s negative
conditioning as an empty string, inherited unmodified from comfyui-mcp's own example workflow.
With nothing to steer away from, Flux filled empty background space with unrequested decorative
clutter — fake gauge/meter bars, garbled pseudo-UI text, a stray "54.1" — competing visually with
the actual topology.

**Decision**: `prompt_builder.py` gained a `NEGATIVE_PROMPT` constant (blurry/distorted/watermark/
fake UI elements/gauges/meters/dashboard widgets/illegible or gibberish text/random
numbers/unrelated icons/jpeg artifacts/oversaturated), threaded through
`comfyui_client.build_controlnet_workflow()`'s new `negative_text` parameter into the workflow's
node `"7"`. At the same time, the positive style suffix was rewritten toward the user's requested
cyberpunk direction (neon cyan/magenta palette, holographic glow, circuit-board grid background,
glowing data streams, dramatic rim lighting) rather than the original generic "digital network
diagram art style."

**Verified end-to-end** (2026-08-29/30): same freeform topology, 72.7s — the hallucinated
dashboard clutter is gone entirely; the background instead shows a coherent magenta/cyan vertical
light-streak pattern, device boxes have a genuine neon-magenta glow outline, and connection lines
render as glowing cyan streaks, all while structure and labels remain correct. This is the current
best/baseline result.

**Alternatives considered**: Tuning `ControlNetApplySD3`'s `strength` (currently a static 0.65)
instead of/alongside negative prompting — left as a documented future tuning knob (see the
handoff/improvement-directions doc referenced from `SKILL.md`) rather than changed here, since the
empty-negative-prompt gap was the clearer, lower-risk fix to make first.

## 12. Testing approach

**Decision**: Pure-Python unit-test coverage (with `comfyui-mcp` tool calls mocked) for
`prompt_builder.py`'s composition/summarization logic, `generation.py`'s deterministic model
selection (FR-006a) and single-in-flight guard (FR-009a), and the three distinct failure
classifications (unreachable backend / no usable model / job failure, FR-007/008/009). One live
integration test runs against whatever ComfyUI instance is actually configured in the test
environment's `.env` — today, per §3 above, that test's correct, expected assertion is the real
"no usable model found" outcome, not a fabricated success.

**Rationale**: Mirrors spec 046's exact testing philosophy (§5 of its own research.md): this
feature's core logic (prompt composition, model selection, failure classification) is pure Python
with no live dependency and should get fast, deterministic unit coverage; the one thing that
legitimately needs a live check is whether the actually-configured ComfyUI backend behaves as this
feature expects when queried for real — and mocking that away would hide exactly the kind of gap this
planning session's live verification (§§2-3) already found once.

**Alternatives considered**: Mocking every ComfyUI interaction, including the live-reachability
integration test — rejected; it would have hidden both real findings this research session surfaced
(reachability works without a workaround; zero checkpoints are actually installed), which is exactly
the failure mode the "never mock the dependency whose failure would matter most" rule from 044/045/046
exists to prevent.
