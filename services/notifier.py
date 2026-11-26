"""
Notifier (Week 3)

Sends Telegram messages from background jobs (scheduler, admin scripts) without
opening a second Telethon session — the bot process already owns that session,
and a duplicate would be killed by Telegram.

Uses the plain Bot API over HTTPS with `BOT_TOKEN` from the environment.
The HTTP call is injectable so tests never touch the network.
"""

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

API_BASE = "https://api.telegram.org"

# (url, body_bytes, timeout_seconds) -> None, raising on transport/API failure
Transport = Callable[[str, bytes, float], None]


@dataclass(frozen=True)
class SendResult:
    ok: bool
    error: str | None = None


def _default_transport(url: str, body: bytes, timeout: float) -> None:
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8") or "{}")
    if not payload.get("ok", False):
        raise RuntimeError(payload.get("description") or "telegram api returned ok=false")


class BotNotifier:
    """
    Thin, fail-soft Telegram sender.

    When no token is configured it reports `enabled=False` and every send is a
    no-op `SendResult(ok=False, error="not_configured")`, so jobs can run on a
    dev machine without sending anything.
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        timeout: float = 10.0,
        transport: Transport | None = None,
        api_base: str = API_BASE,
    ) -> None:
        self.token = (token if token is not None else os.getenv("BOT_TOKEN", "")).strip()
        self.timeout = timeout
        self._transport = transport or _default_transport
        self.api_base = api_base

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def send(self, chat_id: int | str, html: str) -> SendResult:
        if not self.enabled:
            return SendResult(False, "not_configured")
        url = f"{self.api_base}/bot{self.token}/sendMessage"
        body = json.dumps(
            {
                "chat_id": chat_id,
                "text": html,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        try:
            self._transport(url, body, self.timeout)
        except urllib.error.HTTPError as e:  # pragma: no cover - network path
            return SendResult(False, f"http_{e.code}")
        except Exception as e:
            return SendResult(False, str(e)[:200])
        return SendResult(True)


def owner_chat_id() -> int | str | None:
    """The operator's chat id from `MY_CHAT_ID`, normalised like the bot does."""
    raw = os.getenv("MY_CHAT_ID", "").strip()
    if not raw:
        return None
    return int(raw) if raw.lstrip("-").isdigit() else raw
