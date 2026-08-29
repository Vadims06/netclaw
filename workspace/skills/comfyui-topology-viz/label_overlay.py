"""
Burns real, legible hostname labels onto a completed Flux+ControlNet generation — deterministic
Pillow text drawing, not AI-generated. Exists because Canny-edge conditioning is too lossy for
Flux to reliably reproduce exact text: a live end-to-end run with hostnames baked into
topology_renderer.py's structure image produced garbled nonsense ("fret", "svitch", "evrit")
instead of the real device names. The fix is to never ask the diffusion model to render text at
all — topology_renderer.py's structure image is textless (boxes/lines only), and this module
overlays the real hostnames afterward at the same canvas positions, guaranteeing correctness
regardless of anything the diffusion model does to the rest of the image.
"""

import io

from PIL import Image, ImageDraw, ImageFont

import topology_renderer

_TEXT_FILL = (20, 20, 20)
_BACKDROP_FILL = (255, 255, 255, 235)


def overlay_labels(image_bytes: bytes, positions: dict[str, tuple[float, float]]) -> bytes:
    """positions is topology_renderer.compute_positions()'s output — the same canvas-space
    coordinates the structure image (and therefore the ControlNet-conditioned generation) used,
    so labels line up with the boxes Flux actually drew. Scales positions if the generated image
    isn't topology_renderer.CANVAS_SIZE (e.g. a workflow using different EmptySD3LatentImage
    dimensions)."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    scale_x = image.width / topology_renderer.CANVAS_SIZE[0]
    scale_y = image.height / topology_renderer.CANVAS_SIZE[1]

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.load_default(size=20)
    except TypeError:
        font = ImageFont.load_default()

    for hostname, (x, y) in positions.items():
        cx, cy = x * scale_x, y * scale_y
        text_bbox = draw.textbbox((0, 0), hostname, font=font)
        text_w, text_h = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
        pad = 6
        draw.rectangle(
            [cx - text_w / 2 - pad, cy - text_h / 2 - pad, cx + text_w / 2 + pad, cy + text_h / 2 + pad],
            fill=_BACKDROP_FILL,
        )
        draw.text((cx - text_w / 2, cy - text_h / 2), hostname, fill=_TEXT_FILL, font=font)

    composited = Image.alpha_composite(image, overlay).convert("RGB")
    buffer = io.BytesIO()
    composited.save(buffer, format="PNG")
    return buffer.getvalue()
