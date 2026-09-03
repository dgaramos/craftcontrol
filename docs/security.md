# Security

This document describes the threat model, current safeguards, known gaps, and hardening roadmap for CraftControl.

For vulnerability reporting, see [SECURITY.md](../SECURITY.md).

---

## Deployment assumptions

CraftControl is designed for a **trusted homelab LAN**. It assumes:

- All network peers on the LAN are known and trusted.
- The host running CraftControl is not directly exposed to the public internet.
- A reverse proxy (e.g. Nginx, Caddy) is placed in front of CraftControl when remote access is needed.
- The operator controls who can reach the panel.

CraftControl is **not** hardened for public-internet deployments without additional network controls.

---

## Threat model

### In scope

| Threat | Notes |
|--------|-------|
| Unauthenticated panel access | Blocked by session auth |
| Privilege escalation between panel roles | Blocked by RBAC capability checks |
| Arbitrary command injection via Minecraft gamerules or server settings | Blocked by strict allowlists and input validation |
| Invitation link abuse | One-time hashed tokens expire on first use |
| Session hijacking | Revocable opaque server-side sessions |
| CSRF on state-mutating endpoints | Session-bound CSRF tokens |
| Forged origin requests | Origin header validation |
| Container privilege escalation | `no-new-privileges` Docker security option |
| XUID leakage | XUIDs are hidden from API responses and logs |

### Out of scope

| Threat | Reason |
|--------|--------|
| Attacks from the LAN itself | Trusted-LAN assumption |
| Physical access to the host | Out of scope for a software project |
| Minecraft game-level exploits | Managed by the upstream `itzg/minecraft-bedrock-server` image |
| Docker socket access by a compromised container | See Known gaps |
| TLS in transit | Delegated to a reverse proxy — not bundled |

---

## Current safeguards

### Authentication and sessions

- Player-backed local accounts — no external identity provider required.
- Passwords are hashed; plaintext is never stored or logged.
- Sessions are opaque tokens stored server-side and revocable at any time.
- Login throttling limits brute-force attempts.
- Security-relevant events are written to an audit log.

### Authorization

- Role-based capabilities (RBAC) control every panel action.
- Panel roles never imply Minecraft operator (`op`) status.
- Invitations are one-time hashed credentials that expire on first use.

### Input validation and allowlists

- Minecraft gamerule names and values are validated against an explicit allowlist before being passed to the server.
- Server settings mutations go through validated use-case boundaries — no raw input reaches the Docker or filesystem layer.
- Atomic writes prevent partial configuration state.

### Web layer

- CSRF tokens are bound to the active session.
- Origin header validation rejects cross-origin state-mutating requests.

### Container isolation

- The `no-new-privileges` Docker security option prevents privilege escalation inside the Minecraft container.
- XUIDs are stripped from all outward-facing API responses.

---

## Host agent authentication boundary

The split topology introduces a `craftcontrol-bedrock-proxy` systemd service that
runs on the Docker host outside all containers. It owns Docker socket access for
the operations it executes. The explicit allowlist for `PREPARATION` includes
staging and validating the Compose project file and writing Bedrock configuration
files; `RESTART` issues a `docker compose restart`; `HEALTH_WAIT` polls the
Bedrock UDP health probe. No other operations are permitted — the agent rejects
anything outside this allowlist.

Communication between the backend container and the host agent uses a
shared-secret bearer token carried in the `Authorization` header. The token is
read from a file at startup and compared using constant-time comparison; it never
appears in environment variables, logs, or API responses. The agent's threat
model and token rotation procedure are documented in
`docs/bedrock-proxy-contract.md`.

The backend still mounts the Docker socket for Bedrock console operations
(attaching, log streaming, Docker events). These remain a direct socket
dependency and are not mitigated by the host agent.

---

## Known gaps

1. **Partial Docker socket access** — The backend container still mounts the
   Docker socket for `BedrockClient` console and log operations. A compromised
   backend process retains Docker access through that path. The bedrock-proxy
   adapter reduces the Docker footprint for server lifecycle operations when
   configured, but the socket mount cannot be removed entirely while console and
   log streaming remain direct socket operations. Mitigation: run on a dedicated
   host or VM; use network segmentation.

2. **No bundled TLS** — Traffic between the client browser and CraftControl is plain HTTP unless a reverse proxy is configured by the operator. Mitigation: place Nginx or Caddy in front and enforce HTTPS.

3. **No automated dependency scanning** — Third-party dependencies are not yet scanned automatically for known CVEs in CI.

---

## Hardening roadmap

1. Move Bedrock console attachment, log streaming, and Docker event subscription behind a restricted gateway so the Docker socket mount can be removed from the backend container.
2. Document and automate a supported TLS/reverse-proxy boundary (e.g. bundled Caddy configuration).
3. Add automated dependency vulnerability scanning (e.g. `pip-audit`, Dependabot) to CI.
4. Continue removing compatibility overlays after tested migration windows close.
5. Expand community installation documentation and release automation.
