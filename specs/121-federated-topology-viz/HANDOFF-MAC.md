# Handoff: spec 121 federated topology viz — resume on Mac

**Why this exists**: the Windows ComfyUI host crashed repeatedly during real GPU work (cold
model load + sustained diffusion under `--lowvram` on a 16GB card) — three times in one session.
Moving to a Mac to get a stable box for the remaining live verification.

**Branch**: `121-federated-topology-viz`, pushed to `origin`, commit `594ca73` — fully clean on
GitHub (`git ls-remote origin 121-federated-topology-viz` matches local HEAD exactly). Just
`git fetch && git checkout 121-federated-topology-viz` on the Mac; no manual file transfer needed.

**Note**: the WSL2 checkout this was pushed from has real local git corruption (`git fsck` shows
several zero-byte loose objects — `.git/objects/5c/4378...`, `05/a30bad...`, etc.). This is why
GAIT's own audit-trail git commits were failing throughout this session
(`gait.emit git commit failed: ... object file ... is empty`) — same underlying corruption,
unrelated to spec 121's code. It did **not** affect the push (GitHub would have rejected an
incomplete object graph). Worth a `git gc`/repo-repair on the Linux box separately, not urgent for
the Mac handoff.

## What's done (48/54 tasks, all Foundational/US1/US2/US3 code + tests)

- Both new MCP servers (`mcp-servers/topology-diagram-mcp/`, `mcp-servers/image-style-mcp/`)
  written, unit-tested, **live-verified working** against the real `johns-risk/viz` federation
  member, repeatedly, across multiple test runs today.
- `workspace/skills/comfyui-topology-viz/federated_generation.py` (new orchestrator) — routing
  logic (federated / federated_partial / fallback), single-in-flight guard, all unit + live
  integration tested.
- **Four real, live-found bugs in shared federation infrastructure fixed** (all committed,
  additive/backward-compatible, full regression suite green — 485+ pre-existing tests unaffected):
  1. `bgp/federation/service.py`: `n2n/tools/call` had no dispatch entry on the internal
     (Border↔member) channel at all — added it.
  2. `bgp/federation/service.py`: a member's channel never got `attestation="possession"`
     elevated after its pinned-key handshake, so the tier-0 gate always denied `tools/call` —
     fixed in `dial_border()`.
  3. `bgp/federation/invocation.py`: `Invoker._channel()` only knew how to resolve eN2N (external)
     peers, not internal members — added the `is_member_task()` branch to use
     `ensure_member_up()`.
  4. `bgp/federation/authorization.py` + `invocation.py`: `authorize()`'s `is_federated()` check
     has no concept of an iN2N member's self-referential `peer_identity` — added an
     `already_trusted` bypass, set only for internal channels.
  5. **Found today, also fixed**: `bgp/federation/channel.py`'s `_read_loop` awaited `_dispatch`
     inline, so a long `tools/call` (Stage B genuinely runs minutes) blocked the loop from
     reading the peer's next heartbeat frame — the channel's own liveness watchdog then killed it
     as "unresponsive" mid-job (`"3 missed heartbeats — closing"`, live-verified failure). Fixed
     by running dispatch as its own task (`_dispatch_task`) so the read loop keeps consuming
     frames concurrently. **Live-verified this fix works**: a second attempt with it live stayed
     `active`/`live: true` well past the point the first attempt died.
- `N2N_TOOL_TIMEOUT_S` raised 600→**1800** (both `~/.openclaw/mesh.systemd.env` and
  `migration-staging/members/viz/.env` — **not git-tracked, must be set again on the Mac's own
  environment**), plus matching client-side timeouts in `federated_generation.py` (1830s) and
  `image-style-mcp/server.py`'s `_submit_and_poll` (1700s, already committed in code).
- Full Artifact Coherence checklist done (README, catalog.sh, install-steps.sh,
  verify-catalog-coverage.py — passes clean, SOUL.md n/a, TOOLS.md, HUD, .env.example).

## What's NOT done — the actual remaining work

- **T018/T019 (FR-015 spike)**: never reached a completed result. Every attempt died to a
  ComfyUI-host crash (three times) before `KSampler` finished its 20 steps. The workflow itself is
  confirmed correct — real `queue_running` entries, real progress (`step 5/20 at 29s/it` was
  observed live) — just never finished. **This is the actual next step on the Mac.**
- One earlier finding *did* complete (before the crashes): at `denoise=0.5` on a mostly-white
  source image, styling had **zero visible effect** — labels/lines/icons perfectly preserved but
  no stylization applied at all. Raised to `denoise=0.75` (already committed in
  `image-style-mcp/server.py`) to give the model more room; **not yet re-verified against the
  FR-015 fidelity bar at the new value** — that's part of what finishing the spike needs to check.
- `specs/121-federated-topology-viz/spike-findings.md` — not created yet; write it once a real
  result exists.
