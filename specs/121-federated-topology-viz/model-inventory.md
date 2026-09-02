# Model Disk Inventory (spec 121)

Tracks everything this feature downloads onto the ComfyUI host
(`/mnt/c/Users/ptcap/Documents/ComfyUI/models/` — mounted via WSL2, same host spec 120 used),
extending spec 120's own `specs/120-comfyui-topology-viz/model-inventory.md` ledger (Tier C,
untouched by this feature — FR-012) with this feature's new Tier B (federated Stage B) set.

**Drive state before this feature's downloads** (2026-08-30): 41GB free on a 936GB C: drive
(96% used) — see research.md/the disk-space check performed before downloading anything. No
NetClaw-owned files were available to clean up first (the only sized content under `models/` was
spec 120's own intentionally-kept Tier C set; everything else was empty category stubs).

## Tier B (Qwen-Image-Edit-2509 GGUF) — this feature's Stage B model

Every size below was verified directly against the real HuggingFace source (`curl -I` following
the redirect to the actual CDN object, not a quoted estimate) before downloading, per FR-016 —
the same discipline spec 120's own inventory required after two real mistakes there (a wrong
size estimate and a silently-gated repo).

| File | Location | Real size (bytes, HTTP-verified) | Source | License |
|---|---|---|---|---|
| `Qwen-Image-Edit-2509-Q4_K_M.gguf` | `models/unet/` | 13,065,746,976 (13.07 GB) | [`QuantStack/Qwen-Image-Edit-2509-GGUF`](https://huggingface.co/QuantStack/Qwen-Image-Edit-2509-GGUF), ungated | Apache-2.0 (base model; GGUF conversion carries the same terms) |
| `qwen_2.5_vl_7b_fp8_scaled.safetensors` | `models/text_encoders/` | 9,384,670,680 (9.38 GB) | [`Comfy-Org/Qwen-Image_ComfyUI`](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI), ungated | Apache-2.0 |
| `qwen_image_vae.safetensors` | `models/vae/` | 253,806,246 (254 MB) | Same repo as above | Apache-2.0 |

**Total: ~22.7GB.** Left ~18GB spare on the C: drive at download time.

**Download note**: the first attempt at `qwen_2.5_vl_7b_fp8_scaled.safetensors` died mid-transfer
(`curl: (92) HTTP/2 stream 1 was not closed cleanly`) at 4.14GB of 9.38GB — a genuinely truncated
file, not a completed one. Deleted and re-downloaded with `--retry 5` rather than trusting the
partial file's presence on disk (the same "don't trust a file just because it exists" discipline
spec 120's gated-repo incident established).

## FR-015 spike outcome

See `spike-findings.md` for the actual go/no-go finding. If the spike is a "no-go" and FLUX.2
[klein] 4B is downloaded instead per research.md R9's fallback, the Qwen files above become
candidates for cleanup (update this ledger and delete them at that point — don't leave rejected
multi-GB weights on an already-tight drive). If "go," these three files are the load-bearing Tier
B set going forward, alongside spec 120's untouched Tier C fallback.

## Cleanup policy

Same as spec 120's own policy: Tier C (Flux+ControlNet) stays — it's the intentional fallback,
not a leftover. Tier B stays if the spike confirms it; if the spike rejects Qwen-Image-Edit for
FLUX.2 [klein] instead, delete the three files above and update this table.
