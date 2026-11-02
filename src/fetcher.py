"""RSS fetching utilities shared by the news and weather modules."""

import html
import logging
import re

import feedparser
import requests

REQUEST_TIMEOUT = 20
MAX_ENTRIES_PER_FEED = 40

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")

logger = logging.getLogger(__name__)

# A single run fetches the same agency feed for both the news and the weather
# section. Cache the parsed items per URL so each feed is downloaded once.
_feed_cache = {}


def clean_text(value):
    """Strip HTML tags and collapse whitespace from feed text."""
    if not value:
        return ""
    text = html.unescape(_TAG_RE.sub(" ", str(value)))
    return _SPACE_RE.sub(" ", text).strip()


def fetch_feed(url, source, use_cache=True):
    """Fetch one RSS feed and return a list of normalized item dicts."""
    if use_cache and url in _feed_cache:
        return [dict(item, source=source) for item in _feed_cache[url]]

    content = None
    try:
        response = requests.get(
            url,
            headers=config.DEFAULT_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        content = response.content
    except requests.RequestException as exc:
        logger.warning(
            "Could not download feed %s (%s): %s; falling back to feedparser",
            source,
            url,
            exc,
        )

    try:
        parsed = feedparser.parse(content if content is not None else url)
    except Exception as exc:  # A malformed feed must not stop other sources.
        logger.warning("Could not parse feed %s (%s): %s", source, url, exc)
        return []

    if not parsed.entries:
        logger.warning("Feed %s has no entries or is invalid: %s", source, url)
        return []

    items = []
    for entry in parsed.entries[:MAX_ENTRIES_PER_FEED]:
        try:
            title = clean_text(entry.get("title", ""))
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue

            content = entry.get("content") or []
            content_summary = content[0].get("value", "") if content else ""
            summary = clean_text(
                entry.get("summary")
                or entry.get("description")
                or content_summary
            )
            published = (
                entry.get("published")
                or entry.get("updated")
                or entry.get("pubDate")
                or ""
            )
        except (AttributeError, IndexError, TypeError, ValueError) as exc:
            logger.warning("Skipping malformed item from %s: %s", source, exc)
            continue

        items.append(
            {
                "title": title,
                "summary": summary,
                "link": link,
                "source": source,
                "published": published,
            }
        )

    logger.info("Fetched %d items from %s", len(items), source)
    if use_cache:
        _feed_cache[url] = items
    return [dict(item) for item in items]


def fetch_news(feeds):
    """Fetch every configured feed and return one flat list of items."""
    items = []
    for feed in feeds:
        items.extend(fetch_feed(feed["url"], feed["name"]))
    logger.info("Fetched %d items from %d feeds", len(items), len(feeds))
    return items


def fetch_all_news(feeds):
    """Backward-compatible name for :func:`fetch_news`."""
    return fetch_news(feeds)
