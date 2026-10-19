#!/bin/sh
# Mosquitto broker for the smart meter (docker-compose service "mosquitto").
# Builds the config at start from SMART_METER_MQTT_USER / SMART_METER_MQTT_PASSWORD
# in data/.env (mounted read-only at /dashboard-data). Without credentials the
# broker only listens inside its own container, so it is never open to the
# network unauthenticated.
set -e
DATA=/mosquitto/data
CONF="$DATA/mosquitto.conf"
ENV_FILE=/dashboard-data/.env
mkdir -p "$DATA"

# Last KEY=value line for KEY in data/.env, without surrounding quotes
env_value() {
    [ -f "$ENV_FILE" ] || return 0
    sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" "$ENV_FILE" | tail -n 1 |
        sed -e 's/\r$//' -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"
}
# Values from the environment (docker run -e ...) win over data/.env
SMART_METER_MQTT_USER="${SMART_METER_MQTT_USER:-$(env_value SMART_METER_MQTT_USER)}"
SMART_METER_MQTT_PASSWORD="${SMART_METER_MQTT_PASSWORD:-$(env_value SMART_METER_MQTT_PASSWORD)}"

if [ -n "$SMART_METER_MQTT_USER" ] && [ -n "$SMART_METER_MQTT_PASSWORD" ]; then
    rm -f "$DATA/passwd"
    mosquitto_passwd -b -c "$DATA/passwd" "$SMART_METER_MQTT_USER" "$SMART_METER_MQTT_PASSWORD"
    chown mosquitto:mosquitto "$DATA/passwd"
    chmod 0700 "$DATA/passwd"
    cat > "$CONF" <<CONF
listener 1883
allow_anonymous false
password_file $DATA/passwd
persistence true
persistence_location $DATA/
log_dest stdout
CONF
    echo "Mosquitto: listening on port 1883, login required (user: $SMART_METER_MQTT_USER)"
else
    cat > "$CONF" <<CONF
listener 1883 127.0.0.1
allow_anonymous true
log_dest stdout
CONF
    echo "Mosquitto: SMART_METER_MQTT_USER/SMART_METER_MQTT_PASSWORD not set in data/.env;" \
         "broker is NOT reachable from the network until they are set"
fi
chown -R mosquitto:mosquitto "$DATA"
exec mosquitto -c "$CONF"
