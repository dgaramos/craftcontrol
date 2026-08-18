# Security Policy

## Supported versions

CraftControl does not yet have a stable release. Only the current `main` branch receives security fixes.

| Version | Supported |
|---------|-----------|
| `main`  | Yes       |
| older branches | No |

## Reporting a vulnerability

**Do not open a public issue for security vulnerabilities.**

Use [GitHub private advisory](https://github.com/dgaramos/craftcontrol/security/advisories/new) to report a vulnerability confidentially. Provide as much detail as possible: steps to reproduce, affected component, and potential impact.

## Expected response time

| Stage | Target |
|-------|--------|
| Acknowledgement | 3 business days |
| Initial assessment | 7 business days |
| Fix or mitigation | Best effort, depends on severity |

After a fix is merged to `main`, a disclosure timeline will be agreed with the reporter before any public announcement.

## Scope

CraftControl is a homelab tool designed for trusted LAN environments. It manages a `itzg/minecraft-bedrock-server` Docker container. The threat model and current security posture are documented in [docs/security.md](docs/security.md).
