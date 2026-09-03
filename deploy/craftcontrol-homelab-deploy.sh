#!/usr/bin/env bash
set -euo pipefail

# Entry point called by the Gitea self-hosted runner for every push to main.
# The runner mounts this file read-only as /usr/local/bin/craftcontrol-homelab-deploy.
# See docs/deploy-homelab.md for the full infrastructure setup.

readonly expected_revision="${1:?expected accepted GitHub revision}"
[[ "$(git rev-parse HEAD)" == "$expected_revision" ]] || { echo "checked-out revision differs from accepted revision" >&2; exit 1; }

git switch --force-create main "$expected_revision"
[[ -z "$(git status --porcelain)" ]] || { echo "release source is not clean" >&2; exit 1; }
github_url="$(git remote get-url origin)"
if git remote get-url github >/dev/null 2>&1; then
  git remote set-url github "$github_url"
else
  git remote add github "$github_url"
fi
[[ "$(git ls-remote github refs/heads/main | awk '{print $1}')" == "$(git rev-parse HEAD)" ]] \
  || { echo "GitHub revision changed during release" >&2; exit 1; }
[[ "$(git ls-remote origin refs/heads/main | awk '{print $1}')" == "$(git rev-parse HEAD)" ]] \
  || { echo "release source does not match GitHub" >&2; exit 1; }

bin/deploy-craftcontrol-release --check
bin/deploy-craftcontrol-release
