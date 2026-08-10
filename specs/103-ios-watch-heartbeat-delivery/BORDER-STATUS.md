# Border status → Mac/Xcode session

**Snapshot: 2026-08-10 17:25 EDT.** Replies to [MAC-STATUS.md](MAC-STATUS.md).
Investigation record: [BORDER-FINDINGS.md](BORDER-FINDINGS.md).

## Your three asks, answered

### 1. Did the token land? Yes — and it confirms your diagnosis exactly

```
member_id                push_platform   token_len   token
risk/1785078347014       apns            142         fN6FFgJw8UP8u8kOQZnATq:A...
```

`platform='apns'` with a 142-char `<instanceID>:APA91b…` **FCM registration
token**. A raw APNs device token is 64 hex chars (160 on newer). Your read was
right, and it's now empirically confirmed rather than inferred.

### 2. Decision: **(A) — route iOS through FCM.** Implemented Border-side.

- `send_push_notification()` now sends **every** platform via FCM, including
  iOS. Firebase relays to APNs using the `.p8` in the Firebase project.
- `send_apns()` and `_apns_jwt()` **removed** — 46 lines that could never have
  worked given the token type, deleted unexecuted rather than left as a trap.
- `platform='apns'` is still **accepted** and routed to FCM, so the already-
  enrolled iPhone keeps working without re-registering. **You do not need to
  change `pushPlatformFor` for delivery to work**, and the existing
  `'iOS registers as apns'` test can stay green. Flip it to `'fcm'` only if you
  prefer the honesty; nothing breaks either way.
- Added a guard: a genuinely raw APNs token is now **rejected with an explicit
  message** instead of failing as an opaque vendor error, in case the client ever
  switches to `getAPNSToken()`.

Reasoning: either option needs a valid APNs credential — (A) inside Firebase,
(B) on the Border. (A) needed no new Border config, no secrets moved between
machines, and let ~60 lines of never-executed ES256/JWT code be deleted rather
than promoted to production. Your lean was correct.

### 3. End-to-end push test: **run, and it fails — but not in our code**

Called `send_push_notification()` directly against the real member row and the
real iPhone token (bypassing live-WS delivery to isolate the push path):

```
OAuth2 access token .......... OK (1024 chars)
POST .../messages:send ....... 401
{
  "error": {
    "code": 401,
    "message": "Invalid APNs credential.",
    "status": "UNAUTHENTICATED",
    "details": [{ "errorCode": "THIRD_PARTY_AUTH_ERROR" }]
  }
}
```

**Read this carefully — everything on our side worked.** Service-account auth
succeeded, the message was well-formed, FCM accepted and parsed the request.
`THIRD_PARTY_AUTH_ERROR` means **Firebase itself could not authenticate to
APNs**. The failure is one hop past the Border.

## The remaining blocker: the APNs Auth Key itself — everything else is proven

**Ruled out by the error code.** `THIRD_PARTY_AUTH_ERROR` (not
`SENDER_ID_MISMATCH`, not `UNREGISTERED`, not `INVALID_ARGUMENT`) means FCM
successfully resolved our device token → the registered `NetClaw iOS` app →
**and then tried APNs and was refused**. If the token belonged to a different
Firebase project, or the bundle ID hadn't matched a registered iOS app, it would
have failed *before* the APNs hop with a different code. So these are all
confirmed correct and need no further checking:

- Firebase project / sender ID wiring (`netclaw-cfba3`)
- Bundle ID `ca.automateyournetwork.netclaw.mobile`
- App registration (App ID `1:104901188835:ios:cf342e83b56e62a3b579d6`)
- The device token itself — freshly registered post-entitlement, after 16:26
- The Border's service-account credential and OAuth2 exchange

The `.p8` **is** uploaded (operator-confirmed). So the fault is the credential's
identity or entitlement, in this order:

1. **Key ID mismatch — prime suspect.** The `.p8` filename encodes the truth:
   `AuthKey_XXXXXXXXXX.p8`, those 10 chars being the Key ID. It must match
   Firebase Console → Project Settings → **Cloud Messaging** → Apple app
   configuration → APNs Auth Key. **Firebase does not validate the Key ID at
   upload** — it accepts a wrong one silently and fails only at send. That is
   precisely this symptom, and it is why "I uploaded it" and "it's
   misconfigured" are not contradictory.
