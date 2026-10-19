#!/bin/bash
# Package the dashboard + Mosquitto images with everything needed to run them on
# another machine (no source code or build there), e.g. a Synology NAS.
#
#   tools/export_images.sh [arch]     arch: arm64 (default: this machine's) or amd64
#
# Output: dist/extended-dashboard-<arch>.tar.gz (see INSTALL.md inside).
# Your data/.env is NOT included: it holds secrets; copy it over yourself if wanted.
set -euo pipefail
cd "$(dirname "$0")/.."

case "$(uname -m)" in
    arm64|aarch64) HOST_ARCH=arm64 ;;
    x86_64|amd64) HOST_ARCH=amd64 ;;
    *) HOST_ARCH=$(uname -m) ;;
esac
ARCH=${1:-$HOST_ARCH}
case "$ARCH" in arm64|amd64) ;; *) echo "Unsupported arch: $ARCH (use arm64 or amd64)" >&2; exit 1 ;; esac

APP_IMAGE=extended-dashboard
MOSQUITTO_IMAGE=$(sed -n 's/^ *image: *\(eclipse-mosquitto:[^ ]*\).*/\1/p' docker-compose.yml)
NAME=extended-dashboard-$ARCH
OUT=dist/$NAME

if [ "$ARCH" = "$HOST_ARCH" ]; then
    TAG=latest
    echo "==> Building $APP_IMAGE:$TAG"
    docker compose build deye-dashboard
else
    # Separate tag, so the local (native) image isn't replaced by a foreign one
    TAG=latest-$ARCH
    echo "==> Cross-building $APP_IMAGE:$TAG for linux/$ARCH (slower, uses emulation)"
    docker buildx build --platform "linux/$ARCH" --load -t "$APP_IMAGE:$TAG" .
fi
echo "==> Pulling $MOSQUITTO_IMAGE for linux/$ARCH"
docker pull -q --platform "linux/$ARCH" "$MOSQUITTO_IMAGE"

for image in "$APP_IMAGE:$TAG" "$MOSQUITTO_IMAGE"; do
    got=$(docker image inspect -f '{{.Architecture}}' "$image")
    [ "$got" = "$ARCH" ] || { echo "$image is $got, expected $ARCH" >&2; exit 1; }
done

rm -rf "$OUT"
mkdir -p "$OUT/mosquitto"
echo "==> Saving images"
docker save "$APP_IMAGE:$TAG" "$MOSQUITTO_IMAGE" | gzip > "$OUT/images.tar.gz"

if [ "$ARCH" != "$HOST_ARCH" ]; then
    docker pull -q --platform "linux/$HOST_ARCH" "$MOSQUITTO_IMAGE" >/dev/null  # restore the native one
fi

# Compose file without the build section, pointing at the saved image
awk -v image="$APP_IMAGE:$TAG" '
    /^    build:/ { skip = 1; next }
    skip && /^      / { next }
    { skip = 0 }
    /^    image: extended-dashboard:/ { sub(/extended-dashboard:.*/, image) }
    { print }
' docker-compose.yml > "$OUT/docker-compose.yml"
cp mosquitto/entrypoint.sh "$OUT/mosquitto/"
cp .env.example "$OUT/"
mkdir -p "$OUT/data"

cat > "$OUT/INSTALL.md" <<EOF
# Extended Dashboard — install from images ($ARCH)

Built $(date '+%Y-%m-%d %H:%M') from commit $(git rev-parse --short HEAD 2>/dev/null || echo unknown)$(git diff --quiet 2>/dev/null || echo ' + uncommitted changes').

## Synology (DSM 7.2+, Container Manager installed from Package Center)

1. Copy this archive to the NAS, e.g. into the \`docker\` shared folder with File Station.
2. Enable SSH (Control Panel → Terminal & SNMP), connect (\`ssh admin-user@NAS-IP\`) and run:

   \`\`\`bash
   cd /volume1/docker
   tar xzf $NAME.tar.gz
   cd $NAME
   sudo docker load -i images.tar.gz
   # optional: put your existing config at data/.env (see .env.example)
   sudo chown -R 1000:1000 data          # the dashboard runs as user 1000
   sudo docker compose up -d             # older DSM: sudo docker-compose up -d
   \`\`\`

3. Open \`http://NAS-IP:8080\`. Without data/.env the dashboard starts the setup wizard.

Without SSH: Container Manager → Image → Import → Add from file → \`images.tar.gz\`;
give "Everyone" read/write on the \`data\` folder (File Station → Properties → Permission);
then Container Manager → Project → Create, path = this folder, use the existing docker-compose.yml.

## Any other Linux machine with Docker

\`\`\`bash
tar xzf $NAME.tar.gz && cd $NAME
docker load -i images.tar.gz
sudo chown -R 1000:1000 data
docker compose up -d
\`\`\`

## Notes

- Ports: 8080 (dashboard), 1883 (MQTT broker for the smart meter). If one is taken,
  change the left number in docker-compose.yml, e.g. \`"8081:8080"\`.
- Smart meter: set SMART_METER_ENABLED / SMART_METER_MQTT_USER / SMART_METER_MQTT_PASSWORD
  in data/.env, then \`docker compose up -d\` again. Without user and password the broker
  isn't reachable from the network.
- Update: unpack a newer archive over this folder (data/ is kept), \`docker load\` it,
  then \`docker compose up -d\`.
EOF

tar -czf "dist/$NAME.tar.gz" -C dist "$NAME"
rm -rf "$OUT"
echo "==> dist/$NAME.tar.gz ($(du -h "dist/$NAME.tar.gz" | cut -f1))"