- T050 (GAIT session log), T051 (WordPress blog draft) — not started.
- A live agentic smoke test (asking Border directly, in natural language, to use CDP/LLDP to
  build the diagram) was attempted twice; both times the background process was killed by a
  session boundary before returning a result, unrelated to the pipeline itself. Worth trying again
  once the direct-script path below is confirmed working, since that proves the underlying
  capability already.

## Known, separate issues found live today (not blocking, but real)

- `johns-risk/ipfabric` and `johns-risk/pyats` were stuck in a repeating dial/heartbeat-timeout
  churn cycle (~90s period) for the whole session after a `netclaw-mesh.service` restart —
  unrelated to spec 121, never investigated. `johns-risk/viz` was never affected.
- GAIT's git-commit-based audit trail fails on every single audit event due to the local repo
  corruption noted above — audit still gets recorded via other means (SQLite), this only breaks
  the git-based trail specifically.
- A stray `ValueError: unsupported HTTP method; expected GET; got POST` in the websocket server —
  looked like unrelated probe traffic, not investigated.

## Setting up on the Mac

1. `git fetch origin && git checkout 121-federated-topology-viz` — gets everything above.
2. Re-set `N2N_TOOL_TIMEOUT_S=1800` in whatever holds Border's env on the Mac, and in the
   `johns-risk/viz` member's env (if the member also runs on the Mac — if it's staying on the
   Linux box and only ComfyUI is moving, only `COMFYUI_URL` needs to change, pointed at the Mac).
3. Install a local ComfyUI on the Mac (native, or ComfyUI Desktop if that exists for macOS) with
   the **ComfyUI-GGUF custom node** — required for `UnetLoaderGGUF`. Confirm `ComfyUI-Manager` or
   a manual `custom_nodes/` clone gets it.
4. **Models — put them somewhere you can delete cleanly when done**, e.g. a dedicated
   `~/comfyui-spike-models/` directory, and point ComfyUI at it via
   `--extra-model-paths-config` (a YAML mapping extra folders per category) rather than copying
   into ComfyUI's own permanent `models/` tree. Real, HTTP-verified sizes/sources/license (FR-016
   discipline — verify again if anything looks different, don't trust a cached number):

   | File | Category (subfolder) | Size | Source | License |
   |---|---|---|---|---|
   | `Qwen-Image-Edit-2509-Q4_K_M.gguf` | `unet/` | 13,065,746,976 B (13.07 GB) | `https://huggingface.co/QuantStack/Qwen-Image-Edit-2509-GGUF` (ungated) | Apache-2.0 |
   | `qwen_2.5_vl_7b_fp8_scaled.safetensors` | `text_encoders/` | 9,384,670,680 B (9.38 GB) | `https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI` (ungated) | Apache-2.0 |
   | `qwen_image_vae.safetensors` | `vae/` | 253,806,246 B (254 MB) | Same repo as above | Apache-2.0 |

   Total ~22.7GB. Verify each with `curl -I` (follow the redirect) matches these exact byte counts
   before trusting the download completed — one attempt on the Windows box died mid-transfer and
   left a silently truncated file; always check size, don't just check "does the file exist."

5. Confirm ComfyUI sees them: `curl http://<mac-host>:8000/object_info/UnetLoaderGGUF` should list
   the `.gguf` filename in its `unet_name` dropdown; same idea for `CLIPLoader`/`VAELoader`.
6. Set `COMFYUI_URL` to wherever that Mac ComfyUI actually listens.

## Resuming the spike — copy-paste ready

This is the exact script that was mid-run three times when the crashes hit. Run from
`workspace/skills/comfyui-topology-viz/`:

