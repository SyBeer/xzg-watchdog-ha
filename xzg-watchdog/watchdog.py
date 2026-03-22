"""XZG Watchdog — core logic (MQTT-independent, fully testable)."""

import logging
import time

logger = logging.getLogger(__name__)


class XZGWatchdog:
    """Monitors XZG availability and triggers restart on disconnect."""

    def __init__(self, cooldown_seconds: int = 60):
        self.cooldown_seconds = cooldown_seconds
        self._last_restart_at: float | None = None
        self._restart_count = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def on_availability(self, status: str) -> bool:
        """Called when XZG publishes to avty topic.

        Returns True if restart was triggered, False otherwise.
        """
        status = status.strip().lower()
        if status == "online":
            logger.info("XZG is online")
            return False

        if status == "offline":
            return self._handle_offline()

        logger.warning("Unknown availability status: %r", status)
        return False

    @property
    def restart_count(self) -> int:
        return self._restart_count

    @property
    def seconds_since_last_restart(self) -> float | None:
        if self._last_restart_at is None:
            return None
        return time.monotonic() - self._last_restart_at

    # ── Internal ──────────────────────────────────────────────────────────────

    def _handle_offline(self) -> bool:
        if not self._cooldown_elapsed():
            remaining = self.cooldown_seconds - (time.monotonic() - self._last_restart_at)
            logger.warning("XZG offline — cooldown active, %.0fs remaining", remaining)
            return False

        logger.warning("XZG offline — triggering restart (restart #%d)", self._restart_count + 1)
        self._last_restart_at = time.monotonic()
        self._restart_count += 1
        return True

    def _cooldown_elapsed(self) -> bool:
        if self._last_restart_at is None:
            return True
        return (time.monotonic() - self._last_restart_at) >= self.cooldown_seconds
