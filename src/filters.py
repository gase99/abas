"""Filtering rules for Iran relevance, Khuzestan relevance and violent content."""

import logging
import re

from . import config

logger = logging.getLogger(__name__)

# Matches a keyword only at the start of a word so that short terms such as
# "دما" do not match inside unrelated words such as "خدمات".
_LETTER_CLASS = "0-9A-Za-z\u0600-\u06FF"


def _normalize(text):
    """Normalize Persian/Arabic letters and whitespace for matching."""
    value = str(text or "")
    value = value.replace("ي", "ی").replace("ك", "ک")
    value = value.replace("\u200c", " ").replace("\u200f", " ")
    value = re.sub(r"\s+", " ", value)
    return value.lower()


def _haystack(item):
    """Combine title and summary into a normalized search string."""
    return _normalize(f"{item.get('title', '')} {item.get('summary', '')}")


def _contains_any(text, keywords):
    for keyword in keywords:
        needle = _normalize(keyword)
        if not needle:
            continue
        # Persian keywords must match whole words; ASCII keywords may take
        # common inflections such as "attacks" or "killed".
        if needle.isascii():
            pattern = rf"(?<![{_LETTER_CLASS}]){re.escape(needle)}"
        else:
            pattern = rf"(?<![{_LETTER_CLASS}]){re.escape(needle)}(?![{_LETTER_CLASS}])"
        if re.search(pattern, text):
            return True
    return False


def matches_iran(item):
    """Return True when the item mentions Iran or Tehran."""
    return _contains_any(_haystack(item), config.IRAN_KEYWORDS)


def matches_khuzestan(item):
    """Return True when the item mentions a Khuzestan city or region."""
    return _contains_any(_haystack(item), config.KHUZESTAN_KEYWORDS)


def is_violent(item):
    """Return True when the item contains a blocked violent keyword."""
    return _contains_any(_haystack(item), config.VIOLENT_KEYWORDS)


def is_weather_related(item):
    """Return True when the item mentions weather or forecast terms."""
    return _contains_any(_haystack(item), config.WEATHER_KEYWORDS)


def filter_items(items):
    """Return allowed news items flagged with is_khuzestan.

    An item is accepted when it matches Iran or Khuzestan and is not violent.
    Rejected items are logged with a short reason.
    """
    allowed = []
    for item in items:
        title = item.get("title", "")[:80]

        if is_violent(item):
            logger.info("Rejected (violent): %s", title)
            continue

        in_khuzestan = matches_khuzestan(item)
        if not (in_khuzestan or matches_iran(item)):
            logger.info("Rejected (no Iran/Khuzestan match): %s", title)
            continue

        filtered = dict(item)
        filtered["is_khuzestan"] = in_khuzestan
        allowed.append(filtered)

    logger.info("Filter kept %d of %d items", len(allowed), len(items))
    return allowed


def filter_weather_items(items):
    """Return non-violent weather stories that specifically concern Khuzestan."""
    allowed = []
    for item in items:
        title = item.get("title", "")[:80]
        if is_violent(item):
            logger.info("Rejected weather item (blocked keyword): %s", title)
            continue
        if not is_weather_related(item):
            logger.info("Rejected weather item (not weather related): %s", title)
            continue
        if not matches_khuzestan(item):
            logger.info("Rejected weather item (not Khuzestan-related): %s", title)
            continue
        filtered = dict(item)
        filtered["is_khuzestan"] = True
        allowed.append(filtered)
    logger.info("Weather filter kept %d of %d items", len(allowed), len(items))
    return allowed
