"""Telegram message formatting and delivery."""

import html
import json
import logging
import time
from pathlib import Path

import requests

from . import config

logger = logging.getLogger(__name__)

TELEGRAM_TIMEOUT = 20
MAX_TELEGRAM_MESSAGE_LENGTH = 4096
MAX_POSTED_ENTRIES = 2000
KHUZESTAN_TAG = "🔶 خوزستان"

# Safe margin under the Telegram 4096-character limit for forecast messages.
WEATHER_MESSAGE_LIMIT = 3500


def load_posted(path=None):
    """Load the list of already published links from posted.json."""
    target = Path(path) if path else config.POSTED_FILE
    if not target.exists():
        return []

    try:
        with target.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read %s: %s", target, exc)
        return []

    if not isinstance(data, list):
        logger.warning("%s does not contain a list, starting fresh", target)
        return []

    return [str(value) for value in data]


def save_posted(posted, path=None):
    """Persist published links to posted.json, keeping the file small."""
    target = Path(path) if path else config.POSTED_FILE
    trimmed = posted[-MAX_POSTED_ENTRIES:]
    try:
        with target.open("w", encoding="utf-8") as handle:
            json.dump(trimmed, handle, ensure_ascii=False, indent=2)
    except OSError as exc:
        logger.error("Could not write %s: %s", target, exc)


def truncate(text, limit):
    """Trim text to a maximum length without splitting words awkwardly."""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def format_message(item):
    """Build the Telegram text for a news item."""
    lines = []
    if item.get("is_khuzestan"):
        lines.append(KHUZESTAN_TAG)

    title = html.escape(item.get("title", "").strip())
    lines.append(f"<b>{title}</b>")

    summary = (item.get("summary") or "").strip()
    if summary:
        lines.append(html.escape(truncate(summary, config.SUMMARY_MAX_LENGTH)))

    source = (item.get("source") or "").strip()
    if source:
        lines.append(f"منبع: {html.escape(source)}")

    link = (item.get("link") or "").strip()
    if link:
        lines.append(html.escape(link, quote=False))

    return "\n\n".join(lines)


def format_weather_message(weather_data):
    """Build the daily Khuzestan forecast message(s).

    Each returned message is at most WEATHER_MESSAGE_LIMIT characters so long
    forecasts are never truncated. A list is always returned; callers should
    send every member separately.
    """
    header = "\n".join([KHUZESTAN_TAG, "🌤️ پیش‌بینی آب و هوای خوزستان", ""])

    entries = []
    for entry in weather_data:
        entries.append(
            "📍 {city}: بیشینه {temp_max}°C / کمینه {temp_min}°C — "
            "احتمال بارش {precipitation}% — {description}".format(
                city=html.escape(str(entry.get("city", ""))),
                temp_max=entry.get("temp_max", "-"),
                temp_min=entry.get("temp_min", "-"),
                precipitation=entry.get("precipitation_probability", 0),
                description=html.escape(
                    str(entry.get("weather_description", "نامشخص"))
                ),
            )
        )

    messages = []
    current = header
    for entry_text in entries:
        candidate = current + "\n" + entry_text if current else entry_text
        if len(candidate) > WEATHER_MESSAGE_LIMIT and current != header:
            messages.append(current.strip())
            current = header + "\n" + entry_text
        else:
            current = candidate

    if current.strip():
        messages.append(current.strip())
    if not messages:
        messages.append(header.strip())
    return messages


def send_to_telegram(texts, token=None, channel_id=None):
    """Send one or more HTML messages to the configured Telegram channel.

    Accepts a string or a list of strings; every member is sent separately.
    Never raises: returns True only when every message was accepted.
    """
    if token is None or channel_id is None:
        try:
            token, channel_id = config.get_telegram_credentials()
        except RuntimeError as exc:
            logger.error("Telegram credentials missing: %s", exc)
            return False

    if isinstance(texts, str):
        texts = [texts]

    url = f"{config.TELEGRAM_API_URL}/bot{token}/sendMessage"
    for text in texts:
        payload = {
            "chat_id": channel_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if not _send_one(url, payload):
            return False
    return True


def _retry_after(response):
    """Read Telegram's retry_after seconds from a 429 response (default 5)."""
    try:
        return int(response.json().get("parameters", {}).get("retry_after", 5))
    except (ValueError, TypeError, AttributeError):
        return 5


def _send_one(url, payload):
    """Send a single payload with 429/5xx retries; never raises."""
    try:
        response = requests.post(url, data=payload, timeout=TELEGRAM_TIMEOUT)
    except requests.RequestException as exc:
        logger.error("Telegram request failed: %s", exc)
        return False

    # 429 rate limit: exactly one retry, honoring retry_after when provided.
    if response.status_code == 429:
        delay = _retry_after(response)
        logger.warning("Telegram rate limited (429); retrying after %ss", delay)
        time.sleep(delay)
        try:
            response = requests.post(url, data=payload, timeout=TELEGRAM_TIMEOUT)
        except requests.RequestException as exc:
            logger.error("Telegram 429 retry request failed: %s", exc)
            return False

    # 5xx server errors: up to 2 retries, 3 seconds apart.
    if response.status_code >= 500:
        for attempt in range(1, 3):
            logger.warning(
                "Telegram returned %s; retry %d/2 after 3s",
                response.status_code,
                attempt,
            )
            time.sleep(3)
            try:
                response = requests.post(url, data=payload, timeout=TELEGRAM_TIMEOUT)
            except requests.RequestException as exc:
                logger.error("Telegram 5xx retry request failed: %s", exc)
                return False
            if response.status_code < 500:
                break

    if 400 <= response.status_code < 500:
        logger.error(
            "Telegram returned %s: %s",
            response.status_code,
            truncate(response.text, 500),
        )
        return False

    if response.status_code != 200:
        logger.error(
            "Telegram returned %s: %s",
            response.status_code,
            truncate(response.text, 500),
        )
        return False

    try:
        body = response.json()
    except ValueError:
        logger.error("Telegram returned a non-JSON response")
        return False

    if not body.get("ok"):
        logger.error("Telegram rejected the message: %s", body.get("description"))
        return False

    return True
