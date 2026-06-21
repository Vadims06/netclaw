"""Integration tests: tenant name → ID resolution through tool calls.

Each test uses httpx.MockTransport that serves BOTH:
  - GET /v1/tenants  (tenant lookup)
  - GET /v1/<target-endpoint>  (the actual tool call)

Tests assert:
  1. When tenants="frontier" (a name), the outgoing request carries the
     resolved ID ("698055778108510973"), NOT the name.
  2. When tenants="698055778108510973" (already an ID), /v1/tenants is
     NOT called and the ID is forwarded unchanged.
  3. A bad name produces an error envelope (no upstream call to the tool endpoint).
"""

import json

import httpx
import pytest

from clients.auvik_client import AuvikClient
from tools.inventory import auvik_list_devices, auvik_list_networks
from tools.alerts import auvik_list_alerts
from utils.constants import DEFAULT_BASE_URL


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FRONTIER_ID = "698055778108510973"
_FRONTIER_DOMAIN = "frontier"

_TENANT_LIST_PAYLOAD = {
    "data": [
        {
            "id": _FRONTIER_ID,
            "type": "tenant",
            "attributes": {
                "domainPrefix": _FRONTIER_DOMAIN,
                "displayName": "Frontier Networks",
                "tenantType": "client",
            },
        }
    ],
    "links": {},
    "meta": {},
}

_EMPTY_LIST_PAYLOAD = {"data": [], "links": {}, "meta": {}}

_DEVICE_PAYLOAD = {
    "data": [
        {
            "id": "123456789",
            "type": "device",
            "attributes": {
                "deviceName": "sw-01",
                "ipAddresses": ["10.0.0.1"],
                "deviceType": "switch",
                "onlineStatus": "online",
                "makeModel": "Cisco",
                "vendorName": "Cisco",
            },
        }
    ],
    "links": {},
    "meta": {},
}

_NETWORK_PAYLOAD = {
    "data": [
        {
            "id": "200000001",
            "type": "network",
            "attributes": {
                "description": "Corp LAN",
                "networkType": "routed",
                "scanStatus": "ok",
            },
        }
    ],
    "links": {},
    "meta": {},
}

_ALERT_PAYLOAD = {
    "data": [
        {
            "id": "300000001",
            "type": "alert",
            "attributes": {
                "alertDefinitionId": "adef-001",
                "severity": "high",
                "status": "active",
                "detectedTime": "2026-06-01T00:00:00Z",
            },
        }
    ],
    "links": {},
    "meta": {},
}


def _client_for(handler):
    """Build AuvikClient with MockTransport."""
    return AuvikClient(
        base_url=DEFAULT_BASE_URL,
        username="u",
        password="k",
        transport=httpx.MockTransport(handler),
    )


# ---------------------------------------------------------------------------
# Helper: build multi-endpoint handler
# ---------------------------------------------------------------------------

def _multi_handler(tenant_payload, target_path: str, target_payload: dict):
    """Return a handler that serves tenant lookup + target endpoint."""
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append({"path": req.url.path, "params": dict(req.url.params)})
        if req.url.path == "/v1/tenants":
            return httpx.Response(200, json=tenant_payload)
        if req.url.path == target_path:
            return httpx.Response(200, json=target_payload)
        return httpx.Response(404, json={"errors": [{"title": "Not Found"}]})

    return handler, calls


# ---------------------------------------------------------------------------
# Test 1: name "frontier" → ID in outgoing request (auvik_list_devices)
# ---------------------------------------------------------------------------


