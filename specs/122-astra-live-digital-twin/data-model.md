# Phase 1 Data Model: Astra Live Digital Twin

Defined once in `models/twin_schema.py` (frozen — see plan.md's Project Structure) and imported by
both `mcp-servers/astra-twin-mcp/` and `ui/netclaw-visual/server.js`'s twin routes as the single
source of truth for the wire format. Neither side may redefine these shapes independently.

## TwinNode

Represents one device in the live lab topology.

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable identifier (device hostname/testbed name) — must match the identity used by the underlying pyATS/CML MCP tool responses, so deltas can be diffed by identity, not by position. |
| `label` | string | Display name shown in the HUD. |
| `vendor_platform` | string | e.g. `ios`, `iosxe`, `nxos` — informational only; no vendor-specific rendering logic lives here (Constitution VI). |
| `status` | enum: `up` \| `down` \| `unreachable` | Derived from the collector's most recent successful/failed poll of that device. |
| `last_seen` | ISO 8601 timestamp | When this node's state was last confirmed against the lab — backs FR-010's freshness indicator. |

## TwinLink

Represents one observed adjacency between two nodes.

| Field | Type | Notes |
|---|---|---|
| `id` | string | Deterministic from the (unordered) pair of endpoint interface identifiers, so the same physical link always diffs to the same id across polls. |
| `source_node_id` / `target_node_id` | string | References `TwinNode.id`. |
| `source_interface` / `target_interface` | string | Interface names on each end, for label/tooltip use. |
| `state` | enum: `up` \| `down` | |
| `last_seen` | ISO 8601 timestamp | |

## DeltaKind

`node_added` \| `node_removed` \| `node_status_changed` \| `link_added` \| `link_removed` \|
`link_state_changed`

## TwinDelta

One observed change since the collector's previous poll.

| Field | Type | Notes |
|---|---|---|
| `seq` | monotonically increasing integer | Lets a reconnecting client (or `get_deltas(since_seq=...)`) ask "what changed since I last saw sequence N," and lets `harness/visual_verify.py` assert a specific delta was actually applied, not just that *some* update happened. |
| `kind` | `DeltaKind` | |
| `node` | `TwinNode` \| null | Populated for node-kind deltas. |
| `link` | `TwinLink` \| null | Populated for link-kind deltas. |
| `observed_at` | ISO 8601 timestamp | When the collector's poll produced this delta — distinct from when a client receives it. |

## TwinSnapshot

Full current state, served by `GET /api/twin/snapshot` for first load and reconnect-catch-up.

| Field | Type | Notes |
|---|---|---|
| `nodes` | `TwinNode[]` | |
| `links` | `TwinLink[]` | |
| `seq` | integer | The sequence number this snapshot is current as of — a client fetching this snapshot then subscribes to `/ws/twin` and applies only deltas with `seq > snapshot.seq`, so no delta is ever double-applied or dropped across the handoff. |
| `testbed_identity` | string | Which lab testbed this snapshot came from — rendered by the HUD so an operator always knows what they're looking at (supports SC-002's auditability). |

## Astra Twin (iN2N member — extension, not a new entity)

Extends the existing `member` row shape (spec 056/066) already stored in
`~/.openclaw/n2n/federation.db`. No new table.

| Field | Type | Notes |
|---|---|---|
| `model_provider` | string, nullable | **New column** on the existing `member` table (research.md R5). `"claude"` (implicit default for every pre-existing member) or `"openai"` (Astra Twin). |
| *(all existing member fields)* | — | `node_type`, `pinned_key`, `scope`, `health`, `state`, etc. — reused unchanged (spec 056/066/067). |

## State Transitions

- A `TwinNode`'s `status` moves `up → unreachable` when a poll fails to reach it and `unreachable →
  down` is not a modeled transition — "down" is reserved for a device the collector can positively
  confirm is administratively/operationally down (e.g., interface shutdown reported by a *reachable*
  neighbor), while "unreachable" means the collector itself cannot get a read. This distinction is
  what lets the HUD show FR-010's staleness indicator correctly: a node can go stale (unreachable)
  without the twin falsely claiming that node's own state changed.
- A `TwinLink` transitions `up → down` and `down → up` only on confirmed state from a poll of at
  least one reachable endpoint; a link whose *both* endpoints are unreachable is not asserted `down`
  — it is left at last-known state, carried with a stale `last_seen`, consistent with the collector
  never guessing device state (Constitution I: "Device state MUST NOT be assumed or guessed").
