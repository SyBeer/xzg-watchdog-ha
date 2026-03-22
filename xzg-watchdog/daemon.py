"""XZG Watchdog daemon — MQTT listener that restarts XZG on disconnect."""

import json
import logging
import os
import sys
import threading

import paho.mqtt.client as mqtt

from watchdog import XZGWatchdog
from restarter import XZGRestarter

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
XZG_NAME = os.getenv("XZG_NAME")
XZG_HOST = os.getenv("XZG_HOST", "")
COOLDOWN = int(os.getenv("RESTART_COOLDOWN_SEC", "120"))
PERIODIC_HOURS = float(os.getenv("RESTART_INTERVAL_HOURS", "0"))

if not XZG_NAME:
    logger.error("XZG_NAME env var is required (e.g. UZG-01-BEDA)")
    sys.exit(1)

if not XZG_HOST:
    logger.error("XZG_HOST env var is required (e.g. 192.168.1.245)")
    sys.exit(1)

AVTY_TOPIC = f"{XZG_NAME}/avty"
CMD_TOPIC = f"{XZG_NAME}/cmd"
BUTTON_CMD_TOPIC = "xzg-watchdog/restart/set"
DISCOVERY_TOPIC = "homeassistant/button/xzg_watchdog/restart/config"

# ── Core objects ──────────────────────────────────────────────────────────────

watchdog = XZGWatchdog(cooldown_seconds=COOLDOWN, periodic_interval_hours=PERIODIC_HOURS)
restarter = XZGRestarter(host=XZG_HOST)

# ── Restart helper ────────────────────────────────────────────────────────────


_manual_restart_count = 0


def do_restart(client, reason: str):
    global _manual_restart_count
    logger.warning("Restarting XZG — reason: %s", reason)
    ok = restarter.restart()
    if not ok:
        fallback = json.dumps({"cmd": "rst_esp"})
        client.publish(CMD_TOPIC, fallback)
        logger.warning("HTTP failed — sent MQTT fallback → %s", CMD_TOPIC)
    _manual_restart_count += 1
    logger.warning("Total restarts (auto: %d, manual: %d)",
                   watchdog.restart_count, _manual_restart_count)


# ── MQTT callbacks ────────────────────────────────────────────────────────────


def _publish_discovery(client):
    payload = json.dumps({
        "name": "XZG Restart",
        "unique_id": "xzg_watchdog_restart_btn",
        "command_topic": BUTTON_CMD_TOPIC,
        "payload_press": "PRESS",
        "device": {
            "identifiers": ["xzg_watchdog"],
            "name": "XZG Watchdog",
            "model": "XZG Watchdog",
            "manufacturer": "SyBeer",
        },
    })
    client.publish(DISCOVERY_TOPIC, payload, retain=True)
    logger.info("MQTT discovery published — button entity registered in HA")


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info("Connected to MQTT broker %s:%d", MQTT_HOST, MQTT_PORT)
        client.subscribe(AVTY_TOPIC)
        client.subscribe(BUTTON_CMD_TOPIC)
        logger.info("Subscribed to %s, %s", AVTY_TOPIC, BUTTON_CMD_TOPIC)
        _publish_discovery(client)
    else:
        logger.error("MQTT connect failed, rc=%d", rc)


def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8", errors="replace")
    logger.debug("← %s: %r", msg.topic, payload)

    if msg.topic == BUTTON_CMD_TOPIC and payload == "PRESS":
        logger.warning("Manual restart triggered via HA button")
        do_restart(client, "manual button")
        return

    if msg.topic == AVTY_TOPIC:
        should_restart = watchdog.on_availability(payload)
        if should_restart:
            do_restart(client, "device offline")


def on_disconnect(client, userdata, rc, properties=None):
    if rc != 0:
        logger.warning("Unexpected MQTT disconnect (rc=%d), reconnecting…", rc)


# ── Periodic restart thread ───────────────────────────────────────────────────


def _periodic_loop(client):
    import time
    watchdog.should_periodic_restart()  # initialize timer
    if PERIODIC_HOURS > 0:
        logger.info("Periodic restart enabled every %.1f h", PERIODIC_HOURS)
    while True:
        time.sleep(60)
        if watchdog.should_periodic_restart():
            logger.warning("Periodic restart triggered (interval=%.1fh)", PERIODIC_HOURS)
            watchdog.on_periodic_restart()
            do_restart(client, f"periodic ({PERIODIC_HOURS}h interval)")


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    logger.info(
        "XZG Watchdog starting — device=%s host=%s cooldown=%ds periodic=%.1fh",
        XZG_NAME, XZG_HOST, COOLDOWN, PERIODIC_HOURS,
    )

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    t = threading.Thread(target=_periodic_loop, args=(client,), daemon=True)
    t.start()

    client.loop_forever()


if __name__ == "__main__":
    main()
