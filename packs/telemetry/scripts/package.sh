#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="${project_dir}/dist"
mkdir -p "${output_dir}"
(
  cd "${project_dir}/behavior_pack"
  zip -qr "${output_dir}/craftcontrol-telemetry-0.2.0.mcpack" .
)
echo "Created ${output_dir}/craftcontrol-telemetry-0.2.0.mcpack"
