# Phase 0 Research: Generic Multivendor CLI Driver

**Feature**: 076-multivendor-cli-driver
**Date**: 2026-07-30
**Purpose**: Resolve unknowns before design. The headline finding overturns a spec assumption.

---

## R1 — Neither candidate is adoptable as-is. The spec's "adopt, don't build" assumption fails

The spec assumed "a community server will be adopted rather than written from scratch." Both
candidates were assessed against the spec's own hard requirements. **Both fail, and for overlapping
reasons.**

### Candidate A — `sydasif/nornir-mcp-server`

| Property | Finding | Verdict |
|---|---|---|
| License | MIT | OK |
| Stars / activity | 2 stars, **archived (read-only) 4 June 2026** | **Unmaintained** |
| Python | 3.12+ | Constraint to note |
| Tools | 5: `list_devices`, `fetch_data` (NAPALM getters), `show_commands`, `apply_config`, `backup_configs` | Thin but well-chosen |
| Command filtering | Allowlist (`show`, `display`, `get`), denylist on destructive first tokens, **blocks chaining via `;`, `&&`, `>`, `<`** | **Excellent** |
| Input validation | Pydantic throughout | **Good** |
| Path sandboxing | Backups restricted to a root directory, traversal prevented | **Good** |
| Inventory | Nornir `SimpleInventory`: local `hosts.yaml`, `groups.yaml`, `defaults.yaml`; reloads `config.yaml` from cwd per call | **Violates FR-017** |
| Credentials | Stored in group definitions in YAML | **Violates FR-019** |

### Candidate B — `ntunes/netmiko-mcp-server`

| Property | Finding | Verdict |
|---|---|---|
| License | MIT | OK |
| Stars / activity | 3 stars, **5 total commits** | **Immature** |
| Tools | 12, incl. `send_command_parallel`, `send_config_parallel`, `list_groups`, `get_pool_status`, `test_connection` | Good concurrency surface |
| Command filtering | **Not present** | **Violates FR-023, FR-029** |
| Read-only mode | **Not present** | **Violates FR-022** |
| Credentials | Env vars plus YAML credential profiles | Partially violates FR-019 |
| Inventory | `config/devices.yaml` with groups and tags | **Violates FR-017** |

### The shared pattern — and a correction to how this was first assessed

> **Corrected 2026-07-30 after clarification.** This section originally called "a local YAML inventory
> with credentials in it" a single disqualifying pattern. That conflated two separable things and
> overstated the case. The spec's Clarifications section is authoritative; this is kept for the record.

Both projects are built around a local YAML inventory that also holds credentials. Split properly:

- **The YAML inventory is not disqualifying.** It is NetClaw's established pattern — `pyATS` ships
  `PYATS_TESTBED_PATH` for an operator-built `testbed.yaml`. Hostnames, addresses and platform
  identifiers are not secret. The clarified spec accepts three inventory sources, two of which are
  files (FR-017).
- **Credentials in the YAML are disqualifying**, and that is what both candidates actually do wrong —
  candidate A in Nornir group definitions, candidate B in YAML credential profiles. Forbidden by
  FR-019 and Principle XIII regardless of which inventory source is in use.

The build-rather-than-adopt conclusion is unchanged, but rests on narrower and more defensible
grounds: candidate A is **archived and unmaintained** and reloads `config.yaml` from the working
directory on every tool call, threading the inventory assumption through the request path; candidate B
has **no command filtering whatsoever**, which is the hardest part to get right and the part
Principle I most depends on.

Candidate B additionally has **no command filtering of any kind**, which is the single hardest thing
to get right and the thing FR-023/FR-029 and Constitution Principle I most depend on.

### Decision: build on the libraries directly, using Candidate A as the safety reference

**Not** "adopt", **not** "write blind". Specifically:

1. Build directly on `nornir` + `napalm` + `netmiko` — the libraries, not either wrapper.
2. **Port Candidate A's safety model deliberately**, because it is genuinely good and is the part
   most easily got wrong: prefix allowlist, destructive-first-token denylist, **chaining prevention
   (`;`, `&&`, `>`, `<`)**, Pydantic validation, path sandboxing. MIT licence permits this; archived
   status means there is no upstream to track or contribute back to.
3. Replace the inventory layer with a Nornir inventory backed by NetClaw's existing sources of truth,
   and the credential layer with Vault lookups.
4. Take Candidate B's concurrency surface as a design reference (`*_parallel`, `get_pool_status`,
   `test_connection`) without taking its code.

**Rationale**: the two candidates offer, between them, roughly the safety model plus a concurrency
shape — perhaps 300 lines of genuinely valuable design thinking. Everything else they provide is the
inventory/credential layer that must be discarded. Adopting either would mean carrying an
unmaintained dependency *and* rewriting its core abstraction; forking an archived 2-star repository is
functionally the same as building, minus the freedom to structure it for NetClaw's needs.

**Alternatives rejected**:
- *Adopt Candidate A and swap the inventory* — a plugin swap sounds cheap, but every tool reloads
  `config.yaml` from cwd, so the inventory assumption is threaded through the request path. Also
  inherits an archived Python-3.12+ dependency.
- *Adopt Candidate B and add filtering* — writing the safety layer is the hard part; B contributes
  nothing to it, so this is building with extra steps plus a foreign inventory model.
- *Scrapli instead of Netmiko* — faster and cleaner, but materially narrower platform coverage.
  Reach is the entire point of R1 (FR-001), so Netmiko's ~100 platforms wins.

**Consequence for the spec**: the "adopt a community server" assumption is void. Effort increases
from integration to implementation. This is a **material scope change and needs the maintainer's
acknowledgement before implementation proceeds.**

