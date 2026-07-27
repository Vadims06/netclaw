/**
 * Node rendering and the four health treatments (FR-009a, FR-009b, FR-029a).
 *
 * Consumes orgchart/ output. Never classifies health, chooses categories, or
 * computes positions — those answers arrive already decided (see
 * contracts/layout-contract.md, consumer contract).
 *
 * The encoding rule (FR-009a): each state differs in FORM, COLOUR TEMPERATURE
 * and MOTION at once, never opacity alone. Motion is deliberately REDUNDANT
 * (R8) — it is added on top of an already-sufficient form+colour distinction,
 * so suppressing it for prefers-reduced-motion (FR-032c) cannot collapse the
 * encoding. That is also why SC-007 (greyscale) and SC-010 (reduced motion)
 * test the same underlying property.
 */

import * as THREE from 'three';

/**
 * Health treatments. Form and colour alone must separate all four — verified
 * by SC-007's greyscale test, which is why `shape` and `lightness` differ
 * across every row and not just `color`.
 */
export const TREATMENTS = {
  HOT: {
    shape: 'sphere',
    color: 0x37d67a,
    emissive: 0x0f7a3c,
    lightness: 0.82,
    scale: 1.0,
    pulse: 0.10,          // alive: gentle breathing
    label: 'Running now',
  },
  WARM: {
    shape: 'rounded',
    color: 0x6fa8dc,
    emissive: 0x1d3f5c,
    lightness: 0.58,
    scale: 0.86,
    pulse: 0.0,           // idle: still
    label: 'Seen recently, idle',
  },
  COLD: {
    shape: 'flat',        // a disc reads as inert next to a lit sphere
    color: 0x3a4654,
    emissive: 0x0a0f16,
    lightness: 0.26,
    scale: 0.68,
    pulse: 0.0,
    label: 'Never started — inert by design',
  },
  FAULT: {
    shape: 'ring',        // a broken outline, unmistakable at any zoom
    color: 0xff5d5d,
    emissive: 0x8b1a1a,
    lightness: 0.66,
    scale: 1.06,          // FR-009b: most salient state after HOT
    pulse: 0.22,          // urgent, faster and deeper than HOT's breathing
    label: 'Was reachable, now unreachable',
  },
};

export const KIND_SCALE = { border: 2.2, peer: 1.35, member: 1.0, edge: 1.15 };

/** Shared geometries — created once, reused across every node (FR-029a). */
function buildGeometries() {
  return {
    sphere: new THREE.SphereGeometry(1.6, 24, 18),
    rounded: new THREE.SphereGeometry(1.5, 16, 12),
    flat: new THREE.CylinderGeometry(1.5, 1.5, 0.35, 20).rotateX(Math.PI / 2),
    ring: new THREE.TorusGeometry(1.5, 0.42, 10, 24),
    border: new THREE.IcosahedronGeometry(2.4, 1),
    peer: new THREE.OctahedronGeometry(1.8, 0),
    edge: new THREE.BoxGeometry(1.5, 2.6, 0.5),
  };
}

/**
 * Build every node mesh for a computed layout.
 *
 * @param {Array<object>} layoutNodes from computeLayout().nodes
 * @param {(text:string)=>object} makeLabel host label factory (CSS2D), reused per FR-028
 * @returns {{group: THREE.Group, entries: Array<object>, dispose: Function}}
 */
