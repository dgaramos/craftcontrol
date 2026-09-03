# Deploy

This directory contains deployment artifacts for CraftControl.

## Backup interface

The canonical backup interface is the `craftcontrol` binary **inside the
running container**. Always invoke backup via `docker exec`:

```
docker exec <container> craftcontrol backup create
```

**Never** call the host-side `craftcontrol` binary against the running
container's filesystem. The host binary is built from the current source tree
and may reference a different Python module layout than the image that is
actually running. Running `craftcontrol backup create` on the host against a
container built from an older image causes a `ModuleNotFoundError` because the
module names do not match.

The container image always ships `/usr/local/bin/craftcontrol` pointing to the
Python module layout that was current when the image was built. That binary is
the one that must be used for backup, restore, and all other CLI operations
against a live container.

## Upgrade path

When deploying a new image that renames a Python module (e.g.
`minecraft_manager` → `controlplane`), the backup step must be completed
**inside the new container** after it starts, not on the host before the image
is replaced. The deploy script must follow this order:

1. Pull or build the new image.
2. Stop the old container.
3. Start the new container.
4. Run `docker exec <container> craftcontrol backup create` to create a
   post-upgrade backup using the new image's own binary.

## Subdirectories

- `bedrock-proxy/` — host-side artifacts for the Bedrock Proxy service.
