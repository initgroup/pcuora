#!/usr/bin/env bash
set -euo pipefail
OML_PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
exec bash "$OML_PROJECT_ROOT/scripts/render-build.sh" "$@"