class TestTenantNameResolutionListDevices:
    async def test_name_resolved_to_id_in_outgoing_request(self):
        """auvik_list_devices(tenants='frontier') must send tenants=<ID>."""
        handler, calls = _multi_handler(
            _TENANT_LIST_PAYLOAD,
            "/v1/inventory/device/info",
            _DEVICE_PAYLOAD,
        )
        client = _client_for(handler)
        result_str = await auvik_list_devices(client, tenants=_FRONTIER_DOMAIN)
        await client.close()

        # Should succeed
        data = json.loads(result_str)
        assert "error" not in data, f"Unexpected error: {data}"

        # Find the device-endpoint call and verify tenants param is the ID
        device_calls = [c for c in calls if c["path"] == "/v1/inventory/device/info"]
        assert device_calls, "Expected a call to /v1/inventory/device/info"
        assert device_calls[0]["params"].get("tenants") == _FRONTIER_ID

    async def test_id_passthrough_no_tenant_lookup(self):
        """auvik_list_devices(tenants=<ID>) must NOT call /v1/tenants."""
        handler, calls = _multi_handler(
            _TENANT_LIST_PAYLOAD,
            "/v1/inventory/device/info",
            _DEVICE_PAYLOAD,
        )
        client = _client_for(handler)
        result_str = await auvik_list_devices(client, tenants=_FRONTIER_ID)
        await client.close()

        data = json.loads(result_str)
        assert "error" not in data, f"Unexpected error: {data}"

        # /v1/tenants must NOT have been called
        tenant_calls = [c for c in calls if c["path"] == "/v1/tenants"]
        assert tenant_calls == [], "Expected NO /v1/tenants call when input is already an ID"

        # The ID must reach the device endpoint unchanged
        device_calls = [c for c in calls if c["path"] == "/v1/inventory/device/info"]
        assert device_calls, "Expected a call to /v1/inventory/device/info"
        assert device_calls[0]["params"].get("tenants") == _FRONTIER_ID

    async def test_unknown_name_returns_error_envelope(self):
        """An unresolvable tenant name returns NotFound without calling device endpoint."""
        handler, calls = _multi_handler(
            _TENANT_LIST_PAYLOAD,
            "/v1/inventory/device/info",
            _DEVICE_PAYLOAD,
        )
        client = _client_for(handler)
        result_str = await auvik_list_devices(client, tenants="nosuchtenantxyz")
        await client.close()

        data = json.loads(result_str)
        assert "error" in data
        assert data["error"]["code"] == "NotFound"

        # Device endpoint should NOT have been called
        device_calls = [c for c in calls if c["path"] == "/v1/inventory/device/info"]
        assert device_calls == []


# ---------------------------------------------------------------------------
# Test 2: auvik_list_networks — name → ID
# ---------------------------------------------------------------------------


class TestTenantNameResolutionListNetworks:
    async def test_name_resolved_to_id(self):
        """auvik_list_networks(tenants='frontier') sends ID in outgoing request."""
        handler, calls = _multi_handler(
            _TENANT_LIST_PAYLOAD,
            "/v1/inventory/network/info",
            _NETWORK_PAYLOAD,
        )
        client = _client_for(handler)
        result_str = await auvik_list_networks(client, tenants=_FRONTIER_DOMAIN)
        await client.close()

        data = json.loads(result_str)
        assert "error" not in data, f"Unexpected error: {data}"

        network_calls = [c for c in calls if c["path"] == "/v1/inventory/network/info"]
        assert network_calls
        assert network_calls[0]["params"].get("tenants") == _FRONTIER_ID

    async def test_id_passthrough_no_tenant_lookup(self):
        """auvik_list_networks(tenants=<ID>) must NOT call /v1/tenants."""
        handler, calls = _multi_handler(
            _TENANT_LIST_PAYLOAD,
            "/v1/inventory/network/info",
            _NETWORK_PAYLOAD,
        )
        client = _client_for(handler)
        result_str = await auvik_list_networks(client, tenants=_FRONTIER_ID)
        await client.close()

        data = json.loads(result_str)
        assert "error" not in data, f"Unexpected error: {data}"

        tenant_calls = [c for c in calls if c["path"] == "/v1/tenants"]
        assert tenant_calls == []


# ---------------------------------------------------------------------------
# Test 3: auvik_list_alerts — name → ID
# ---------------------------------------------------------------------------


class TestTenantNameResolutionAlerts:
    async def test_name_resolved_to_id(self):
        """auvik_list_alerts(tenants='frontier') sends ID in outgoing request."""
        handler, calls = _multi_handler(
            _TENANT_LIST_PAYLOAD,
            "/v1/alert/history/info",
            _ALERT_PAYLOAD,
        )
        client = _client_for(handler)
        result_str = await auvik_list_alerts(client, tenants=_FRONTIER_DOMAIN)
        await client.close()

        data = json.loads(result_str)
        assert "error" not in data, f"Unexpected error: {data}"

        alert_calls = [c for c in calls if c["path"] == "/v1/alert/history/info"]
        assert alert_calls
        assert alert_calls[0]["params"].get("tenants") == _FRONTIER_ID
