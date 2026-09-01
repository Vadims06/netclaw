# Agentic Operations Goes Mobile

### The official NetClaw Mobile app is here — drive your infrastructure securely right from your phone, or even your watch.

A few months ago I wrote about wanting my network agent to live in my pocket, with nobody in the
middle. Today that stopped being a wish. **NetClaw Mobile is live on the Apple App Store**, and I
want to walk you through what it actually does, why it exists, and why I think the way it's built
says something bigger about where network automation is headed.

**[Download NetClaw Mobile on the App Store](https://apps.apple.com/us/app/netclaw/id6800859524)**

## Why mobile, why now

We stopped being desk-bound a long time ago, and network operations never really caught up. Since
the pandemic reshuffled where and how we work, "at the office, on the VPN, on the laptop" stopped
being the default for a huge number of us — and yet most of the tooling we use to actually run
infrastructure still quietly assumes exactly that. An outage doesn't wait for you to get back to a
desk. A pending change doesn't politely hold off until you're back on the VPN. We're on the move —
on the road, in an airport, at a kid's soccer game — far more of the time than the tools we use
were ever designed to assume. Every other part of our lives went mobile-first years ago: banking,
healthcare, commerce. Infrastructure operations, for the most part, didn't. That gap is exactly
what this is for.

## The problem I kept running into

Most of what passes for "mobile network automation" today is really just ChatOps wearing a
different hat — you ask a bot a question inside Slack, Discord, Microsoft Teams, WhatsApp,
Telegram, or Webex, and something on the other end eventually answers. That was NetClaw's own
first six months, too. It works, but it comes with real limitations that have nothing to do with
the automation itself and everything to do with where the conversation lives:

- Your infrastructure conversation is a guest inside somebody else's cloud, subject to somebody
  else's retention policy, somebody else's breach history, somebody else's outage.
- A generic chat bot integration was never purpose-built for "approve this config change with
  biometrics" or "here's a photo of the rack, what's wrong with it" — those are bolted-on
  afterthoughts, not first-class flows.
- There's no hardware-backed device identity. A bot token can leak. A phone's Secure Enclave can't.
- None of it is designed to work when you'd rather not route sensitive infrastructure commands
  through a platform whose entire business model is somebody else's data.

I didn't want to build another bot for another chat platform. I wanted my phone to talk directly
to *my* agent, running on *my* infrastructure, with nothing in between.

## What NetClaw Mobile actually is

NetClaw Mobile is a **companion app** — deliberately lightweight, because it isn't the agent
itself. The real intelligence lives on your own self-hosted **NetClaw Border**, the same agent
you'd talk to from a terminal or a lab session. The phone (and watch) app is just a secure,
direct, encrypted window into it.

That "lightweight" claim isn't marketing fluff — the shipping app is roughly 8,300 lines of Dart
and 2,850 lines of native Swift (the Watch app, widgets, Live Activities, Siri integration), and
the installed app itself is about 25MB. No embedded model, no bundled inference engine, no bloat.
It doesn't need any of that, because it isn't the thing doing the thinking.

**Not one byte of a conversation touches Slack, Discord, Webex, or anybody else's cloud.** Your
phone and your Border talk to each other directly, over a connection you control, secured by a key
that never leaves your device's hardware keystore — Secure Enclave on iPhone. It's trust-on-first-
use, then pinned: you scan a one-time QR code (or enter a manual enrollment code) to introduce your
phone to your Border exactly once, and from then on the two of them recognize each other
cryptographically, the same way SSH host keys work, not the same way an OAuth token you have to
trust a third party to protect works.

## A quick tour of the app

Before I get into the deeper stuff, here's plainly what's actually on the screen, top to bottom:

- **Welcome** — a one-time explainer screen: what this app is, what it needs (your own Border),
  and what it doesn't do (there is no NetClaw account to sign up for).
- **Enroll** — point your camera at your Border's QR code, or type the details in by hand if
  scanning isn't practical. One time, ever, per device.
- **Dashboard** — connection status at a glance, your device's identity, an unread count, a
  pending-approvals count. The "is everything okay" screen.
- **Chat** — type or speak a question to your Border's agent and get a real answer back. Search
  your own chat history. Copy or share any answer straight from the message itself. If a question
  failed, retry it with one tap instead of retyping it.
- **Feed** — your Border's heartbeats, alerts, and pushed notifications, in one running list.
  Search it, acknowledge an item once you've seen it, delete what you don't need to keep.
- **Approvals** — anything your Border wants to do that needs a human yes first. Approve or deny,
  gated by Face ID or Touch ID.
- **Settings** — toggle which capture types (photo/video/audio) your Border is allowed to request,
  check your notification status, turn on an app-lock with a grace period, switch appearance, find
  the privacy policy, and remove this device's enrollment if you ever need to.
- **The Watch** — the same core ideas, sized for a wrist: Status (a live heartbeat summary),
  Approvals, Feed, Ask, and History, each independently reachable, each relayed securely through
  your phone.

Nothing exotic. It looks like an app, because it is one — the interesting part is what's
underneath it.

## The part most people won't see: this started as a protocol, not an app

*(Fair warning: this section gets genuinely technical. If you just want to know what the app does,
skip ahead to the next section — nothing below is required to understand or use NetClaw Mobile.)*

Here's something I want to be completely clear about, because it's easy to assume the causality
runs the other way: **the mobile app did not come first and get a security model bolted on
afterward. The protocol came first, and the mobile app is one of its consumers.**

That protocol is **NCFED — the NetClaw-to-NetClaw Federation Protocol** — and it's not just an
internal design doc. It's a real IETF Internet-Draft:
**[draft-capobianco-ncfed-00](https://www.ietf.org/archive/id/draft-capobianco-ncfed-00.html)**.

NCFED exists to let independent AI network-engineering agents — potentially run by entirely
different organizations, on entirely different reasoning stacks — discover each other's
capabilities, invoke each other's tools, and delegate tasks, securely, over the wire, without
sharing code or trusting a shared intermediary. It shares a single TCP port with BGP-4 and a data
plane tunnel by inspecting the first octet of an incoming connection. Peers identify themselves
with BGP-style identities — a 4-octet AS number and a 4-octet router ID — in a 13-octet binary
handshake, before any encryption or semantics enter the picture. The channel then upgrades to TLS
1.3 in place, and each side proves possession of its identity key with an ECDSA signature over a
server-issued nonce, under one of two trust models: domain-verified (a real, publicly trusted
certificate) or pinned (trust-on-first-use, then locked to that exact key forever after). Every
message beyond that point is a length-prefixed frame carrying JSON-RPC 2.0, mapping cleanly onto
MCP tool-invocation and A2A task-delegation semantics.

NCFED defines two federation modes. **eN2N** is external — two different operators' Borders,
federating by mutual, explicit, out-of-band consent. **iN2N** is internal — one operator's own
hub-and-spoke mesh, where only the Border (the hub) accepts inbound connections, and spokes join
via a single-use enrollment token plus key pinning.

If that description of iN2N sounds exactly like how your phone enrolls against your Border —
that's not a coincidence, that's the point. **The phone is just another iN2N peer.** The QR-code
enrollment, the single-use token, the trust-on-first-use key pinning I described above, the "your
phone and your Border talk directly, nobody in the middle" claim — none of that is mobile-app-
specific security theater. It's the exact same wire protocol and trust model NCFED already defined
for a Border coordinating any of its other members, applied to a phone because a phone is,
architecturally, just another member. The app didn't invent a security model and hope it was
sound. It inherited one that already had to work for machine-to-machine federation first, where
there's no forgiving human tapping "Cancel" on a suspicious cert warning.

## The stuff I'm genuinely proud of

I could talk about every one of the dozens of specs that went into getting here, but let me
highlight the half-dozen that I think best capture what this app is actually for:

**Siri is now, against all odds, actually useful. ;)** For years "Hey Siri" mostly meant timers,
weather, and the occasional dad joke. Now you can genuinely say **"Hey Siri, ask NetClaw is BGP up
on the core switch"** — out loud, hands-free, walking into a meeting — and instead of the old
"sent to NetClaw, I'll let you know," Siri waits for your Border's real answer and speaks it back
to you, tuned against real, measured response times so the window is honest instead of
generous-and-useless. Getting a straight, correct, spoken answer out of Siri might be the single
most quietly satisfying bug I fixed this year.

**Your watch is a first-class citizen, not an afterthought.** The Apple Watch companion isn't a
scaled-down phone screen — it shows live Border health, lets you review and approve pending
actions right from your wrist, and answers questions independently, relayed securely through your
phone.

**Biometric-gated approvals, with real captures.** When your Border wants to make a change, you
approve or deny it with Face ID or Touch ID — the same security posture as unlocking your banking
app, applied to unlocking a config push. And when you need to show your agent something physical —
a blinking port LED, a cable run, a rack — you can send a photo, video, or audio capture straight
through the same encrypted channel.

**It lives where you already look.** Home Screen widgets, Lock Screen widgets, Control Center
widgets, and Live Activities that track a long-running task in real time, right in your Dynamic
Island. A Watch complication you can reach with a double-tap. None of this required leaving the
platform's own native surfaces to fake something custom.

**Push notifications that actually work end-to-end**, even when the app is fully closed — your
Border can reach you the moment it has an answer or needs a decision, not just when you happen to
have the app open.

**And I built the whole App Store journey in the open, including the parts that didn't go
smoothly.** Real review rejections, real fixes, real privacy disclosures written honestly instead
of vaguely — the full spec for how this app actually reached the store, mistakes included, is
already sitting in the same public repo as everything else, because I think that's more useful to
other builders than a highlight reel.

## What this actually looks like in the wild

A few real shapes this takes, not hypotheticals:

- You're walking into a meeting with two minutes to spare and a nagging feeling. "Hey Siri, ask
  NetClaw if BGP is stable on the core switches." You get a real, spoken answer before you sit
  down — not a "sent, I'll let you know."
- A BGP session flaps three times in five minutes at 11pm. Your Border already applied its own
  auto-remediation and logged it to the Feed. You see it, acknowledge it, and go back to sleep —
  no page, no laptop, no VPN client to open first.
- You're standing in a server room, staring at a rack, and something looks wrong. You snap a photo
  right there in the app and send it through the same encrypted channel — no separate "email it to
  yourself later and forget."
- Your Border wants to push a config change it's confident about but shouldn't do unattended.
  A Watch notification lands on your wrist mid-walk; you review it and approve with a glance and a
  double-tap, without ever pulling your phone out.
- You built a full topology diagram in Cisco Modeling Labs — from a photo of a literal napkin
  sketch — entirely through a conversation with your Border, checked the render, and iterated on
  it from your phone before you were back at a desk.
- You ask a plain-language question about interface health on a lab node and get back a real,
  live table pulled via pyATS — not a canned response, an actual query against actual running
  infrastructure, answered in a chat bubble.

## Names you'll recognize

Whatever your Border already knows how to talk to, your phone and watch can reach too — that's not
an abstract claim, so here's some of what's actually in there today: **IP Fabric** for network
assurance, **Itential** for orchestration, **Forward Networks** for intent-based verification,
**Check Point** for security policy, Cisco **ACI** and **Catalyst Center**, **Arista CloudVision**,
**Palo Alto Panorama**, **Juniper JunOS**, **pyATS** for real device/lab validation, **ServiceNow**
for change workflows, **PagerDuty** for on-call and incidents, **Zabbix** for monitoring,
**Nautobot**, **NetBox**, and **InfraHub** for source-of-truth, plus full lab and container
environments to build and test topologies from scratch — **Cisco Modeling Labs**, **GNS3**,
**EVE-NG**, and **Containerlab**. That's not a "someday roadmap" list — those are real,
working skills your Border can already call today, and every one of them just became something you
can reach from your pocket.

## A network far, far away (yes, really)

Not every "name you'll recognize" is a network vendor. NetClaw can also render your topology as an
actual, explorable 3D scene, not a flat box-and-line diagram: **Blender** for a cinematic,
walk-through render; **Unreal Engine 5** for a real-time, explorable digital twin you can fly
through like a level; **Three.js** for an interactive, browser-based view your whole team can
spin, zoom, and walk around with nothing to install. Somewhere between "Death Star briefing-room
hologram" and "a genuinely useful way to actually see your own fabric" — and yes, that CML lab I
mentioned earlier, the one built from a photo of a napkin sketch? Once it existed, turning it into
something you could stand inside was one more conversation away.

## The part I think actually matters

Here's the thing that I think is bigger than any single feature: **every vendor, every skill, every
tool, every automation your Border already knows how to talk to is now reachable from your phone
and your watch too.** NetClaw's Border already integrates with over a hundred different tools and
platforms across more than 200 skills — the mobile app doesn't add a new, narrower surface, it
extends the *entire* thing you've already built to a form factor you always have on you.

Which brings me to something I want to get exactly right, because I looked into it properly before
writing it: **no major network or security vendor's flagship enterprise management platform ships
a real, capable mobile app today.** I want to be precise here, because a few vendors do have real
mobile apps worth acknowledging — Juniper's Mist app is a genuinely capable onboarding/management
tool, Check Point's WatchTower app can actually configure security policy, Cisco has a real
"Business" app, Fortinet has FortiExplorer Go. Credit where it's due. But every one of those is
scoped to an SMB, branch, or wireless-onboarding product line — not Catalyst Center, not ACI, not
Panorama, not NSX-T, not the Ansible Automation Platform, not CloudVision at full scale. If you run
enterprise infrastructure from any of the big names, there has never been a real mobile app for
*that* — until now, indirectly, through your own Border, which doesn't care which vendor you run,
because it's not tied to any one of them.

## It's free. It's open source. And I mean all of it.

NetClaw is fully open source. Every spec that describes how a feature should behave, every skill
that talks to a real platform, every line of the mobile app's code, every single test — public,
on GitHub, right now. I'm not asking anyone to trust a black box. I hope seeing the whole thing
laid bare — including the messy parts, the App Review rejections, the bugs found by real testers —
inspires other people building in this space to work in the open too.

**[github.com/automateyournetwork/netclaw](https://github.com/automateyournetwork/netclaw)**

## What's on the horizon

**Android.** This isn't a "someday, maybe" — an early Android build was actually the *first*
place any of this got tested, months before iOS, and the underlying architecture already supports
it. What's actually gating a public release is Google Play's own requirement: a brand-new app
needs a closed test with real testers before it's allowed to go live. I need **12 volunteers** to
get there. If that's you — say so in the comments, or reach out directly. And if there's real
demand for it, I'm happy to cover the one-time $25 Google Play developer registration myself to
make it happen. This is genuinely reader-gated: enough of you show up, and Android happens.

A couple of smaller things on the list too: a real adaptive layout for iPad instead of today's
scaled-up phone screen, and — since more than one person asked after my last post — a look at
Wear OS/Garmin for the watch side once Android itself is further along.

## Thank you

This app did not get built or tested alone. Real testers, in real time zones around the world,
found real bugs I never would have — reconnect leaks, microphone permission edge cases, things
that only show up on real hardware in real hands. And the ideation, the pressure-testing, the "have
you thought about..." questions that made this better came in large part from the
**[VibeOps Forum](https://join.slack.com/t/vibeopsforum/shared_invite/zt-40mvrfmy8-gqycEL7G~Q2tB5KuNW8tBQ)**
community. Thank you — genuinely.

## What you need to try it

- A **NetClaw Border** — and it doesn't need to be big. A small footprint with just a handful of
  skills and tools is enough to get started; you don't need the full hundred-plus integration set
  running day one.
- Or, join an existing **Risk of NetClaws** (a federated group of peer Borders) if you don't want
  to run your own Border at all.
- An Apple ID capable of installing from the App Store, and — for the Watch features — an Apple
  Watch paired to that phone.
- Five minutes for enrollment: scan a one-time QR code your Border shows you, or enter a manual
  code. During a fresh Border install, the installer can now offer to walk you through enrolling
  your first device right at the end of setup, once your Border is actually up and running — no
  separate step to go hunt down afterward.

**[Download NetClaw Mobile on the App Store](https://apps.apple.com/us/app/netclaw/id6800859524)**

## A few quick questions

**Is it actually free?** Yes. No subscription, no in-app purchase, no paid tier.

**Do I need to already have NetClaw running?** Yes — this is a companion app for a self-hosted
Border you (or your operator) run. There's nothing to sign up for on its own.

**Does my conversation data go to you, or to NetClaw the project?** No. It goes only to your own
Border, which forwards it to whichever AI model *you* (or your operator) configured — including a
fully local, offline model with zero third-party sharing, if that's what you set up.

**Does it work on iPad?** Yes, today — just without an iPad-shaped layout yet (see "on the
horizon" above).

**What about Android / Garmin?** Coming — see "on the horizon" above. I need 12 testers to unlock
it on Google Play.

## Where this started

If you want the origin story: [I wrote about wanting this months
ago](https://www.linkedin.com/posts/john-capobianco-644a1515_today-apple-reviewed-and-approved-netclaw-activity-7493686767502594049-SInx),
and went deeper on the architecture and why nobody sits in the middle [in this
post](https://www.automateyournetwork.ca/uncategorized/my-network-agent-lives-in-my-pocket-now-and-nobody-is-in-the-middle/).
Two early prototype walkthroughs are here too — [iPhone](https://youtu.be/7GrbwIRGBUU) and
[Apple Watch](https://youtu.be/9GUcBGuVZrc). And if the protocol section above hooked you, the
actual IETF Internet-Draft is here:
[draft-capobianco-ncfed-00](https://www.ietf.org/archive/id/draft-capobianco-ncfed-00.html).

Your phone. Your Border. Your network. Now in your pocket, and on your wrist.
