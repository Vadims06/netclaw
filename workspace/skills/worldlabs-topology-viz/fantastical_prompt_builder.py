"""
Composes a bounded-length World Labs Marble text prompt from a TopologySnapshot.

REWRITTEN after live evidence gathered in production (2026-09-03, six real Marble generations,
credits actually spent): the original version of this module summarized the topology as aggregate
role counts ("2 routers, 2 switches... connected in a typical hierarchical pattern"). That
consistently produced a visually coherent but completely untraceable-to-real-data result — "just
another fantasy world," confirmed by directly inspecting the generated images. A live side-by-side
comparison showed that describing each device individually and each real link explicitly
("R1's tower connects down to SW1...") makes the model visibly attempt to reflect the real
structure (its own caption correctly named every real hostname), where an aggregate summary gave
it nothing concrete to anchor to. So this module now emits one clause per device and one clause per
link — a small graph description in prose — instead of a count-based summary. See
specs/122-worldlabs-topology-viz/research.md R9/R10 for the full account.

This module makes no external call and is deterministic for a given (snapshot, theme) pair
(FR-002/FR-003): the same snapshot with a different theme produces a new prompt describing the same
real connectivity pattern.

Deliberately does NOT ask Marble to inscribe hostnames as legible text/sigils on structures —
also confirmed live: text rendering is unreliable (a real attempt at "eth0/1" came back as garbled
"Fco/1"), a known, model-class-wide limitation, not something prompt wording fixes. Real hostnames
appear only in this prompt's own language (which shapes structure and captions), never as an
instruction to paint words into the scene.

Relies entirely on topology_model.py's sanitize_metadata having already stripped
credentials/secrets/config content from any Device.metadata before this module ever sees it — this
module does not re-sanitize, it only describes role/hostname/connectivity. It never reads
Device.metadata at all, so there is nothing to leak even if a caller forgot to sanitize.
"""

from topology_model import TopologySnapshot

# Same bound as spec 120's prompt_builder.py, for the same reason: past this length a prompt stops
# helping a generative model and starts hurting it.
_MAX_PROMPT_CHARS = 900

# Rough vertical tier per role — routers/firewalls read as "core" (top), switches/load_balancers as
# "distribution" (middle), everything else (clients, unclassified) as "access" (ground). This is a
# generalization beyond the exact 8-device lab this was validated against, not a hard rule.
_TIER_BY_ROLE = {
    "router": "top",
    "firewall": "top",
    "switch": "middle",
    "load_balancer": "middle",
}

_ROLE_SHAPE = {
    "router": "a towering cybernetic monolith lined with pulsing status lights",
    "firewall": "a fortified, armored bastion structure",
    "switch": "a wide, hex-plated hub platform hovering in the haze",
    "load_balancer": "a rotating four-armed distributor spire",
    "client": "a small, glowing terminal-pod",
    "unclassified": "a glowing waypoint structure",
}

# Applied when the caller specifies no theme (FR-003's Assumptions: "defaulting to a reasonable
# generic theme... when the user does not specify one").
DEFAULT_THEME = "a fantastical cyberpunk world, vivid neon color, dramatic volumetric lighting"


def _shape_for(role: str) -> str:
    return _ROLE_SHAPE.get(role, _ROLE_SHAPE["unclassified"])


def _tier_for(role: str) -> str:
    return _TIER_BY_ROLE.get(role, "ground")


def build_prompt(snapshot: TopologySnapshot, theme: str | None = None) -> str:
    """FR-002/FR-003: compose a themed generation prompt that describes the topology's actual
    devices and real links individually — not as an aggregate summary — so the resulting world's
    structure is recognizably driven by this specific topology. Makes no claim about precise
    geometry or legible text (Marble has neither mechanism — research.md R1/R9/R10)."""
    theme = theme or DEFAULT_THEME

    if not snapshot.devices:
        # Reachable only if this is called directly (unit tests) with zero devices — the real
        # workflow never reaches this, since render_structural rejects an empty snapshot first
        # (spec.md Edge Cases correction) and the preview stops there.
        return f"A fantastical, explorable 3D world themed as {theme}, with no locations to place yet."

    device_clauses = []
    for device in snapshot.devices:
        tier = _tier_for(device.role)
        shape = _shape_for(device.role)
        device_clauses.append(f"At the {tier} tier, {device.hostname} is {shape}.")

    link_clauses = []
    for link in snapshot.links:
        link_clauses.append(
            f"A glowing conduit connects {link.a} down to {link.b}, pulsing with streams of light."
        )

    body = " ".join(device_clauses + link_clauses) if link_clauses else " ".join(device_clauses)

    prompt = (
        f"A single cohesive, fully realized 3D world themed as {theme} — no flat images, no 2D "
        f"diagrams, no readable text or writing anywhere in the scene, only pure 3D geometry. Its "
        f"structure is inspired by a real network topology: {body} Render this as one seamless "
        f"explorable environment where every named connection above is visibly present."
    )

    if len(prompt) > _MAX_PROMPT_CHARS:
        prompt = prompt[: _MAX_PROMPT_CHARS - 1].rstrip() + "…"

    return prompt
