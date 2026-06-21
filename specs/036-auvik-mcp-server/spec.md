# Feature Specification: Auvik API MCP Server

**Feature Branch**: `036-auvik-mcp-server`
**Created**: 2026-06-20
**Status**: Draft
**Input**: Add an Auvik API MCP server + skills to NetClaw covering network alerts, inventory, lifecycle, and performance — read-only, multi-tenant (MSP), built from the attached Auvik OpenAPI 3.0.1 definition.

## User Scenarios & Testing

<!--
  Read-only network-monitoring server. Four user journeys map 1:1 to the four
  requested themes. Each is independently testable and delivers standalone value;
  Inventory (P1) is the foundation the other three build on.
-->

### User Story 1 — Multi-tenant inventory & discovery (Priority: P1)

An MSP NetClaw operator needs to enumerate the devices, networks, interfaces, and components Auvik has discovered across one or many client tenants, drill into a single asset's details, see the device's billing/usage rollup, and read the notes and audit history attached to any entity.

**Why this priority**: Asset visibility is the foundation of every other Auvik workflow. Without an inventory the operator cannot reason about alerts, lifecycle posture, or performance for a given device.

**Independent Test**: With a valid `AUVIK_USERNAME` / `AUVIK_API_KEY`, invoke the `auvik-inventory` skill with "list the first 50 devices for tenant acme" and verify the response includes device IDs, names, IPs, makeModel, vendor, deviceType, and online status in a TOON-formatted table.

**Acceptance Scenarios**:

1. **Given** a configured Auvik tenant, **When** the operator asks "list the first 50 devices for tenant acme", **Then** `auvik_list_devices(tenants="acme", page_first=50)` returns a TOON device table.
2. **Given** a known device ID, **When** the operator asks "show full details for device 99…", **Then** `auvik_list_devices(device_id="99…", detail_level="extended")` returns the single device's extended attributes.
3. **Given** the user has access to several client tenants, **When** the operator asks "which tenants can I see?", **Then** `auvik_list_tenants()` returns the multi-client/client catalog.
4. **Given** a device discovered by Auvik, **When** the operator asks "what is the monthly billed usage for device 99…?", **Then** `auvik_get_usage(scope="device", device_id="99…")` returns the usage record.
5. **Given** an entity with notes, **When** the operator asks "show notes on network N…", **Then** `auvik_list_entity_notes(filter_entity_id="N…")` returns the note set.

---

### User Story 2 — Network alert monitoring & triage (Priority: P2)

A NOC operator needs to surface the alerts Auvik has triggered across tenants, filter by severity / status / dismissed-state / time window, and drill into a single alert to read its full detail (triggering entity, alert definition, message).

**Why this priority**: Alert monitoring is the highest-frequency day-to-day operator action, but it is interpreted against the inventory from User Story 1 (an alert references a device/interface/network).

**Independent Test**: With a valid key, invoke the `auvik-network-alerts` skill with "show all unresolved critical alerts in the last 24 hours" and verify the response is a severity-sorted alert table with detected timestamps.

**Acceptance Scenarios**:

1. **Given** active alerts in Auvik, **When** the operator asks "list all critical, non-dismissed alerts", **Then** `auvik_list_alerts(filter_severity="critical", filter_dismissed=false)` returns a severity-sorted table.
2. **Given** an alert ID, **When** the operator asks "show the full detail for alert A…", **Then** `auvik_list_alerts(alert_id="A…")` returns the single alert's attributes.
3. **Given** a time window, **When** the operator asks "what alerted between two timestamps?", **Then** `auvik_list_alerts(filter_detected_time_after=…, filter_detected_time_before=…)` returns the windowed alert series.

---

### User Story 3 — Performance & SNMP statistics (Priority: P3)

A performance analyst needs to pull Auvik's monitored statistics — device CPU/memory/availability, interface throughput, service and component metrics, and custom SNMP poller values — over a time range and interval, to spot saturation and trends.

**Why this priority**: Performance analysis is high value but lower frequency than inventory or alerting, and it requires the operator to already know which device/interface to inspect (from User Story 1).

**Independent Test**: Invoke `auvik-performance` with "show interface throughput for interface I… over the last hour at 1-minute intervals" and verify the response includes a timestamped statistics series.

**Acceptance Scenarios**:

1. **Given** a device under monitoring, **When** the operator asks for its CPU utilization over a window, **Then** `auvik_get_device_statistics(stat_id="cpuUtilization", from_time=…, thru_time=…, interval="hour")` returns a stats series.
2. **Given** a device, **When** the operator asks for its availability, **Then** `auvik_get_device_statistics(stat_id="availability", …)` (deviceAvailability) returns the uptime series.
3. **Given** an interface, **When** the operator asks for throughput, **Then** `auvik_get_interface_statistics(...)` returns the series.
4. **Given** an SNMP poller setting, **When** the operator asks for its history, **Then** `auvik_get_snmp_poller_history(value_type="int", …)` returns the numeric history.
5. **Given** a configured poller, **When** the operator asks "what SNMP pollers are configured and on which devices?", **Then** `auvik_list_snmp_poller_settings(with_devices=true)` returns the settings and their device bindings.

