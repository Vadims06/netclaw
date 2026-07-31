# Feature Specification: Dependency-Pin Hazards

**Feature Branch**: `077-dependency-pin-hazards`
**Created**: 2026-07-31
**Status**: Draft
**Roadmap item**: R0a in `docs/COVERAGE-ROADMAP.md`
**Builds on**: R0 / spec 075 (the reconciliation gate this feature extends), R1 / spec 076 (where all three hazards were found)

---

## The problem, in one sentence

**NetClaw installs correctly today and would fail to install tomorrow**, because three classes of
dependency breakage are invisible to every existing check — and all three break only *new* installs,
which is exactly why nobody noticed.

This directly undermines R0's ratified goal: *"all 89 available for people when they install their own
risk."* R0 made integrations *registered and catalogued*. It did not make them *installable next
Tuesday*.

## Measured state (audited 2026-07-31)

### Hazard 1 — `mcp 2.0.0` removed `mcp.server.fastmcp`

Verified directly: the `mcp 2.0.0` wheel contains **zero** `mcp/server/fastmcp/` files and declares **no
`fastmcp` dependency**, so there is no re-export. FastMCP moved to a standalone distribution.

Seven servers have an unbounded pin *and* import the removed module, so all seven resolve a breaking
major on a fresh install:

| Server | Current pin | Hazard |
|---|---|---|
| `claroty-mcp` | `mcp>=1.0.0` | mcp 2.x removed the module |
| `protocol-mcp` | `mcp>=1.0.0` | mcp 2.x |
| `suzieq-mcp` | `mcp>=1.0.0` | mcp 2.x |
| `nautobot-mcp-v2` | `mcp>=1.0.0` | mcp 2.x |
| `uml-mcp` | `mcp>=1.2.0` | mcp 2.x |
| `thousandeyes-mcp-community` | `mcp>=1.13` | mcp 2.x |
| **`n2n-mcp`** | `fastmcp>=0.1.0` | standalone `fastmcp` major drift — **and it is one of the 7 live servers, backing the federation** |

**Correction to an earlier count.** A first pass reported seven servers with a slightly different
composition, because the audit treated exact `==` pins as unbounded. `f5-mcp-server` (`mcp==1.4.1`) and
`meraki-magic-mcp-community` (`fastmcp==2.2.10`) are safe. The total is coincidentally still seven; the
membership is not.

Three servers are already safe and demonstrate the fix works: the two exact pins above, plus
`multivendor-cli-mcp` (`mcp>=1.2.0,<2`), pinned by spec 076 when it hit this exact failure.

### Hazard 2 — `pip3` and `python3` can be different interpreters

On the development host:

```
python3 -> /usr/bin/python3        3.14.4   cryptography 46.0.5
pip3    -> ~/.local/bin/pip3       3.13     cryptography 45.0.2
```

`pip3` installs into a stranded `site-packages` that `python3` cannot import from. Audited in
`scripts/lib/install-steps.sh`:

| Invocation style | Count |
|---|---|
| bare `pip3 install` | **143** |
| bare `pip install` | **46** |
| venv-scoped (`<venv>/bin/python -m pip`) | **2** |
| **total** | **188** |

Any bare invocation on a split-toolchain host installs where the server cannot see it. This is the same
defect class as the hardcoded interpreter paths R0 fixed — a path that resolves on the author's machine
and nowhere else.

### Hazard 3 — `python3 -m venv` fails without `ensurepip`

Python 3.14 here has no `ensurepip`, because `python3.14-venv` is not installed and installing it needs
root. `python3 -m venv` therefore fails outright. Audited: **two** places create venvs this way —

- `scripts/gait-venv-setup.sh` — **GAIT is the audit trail Constitution Principle IV makes
  non-negotiable.** Its venv failing to build is not cosmetic.
- `scripts/lib/install-steps.sh`

Spec 076 works around it with `virtualenv`, which bundles pip and needs no root.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A fresh install actually works (Priority: P1)

Someone clones NetClaw and installs it today, on a current Python. Every integration the installer
offers either installs and imports successfully, or fails with a message naming what is wrong.

**Why this priority**: This is the whole feature. Seven servers currently fail on import after a
successful-looking install, and the failure surfaces as an obscure `ModuleNotFoundError` at first use
rather than at install time.

**Independent Test**: In a clean environment, install each affected server and import its entry point.
Every one succeeds, or reports a specific actionable error.

**Acceptance Scenarios**:

1. **Given** a clean environment on current Python, **When** an affected server is installed, **Then**
   its dependencies resolve to versions whose API it actually uses.
