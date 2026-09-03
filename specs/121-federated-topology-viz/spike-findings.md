# FR-015 Research Spike — Findings (T018/T019)

**Status: NO-GO. Spec closed 2026-09-03 without a passing result on either attempted host.**

Per spec.md's fixed pass/fail bar (100% of device labels reproduced exactly character-for-character,
every connection line traceable without gaps — see spec.md's clarification under FR-015/SC-005),
Qwen-Image-Edit-2509 (GGUF-quantized) was tried on two separate hosts across two sessions. Neither
produced a result clearing that bar. FLUX.2 [klein] 4B (research.md R9's documented fallback) was
never attempted — the spike was closed out as NO-GO rather than continuing to iterate.

## Attempt 1 — Windows/WSL2 host (`johns-risk/viz` federation member)

See `HANDOFF-MAC.md` for the full contemporaneous account. Summary: the ComfyUI host crashed three
times during real GPU work (cold model load + sustained diffusion under `--lowvram` on a 16GB card)
before `KSampler` ever completed its 20 steps. Real progress was observed live (`queue_running`
entries, `step 5/20 at 29s/it`) but no attempt ever finished — no scoreable output was produced on
this host at all. A real, live-found bug in the shared federation channel (`channel.py`'s `_read_loop`
blocking on long `tools/call` dispatch, causing the liveness watchdog to kill a genuinely-still-running
Stage B job) was found and fixed along the way; unrelated to the spike's own outcome.

## Attempt 2 — macOS host (local ComfyUI, direct call, no federation)

Run out-of-band from the federated pipeline: a native ComfyUI install on an Apple M4 Pro / 48GB
unified-memory Mac, calling `image-style-mcp/server.py`'s `style_image` logic directly against a
locally-hosted ComfyUI (`COMFYUI_URL=http://127.0.0.1:8188`), bypassing the mesh entirely since
Border/`johns-risk/viz` weren't running on this host. Source image: a real pyATS-derived single-device
interface dashboard (Cisco DevNet IOS-XE C9K sandbox, live device — unrelated substitution for CML,
irrelevant to the spike's own model-quality question).

Unlike the Windows host, a result **did** complete here — but it failed the fidelity bar:

- **20 steps, 1024×1024, denoise=0.75** (the value already raised once per the Windows session's own
  note that 0.5 produced zero visible stylization): repeatedly stalled at steps 7-9 with per-step time
  spiking from ~75-105s/it to 400-1100s/it. Confirmed via `top`/`vm_stat`/`sysctl vm.swapusage` as
  genuine physical memory exhaustion — ComfyUI's own resident footprint grew to 25-28GB over the
  course of the sampling loop, against a 48GB total pool, regardless of what else was running
  (confirmed by closing every other application and re-running: same stall, same step, flat swap this
  time, ruling out background-app contention as the cause). This looks like a memory-growth pattern
  specific to this ComfyUI+PyTorch-MPS+GGUF stack on Apple Silicon, not a config mistake.
- **12 steps, 768×768, denoise=0.75, `--lowvram`** (steps deliberately capped inside the proven-stable
  8-step window to dodge the memory wall above): completed in 15m39s, all 12 steps stable at
  ~75-78s/it. This is the one real, complete output this spike produced. It **fails the bar**: device
  labels and the traffic-counter table are garbled/illegible (only "CAT9k_AO" itself survived
  correctly), and the requested cyberpunk styling barely applied at all — the central device icon
  picked up some shading/texture, but no visible color/lighting/background transformation. Denoise=0.75
  is confirmed too aggressive for text fidelity at this step count; denoise=0.5 was already established
  (Windows session) to produce ~zero stylization. No value in between was tried before the spec was
  closed.

## Conclusion

Two real hosts, two different failure modes — Windows never finished a job at all; macOS finished one
and it failed the fidelity bar outright. No completed result on either host has cleared FR-015's bar.
Per the user's explicit decision, this spec is closed here rather than continuing to the FLUX.2
[klein] 4B fallback (research.md R9) or further denoise/step tuning. **T019 is deliberately left
undone** — the fallback was never attempted, not silently skipped.

All Tier B model weights (Qwen-Image-Edit-2509 GGUF unet, text encoder, VAE — ~22.7GB) downloaded to
the macOS host during Attempt 2 were deleted along with the local ComfyUI install itself
(2026-09-03 cleanup — see `model-inventory.md`). The Windows/WSL2 host's own Tier B weights (same
model, downloaded during Attempt 1, path `/mnt/c/Users/ptcap/Documents/ComfyUI/models/` per that
host's `model-inventory.md` entry) were **not** touched by this cleanup — that host is not reachable
from this session. If that machine is being decommissioned or repurposed, its Tier B weights should
be deleted there separately, following the same cleanup policy.

The already-merged pipeline code (both new MCP servers, `federated_generation.py`, federation wiring,
tests, docs — T001-T017, T020-T048) is left in place; it works mechanically end-to-end (Stage A alone
is fully correct and already proven — the deterministic renderer was never in question). Only the
Stage B *model choice* failed its own gating spike. A future attempt, if ever made, should pick up at
T019 (FLUX.2 [klein] 4B) or try further denoise/step tuning on Qwen-Image-Edit-2509 — this document
is not a claim that federated AI-styled topology visualization is impossible, only that this spec's
two real attempts at it did not produce a usable result.