---

### User Story 4 — Asset lifecycle & warranty posture (Priority: P4)

An asset manager needs to review Auvik-collected lifecycle data — sales availability, last-day-of-support, software/security maintenance status — plus warranty/service coverage and the device configuration-backup history, to plan refresh and renewals.

**Why this priority**: Lifecycle/warranty reporting is periodic (planning cycles) rather than daily, and like performance it is anchored to the device inventory from User Story 1.

**Independent Test**: Invoke `auvik-lifecycle` with "list devices whose support has ended" and verify the response includes makeModel, lastSupportStatus, and end-of-life dates.

**Acceptance Scenarios**:

1. **Given** devices with lifecycle data, **When** the operator asks "which devices are past end-of-support?", **Then** `auvik_list_device_lifecycle(filter_last_support_status=...)` returns the matching devices.
2. **Given** devices with warranty data, **When** the operator asks "what is covered under warranty?", **Then** `auvik_list_device_warranty(filter_covered_under_warranty=true)` returns the covered set.
3. **Given** a device with config backups, **When** the operator asks "show the configuration backup history for device 99…", **Then** `auvik_list_configurations(filter_device_id="99…")` returns the backup history (metadata + config payload for a single backup by ID).

---

### Edge Cases

- **Auth missing/invalid**: missing `AUVIK_USERNAME` or `AUVIK_API_KEY` → server fails fast at start with a logged ERROR; an invalid key surfaces the upstream 401 via `auvik_verify_credentials` rather than a silent empty result.
- **Rate limiting (HTTP 429)**: the client honors `Retry-After` and retries with backoff up to a bounded number of attempts; the sliding-window limiter caps outgoing requests.
- **Cursor pagination end**: when Auvik returns fewer items than `page[first]` or an empty `next` link, the paginator stops cleanly; a `page_all` convenience walks links up to a safety cap.
- **Wrong region/base URL**: a base URL pointing at the wrong Auvik regional cluster returns 401/404 — surfaced as a clear error, not retried indefinitely.
- **Multi-tenant scope**: when `tenants` is omitted, the query uses the API key's accessible tenant scope; an operator without access to a requested tenant receives the upstream 403/empty set, reported plainly.
- **Invalid statistics request**: an unknown `stat_id`, an inverted time range, or an unsupported `interval` returns the upstream 400 — the tool returns the error dict, no retry.
- **Large result sets**: list tools default to a bounded page size and return cursor metadata so the operator can page rather than overloading a single response; TOON serialization keeps token cost down.

## Requirements

### Functional Requirements

**Inventory (User Story 1)**
- **FR-001**: System MUST list devices with `detail_level` (info | detail | extended) and filters (deviceType, makeModel, vendorName, onlineStatus, manageStatus, networks, notSeenSince, dateAdded range), and MUST fetch a single device by ID.
- **FR-002**: System MUST list networks with `detail_level` (info | detail) and filters (networkType, scope), and MUST fetch a single network by ID.
- **FR-003**: System MUST list interfaces with filters (interfaceType, parentDevice, adminStatus, operationalStatus) and MUST fetch a single interface by ID.
- **FR-004**: System MUST list components with filters (deviceId, componentType) and MUST fetch a single component by ID.
- **FR-005**: System MUST list accessible tenants (multi-client and client), optionally with detail, and MUST fetch a single tenant's detail by ID.
- **FR-006**: System MUST list entity notes and entity audits with filters (entityType, entityId, lastModifiedBy / category, status, detected-time range), each fetchable by ID.
- **FR-007**: System MUST return client-scope and device-scope billing usage (`scope` = client | device, optional `device_id`, date filters).

**Alerts (User Story 2)**
- **FR-008**: System MUST list alert-history records with filters (severity, status, dismissed, dispatched, detectedTime range, entityId, alertDefinitionId) and MUST fetch a single alert by ID.
- **FR-009**: System MUST NOT expose any alert-dismiss or other write operation; the server is strictly read-only (per operator decision and the read-only-preferred standard).

**Performance (User Story 3)**
- **FR-010**: System MUST return device statistics (including device availability) for a `stat_id`, time range, and interval, filterable by device.
- **FR-011**: System MUST return interface, service, component, and OID statistics for a `stat_id`, time range, and interval, filterable by the relevant entity.
- **FR-012**: System MUST list SNMP poller settings (optionally with their bound devices) and fetch a single poller setting by ID.
- **FR-013**: System MUST return SNMP poller history for string and numeric value types over a time range/interval.

**Lifecycle (User Story 4)**
- **FR-014**: System MUST list device lifecycle records (salesAvailability, lastSupportStatus, software/security maintenance status) and fetch a single device's lifecycle by ID.
- **FR-015**: System MUST list device warranty/service records (coveredUnderWarranty, coveredUnderService) and fetch a single device's warranty by ID.
- **FR-016**: System MUST list device configuration-backup history (filters: deviceId, backupTime range) and fetch a single configuration by ID including its payload.