```python
import sys, time, json, base64
sys.path.insert(0, '.')
import federated_generation
import sources

# Real CML lab data already fetched live from johns-risk/cml (lab "NetClaw-Full-Topo") —
# re-fetch fresh via that member if preferred (see below), or just reuse this.
raw_topology = {
    "source": "CML lab NetClaw-Full-Topo (live, real, johns-risk/cml)",
    "devices": [
        {"hostname": "PC1", "device_type": "client", "interfaces": [{"name": "eth0"}]},
        {"hostname": "PC2", "device_type": "client", "interfaces": [{"name": "eth0"}]},
        {"hostname": "PC3", "device_type": "client", "interfaces": [{"name": "eth0"}]},
        {"hostname": "PC4", "device_type": "client", "interfaces": [{"name": "eth0"}]},
        {"hostname": "R1", "device_type": "router", "interfaces": [{"name": "Ethernet0/0"}, {"name": "Ethernet0/2"}, {"name": "Ethernet0/3"}]},
        {"hostname": "R2", "device_type": "router", "interfaces": [{"name": "Ethernet0/0"}, {"name": "Ethernet0/2"}, {"name": "Ethernet0/3"}]},
        {"hostname": "SW1", "device_type": "switch", "interfaces": [{"name": "Ethernet0/0"}, {"name": "Ethernet0/1"}, {"name": "Ethernet0/2"}, {"name": "Ethernet0/3"}]},
        {"hostname": "SW2", "device_type": "switch", "interfaces": [{"name": "Ethernet0/0"}, {"name": "Ethernet0/1"}, {"name": "Ethernet0/2"}, {"name": "Ethernet0/3"}]},
        {"hostname": "OOB-SW", "device_type": "switch", "interfaces": [{"name": "port0"}, {"name": "port1"}, {"name": "port2"}, {"name": "port3"}, {"name": "port4"}]},
        {"hostname": "OOB-EXT", "device_type": "unclassified", "interfaces": [{"name": "port"}]},
    ],
    "links": [
        {"source_device": "SW1", "source_interface": "Ethernet0/0", "target_device": "PC1", "target_interface": "eth0"},
        {"source_device": "SW1", "source_interface": "Ethernet0/1", "target_device": "PC2", "target_interface": "eth0"},
        {"source_device": "SW2", "source_interface": "Ethernet0/0", "target_device": "PC3", "target_interface": "eth0"},
        {"source_device": "SW2", "source_interface": "Ethernet0/1", "target_device": "PC4", "target_interface": "eth0"},
        {"source_device": "R1", "source_interface": "Ethernet0/0", "target_device": "R2", "target_interface": "Ethernet0/0"},
        {"source_device": "R1", "source_interface": "Ethernet0/2", "target_device": "SW1", "target_interface": "Ethernet0/2"},
        {"source_device": "R2", "source_interface": "Ethernet0/2", "target_device": "SW2", "target_interface": "Ethernet0/2"},
        {"source_device": "R1", "source_interface": "Ethernet0/3", "target_device": "OOB-SW", "target_interface": "port0"},
        {"source_device": "R2", "source_interface": "Ethernet0/3", "target_device": "OOB-SW", "target_interface": "port1"},
        {"source_device": "SW1", "source_interface": "Ethernet0/3", "target_device": "OOB-SW", "target_interface": "port2"},
        {"source_device": "SW2", "source_interface": "Ethernet0/3", "target_device": "OOB-SW", "target_interface": "port3"},
        {"source_device": "OOB-SW", "source_interface": "port4", "target_device": "OOB-EXT", "target_interface": "port"},
    ],
}

snapshot = sources.from_cml(raw_topology)
snapshot.snapshot_id = "killer-test-mac"

killer_prompt = (
    "A breathtaking cyberpunk network operations center hologram, glowing "
    "neon-cyan and hot-magenta circuitry, the network topology floating as a "
    "luminous 3D wireframe schematic above a obsidian-black holographic "
    "control table, electric data packets streaming like comet trails along "
    "every connection line, dramatic volumetric rim lighting, deep-space "
    "background dusted with distant server-city lights, ultra-detailed "
    "sci-fi HUD interface glow, Blade Runner meets Tron aesthetic, "
    "cinematic 8k digital art, high contrast, crisp bloom"
)
negative_prompt = (
    "blurry, low quality, distorted, watermark, fake UI elements, gauges, "
    "meters, progress bars, dashboard widgets, illegible text, gibberish "
    "text, random numbers, extra unrelated icons, jpeg artifacts, "
    "oversaturated, washed out"
)

stage_a = federated_generation._run_stage_a(snapshot)
print("Stage A:", stage_a["device_count"], "devices")

stage_b = federated_generation._run_stage_b(stage_a["image_base64"], killer_prompt, negative_prompt)

styled_bytes = base64.b64decode(stage_b["styled_image_base64"])
image = federated_generation._write_federated_image(
    snapshot, styled_bytes, "topology-diagram-mcp + image-style-mcp", "killer-test-mac"
)
print("DONE:", image.file_path)
```

To re-fetch fresh CML data instead of the embedded snapshot above (needs `johns-risk/cml` live —
check with `curl http://127.0.0.1:8179/n2n/members/health`):

```bash
curl -X POST http://127.0.0.1:8179/n2n/tasks -H "Content-Type: application/json" \
  -d '{"peer":"johns-risk/cml","target_type":"skill","target_name":"cml-topology-builder","input_text":"List the current CML lab(s) and, for whichever lab is active, return its full topology as JSON: every node with its hostname and node/device type, and every link between nodes with the interfaces involved. Return only the JSON, no prose."}'
# then poll: curl http://127.0.0.1:8179/n2n/tasks/<task_id>
```

## Once the spike completes

1. Score the output against the FR-015 bar (100% exact label reproduction, every connection line
   traceable, spec.md FR-015/SC-005) — look at it directly, same rigor spec 120 used to catch its
   own garbled-text regression.
2. Write `specs/121-federated-topology-viz/spike-findings.md` with the go/no-go finding.
3. If go: mark T018/T019 done in `tasks.md`, move on to T050/T051.
4. If no-go: repeat against FLUX.2 [klein] 4B per research.md R9's documented fallback, verifying
   its own real size/license first (same FR-016 discipline).
