# ComfyUI Model Disk Inventory (spec 119)

Tracks everything NetClaw has downloaded onto the ComfyUI host
(`/mnt/c/Users/ptcap/Documents/ComfyUI/models/`), so cleanup is a clean one-shot, not guesswork.
Drive at 98% used (29GB free as of 2026-08-30) — every entry here matters.

| File | Location | Size (verified on disk) | Added | Status |
|---|---|---|---|---|
| `flux1-schnell-fp8.safetensors` | `models/unet/` | **16.05GB** (comfyui-mcp's own `get_download_url` quoted ~11.9GB — wrong) | 2026-08-27 | Base image model for the Tier C (fallback) ControlNet pipeline; loaded via `UNETLoader` |
| `t5xxl_fp8_e4m3fn.safetensors` | `models/clip/` | 4.89GB | 2026-08-27 | Flux text encoder, via `DualCLIPLoader` |
| `clip_l.safetensors` | `models/clip/` | 246MB | 2026-08-27 | Flux's second text encoder, via `DualCLIPLoader` |
| `ae.safetensors` | `models/vae/` | 168MB | 2026-08-28 | Flux VAE, via `VAELoader`. Sourced from `Kijai/flux-fp8` (`flux-vae-bf16.safetensors`) after the original `black-forest-labs/FLUX.1-schnell` URL turned out to be a gated HF repo |
| `instantx_flux_canny.safetensors` | `models/controlnet/` | 3.58GB | 2026-08-28 | Canny-edge ControlNet for the Tier C pipeline — source: https://huggingface.co/InstantX/FLUX.1-dev-Controlnet-Canny |

**Deleted, 2026-08-30**: `sd_xl_base_1.0.safetensors` (6.9GB, was `models/checkpoints/`). Freed by
the colleague-reviewed architecture decision — the plain-SDXL-txt2img fallback it served is now
superseded by the confirmed-working Flux+ControlNet structural path, which becomes this
architecture's Tier C fallback (see `research.md` §13 for the 3-tier plan). Freed 22GB → 29GB.

**Currently installed**: the 5 Flux/ControlNet files above, ~25GB total — this is Tier C
(fallback path), kept intentionally, not a leftover.

**Not ours — do not touch**: `ComfyUI/output/__FILENAME_PREFIX__*.png`, `ComfyUI/output/board_*.png`
(dated Dec 2025, pre-existing user content, ~369MB). NetClaw's own generated files there
(`ComfyUI_MCP_0000*.png`, small) are copied into `workspace/output/comfyui-topology-viz/` and are
safe to leave or clean independently of this ledger.

## Pending: Tier B (Qwen-Image-Edit) models — not yet downloaded, needs confirmation per-file

| File | Type | Real size (verified) | Purpose |
|---|---|---|---|
| `Qwen-Image-Edit-2509-Q4_0.gguf` (or `Q4_K_S`) | `models/unet/` | ~11.9–12.2GB | Edit-conditioned base model (GGUF-quantized for 16GB VRAM) |
| `qwen_2.5_vl_7b_fp8_scaled.safetensors` | `models/text_encoders/` | ~8GB (unverified exact — check at download time) | Qwen2.5-VL-7B text/vision encoder |
| `qwen_image_vae.safetensors` | `models/vae/` | small, likely <1GB (unverified exact) | Qwen-Image VAE |

**~20GB estimated total.** Against 29GB currently free, this leaves ~9GB headroom — tight but
workable. Verify each file's real size via HuggingFace before pulling (same discipline as the
Flux/ControlNet set above — `get_download_url`-style checks caught a wrong estimate and a gated
repo there; don't skip that step here).

## Cleanup policy going forward

- Tier C (Flux+ControlNet, this file's top table) is the intentional, load-bearing fallback in
  the 3-tier architecture — not a deletion candidate.
- If Tier B (Qwen-Image-Edit) proves out and becomes the default path, Tier C stays as-is; it's
  the documented fallback for "ComfyUI-edit host unavailable" or "no real device data behind a
  freeform description," not redundant with Tier B.
- If Tier B does NOT pan out (line-work/text fidelity fails the one-afternoon test), delete the
  ~20GB Qwen-Image-Edit set and stay on Tier C alone.
