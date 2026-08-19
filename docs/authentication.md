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
docker compose -f docker-compose.split.yml exec craftcontrol-backend \
  craftcontrol auth bootstrap --player VonCrush
```

Open the CraftControl login screen, choose **First access or invitation**, enter the Gamertag, one-time code, and a new password of 8–128 characters. The code expires after 30 minutes and is stored only as a SHA-256 hash.

Passwords use `scrypt` with independent random salts. Session identifiers are random, stored only as hashes, idle-expire after 12 hours, absolute-expire after 7 days, and are revocable. Login attempts are limited to five failures in 15 minutes per normalized Gamertag.

## CSRF protection

Every authenticated state-changing request requires a synchronizer token in the `X-CSRF-Token` header. The token is cryptographically bound to the opaque session, returned by login, claim, and `/api/auth/me`, and attached automatically by the browser client. A missing token, an invalid token, or a token issued for another session is rejected with `403` before authorization or application code runs. When a browser supplies an `Origin` header, its host must also match the request host.

Login and invitation claim are exempt because they do not rely on an existing authenticated session. `AUTH_MODE=disabled` is an explicit trusted-LAN recovery mode and disables both session authentication and CSRF enforcement.

## Recovery and invitations

Generate a recovery code for an observed player:

```bash
docker compose -f docker-compose.split.yml exec craftcontrol-backend \
  craftcontrol auth recover VonCrush
```

Owners can generate invitations from the dedicated player profile: open **Players**, select the player, then use the separate **CraftControl access** card. Choose `viewer`, `operator`, or `owner`, press **Generate access**, and copy the one-time code. The Minecraft permission card beside it is independent and never changes panel access. Active accounts instead receive a recovery code. Owners can suspend access, which revokes every active session immediately; the last active owner cannot be suspended or demoted.

The same operations remain available from the CLI for recovery:

```bash
docker compose -f docker-compose.split.yml exec craftcontrol-backend \
  craftcontrol auth invite Nicole --role operator
docker compose -f docker-compose.split.yml exec craftcontrol-backend \
  craftcontrol auth invite PlayerName --role viewer
```

Tokens are printed once. Do not store them in shell history, tickets, screenshots, or logs. CLI recovery preserves the account's existing role and never promotes a viewer or operator to owner.

## Deployment transition

`AUTH_MODE=local` enables internal authentication and is the community default. `AUTH_MODE=disabled` exists only as a trusted-LAN recovery compatibility mode and must not be used for Internet exposure. `AUTH_COOKIE_SECURE=true` requires HTTPS, which is the recommended configuration.

Authelia is optional for trusted-LAN deployments after owner claim, login, logout, recovery, role enforcement, and CSRF behavior have been validated. Removing it also removes its MFA and second authentication layer. Keep HTTPS enabled, and do not expose CraftControl directly to the Internet while direct Docker socket access remains.
