"""XZG HTTP restarter — calls /api?action=8&cmd=3 (CMD_ESP_RES) directly on device."""

import logging
import urllib.request

logger = logging.getLogger(__name__)

# XZG HTTP API: action=8 → API_CMD, cmd=3 → CMD_ESP_RES (restart ESP32)
_CMD_ESP_RES = "action=8&cmd=3"


class XZGRestarter:
    def __init__(self, host: str, timeout: int = 10):
        self.host = host
        self.timeout = timeout

    @property
    def restart_url(self) -> str:
        return f"http://{self.host}/api?{_CMD_ESP_RES}"

    def restart(self) -> bool:
        """Send HTTP restart command to XZG. Returns True on success."""
        url = self.restart_url
        try:
            req = urllib.request.Request(url, method="GET", headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "*/*",
            })
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace").strip()
                logger.warning("HTTP restart sent → %s (status %s, body: %r)", url, resp.status, body)
                return True
        except Exception as e:
            logger.error("HTTP restart failed → %s: %s", url, e)
            return False
