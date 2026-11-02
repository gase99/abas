"""Run the whole bot pipeline offline, against a local stub of the internet.

The sandbox that runs this demo has no outbound access to RSS providers,
Open-Meteo or Telegram, so this script starts a small HTTP server on
127.0.0.1 that pretends to be all three services:

* ``/feeds/*.xml``  -> sample Persian RSS feeds (accepted, rejected and duplicate
  items, plus one weather feed and one non-Khuzestan weather item),
* ``/open-meteo``   -> an Open-Meteo ``/v1/forecast`` response for the
  requested batch of cities,
* ``/bot<token>/sendMessage`` -> a fake Telegram Bot API that records the
  messages instead of publishing them.

``src/`` is not modified: the script only points ``src.config`` at the stub and
uses the real ``src.main.run`` code path (fetch -> filter -> dedupe -> format ->
send).  ``posted.json`` is redirected to a temporary file, so the repository is
left untouched.

Usage::

    python tools/offline_demo.py
"""

import json
import logging
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, fetcher, main, poster  # noqa: E402

STUB_PORT = 8765
STUB_BASE = f"http://127.0.0.1:{STUB_PORT}"

SENT_MESSAGES = []

# (title, summary, link) tuples used to build the stub feeds.
FEED_ITEMS = {
    "news": [
        (
            "افزایش صادرات غیرنفتی ایران در ماه گذشته",
            "گزارش گمرک از رشد صادرات غیرنفتی ایران خبر می‌دهد.",
            "https://example.com/iran-1",
        ),
        (
            "افتتاح طرح آبرسانی در اهواز",
            "طرح آبرسانی با حضور مسئولان استان خوزستان به بهره‌برداری رسید.",
            "https://example.com/khuzestan-1",
        ),
        (
            "انفجار در یک کارگاه صنعتی ایران",
            "شمار زخمی‌ها اعلام نشده است.",
            "https://example.com/violent-1",
        ),
        (
            "نتایج مسابقات فوتبال باشگاه‌های آلمان",
            "بایرن مونیخ در خانه به برتری رسید.",
            "https://example.com/unrelated-1",
        ),
        (
            "قیمت نفت و بازار ارز ایران امروز",
            "بازار ارز تهران روند آرامی داشت.",
            "https://example.com/iran-2",
        ),
        (
            "افتتاح بیمارستان در دزفول",
            "بیمارستان تخصصی با ظرفیت ۲۰۰ تخت در دزفول افتتاح شد.",
            "https://example.com/khuzestan-2",
        ),
        (
            "برگزاری جشنواره ملی تئاتر در تهران",
            "جشنواره با حضور گروه‌هایی از سراسر ایران آغاز شد.",
            "https://example.com/iran-3",
        ),
        # Same headline as the first item but a different link: the title
        # dedupe in src.main must drop it.
        (
            "افزایش صادرات غیرنفتی ایران در ماه گذشته",
            "نسخهٔ دوم همین خبر از یک خبرگزاری دیگر.",
            "https://example.com/iran-1-mirror",
        ),
    ],
    "weather": [
        (
            "هشدار هواشناسی خوزستان درباره سامانه بارشی و رگبار",
            "بارش شدید و تندباد در اهواز و آبادان پیش‌بینی می‌شود.",
            "https://example.com/weather-khuzestan",
        ),
        (
            "هشدار هواشناسی درباره بارش در شیراز",
            "سامانه بارشی وارد استان فارس شد.",
            "https://example.com/weather-fars",
        ),
        (
            "افزایش تولید محصولات کشاورزی در ایران",
            "برداشت گندم در استان‌های مختلف آغاز شد.",
            "https://example.com/not-weather",
        ),
    ],
}

CITY_TEMP_OFFSET = {
    "اهواز": 4,
    "آبادان": 5,
    "خرمشهر": 5,
    "دزفول": 2,
}


def _rss(items):
    entries = []
    for index, (title, summary, link) in enumerate(items):
        entries.append(
            "<item>"
            f"<title>{title}</title>"
            f"<link>{link}</link>"
            f"<description><![CDATA[<p>{summary}</p>]]></description>"
            f"<pubDate>Sun, 02 Nov 2026 0{index}:00:00 GMT</pubDate>"
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<rss version="2.0"><channel>'
        "<title>Stub feed</title><link>https://example.com</link>"
        "<description>Offline demo feed</description>"
        + "".join(entries)
        + "</channel></rss>"
    ).encode("utf-8")


