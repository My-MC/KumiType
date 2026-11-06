#!/usr/bin/env bash
set -euo pipefail
runtime=${CONTAINER_RUNTIME:-docker}
label=''
if command -v selinuxenabled >/dev/null && selinuxenabled; then
    label=':z'
fi
if [[ $# -eq 0 ]]; then
    set -- kumitype --help
fi
exec "$runtime" run --rm --user "$(id -u):$(id -g)" \
    -v "$PWD:/work$label" -w /work kumitype-builder:local "$@"
