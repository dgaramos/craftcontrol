#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="${project_dir}/dist"
staging_dir="$(mktemp -d)"
trap 'rm -rf "${staging_dir}"' EXIT
mkdir -p "${output_dir}"
cp -a "${project_dir}/behavior_pack/." "${staging_dir}/"
find "${staging_dir}" -exec touch -t 198001010000 {} +
archive="${output_dir}/craftcontrol-telemetry-0.3.1.mcpack"
rm -f "${archive}"
(
  cd "${staging_dir}"
  find . -type f -print | LC_ALL=C sort | zip -X -q "${archive}" -@
)
echo "Created ${archive}"