def _forecast_payload(latitudes, longitudes):
    payloads = []
    for index, (lat, lon) in enumerate(zip(latitudes, longitudes)):
        base = 20 + (index % 5)
        payloads.append(
            {
                "latitude": lat,
                "longitude": lon,
                "timezone": "Asia/Tehran",
                "daily": {
                    "time": ["2026-11-02"],
                    "temperature_2m_max": [base + 14.4],
                    "temperature_2m_min": [base + 1.6],
                    "precipitation_probability_max": [8 + index],
                    "weathercode": [3 if index % 2 == 0 else 61],
                },
            }
        )
    return payloads[0] if len(payloads) == 1 else payloads


class StubHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep the demo output readable
        pass

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, body, content_type="application/rss+xml; charset=utf-8"):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/feeds/"):
            name = parsed.path.rsplit("/", 1)[-1].removesuffix(".xml")
            items = FEED_ITEMS.get(name)
            if items is None:
                self.send_error(404, "unknown stub feed")
                return
            self._send_bytes(_rss(items))
            return

        if parsed.path == "/open-meteo":
            query = parse_qs(parsed.query)
            latitudes = (query.get("latitude") or [""])[0].split(",")
            longitudes = (query.get("longitude") or [""])[0].split(",")
            self._send_json(_forecast_payload(latitudes, longitudes))
            return

        self.send_error(404, "not found")

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8")
        if self.path.endswith("/sendMessage"):
            fields = parse_qs(raw)
            SENT_MESSAGES.append(
                {
                    "chat_id": (fields.get("chat_id") or [""])[0],
                    "parse_mode": (fields.get("parse_mode") or [""])[0],
                    "text": (fields.get("text") or [""])[0],
                }
            )
            self._send_json(
                {
                    "ok": True,
                    "result": {"message_id": len(SENT_MESSAGES), "chat": {"id": 1}},
                }
            )
            return
        self.send_error(404, "not found")


def _patch_config(posted_path):
    """Point every outbound URL at the local stub."""
    news_feed = {"name": "Stub News", "url": f"{STUB_BASE}/feeds/news.xml"}
    weather_feed = {"name": "Stub Weather", "url": f"{STUB_BASE}/feeds/weather.xml"}

    config.NEWS_FEEDS = [news_feed]
    config.WEATHER_NEWS_FEEDS = [weather_feed]
    config.OPEN_METEO_URL = f"{STUB_BASE}/open-meteo"
    config.TELEGRAM_API_URL = STUB_BASE
    config.POSTED_FILE = Path(posted_path)

    # The stub never keeps the whole city list in one response, but the real
    # batching logic must still be exercised, so keep the production batch size.
    os.environ["TELEGRAM_BOT_TOKEN"] = "000000:OFFLINE-DEMO-TOKEN"
    os.environ["TELEGRAM_CHANNEL_ID"] = "-1001234567890"


def _print_messages(title, messages):
    print(f"\n=== {title} ({len(messages)} message(s)) ===")
    for index, message in enumerate(messages, start=1):
        print(f"\n--- message {index} (chat_id={message['chat_id']}, "
              f"parse_mode={message['parse_mode']}) ---")
        print(message["text"])


def run_demo():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    server = ThreadingHTTPServer(("127.0.0.1", STUB_PORT), StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    with tempfile.TemporaryDirectory() as tmp:
        posted_path = Path(tmp) / "posted.json"
        posted_path.write_text("[]", encoding="utf-8")
        _patch_config(posted_path)

        print("=== run 1: cold start ===")
        first = main.run()
        first_messages = list(SENT_MESSAGES)

        print("\n=== run 2: immediately again (dedupe check) ===")
        fetcher._feed_cache.clear()
        second = main.run()
        second_messages = SENT_MESSAGES[len(first_messages):]

        _print_messages("run 1 messages", first_messages)
        _print_messages("run 2 messages", second_messages)

        posted = json.loads(posted_path.read_text(encoding="utf-8"))
        print("\n=== posted.json written by the demo ===")
        print(json.dumps(posted, ensure_ascii=False, indent=2))
        print(
            f"\nrun 1 published {first} post(s), run 2 published {second} post(s), "
            f"{len(posted)} entries persisted"
        )

    server.shutdown()
    server.server_close()
    return first, second


if __name__ == "__main__":
    run_demo()
