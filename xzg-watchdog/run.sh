#!/usr/bin/with-contenv bashio

export XZG_NAME=$(bashio::config 'xzg_name')
export XZG_HOST=$(bashio::config 'xzg_host')
export MQTT_HOST=$(bashio::config 'mqtt_host')
export MQTT_PORT=$(bashio::config 'mqtt_port')
export MQTT_USER=$(bashio::config 'mqtt_user')
export MQTT_PASS=$(bashio::config 'mqtt_pass')
export RESTART_COOLDOWN_SEC=$(bashio::config 'restart_cooldown_sec')
export RESTART_INTERVAL_HOURS=$(bashio::config 'restart_interval_hours')
export LOG_LEVEL=$(bashio::config 'log_level' | tr '[:lower:]' '[:upper:]')

bashio::log.info "Starting XZG Watchdog for device: ${XZG_NAME} (${XZG_HOST})"
bashio::log.info "MQTT broker: ${MQTT_HOST}:${MQTT_PORT}"

exec python3 /app/daemon.py
