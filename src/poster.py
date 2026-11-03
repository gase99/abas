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

# Safe margin under the Telegram 4096-character limit for forecast messages.
WEATHER_MESSAGE_LIMIT = 3500

# Mapping of feed source names to friendly Persian display names.
SOURCE_NAME_MAP = {
    "BBC Persian": "بی‌بی‌سی فارسی",
    "Iran International": "ایران اینترنشنال",
    "IRNA": "ایرنا",
    "ISNA": "ایسنا",
    "Khabaronline": "خبرآنلاین",
    "Mehr Khuzestan": "مهر خوزستان",
    "Sahebkhabar": "صاحبخبر",
    "Borna": "برنا",
    "Khuzestan Bartar": "خوزستان برتر",
    "Fars Khuzestan": "فارس خوزستان",
}


def _nice_source_name(source: str) -> str:
    """Return a friendly Persian name for a feed source."""
    return SOURCE_NAME_MAP.get(source, source)


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
    """Build the Telegram text for a news item using HTML.

    Format:
        🔶 <b>#خوزستان</b>   (only when the item is Khuzestan-related)

        <b>{title}</b>

        <i>{summary}</i>

        📌 منبع: {source_name}

    The raw link is intentionally omitted to keep the message clean.
    """
    lines = []

    if item.get("is_khuzestan"):
        lines.append("🔶 <b>#خوزستان</b>")
        lines.append("")

    title = html.escape(item.get("title", "").strip())
    lines.append(f"<b>{title}</b>")
    lines.append("")

    summary = (item.get("summary") or "").strip()
    if summary:
        lines.append(
            f"<i>{html.escape(truncate(summary, config.SUMMARY_MAX_LENGTH))}</i>"
        )
        lines.append("")

    source = (item.get("source") or "").strip()
    if source:
        nice_source = _nice_source_name(source)
        lines.append(f"📌 منبع: {html.escape(nice_source)}")

    return "\n".join(lines)


def format_weather_message(weather_data):
    """Build the daily Khuzestan forecast message(s) with blockquote.

    Each returned message is at most WEATHER_MESSAGE_LIMIT characters so long
    forecasts are never truncated. A list is always returned; callers should
    send every member separately.
    """
    header = "🌤️ <b>پیش‌بینی آب و هوای خوزستان</b>"

    entries = []
    for entry in weather_data:
        city = html.escape(str(entry.get("city", "")))
        temp_max = entry.get("temp_max", "-")
        temp_min = entry.get("temp_min", "-")
        precipitation = entry.get("precipitation_probability", 0)
        description = html.escape(
            str(entry.get("weather_description", "نامشخص"))
        )

        entries.append(
            f"📍 <b>{city}</b>: بیشینه {temp_max}°C / کمینه {temp_min}°C — "
            f"احتمال بارش {precipitation}% — {description}"
        )

    def build_message(block_entries: list) -> str:
        inner = "\n".join(block_entries)
        return (
            f"{header}\n\n"
            f"<blockquote>\n{inner}\n</blockquote>"
        )

    messages = []
    current_entries = []
    current_length = len(header) + len("<blockquote>\n\n</blockquote>")

    for entry_text in entries:
        entry_addition = ("\n" + entry_text) if current_entries else entry_text
        trial_length = current_length + len(entry_addition)
        if trial_length > WEATHER_MESSAGE_LIMIT and current_entries:
            messages.append(build_message(current_entries))
            current_entries = [entry_text]
            current_length = (
                len(header)
                + len("<blockquote>\n")
                + len(entry_text)
                + len("\n</blockquote>")
            )
        else:
            current_entries.append(entry_text)
            current_length = trial_length

    if current_entries:
        messages.append(build_message(current_entries))

    if not messages:
        messages.append(
            f"{header}\n\n<blockquote>\nهیچ اطلاعات هواشناسی در حال حاضر موجود نیست.\n</blockquote>"
        )

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