2. **Given** a server that imports `mcp.server.fastmcp`, **When** its dependencies are resolved,
   **Then** a version providing that module is selected.
3. **Given** a host where `pip3` and `python3` are different interpreters, **When** the installer runs,
   **Then** packages land where the server will import them from.
4. **Given** a host without `ensurepip`, **When** something needs a virtualenv, **Then** it is created
   successfully or the failure names the missing prerequisite and how to satisfy it.
5. **Given** any install failure, **When** it occurs, **Then** it fails at install time rather than
   silently succeeding and breaking at first use.

---

### User Story 2 - This class of breakage cannot silently return (Priority: P1)

A maintainer adds or edits a server's dependencies. An unbounded pin on a package whose API the server
depends on, or a bare `pip` invocation, is caught before merge rather than by the next person to
install.

**Why this priority**: Equal to US1. US1 is a one-time repair; this is what stops the next `mcp 3.0` or
the next 188 bare `pip3` calls. R0 established a reconciliation gate precisely so foundation problems
stay fixed — this extends it to dependency resolution.

**Independent Test**: Add an unbounded pin for a package the server imports a specific API from, and a
bare `pip3 install`, and confirm the gate fails naming both.

**Acceptance Scenarios**:

1. **Given** a server whose requirements gain an unbounded pin on a package it imports a submodule
   from, **When** the gate runs, **Then** it fails and names the server and package.
2. **Given** a new bare `pip install` in an install step, **When** the gate runs, **Then** it fails and
   names the file and line.
3. **Given** new venv creation via `python3 -m venv`, **When** the gate runs, **Then** it fails or warns
   with the `ensurepip` caveat.
4. **Given** a clean repository, **When** the gate runs, **Then** it passes and exits zero.
5. **Given** an intentional exception, **When** it is recorded with a reason, **Then** the gate accepts
   it — matching how R0 handles intentionally-external integrations.

---

### User Story 3 - Installability is verifiable without installing everything (Priority: P2)

A maintainer can check whether declared dependencies would resolve, and whether the resolved versions
provide the APIs the code imports, without performing 90 installs.

**Why this priority**: P2 because US1 and US2 deliver the fix and the guard. But a check nobody can run
cheaply is a check that rots — and the reason this hazard survived is that verifying it required
actually installing things.

**Independent Test**: Run the check against the repository and confirm it reports per-server resolution
status in a time short enough to run before pushing.

**Acceptance Scenarios**:

1. **Given** the repository, **When** installability is checked, **Then** each server reports whether
   its declared dependencies resolve.
2. **Given** a resolvable server, **When** checked, **Then** the resolved version of each
   API-significant dependency is reported.
3. **Given** the check runs, **When** it completes, **Then** it required no credentials and no running
   agent.

---

### Edge Cases

- **A server legitimately wants the new major.** Migrating to standalone `fastmcp` is a valid fix, not
  only pinning `<2`. The gate must accept either, and check that imports match the pinned major.
- **An exact `==` pin.** Safe against drift but freezes security fixes. Should be accepted and not
  flagged, since it is bounded — but the distinction from a range is worth reporting.
- **A dependency not imported by name.** Unbounded pins on packages used only via stable top-level APIs
  are far lower risk than on packages whose submodules are imported. The check should weight these
  differently rather than demanding upper bounds everywhere.
- **`pip` inside an already-activated virtualenv** is correct, not a defect. The check must distinguish
  a bare invocation from one scoped to a venv.
- **A host where `pip3` and `python3` agree.** The common case. Fixes must not break it.
- **`virtualenv` itself is absent.** The fallback needs its own fallback, or a clear failure naming the
  one-line remedy.
- **A transitive dependency causes the break**, not a declared one. Out of scope for declared-pin
  auditing, and should be stated as such rather than implied to be covered.
- **A server with no `requirements.txt`** (npx/uvx/remote). Has no pins to audit and must not be
  reported as a gap.

## Requirements *(mandatory)*

### Functional Requirements

**Repair**

- **FR-001**: All seven exposed servers MUST resolve to a dependency version providing the API they
  import, either by bounding the pin or by migrating to the successor distribution.
- **FR-002**: Each repair MUST be verified by importing the server's entry point under the resolved
  versions, not by inspecting the pin alone.
- **FR-003**: Bare `pip`/`pip3` invocations in install steps MUST be replaced with invocations scoped to
  the interpreter the server will actually run under.
- **FR-004**: Venv creation MUST work on hosts lacking `ensurepip`, or fail with a message naming the
  missing prerequisite and the remedy.
- **FR-005**: `scripts/gait-venv-setup.sh` MUST be included in FR-004's fix — GAIT is the audit trail
  Principle IV makes non-negotiable.

