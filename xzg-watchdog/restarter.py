"""XZG HTTP restarter — logs in and calls /api?action=8&cmd=3 (CMD_ESP_RES)."""

import logging
import urllib.parse
import urllib.request
import http.cookiejar

logger = logging.getLogger(__name__)

_CMD_ESP_RES = "action=8&cmd=3"
_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
    "Accept-Encoding": "identity",
}


class XZGRestarter:
    def __init__(self, host: str, username: str = "", password: str = "", timeout: int = 10):
        self.host = host
        self.username = username
        self.password = password
        self.timeout = timeout
        self._opener = self._build_opener()

    @property
    def restart_url(self) -> str:
        return f"http://{self.host}/api?{_CMD_ESP_RES}"

    def _build_opener(self) -> urllib.request.OpenerDirector:
        jar = http.cookiejar.CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def _login(self) -> bool:
        if not self.username:
            return True  # no auth configured
        url = f"http://{self.host}/login"
        data = urllib.parse.urlencode({
            "username": self.username,
            "password": self.password,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST", headers={
            **_HEADERS,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"http://{self.host}/login",
        })
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                logger.debug("Login response status: %s", resp.status)
                return resp.status == 200
        except Exception as e:
            logger.error("Login failed: %s", e)
            return False

    def restart(self) -> bool:
        """Login and send HTTP restart command. Returns True on success."""
        self._opener = self._build_opener()  # fresh session each time

        if not self._login():
            logger.error("HTTP restart aborted — login failed")
            return False

        url = self.restart_url
        req = urllib.request.Request(url, method="GET", headers={
            **_HEADERS,
            "Referer": f"http://{self.host}/",
        })
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace").strip()
                logger.warning("HTTP restart sent → %s (status %s, body: %r)", url, resp.status, body)
                return True
        except Exception as e:
            logger.error("HTTP restart failed → %s: %s", url, e)
            return False
