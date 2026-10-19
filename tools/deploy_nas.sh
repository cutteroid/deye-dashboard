#!/bin/bash
# Update the dashboard on a NAS / server that runs it with Docker (e.g. Synology):
# sends only the files the image is built from (~2 MB) over SSH, then rebuilds
# and restarts there. Docker reuses its cached layers, so a code-only update
# takes seconds; only the first run (base image + Python packages) is slow.
#
#   tools/deploy_nas.sh            deploy (asks for the NAS address on first run)
#   tools/deploy_nas.sh --setup    change the saved NAS address / folder
#
# Settings are kept in tools/.deploy_nas.env (not committed). The NAS folder's
# data/ (config, stats, broker files) is never touched.
set -euo pipefail
cd "$(dirname "$0")/.."

CONF=tools/.deploy_nas.env
if [ "${1:-}" = "--setup" ] || [ ! -f "$CONF" ]; then
    # shellcheck disable=SC1090
    [ -f "$CONF" ] && . "$CONF"
    echo "NAS deployment settings (saved to $CONF)"
    read -rp "  SSH login, user@host [${NAS_SSH:-}]: " v; NAS_SSH=${v:-${NAS_SSH:-}}
    read -rp "  SSH port [${NAS_PORT:-22}]: " v; NAS_PORT=${v:-${NAS_PORT:-22}}
    read -rp "  Dashboard folder on the NAS [${NAS_DIR:-/volume1/docker/extended-dashboard-arm64}]: " v
    NAS_DIR=${v:-${NAS_DIR:-/volume1/docker/extended-dashboard-arm64}}
    [ -n "$NAS_SSH" ] && [ -n "$NAS_DIR" ] || { echo "SSH login and folder are required" >&2; exit 1; }
    printf 'NAS_SSH=%q\nNAS_PORT=%q\nNAS_DIR=%q\n' "$NAS_SSH" "$NAS_PORT" "$NAS_DIR" > "$CONF"
    [ "${1:-}" = "--setup" ] && exit 0
fi
# shellcheck disable=SC1090
. "$CONF"
case "$NAS_DIR" in /*/*) ;; *) echo "NAS_DIR must be an absolute path like /volume1/docker/..." >&2; exit 1 ;; esac

SSH=(ssh -p "$NAS_PORT" -o ConnectTimeout=10)
# One connection for all steps (one login / key prompt)
SOCKET_DIR=$(mktemp -d)
trap 'ssh -p "$NAS_PORT" -o ControlPath="$SOCKET_DIR/s" -O exit "$NAS_SSH" 2>/dev/null; rm -rf "$SOCKET_DIR"' EXIT
SSH+=(-o ControlMaster=auto -o ControlPath="$SOCKET_DIR/s" -o ControlPersist=60)

# What the image is built from: Dockerfile COPY sources + compose + broker entrypoint
FILES=(Dockerfile .dockerignore docker-compose.yml mosquitto/entrypoint.sh)
while read -r src; do FILES+=("$src"); done < <(sed -n 's/^COPY \([^ ]*\) .*/\1/p' Dockerfile)
DIRS=()
for f in "${FILES[@]}"; do
    [ -e "$f" ] || { echo "Missing $f (listed in Dockerfile)" >&2; exit 1; }
    [ -d "$f" ] && DIRS+=("${f%/}")
done

echo "==> Sending $(COPYFILE_DISABLE=1 tar -czf - --exclude='__pycache__' --exclude='*.pyc' --exclude='.DS_Store' "${FILES[@]}" | wc -c | awk '{printf "%.1f MB", $1/1048576}') to $NAS_SSH:$NAS_DIR"
# Directories are replaced as a whole so files deleted here don't linger there
COPYFILE_DISABLE=1 tar -czf - --exclude='__pycache__' --exclude='*.pyc' --exclude='.DS_Store' "${FILES[@]}" |
    "${SSH[@]}" "$NAS_SSH" "set -e; mkdir -p '$NAS_DIR'; cd '$NAS_DIR'; rm -rf ${DIRS[*]}; mkdir -p data/mosquitto; tar -xzf -"

echo "==> Rebuilding and restarting on the NAS (sudo may ask for your NAS password)"
# Synology: docker lives in /usr/local/bin, which sudo's PATH may not include;
# older DSM only has the standalone docker-compose
"${SSH[@]}" -t "$NAS_SSH" "set -e; cd '$NAS_DIR'
    DOCKER=\$(command -v docker || echo /usr/local/bin/docker)
    if sudo \"\$DOCKER\" compose version >/dev/null 2>&1; then DC=\"\$DOCKER compose\"
    else DC=\$(command -v docker-compose || echo /usr/local/bin/docker-compose); fi
    sudo \$DC up -d --build
    sudo \"\$DOCKER\" image prune -f >/dev/null   # drop the replaced image
    sudo \$DC ps"
echo "==> Done: http://${NAS_SSH#*@}:8080"