**Enforcement**

- **FR-006**: The reconciliation gate MUST fail when a server declares an unbounded pin on a package
  whose submodule it imports.
- **FR-007**: The gate MUST fail on a new bare `pip`/`pip3` invocation in an install step.
- **FR-008**: The gate MUST flag `python3 -m venv` usage with the `ensurepip` caveat.
- **FR-009**: Every failure MUST name the file, the server, and the specific package or line.
- **FR-010**: Intentional exceptions MUST be recordable with a reason and accepted thereafter, matching
  R0's treatment of intentionally-external integrations.
- **FR-011**: The gate MUST exit non-zero on failure and MUST run in CI.

**Verifiability**

- **FR-012**: Dependency resolution MUST be checkable without installing, and MUST report the resolved
  version of each API-significant dependency.
- **FR-013**: The check MUST require no credentials, no network beyond a package index, and no running
  agent.
- **FR-014**: A server with no declared requirements MUST NOT be reported as a gap.

**Scope discipline**

- **FR-015**: This feature MUST NOT add or remove any integration capability.
- **FR-016**: Existing behaviour MUST NOT regress — 202 skills and 150 integrations available before
  MUST remain available after.
- **FR-017**: Hosts where `pip3` and `python3` agree MUST continue to work unchanged.

### Key Entities

- **Dependency declaration**: A pin in a server's requirements — package, operator, version, and
  whether it is bounded above.
- **API-significant dependency**: One whose *submodule* the code imports (e.g. `mcp.server.fastmcp`), as
  opposed to one used through a stable top-level API. Unbounded pins on the former are the hazard.
- **Install invocation**: A pip call in an install step, classified as bare or interpreter-scoped.
- **Venv creation**: A call creating a virtualenv, classified by whether it depends on `ensurepip`.
- **Pin exception**: A recorded, reasoned acceptance of an otherwise-failing declaration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero servers resolve to a dependency major that lacks an API they import — down from 7.
- **SC-002**: Every one of the 7 repaired servers imports its entry point successfully under resolved
  versions.
- **SC-003**: Bare pip invocations in install steps drop from 189 to zero, or each remaining one is
  recorded as an intentional exception with a reason.
- **SC-004**: Both `python3 -m venv` call sites work on a host without `ensurepip`, or fail naming the
  remedy.
- **SC-005**: Introducing an unbounded API-significant pin causes the gate to fail, confirmed by test.
- **SC-006**: Introducing a bare `pip3 install` causes the gate to fail, confirmed by test.
- **SC-007**: The gate passes and exits zero on a clean repository.
- **SC-008**: Dependency resolution is checkable for all servers in under 5 minutes without installing.
- **SC-009**: 202 skills and 150 integrations remain available.
- **SC-010**: The check completes with no credentials and no running agent.

## Assumptions

- **Extend R0's gate, do not build a second one.** `scripts/reconcile-mcp.py` is the established single
  entry point and CI already runs it. A separate dependency checker would be a second thing to remember.
- **Pinning `<2` is the default repair**, since it is the minimal change and spec 076 already proved it.
  Migrating to standalone `fastmcp` is a legitimate alternative where a server wants the new API, but is
  a bigger change per server and should not be forced by this feature.
- **Declared pins only.** Transitive breakage is real but out of scope; auditing it needs a lockfile
  strategy this repository does not have. Stated so the limitation is explicit rather than implied.
- **A package index is reachable** for resolution checking. Offline, the check reports that it could not
  resolve rather than passing vacuously.
- **`virtualenv` is the venv remedy**, matching spec 076. If absent, failure names the one-line install.
- **The audit figures are ground truth** as of 2026-07-31: 7 exposed servers, 188 pip installs (143 bare
  `pip3`, 46 bare `pip`, 2 venv-scoped), 2 `ensurepip`-dependent venv creations.
- **No capability changes**, per FR-015 — this is repair and enforcement only, like R0.

## Dependencies

- `scripts/reconcile-mcp.py`, `scripts/verify-catalog-coverage.py` — the gate being extended (spec 075).
- `mcp-servers/*/requirements.txt` — the declarations being audited.
- `scripts/lib/install-steps.sh` — 188 pip invocations.
- `scripts/gait-venv-setup.sh` — the second `ensurepip`-dependent venv creation.
- `tests/reconcile/run-tests.sh` — the harness the new contract tests join.
- `docs/ADDING-AN-MCP.md` — gains the pinning rule so R2–R24 inherit it.
- `mcp-servers/multivendor-cli-mcp/requirements.txt` — the reference example of a correct bounded pin.
