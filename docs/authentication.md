# Local authentication and authorization

CraftControl provides local accounts attached to permanent Minecraft player profiles. It does not create a separate identity directory and never exposes the profile's XUID. In-game operator status and panel access are independent.

## Roles

| Capability | Owner | Operator | Viewer |
| --- | --- | --- | --- |
| Read server, players, history, and telemetry | Yes | Yes | Yes |
| Configure server, gamerules, time, and weather | Yes | Yes | No |
| Start and restart Bedrock | Yes | Yes | No |
| Stop Bedrock | Yes | No | No |
| Change in-game operator permission | Yes | Yes | No |
| Manage Telemetry Pack and panel security | Yes | No | No |

Authorization is enforced in the API. The browser interface is not a security boundary.

## First owner

After the local-auth release is deployed, create a one-time setup code:

```bash
docker compose exec craftcontrol craftcontrol auth bootstrap --player VonCrush
```

Open the CraftControl login screen, choose **First access or invitation**, enter the Gamertag, one-time code, and a new password of 8–128 characters. The code expires after 30 minutes and is stored only as a SHA-256 hash.

Passwords use `scrypt` with independent random salts. Session identifiers are random, stored only as hashes, idle-expire after 12 hours, absolute-expire after 7 days, and are revocable. Login attempts are limited to five failures in 15 minutes per normalized Gamertag.

## Recovery and invitations

Generate a recovery code for an observed player:

```bash
docker compose exec craftcontrol craftcontrol auth recover VonCrush
```

Generate an invitation from the CLI during the initial release:

```bash
docker compose exec craftcontrol craftcontrol auth invite Nicole --role operator
docker compose exec craftcontrol craftcontrol auth invite PlayerName --role viewer
```

Tokens are printed once. Do not store them in shell history, tickets, screenshots, or logs. Player-access management will also be exposed in the owner-only Players interface.

## Deployment transition

`AUTH_MODE=local` enables internal authentication and is the community default. `AUTH_MODE=disabled` exists only as a trusted-LAN recovery compatibility mode and must not be used for Internet exposure. `AUTH_COOKIE_SECURE=true` requires HTTPS, which is the recommended configuration.

Keep Authelia in front of CraftControl until the owner claim, login, logout, recovery, role enforcement, and the following CSRF release are validated. Local authentication replaces Authelia only after those checks pass.
