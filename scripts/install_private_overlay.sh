#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OVERLAY_ROOT="${PROJECT_ROOT}/local-private-overlay/project-root"

if [[ ! -d "${OVERLAY_ROOT}" ]]; then
  echo "Private overlay not found: ${OVERLAY_ROOT}" >&2
  echo "Ask the GM for the local-private-overlay folder, then place it in the project root." >&2
  exit 1
fi

echo "Installing private campaign overlay from:"
echo "  ${OVERLAY_ROOT}"
echo
echo "Copying into:"
echo "  ${PROJECT_ROOT}"
echo

cp -R "${OVERLAY_ROOT}/." "${PROJECT_ROOT}/"

echo "Private overlay installed. Git ignore rules should keep these files local."
