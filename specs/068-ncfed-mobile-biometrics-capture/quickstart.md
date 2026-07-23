# Quickstart: NCFED Mobile Biometrics and Capture

## Manual walkthrough

1. **Register capture capabilities**: from the app's Settings, enable photo + audio capture,
   disable video. Confirm the Border's view of the member's `scope` shows only the enabled
   two — video is absent entirely, not present-but-disabled.
2. **Trigger a `requires_approval` grant**: confirm a prompt reaches the phone (foreground) or
   a push notification (backgrounded) with device/change/reason/agent/risk visible.
3. **Approve with biometric**: tap approve, complete Face ID/BiometricPrompt, confirm the
   audit trail shows `resolved_via=biometric`.
4. **Fail the biometric**: cancel/fail authentication; confirm the approval remains pending —
   not approved, not denied.
5. **Resolve via CLI while a phone prompt is pending**: `netclaw` CLI `n2n_approve`; confirm
   the phone reflects it as already resolved rather than staying actionable.
6. **Phone-initiated capture**: take a photo, attach it to a typed question; separately, send
   a bare photo with no text. Confirm both reach the Border and produce a response reflecting
   the image.
7. **Border-requested capture**: submit a request needing a phone-advertised capability;
   confirm the phone's native capture UI activates and the result flows back attributed to
   the phone. Decline the OS permission prompt on a second attempt; confirm an explicit
   failure, not a hang.
8. **Disconnected phone**: with the phone offline, request its capture capability from the
   Border; confirm a clean "capability not available" failure, not a hang.

## Automated checks

```bash
cd ~/netclaw
python3 -m pytest tests/n2n/test_edge_approval.py tests/n2n/test_edge_capture.py -q

cd mobile/netclaw-mobile
flutter test
```

## Success signals (from spec)

- SC-001/SC-002: biometric resolution recorded 100%; 0% resolved without successful local auth.
- SC-003/SC-004: phone-initiated capture reaches the Border 100% (healthy connection);
  Border-requested capture never silently hangs (0%).
- SC-005: no successful biometric auth ever exposes the enrollment key (verified by code
  review — `local_auth` and `EdgeIdentity` share no class/state, see research D7).
- SC-006: declined OS permission produces an explicit failure in both directions.
- SC-007: 100% of captures fit the existing 16 MiB channel bound (capped at capture time).
- SC-008: a disabled capture type is verifiably absent from the Border's view of `scope`.

## T028: automated coverage as of implementation — mapped to SC-001…SC-008

Full n2n suite: `python3 -m pytest tests/n2n -q` → 266 passed, zero regressions
(the 9 new tests below plus every 052–067 test unchanged). Mobile suite:
`flutter test` → 45 passed (13 new for this feature, plus every 066/067 test
unchanged).

| SC | Automated coverage | Notes |
|----|---------------------|-------|
| SC-001/SC-002 | `test_edge_approval.py::test_edge_approval_resolve_calls_existing_resolve_approval_unchanged`, `::test_first_resolution_wins_cli_then_phone`; `approval_client_test.dart`'s "a failed/cancelled biometric attempt never triggers n2n/edge/approval_resolve" (parameterized over every non-`true` return: `false`, an exception, a delayed `false`) | `resolve_approval`'s pre-existing `WHERE status='pending'` clause is what makes "first resolution wins" true regardless of biometric vs CLI order — proven directly, not assumed. Whether a *specific* device's Face ID/fingerprint sensor itself fired is outside what CI can check; the Dart test instead proves the wire call structurally never fires without the `authenticate` callback returning `true`. |
| SC-003/SC-004 | `test_edge_capture.py::test_delegate_resolves_edge_node_and_calls_capture_not_tasks_submit`, `::test_declined_capture_surfaces_as_explicit_failure`; `capture_client_test.dart`'s full "captureAndAsk (US2, phone-initiated)" and "n2n/edge/capture handler (US3, Border-requested)" groups (7 tests) | Both directions' declined/cancelled path returns an explicit `decision: 'declined'`/raises, never an empty success — directly exercised, not inferred. |
| SC-005 | Not independently automated — verified by code review (research D7): `approval_client.dart`/`capture_client.dart`/`approvals_screen.dart` import nothing from `edge_identity.dart`, and `grep -rn EdgeIdentity` across the new 068 files returns no hits. | A negative/absence property; a test asserting "this file doesn't import X" would be weaker than the review already performed. |
| SC-006 | `capture_screen.dart`'s `_init()`/`_shutter()` catch blocks (camera-permission/capture-failure → explicit `_error` state, no silent hang) plus `capture_client_test.dart`'s declined-capture cases on both sides | The real OS permission dialog itself isn't invokable under `flutter test`; T030's manual walkthrough covers the actual dialog. |
| SC-007 | `test_edge_capture.py::test_declined_capture_surfaces_as_explicit_failure` (server-side cap, via `kMaxCaptureBytes`-equivalent check in `delegate_to_edge`'s wire contract), `capture_client_test.dart`'s "a capture exceeding the size cap is refused, never sent" and "an oversized capture is declined server-side too, not just client-side" | Both the phone-side pre-check and the (defense-in-depth) handler-side check are exercised, not just one. |
| SC-008 | `test_edge_capture.py::test_disabled_capability_invisible_to_router`, `::test_set_capture_capabilities_rejects_unknown_name`; `capability_registration_test.dart`'s all 3 cases | Direct coverage — inspects `RiskRouter.candidates()`/`member.scope` itself, not just an attempted request's outcome. |

### T030 — manual-only, deferred

The full numbered walkthrough above needs real biometric hardware (Face ID/
fingerprint sensor) and a real camera — neither exists in this Linux/WSL2
dev environment's Android emulator (the emulator's virtual camera and
`local_auth`'s biometric enrollment both require host-level setup this
session doesn't have). Steps 1, 5, and 8 (capability registration/toggle,
CLI-resolves-while-phone-pending, disconnected-phone capability-not-available)
are fully covered by the automated tests above and don't need to be repeated
manually. Steps 2-4, 6-7 (the actual push arriving, a real biometric
success/failure, and a real photo reaching the Border) require the Mac/iOS
session or a properly provisioned Android device and should be run there.
