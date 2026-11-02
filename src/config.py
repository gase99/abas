"""Project configuration: environment variables, feeds, keywords and coordinates."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
POSTED_FILE = BASE_DIR / "posted.json"

# Load .env for local runs. GitHub Actions provides the variables as secrets.
load_dotenv(BASE_DIR / ".env")

# Maximum number of ordinary news posts and weather posts per run.
MAX_NEWS_POSTS = 5
MAX_WEATHER_POSTS = 3

# Maximum summary length used when building Telegram messages.
SUMMARY_MAX_LENGTH = 300

# Ordinary news feeds (all free and public).
NEWS_FEEDS = [
    {"name": "BBC Persian", "url": "https://feeds.bbci.co.uk/persian/rss.xml"},
    {"name": "Iran International", "url": "https://www.iranintl.com/feed"},
    {"name": "IRNA", "url": "https://www.irna.ir/rss"},
    {"name": "ISNA", "url": "https://www.isna.ir/rss"},
    {"name": "Khabaronline", "url": "https://www.khabaronline.ir/rss"},
    {"name": "Mehr Khuzestan", "url": "https://www.mehrnews.com/rss/tp/92"},
    {"name": "Sahebkhabar", "url": "https://sahebkhabar.ir/rss"},
    {"name": "Borna", "url": "https://borna.news/fa/rss/allnews"},
]

# Feeds used by the weather news section. Some agencies change or block their
# feed URLs; a failing feed is logged and skipped without stopping the run.
WEATHER_NEWS_FEEDS = [
    {"name": "Mehr Khuzestan", "url": "https://www.mehrnews.com/rss/tp/92"},
    {"name": "IRNA", "url": "https://www.irna.ir/rss"},
    {"name": "Borna", "url": "https://borna.news/fa/rss/allnews"},
    {"name": "Sahebkhabar", "url": "https://sahebkhabar.ir/rss"},
    {"name": "ISNA", "url": "https://www.isna.ir/rss"},
    {"name": "Khabaronline", "url": "https://www.khabaronline.ir/rss"},
    {"name": "Khuzestan Bartar", "url": "https://khouzestanbartar.ir/rss"},
    # Fars currently serves HTML instead of RSS at this address. It is kept so
    # the feed is picked up automatically if the agency restores it.
    {"name": "Fars Khuzestan", "url": "https://farsnews.ir/rss/استان-ها/خوزستان"},
]

IRAN_KEYWORDS = [
    "ایران",
    "ایرانی",
    "Iran",
    "Iranian",
    "تهران",
    "Tehran",
]

# Cities and regions of Khuzestan in Persian and English.
KHUZESTAN_KEYWORDS = [
    "خوزستان",
    "خوزستانی",
    "اهواز",
    "اهوازی",
    "آبادان",
    "آبادانی",
    "خرمشهر",
    "خرمشهری",
    "دزفول",
    "دزفولی",
    "اندیمشک",
    "بهبهان",
    "ماهشهر",
    "شوشتر",
    "شوش",
    "ایذه",
    "باغ‌ملک",
    "باغملک",
    "رامهرمز",
    "مسجدسلیمان",
    "مسجد سلیمان",
    "هفتکل",
    "هندیجان",
    "امیدیه",
    "آغاجاری",
    "رامشیر",
    "هویزه",
    "سوسنگرد",
    "بستان",
    "شادگان",
    "لالی",
    "اندیکا",
    "گتوند",
    "دشت آزادگان",
    "کارون",
    "حمیدیه",
    "بندر امام خمینی",
    "بندر ماهشهر",
    "Ahvaz",
    "Abadan",
    "Khorramshahr",
    "Dezful",
    "Andimeshk",
    "Behbahan",
    "Mahshahr",
    "Shushtar",
    "Shush",
    "Izeh",
    "Baghmalek",
    "Ramhormoz",
    "Masjed Soleyman",
    "Haftkel",
    "Hendijan",
    "Omidiyeh",
    "Aghajari",
    "Ramshir",
    "Hoveyzeh",
    "Susangerd",
    "Bostan",
    "Shadegan",
    "Lali",
    "Andika",
    "Gotvand",
    "Dasht-e Azadegan",
    "Karun",
    "Hamidiyeh",
    "Bandar Imam Khomeini",
]

VIOLENT_KEYWORDS = [
    "کشته",
    "کشتار",
    "کشته و زخمی",
    "زخمی",
    "حمله",
    "حملات",
    "انفجار",
    "بمب",
    "بمباران",
    "خون",
    "خونریزی",
    "جنازه",
    "ترور",
    "تروریستی",
    "شلیک",
    "گلوله",
    "تیراندازی",
    "درگیری مسلحانه",
    "dead",
    "killed",
    "blood",
    "bomb",
    "explosion",
    "attack",
    "shot",
    "corpse",
    "terror",
]

WEATHER_KEYWORDS = [
    "آب و هوا",
    "آبوهوا",
    "هواشناسی",
    "بارش",
    "بارشی",
    "بارندگی",
    "دما",
    "گرما",
    "سرما",
    "رگبار",
    "رگباری",
    "تندباد",
    "سامانه بارشی",
    "هشدار هواشناسی",
    "هوای استان",
    "هوای خوزستان",
    "وضعیت هوای",
    "آلودگی هوا",
    "پیش‌بینی هوا",
    "پیش بینی هوا",
    "پیش‌بینی آب و هوا",
    "وضعیت هوا",
    "دمای هوا",
    "دمای",
    "باران",
    "برف",
    "برفی",
    "سیل",
    "سیلابی",
    "گرد و غبار",
    "ریزگرد",
    "طوفان",
    "آبگرفتگی",
    "forecast",
    "weather",
]

# Coordinates for all cities covered by the forecast section.
CITY_COORDINATES = {
    "اهواز": (31.3183, 48.6706),
    "آبادان": (30.3392, 48.3043),
    "خرمشهر": (30.4404, 48.1760),
    "دزفول": (32.3831, 48.4057),
    "اندیمشک": (32.4536, 48.3567),
    "بهبهان": (30.5959, 50.2417),
    "ماهشهر": (30.5589, 49.1981),
    "بندر امام خمینی": (30.4300, 49.0800),
    "شوشتر": (32.0450, 48.8567),
    "شوش": (32.1942, 48.2436),
    "ایذه": (31.8322, 49.8694),
    "باغ‌ملک": (31.5231, 49.8847),
    "رامهرمز": (31.2800, 49.6036),
    "مسجدسلیمان": (31.9364, 49.3039),
    "هفتکل": (31.4460, 49.5290),
    "هندیجان": (30.2364, 49.7119),
    "امیدیه": (30.7622, 49.7047),
    "آغاجاری": (30.7000, 49.8300),
    "رامشیر": (30.8950, 49.4090),
    "هویزه": (31.4620, 48.0750),
    "سوسنگرد": (31.5600, 48.1800),
    "بستان": (31.7160, 48.2700),
    "شادگان": (30.6490, 48.6650),
    "لالی": (32.3280, 49.0930),
    "اندیکا": (32.2000, 49.4500),
    "گتوند": (32.2500, 48.8300),
    "حمیدیه": (31.5000, 48.4300),
    "کارون": (31.1500, 48.4800),
    "باوی": (31.5800, 48.8800),
    "ملاثانی": (31.5850, 48.8850),
    "دزپارت": (31.9000, 50.1000),
    "اروندکنار": (30.0500, 48.4500),
    "مینوشهر": (30.3500, 48.2200),
}

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_TIMEOUT = 20
OPEN_METEO_MAX_CITIES_PER_REQUEST = 10

TELEGRAM_API_URL = "https://api.telegram.org"


def get_telegram_credentials():
    """Return (token, channel_id) or raise a clear error when values are missing."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()

    missing = []
    if not token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not channel_id:
        missing.append("TELEGRAM_CHANNEL_ID")

    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill in the values."
        )

    return token, channel_id
