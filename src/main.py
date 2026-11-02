"""Entry point: collect news and weather, then publish to Telegram."""

import logging
import re
from datetime import datetime, timedelta, timezone

from . import config
from .fetcher import fetch_news
from .filters import filter_items
from .poster import (
    format_message,
    format_weather_message,
    load_posted,
    save_posted,
    send_to_telegram,
)
from .weather import fetch_weather_forecast, fetch_weather_news

logger = logging.getLogger(__name__)


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _title_key(item):
    """Normalize a title so the same story from two feeds is sent once."""
    title = str(item.get("title", "")).lower()
    title = title.replace("ي", "ی").replace("ك", "ک")
    return "title:" + re.sub(r"\s+", " ", title).strip()


def _deduplicate(items, seen):
    """Drop items already published, already queued, or with a duplicate title."""
    unique = []
    for item in items:
        link = item.get("link", "")
        title = _title_key(item)
        if not link or link in seen or title in seen or title == "title:":
            continue
        seen.add(link)
        seen.add(title)
        unique.append(item)
    return unique


def _publish(items, posted, token, channel_id, seen):
    """Send up to the configured number of items and update posted links."""
    sent = 0
    for item in items:
        text = format_message(item)
        if send_to_telegram(text, token=token, channel_id=channel_id):
            link = item.get("link", "")
            title = _title_key(item)
            posted.append(link)
            posted.append(title)
            seen.add(link)
            seen.add(title)
            sent += 1
            logger.info("Published news: %s", item.get("title", "")[:80])
        else:
            logger.warning("Skipped news after send failure: %s", item.get("title", "")[:80])
    save_posted(posted)
    return sent


def _forecast_signature():
    """Return the current date in Tehran so the forecast posts once a day."""
    tehran = timezone(timedelta(hours=3, minutes=30))
    today = datetime.now(tehran).strftime("%Y-%m-%d")
    return f"weather:{today}"


def run():
    """Execute one full news and weather publishing cycle."""
    token, channel_id = config.get_telegram_credentials()
    posted = load_posted()
    seen = set(posted)

    logger.info("Starting run with %d previously posted links", len(posted))

    # 1. Ordinary news.
    news_items = fetch_news(config.NEWS_FEEDS)
    allowed_news = filter_items(news_items)
    unique_news = _deduplicate(allowed_news, seen)
    news_to_send = unique_news[: config.MAX_NEWS_POSTS]
    logger.info("Preparing %d news posts", len(news_to_send))
    news_sent = _publish(news_to_send, posted, token, channel_id, seen)

    # 2. Weather news and live forecast share the weather post budget.
    weather_items = fetch_weather_news()
    unique_weather = _deduplicate(weather_items, seen)

    forecast = fetch_weather_forecast()
    forecast_key = _forecast_signature() if forecast else None
    forecast_pending = bool(forecast_key) and forecast_key not in seen

    weather_budget = config.MAX_WEATHER_POSTS
    news_budget = max(weather_budget - (1 if forecast_pending else 0), 0)
    weather_to_send = unique_weather[:news_budget]

    logger.info(
        "Preparing %d weather news posts and forecast=%s",
        len(weather_to_send),
        forecast_pending,
    )
    weather_sent = _publish(weather_to_send, posted, token, channel_id, seen)

    forecast_sent = 0
    if forecast_pending and weather_budget > weather_sent:
        text = format_weather_message(forecast)
        if send_to_telegram(text, token=token, channel_id=channel_id):
            posted.append(forecast_key)
            seen.add(forecast_key)
            forecast_sent = 1
            logger.info("Published forecast for %d cities", len(forecast))
        else:
            logger.warning("Forecast send failed")

    save_posted(posted)
    logger.info(
        "Run finished: news=%d weather_news=%d forecast=%d",
        news_sent,
        weather_sent,
        forecast_sent,
    )
    return news_sent + weather_sent + forecast_sent


def main():
    _setup_logging()
    try:
        run()
    except RuntimeError as exc:
        logger.error("Configuration error: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
