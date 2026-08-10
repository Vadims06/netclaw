# Border status report → Mac/Xcode session

**Snapshot: 2026-08-10 16:41 EDT.** Live status, refreshed as things change.
For the full investigation record see [BORDER-FINDINGS.md](BORDER-FINDINGS.md).

## Right now: the phone is connected and healthy

| | |
|---|---|
| iPhone `risk/1785078347014` | **connected**, authenticated, queue depth **0** |
| Current session | open since **16:36:56** |
| Previous session | 16:33:35, held **185s** |
| Heartbeat failures since 16:33 | **0** |
| Android `risk/1785267858182` | not connected, queue 0 (FCM push works) |

The phone is reconnecting on its own, answering the Border's 30s liveness
checks, and receiving pushes. Nothing is broken on the Border side.

## Queue replay is DONE — don't spend more time on it

All 5 backlogged heartbeats delivered at **16:33:39**, audited
`gait=f696e3b8fe`, queue depth now 0. Confirmed end-to-end twice (13:38 and
16:33). US1 is closed.

## The one measurement that should drive your instrumentation

Queue row 5 was the **same message** that timed out at 13:57 when the Border
dispatched it **86ms** after socket accept. At 16:33 the Border dispatched it
**3.087s** after accept and it delivered in under a second.

```
13:57:10.566  Accepted edge WS dial-in
13:57:10.652  Replaying 1 queued message(s)      ← 86ms after accept
13:57:40.663  FAILED (n2n/edge/message timed out — full 30s)

16:33:35.870  Accepted edge WS dial-in
16:33:38.957  Replaying 5 queued message(s)      ← 3.087s after accept
16:33:39.951  pushed/success gait=f696e3b8fe     ← all 5, under a second
```

Same message, same client, same method, same socket lifecycle.

> **86ms fails. 3.087s works.** The Dart client drops inbound frames that
> arrive too soon after the WebSocket opens. Measured, not theorised.

**So look for something taking on the order of seconds** to become ready after
socket open — not microseconds. Candidates:

- an `await` on secure storage before subscribing to the socket stream
- a deferred `.listen()` on the WebSocket
- handler-map registration sitting behind a `Future` chain

The fix is to subscribe to inbound **first** and buffer whatever arrives until
handlers are ready.

## Why the client fix is still required

The Border-side settle delay (`N2N_EDGE_REPLAY_SETTLE_S`, default 3s) protects
**queue replay only**. It cannot protect authentication:

```python
# FederationService.accept_edge_ws()
ch = EdgeChannel(ws, ...)
ch.nonce = nonce
await ch.notify("n2n/edge/challenge", {"nonce": nonce.hex()})   # ← FIRST frame
await ch.start()                                                #   read loop starts AFTER
logger.info("Accepted edge WS dial-in (awaiting device auth)")
```

The nonce challenge is the **very first frame**, sent before the channel is even
registered, and there is **no retransmit**. A client that isn't listening at
socket-open misses it, never sends `in2n/hello`, and hangs in
`awaiting device auth` forever.

Consistent with observation: the iPhone went a **full hour** (14:56:22 →
16:33:35) without authenticating, while the Android authenticated repeatedly
over the identical network path. **`auth_failure_bucket` is empty on every
attempt** — it never *fails* auth, it never *attempts* it. That rules out a
credential or enrollment problem, so the redeploy did not wipe the stored key.

## Two red herrings — don't chase these

1. **It is not iOS suspension.** The Android flaps identically (10s–96s holds,
   same `no close frame received or sent`) on the same Flutter codebase. An
   earlier `keepalive ping timeout` led me to an "app freezing" theory; the
   Android data kills it.
2. **`[n2n.edge[unauthenticated]]` on every close line is cosmetic** — the
   channel logger is never relabelled after successful auth. The `deregistered`
   line on the following row identifies the actual device.

## Corrections to earlier Border-side reports

Recorded so they don't mislead anyone reading back through the history:

- **"Dies in 18–57s" was wrong** — over-generalized from two samples. Observed
  holds since: 84s, 185s, and once **3520s (59 minutes)**.
- **Several short drops attributed to the iPhone were actually the Android.**
- **Source IP cannot distinguish the two devices** — both sit behind the same
  NAT (`142.169.80.82`). Device identity is only knowable after auth, when the
  member ID appears in the log.
- **A "sharp degradation" I flagged at 15:30** (5s and 6s holds) was a transient
  blip; the next session held 56s. Not a deploy regression.

## Reading the live event stream

```bash
journalctl --user -u netclaw-mesh -f | grep -E "Accepted edge|channel closed|Replay|stay queued|heartbeat failed|edge_push"
```

Ground truth for delivery is the audit trail, not the queue table:

```bash
journalctl --user -u netclaw-mesh | grep 'edge_push'
```

**Do not use `select count(*) from edge_message_queue`** to judge whether a
drain worked — delivered rows are pruned on the next enqueue, and a new
heartbeat lands every 30 minutes, so a non-zero count is usually
re-accumulation. Query with timestamps:

```sql
select queue_id, attempts,
       datetime(enqueued_at,'unixepoch','localtime') as enqueued,
       coalesce(datetime(delivered_at,'unixepoch','localtime'),'PENDING') as delivered
from edge_message_queue where member_id='risk/1785078347014' order by queue_id;
```

## Offer: on-demand push for correlation

While the phone is connected I can fire a push **immediately** on request and
hand back the exact Border timestamp, so you can line it up against your
`debugPrint` output instead of waiting for the 30-minute timer tick:

```bash
python3 scripts/edge-heartbeat.py --member risk/1785078347014
```

Ask and I'll run it and report the millisecond timing.

## What would most help back from the Mac side

1. Timestamped logs at: WS open, handshake complete, **read loop / `.listen()`
   live**, `in2n/hello` sent, and each inbound method dispatch by name. The gap
   between *WS open* and *read loop live* is the suspect — and we now know it is
   somewhere between 86ms and 3s wide.
2. Whether the app is foregrounded, backgrounded, or mid-redeploy at the
   timestamps of any drop.
3. Anything in the iOS console about termination, jetsam, or a watchdog firing.
