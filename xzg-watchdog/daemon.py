"""XZG Watchdog daemon — MQTT listener that restarts XZG on disconnect."""

import json
import logging
import os
import sys
import time

import paho.mqtt.client as mqtt

from watchdog import XZGWatchdog

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "")

handlers: list[logging.Handler] = [logging.StreamHandler()]
if LOG_FILE:
    handlers.append(logging.FileHandler(LOG_FILE))

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=handlers,
)
logger = logging.getLogger("xzg-watchdog")

# ── Config ────────────────────────────────────────────────────────────────────

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
XZG_NAME = os.getenv("XZG_NAME")          # e.g. "XZG-1A2B"
COOLDOWN = int(os.getenv("RESTART_COOLDOWN_SEC", "120"))

if not XZG_NAME:
    logger.error("XZG_NAME env var is required (e.g. XZG-1A2B)")
    sys.exit(1)

AVTY_TOPIC = f"{XZG_NAME}/avty"
CMD_TOPIC = f"{XZG_NAME}/cmd"

# ── MQTT callbacks ────────────────────────────────────────────────────────────

watchdog = XZGWatchdog(cooldown_seconds=COOLDOWN)


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info("Connected to MQTT broker %s:%d", MQTT_HOST, MQTT_PORT)
        client.subscribe(AVTY_TOPIC)
        logger.info("Subscribed to %s", AVTY_TOPIC)
    else:
        logger.error("MQTT connect failed, rc=%d", rc)


def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8", errors="replace")
    logger.debug("← %s: %r", msg.topic, payload)

    should_restart = watchdog.on_availability(payload)
    if should_restart:
        restart_cmd = json.dumps({"cmd": "rst_esp"})
        client.publish(CMD_TOPIC, restart_cmd)
        logger.warning("→ %s: %s  (total restarts: %d)", CMD_TOPIC, restart_cmd, watchdog.restart_count)


def on_disconnect(client, userdata, rc, properties=None):
    if rc != 0:
        logger.warning("Unexpected MQTT disconnect (rc=%d), reconnecting…", rc)


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    logger.info("XZG Watchdog starting — device=%s cooldown=%ds", XZG_NAME, COOLDOWN)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()