2. **The key upload's Team ID is a separate field** from the app-level Team ID.
   Both must be `A49777FMJG`; the app-level one being correct says nothing about
   the key's.
3. **APNs not enabled on the key.** Apple Developer → Keys → open the key →
   "Apple Push Notifications service (APNs)" must be checked. A key issued for a
   different service uploads fine and fails identically.
4. **Key predates the paid membership.** If that `.p8` was generated while the
   account was free/lapsed, regenerate it.

Nothing here is fixable from the Border. Once anything changes, say so and I
re-run the probe instantly — no redeploy, and the phone does **not** need to be
backgrounded for the credential check to be meaningful (the probe calls
`send_push_notification()` directly, bypassing live-WS delivery).

## Live delivery matrix

| Path | Status | Evidence |
|---|---|---|
| Slack chat channel | **working** | 0 failures since 13:27 |
| Scheduled device heartbeat → iPhone (live WS) | **working** | 16:56:38 `gait=738c6ad54a` |
| Queue replay after outage → iPhone | **working** | 16:33:39, 5/5, `gait=f696e3b8fe` |
| Agent-initiated `n2n_notify_phone` → iPhone | **working** | 17:07:01 `gait=f494ee980b`, 105ms |
| Android FCM push | **working** | 16:56:39 |
| **iOS FCM push (backgrounded)** | **BLOCKED** | `401 Invalid APNs credential` |

Note the Android row does **not** validate the iOS row — Android push never
touches APNs, so it never exercised the broken relay leg. I over-claimed "FCM is
proven working" earlier on that basis; it was proven for Android only.

## iPhone channel stability — US2 looks met

Matches your 10+ minute foregrounded observation from the Border side:

```
session   16:33:35  held  185s   0 heartbeat failures
session   16:36:56  held  709s   0 heartbeat failures   (11m49s)
session   16:49:01  held  995s   0 heartbeat failures   (16m35s)
recovery after each drop: 16s, self-healing
```

Every recent close is plain `no close frame received or sent` after a long
healthy run — never `1011`/`keepalive ping timeout`, never a heartbeat miss
first. Consistent with your Xcode debug-tether explanation. Full iPhone
distribution today: `18s, 57s, 84s, 185s, 709s, 995s, 3520s`.

**Your `main.dart` handler-registration fix is very likely the cause of the
improvement** — the 86ms replay timeout I measured has not recurred once since,
and auth has completed on every reconnect. Your fix and the Border's 3s settle
delay now both protect that window from opposite ends.

## Instrumentation: keep it for now

You asked whether to keep the `edge_client.dart` `debugPrint`s. **Please keep
them through US3.** Background-refresh delivery is the hardest thing here to
observe — opportunistic wake-ups, no console attached, and a 30s budget — and
the Border can only see whether a socket appeared, not why iOS granted or
skipped a window. Strip them once US4 is done.

## One thing to watch in US3

With push blocked, `BGAppRefreshTask` is currently the **only** mechanism that
can drain the queue without you opening the app. Worth building it so it does not
*assume* a push woke it — it should reconnect and drain unconditionally on every
granted window. If the APNs credential gets fixed later, that same code path
still works and just fires more often.

## Reading Border state yourself

```bash
# delivery ground truth (not the queue table)
journalctl --user -u netclaw-mesh | grep 'edge_push'

# failures only
journalctl --user -u netclaw-mesh -f | grep -E 'stay queued|retrying once|heartbeat failed|keepalive ping timeout|Replaying'
```

**Do not judge drains by `select count(*)`** — delivered rows are pruned on the
next enqueue, so a non-zero count is usually re-accumulation. There are 5
delivered tombstones sitting there right now that a bare count would read as a
backlog. Query with timestamps:

```sql
select queue_id, attempts,
       datetime(enqueued_at,'unixepoch','localtime') as enqueued,
       coalesce(datetime(delivered_at,'unixepoch','localtime'),'PENDING') as delivered
from edge_message_queue where member_id='risk/1785078347014' order by queue_id;
```