---

## R2 — Dependency footprint is the real Principle XV risk

None of `napalm`, `netmiko`, `nornir`, `scrapli` is currently installed. Unlike R0, which added zero
dependencies, this feature pulls a substantial transitive tree — `paramiko`/`cryptography` (SSH),
`ncclient`/`lxml` (NAPALM's NETCONF drivers), `ruamel.yaml`, `pydantic`, and per-vendor driver
packages.

**Risk**: `cryptography` and `paramiko` are shared with NetClaw's existing federation/TLS stack (spec
060 uses `cryptography` for X.509 issuance). A version conflict here would not break this feature — it
would break NCFED certificate handling. Constitution Principle XV requires new dependencies not
conflict with existing ones.

**Decision**: isolate this server's dependencies rather than installing into the shared system
environment, and pin explicitly. Verify the installed `cryptography` version is unchanged after
install, since the federation stack depends on it.

**Open item for Phase 1**: confirm whether NetClaw's other MCP servers use per-server virtualenvs or
a shared environment, and match the prevailing pattern. (Note: the repo has a `.venv`, and R0 found
three registrations that had hardcoded a `.venv` interpreter — so the pattern is not currently
consistent and this needs deciding rather than assuming.)

---

## R3 — Platform coverage claim, verified

Netmiko's supported-platforms list confirms the spec's reach claim. Platforms NetClaw cannot touch
today that Netmiko drives: MikroTik RouterOS and SwitchOS, VyOS, Nokia SR Linux and SR OS, Dell SONiC
(and Dell OS6/OS9/OS10), Extreme (EXOS/VSP/SLX), Huawei (VRP/SmartAX), Ubiquiti EdgeOS/Unifi,
Alcatel, Arista EOS, Check Point GAiA, F5 TMSH, Fortinet, Palo Alto PAN-OS, and more.

**Note worth flagging**: Netmiko also drives Fortinet, Palo Alto and Check Point — all of which are
separate roadmap items (R3, R4, and an existing Check Point integration). This server therefore
provides a *CLI-level* fallback for those vendors even before their dedicated API-level servers land.
That is a genuine bonus, but it must not be mistaken for completing R3/R4: CLI access is not
equivalent to FortiManager's policy-package API or Panorama's device-group model.

**Decision**: document this explicitly in the routing skill so the agent does not treat CLI reach as
"Fortinet support" and skip R3.

---

## R4 — SC-001 is testable without hardware, but not for every platform

NetClaw already integrates containerlab, GNS3 and EVE-NG. Containerlab natively runs Nokia SR Linux,
SONiC, VyOS, Arista cEOS and FRR as containers — comfortably satisfying SC-001's "five platform
families NetClaw cannot reach today" with no hardware and no licences.

MikroTik RouterOS, Extreme and Huawei need VM images (GNS3/EVE-NG) with licensing NetClaw's lab
tooling cannot assume.

**Decision**: target containerlab-hosted platforms for acceptance testing — SR Linux, SONiC, VyOS —
plus any two more available. Do not gate SC-001 on platforms requiring licensed images.

---

## R5 — The normalized-fact set is bounded by NAPALM, not by ambition

FR-006 requires normalized facts in one shape across platforms. In practice this is exactly NAPALM's
getter set (`get_facts`, `get_interfaces`, `get_interfaces_ip`, `get_bgp_neighbors`, `get_lldp_neighbors`,
`get_arp_table`, `get_environment`, …), and getter support is **uneven across drivers** — a driver may
implement `get_facts` but not `get_bgp_neighbors`.

**Decision**: enumerate supported getters per platform at runtime and report unavailability
explicitly, which is precisely what FR-007 demands. Do not emulate a missing getter by scraping CLI
output — that would silently produce a normalized-looking answer of lower reliability, the exact
failure mode FR-007 exists to prevent.

---

## R6 — Command filtering must be per-platform, and this is the subtle part

The Constitution forbids `write erase`, `reload`, `format flash:` — all **Cisco** syntax. The
equivalents differ: VyOS `delete`/`commit`, MikroTik `/system reset-configuration`, SR Linux
`tools system configuration`, Junos `request system zeroize`, SONiC `config erase`.

A Cisco-shaped denylist is therefore not sufficient (FR-023 says so explicitly). Candidate A's design
insight — deny on **destructive first tokens** plus block **chaining metacharacters** — generalises
far better than pattern-matching full command strings, because chaining is how a denylist gets
bypassed regardless of vendor.

**Decision**: implement per-platform denylists keyed by platform family, layered on top of a
universal chaining prohibition and a universal read-only prefix allowlist. Enforce server-side
(FR-029), never in skill prose.

---

## Summary: what changed versus the spec

| Spec assumption | Research finding | Impact |
|---|---|---|
| A community server will be adopted | A is **archived** and threads its inventory assumption through the request path; B has **no command filtering at all**. Both store credentials in YAML (FR-019). Their *YAML inventory* is fine — see the correction in R1 | **Build on libraries, port A's safety model. Scope increases.** |
| Dependency isolation "needs attention" | `cryptography`/`paramiko` are shared with the NCFED TLS stack | Isolation is a hard requirement, not a nicety |
| Reach claim ~90 platforms | Confirmed, and includes Fortinet/PAN-OS/Check Point | Bonus reach — must not be mistaken for R3/R4 completion |
| Lab platforms available | True for SR Linux/SONiC/VyOS; MikroTik/Extreme/Huawei need licensed images | SC-001 targets containerlab platforms |
| Normalized facts across platforms | Bounded by uneven NAPALM getter support | FR-007's explicit-gap reporting is essential, not optional |
