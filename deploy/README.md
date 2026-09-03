# Deploy

This directory contains deployment artifacts for CraftControl.

## Backup interface

The canonical backup interface is the `craftcontrol` binary **inside the
running container**. Always invoke backup via `docker exec`:

```bash
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
`minecraft_manager` → `controlplane`), running the backup on the host fails
because the host binary and the running container may use different module
paths. The deploy script must follow this order:

1. Run `docker exec <container> craftcontrol backup create` against the
   **currently running container** to create a pre-upgrade backup using that
   image's own binary.
2. Pull or build the new image.
3. Stop the old container.
4. Start the new container.
5. Optionally verify the backup: `docker exec <container> craftcontrol backup verify <id>`.

## Subdirectories

- `bedrock-proxy/` — host-side artifacts for the Bedrock Proxy service.