export function buildNodes(layoutNodes, makeLabel) {
  const group = new THREE.Group();
  group.name = 'orgchart-nodes';
  const geometries = buildGeometries();
  const materials = [];
  const entries = [];

  for (const node of layoutNodes || []) {
    const treatment = TREATMENTS[node.health] || TREATMENTS.COLD;

    let geometry;
    if (node.kind === 'border') geometry = geometries.border;
    else if (node.kind === 'peer') geometry = geometries.peer;
    else if (node.kind === 'edge') geometry = geometries.edge;
    else geometry = geometries[treatment.shape] || geometries.sphere;

    const isStructural = node.kind === 'border' || node.kind === 'peer';
    const color = isStructural ? colorForStructural(node) : treatment.color;

    const material = new THREE.MeshStandardMaterial({
      color,
      emissive: isStructural ? 0x102030 : treatment.emissive,
      emissiveIntensity: node.health === 'FAULT' ? 1.5 : 0.85,
      roughness: node.health === 'COLD' ? 0.95 : 0.35,
      metalness: node.health === 'COLD' ? 0.05 : 0.45,
    });
    materials.push(material);

    const mesh = new THREE.Mesh(geometry, material);
    const scale = (KIND_SCALE[node.kind] || 1) * (isStructural ? 1 : treatment.scale);
    mesh.scale.setScalar(scale);
    mesh.position.set(node.position.x, node.position.y, node.position.z);
    mesh.userData = { nodeId: node.id, kind: node.kind, payload: node.payload, node };

    // Label: never blank — orgchart/normalize guarantees a fallback (FR-015).
    let text = node.label;
    if (node.kind === 'member' && node.toolCount > 0) text += `  ·${node.toolCount}`;
    if (node.kind === 'edge' && node.heartbeatAgeS != null) text += `  ${formatAge(node.heartbeatAgeS)}`;

    const label = makeLabel(text);
    label.position.set(0, -(scale * 1.6 + 1.4), 0);
    mesh.add(label);

    group.add(mesh);
    entries.push({ node, mesh, material, label, baseScale: scale, pulse: treatment.pulse });
  }

  return {
    group,
    entries,
    dispose() {
      for (const g of Object.values(geometries)) g.dispose();
      for (const m of materials) m.dispose();
    },
  };
}

function colorForStructural(node) {
  if (node.kind === 'border') return 0xffc857;
  if (node.severed) return 0x6b3f3f;
  if (node.channelState === 'unreachable' || node.channelState === 'reconnecting') return 0x5b7fa6;
  return 0x65c3ff;
}

/**
 * Human-readable last-seen age for edge nodes (US2 AC2) — legible on the node
 * itself, without opening the detail panel.
 *
 * @param {number} seconds
 * @returns {string}
 */
export function formatAge(seconds) {
  const s = Number(seconds);
  if (!Number.isFinite(s) || s < 0) return '';
  if (s < 90) return `${Math.round(s)}s ago`;
  if (s < 5400) return `${Math.round(s / 60)}m ago`;
  if (s < 172800) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

/**
 * Per-frame animation. Motion is redundant to the encoding (R8), so honouring
 * reduced motion simply skips this entirely (FR-032c).
 *
 * @param {Array<object>} entries from buildNodes
 * @param {number} elapsed seconds
 * @param {boolean} reducedMotion
 */
export function animateNodes(entries, elapsed, reducedMotion) {
  if (reducedMotion) return;
  for (const e of entries) {
    if (!e.pulse) continue;
    // FAULT beats faster than HOT: urgency reads differently from liveness.
    const rate = e.node.health === 'FAULT' ? 4.2 : 1.6;
    const factor = 1 + Math.sin(elapsed * rate) * e.pulse;
    e.mesh.scale.setScalar(e.baseScale * factor);
  }
}

/**
 * Apply search highlight/dim in place (FR-031a) — never hides, never re-packs.
 *
 * @param {Array<object>} entries
 * @param {(node:object)=>boolean} matches
 * @param {boolean} searching
 */
export function applyHighlight(entries, matches, searching) {
  for (const e of entries) {
    const hit = !searching || matches(e.node);
    e.material.opacity = hit ? 1 : 0.18;
    e.material.transparent = !hit;
    e.material.emissiveIntensity = hit ? (e.node.health === 'FAULT' ? 1.5 : 0.85) : 0.05;
    if (e.label?.element) e.label.element.style.opacity = hit ? '1' : '0.2';
  }
}
