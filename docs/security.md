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

## Known gaps

1. **Direct Docker socket access** — CraftControl communicates with the Docker daemon via the raw socket. A compromised CraftControl process could escalate to full host access through Docker. Mitigation: run on a dedicated host or VM; use network segmentation.

2. **No bundled TLS** — Traffic between the client browser and CraftControl is plain HTTP unless a reverse proxy is configured by the operator. Mitigation: place Nginx or Caddy in front and enforce HTTPS.

3. **No automated dependency scanning** — Third-party dependencies are not yet scanned automatically for known CVEs in CI.

---

## Hardening roadmap

1. Replace direct Docker socket access with a restricted operations gateway that exposes only the operations CraftControl requires.
2. Document and automate a supported TLS/reverse-proxy boundary (e.g. bundled Caddy configuration).
3. Add automated dependency vulnerability scanning (e.g. `pip-audit`, Dependabot) to CI.
4. Continue removing compatibility overlays after tested migration windows close.
5. Expand community installation documentation and release automation.
