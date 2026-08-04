#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 DATA_DIRECTORY WORLD_NAME" >&2
  exit 2
fi
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
node "${project_dir}/scripts/install.mjs" "${project_dir}" "$1" "$2"
