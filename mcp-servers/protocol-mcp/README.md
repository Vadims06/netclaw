# protocol-mcp — eN2N Federation Protocol Server

MCP server implementing the NCFED (NetClaw Federation) protocol for
inter-claw communication over the eN2N mesh.

Core modules:
- `bgp-daemon-v2.py` — main HTTP control plane + eN2N listener
- `bgp/federation/` — channel management, TLS (060), endpoint persistence (063)
- `server.py` — MCP tool surface (`n2n_health`, `n2n_status`, `n2n_connect`, etc.)

---

## Cloudflare Tunnel Transport (Feature 108)

> **READ THIS BEFORE writing a `cloudflared` config for eN2N traffic.**

### Fixed Architectural Decision: TCP / Private-Network Mode ONLY

| Aspect | Decision |
|--------|----------|
| **Required mode** | TCP / private-network (opaque byte relay) |
| **Forbidden mode** | HTTP(S) ingress — **NEVER** for eN2N traffic |
| **Configurability** | None. This is a fixed decision (FR-009), not operator-selectable. |

### Why — Confidentiality Rationale

The eN2N listener speaks **NCFED**, a custom framed protocol (`NCFED_MAGIC`
handshake → TLS upgrade → JSON-RPC 2.0 frames). It is not HTTP.

If `cloudflared` were configured in HTTP(S) ingress mode:

1. Cloudflare's edge would terminate TLS on behalf of the origin.
2. NCFED payload would transit Cloudflare infrastructure **in plaintext**
   (or re-encrypted under Cloudflare's own keys, not the peers' keys).
3. This is a **confidentiality regression** — the whole point of spec 060's
   in-protocol TLS is that only the two authenticated peers can decrypt
   the channel. Delegating decryption to an intermediary defeats that.

In TCP / private-network mode:

- `cloudflared` relays **opaque bytes** end-to-end.
- Cloudflare's infrastructure never observes decrypted NCFED payload.
- Spec 060's peer-to-peer TLS remains the **sole layer** that can decrypt.
- Consistent with spec 063 R2's principle: *"encrypt in-protocol, don't rely
  on an incidental transport"* — applied here to the transport choice itself.

### Correct `config.yml` Ingress (Example)

```yaml
# /etc/cloudflared/config.yml (or ~/.cloudflared/config.yml)
tunnel: <TUNNEL-UUID>
credentials-file: /path/to/credentials.json

ingress:
  # eN2N federation listener — TCP mode, opaque relay
  - hostname: netclaw-en2n.example.com
    service: tcp://127.0.0.1:7179    # local eN2N listener port
  # Catch-all (required by cloudflared)
  - service: http_status:404
```

**Key points:**
- The `service:` value is `tcp://...` — this tells `cloudflared` to relay raw
  TCP, not interpret it as HTTP.
- The hostname resolves via Cloudflare DNS (CNAME to the tunnel), giving the
  stable address that eliminates ngrok-style address rot (spec 108, US1).
- The local port (`7179` above) must match the eN2N listener's bind port in
  `bgp-daemon-v2.py`.

### What NOT to Do

```yaml
# ❌ WRONG — HTTP(S) ingress. Cloudflare terminates TLS at the edge.
ingress:
  - hostname: netclaw-en2n.example.com
    service: https://127.0.0.1:7179   # BREAKS CONFIDENTIALITY
```

```yaml
# ❌ WRONG — HTTP mode. NCFED is not HTTP; this will fail AND leak.
ingress:
  - hostname: netclaw-en2n.example.com
    service: http://127.0.0.1:7179    # PROTOCOL MISMATCH + LEAK
```

### Deployment

For the full deployment procedure (tunnel creation, DNS binding, systemd unit,
smoke tests), see:

- **Quickstart**: `specs/108-cloudflare-tunnel-transport/quickstart.md`
- **Durable service pattern**: `scripts/cloudflared-transport.sh` (mirrors
  spec 057's `in2n-services.py` systemd-unit generation)

### Related Specs

| Spec | Relevance |
|------|-----------|
| 060 | In-protocol TLS — the peer-to-peer encryption that this decision protects |
| 063 | Endpoint persistence — the mechanism that stores the stable tunnel address |
| 057 | Durable service pattern — `cloudflared` runs as a systemd unit, not ad-hoc |
| 108 | This feature — Cloudflare Tunnel as a hardened transport |
