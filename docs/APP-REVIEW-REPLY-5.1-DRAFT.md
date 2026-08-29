# Reply draft — Guidelines 5.1.1(i) / 5.1.2(i)

Post this as a reply to Apple's review message in App Store Connect, then attach build 1.0.1 (3)
to the version and resubmit.

```
Thank you for the detailed feedback. We've made the following changes in build 1.0.1 (3):

1. The app now discloses, on the very first screen every device sees (before any question or
   capture can be sent), exactly what data is sent and why: any question the operator types or
   speaks, and any photo/video/audio capture they choose to send, is forwarded by their NetClaw
   Border to whichever AI language model the Border's operator configured at setup.

2. This is the Border operator's own decision, made when they set up their Border -- NetClaw does
   not require, default to, or control which AI provider is used. That may be a third-party cloud
   AI service, or a model the operator runs entirely locally and offline, in which case nothing
   about the operator's question ever leaves their own infrastructure.

3. The app now requires an explicit checkbox acknowledgment of this disclosure before the primary
   "Continue" action becomes enabled -- this is the app's one point of affirmative consent, since
   it is the single screen every device sees exactly once, before any data-sending feature is
   reachable.

4. The app's Privacy Policy (https://automateyournetwork.github.io/netclaw/privacy-policy.html)
   now includes a dedicated section identifying what is sent, who it is sent to, when this
   happens, how consent is obtained, and how to find the specific provider's own privacy practices
   (since that provider is chosen by each Border's operator, not NetClaw).

Please let us know if any further detail is needed.
```

## Notes

- Reference this same text (trimmed) in App Store Connect's App Review Information → Notes field
  if there's room, alongside the existing video/QR notes from the prior round -- don't delete those,
  since Apple may still want them for the completeness review.
- Build 1.0.1 (3) is already uploaded (Delivery UUID 5f5c77a2-91cd-4729-9ca1-d44e2ede5cd0) — attach
  it to the version once it finishes processing, then resubmit.