**Cross-cutting**
- **FR-017**: System MUST authenticate to Auvik using HTTP Basic auth with `AUVIK_USERNAME` and `AUVIK_API_KEY` (API key as password), read from environment at runtime (never hardcoded).
- **FR-018**: System MUST target a configurable regional base URL via `AUVIK_BASE_URL` (default `https://auvikapi.us1.my.auvik.com`), supporting other regions (eu1/au1/…).
- **FR-019**: Every list tool MUST accept an optional `tenants` parameter for MSP multi-client scoping and MUST support JSON:API cursor pagination (`page[first]`, `page[after]`, `page[before]`, `page[last]`) plus a bounded `page_all` convenience.
- **FR-020**: System MUST cap outgoing requests with a sliding-window rate limiter (`AUVIK_RATE_LIMIT`) and MUST honor `Retry-After` / back off on HTTP 429.
- **FR-021**: System MUST serialize tool responses through the TOON helper (Feature 006) to minimize token usage, preserving an option for raw JSON.
- **FR-022**: System MUST provide `auvik_verify_credentials` (`/v1/authentication/verify`) as an auth/health check.
- **FR-023**: System MUST register as a FastMCP stdio server implementing the standard MCP lifecycle (`initialize`, `tools/list`, `tools/call`) and MUST NOT break any existing MCP server or skill.

### Key Entities

- **Device**: id, name, ipAddresses, deviceType, makeModel, vendorName, serialNumber, onlineStatus, manageStatus, networkId, lastSeen, firstSeen (info → detail → extended attribute tiers).
- **DeviceLifecycle**: deviceId, salesAvailability, lastSupportStatus, softwareMaintenanceStatus, securitySoftwareMaintenanceStatus, end-of-life / end-of-support dates.
- **DeviceWarranty**: deviceId, coveredUnderWarranty, coveredUnderService, warranty/service expiry.
- **Network**: id, networkType, scope, description, deviceCount.
- **Interface**: id, interfaceType, parentDevice, adminStatus, operationalStatus, macAddress.
- **Component**: id, deviceId, componentType, name, attributes.
- **Configuration**: id, deviceId, backupTime, configType, contents (single-fetch payload).
- **Tenant**: id, domainPrefix, tenantType (multiClient | client), name.
- **EntityNote / EntityAudit**: id, entityType, entityId, author/user, timestamp, body/action.
- **Alert**: id, alertDefinitionId, severity, status, dismissed, dispatched, entityId/entityType, detectedTime, message.
- **Statistic**: statId, entity reference, interval, series of {time, value} points (device/interface/service/component/OID/availability).
- **SnmpPollerSetting / SnmpPollerHistory**: pollerSettingId, deviceBindings, oid, value series (string | numeric).
- **Usage**: tenant/device scope, period, billed device counts/metrics.

## Success Criteria

### Measurable Outcomes

- **SC-001**: An operator can list, filter, and inspect any Auvik-discovered device across a chosen tenant in fewer than 3 chat turns.
- **SC-002**: 0 write operations exist in the server — verified by source inspection (no POST/PUT/DELETE/PATCH tool) and by smoke test in `quickstart.md`.
- **SC-003**: When list calls are issued concurrently above the configured limit, the sliding-window limiter prevents any 429 from reaching the user (or it is transparently retried via `Retry-After`).
- **SC-004**: Adding Auvik does not regress any existing skill — a representative existing skill smoke (e.g. `pyats-health-check` or `suzieq` list) continues to pass after the merge.
- **SC-005**: The Coherence Checklist in `.specify/memory/constitution.md` passes with every box ticked; the artifacts touched are enumerated in `checklists/requirements.md`.
- **SC-006**: All four skills (`auvik-network-alerts`, `auvik-inventory`, `auvik-lifecycle`, `auvik-performance`) resolve their documented tools and return TOON-formatted output for at least one representative query each.

## Assumptions

- The operator has a valid Auvik user + API key with the role permissions required for the read APIs in scope, and the key's tenant scope covers the tenants they query.
- ASM (SaaS Management) endpoints are **out of scope** for v1 (operator decision); they may be added in a follow-up spec.
- Billing/Usage endpoints are **in scope** and surfaced through the `auvik-inventory` skill as a billing view of inventory (no separate skill).
- Configuration-backup history is grouped under the **lifecycle** theme (device change history) rather than inventory.
- The default regional cluster is `us1`; other regions are reached by overriding `AUVIK_BASE_URL`.
- TOON serialization, cursor pagination, and the sliding-window rate limiter follow the existing `azure-network-mcp` / `claroty-mcp` conventions and are not reinvented.
- Exact Auvik rate-limit numbers and the enumerated statistics `statId` / `interval` vocabularies will be confirmed from the Auvik API documentation during the research/plan phase and recorded in `research.md`.
