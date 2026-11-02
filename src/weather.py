"""Weather news and live forecast collection for Khuzestan."""

import logging

import requests

from . import config
from .fetcher import fetch_news
from .filters import filter_weather_items, matches_khuzestan

logger = logging.getLogger(__name__)

# WMO weather code groups used by Open-Meteo.
WEATHER_CODE_GROUPS = [
    (range(0, 1), "صاف"),
    (range(1, 4), "نیمه‌ابری"),
    (range(4, 20), "ابری"),
    (range(45, 49), "مه"),
    (range(51, 58), "نم‌نم باران"),
    (range(61, 68), "باران"),
    (range(71, 78), "برف"),
    (range(80, 83), "رگبار"),
    (range(85, 87), "رگبار برف"),
    (range(95, 100), "رعدوبرق"),
]


def weather_code_to_description(code):
    """Convert an Open-Meteo WMO weather code to a Persian description."""
    try:
        value = int(code)
    except (TypeError, ValueError):
        return "نامشخص"

    for codes, description in WEATHER_CODE_GROUPS:
        if value in codes:
            return description
    return "نامشخص"


def fetch_weather_news():
    """Fetch RSS weather news related to Khuzestan.

    Items are kept when they mention weather terms and pass the shared
    violence filter. Network failures are logged and result in fewer items.
    """
    items = fetch_news(config.WEATHER_NEWS_FEEDS)
    weather_items = filter_weather_items(items)
    # Khuzestan-specific weather news is published before general weather news.
    weather_items.sort(key=lambda item: not matches_khuzestan(item))
    logger.info("Collected %d weather news items", len(weather_items))
    return weather_items


def _chunks(values, size):
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _request_forecast(city_batch):
    """Request one Open-Meteo payload for a batch of cities."""
    latitudes = ",".join(str(lat) for lat, _ in city_batch)
    longitudes = ",".join(str(lon) for _, lon in city_batch)

    params = {
        "latitude": latitudes,
        "longitude": longitudes,
        "current_weather": "true",
        "daily": ",".join(
            [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
                "weathercode",
            ]
        ),
        "timezone": "Asia/Tehran",
    }

    response = requests.get(
        config.OPEN_METEO_URL,
        params=params,
        timeout=config.OPEN_METEO_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _first_daily_value(daily, key):
    values = daily.get(key) or []
    return values[0] if values else None


def _parse_city_forecast(city, payload):
    daily = payload.get("daily") or {}
    temp_max = _first_daily_value(daily, "temperature_2m_max")
    temp_min = _first_daily_value(daily, "temperature_2m_min")
    precipitation = _first_daily_value(daily, "precipitation_probability_max")
    weather_code = _first_daily_value(daily, "weathercode")

    if temp_max is None or temp_min is None:
        return None

    return {
        "city": city,
        "temp_max": round(float(temp_max), 1),
        "temp_min": round(float(temp_min), 1),
        "precipitation_probability": (
            int(precipitation) if precipitation is not None else 0
        ),
        "weather_code": weather_code,
        "weather_description": weather_code_to_description(weather_code),
    }


def fetch_weather_forecast():
    """Fetch the daily forecast for every configured Khuzestan city.

    Cities are requested in batches to keep the run fast and within the
    Open-Meteo free tier. Any failure returns an empty list after logging.
    """
    cities = list(config.CITY_COORDINATES.items())
    results = []

    for batch in _chunks(cities, config.OPEN_METEO_MAX_CITIES_PER_REQUEST):
        names = [name for name, _ in batch]
        coordinates = [coords for _, coords in batch]

        try:
            payload = _request_forecast(coordinates)
        except (requests.RequestException, ValueError) as exc:
            logger.error("Open-Meteo request failed for %s: %s", names, exc)
            continue

        if isinstance(payload, dict):
            payloads = [payload]
        elif isinstance(payload, list):
            payloads = payload
        else:
            logger.error("Unexpected Open-Meteo payload for %s", names)
            continue

        if len(payloads) != len(names):
            logger.warning(
                "Open-Meteo returned %d payloads for %d cities",
                len(payloads),
                len(names),
            )

        for name, item in zip(names, payloads):
            try:
                parsed = _parse_city_forecast(name, item)
            except (AttributeError, IndexError, TypeError, ValueError, OverflowError) as exc:
                logger.warning("Could not parse forecast for %s: %s", name, exc)
                continue
            if parsed:
                results.append(parsed)
            else:
                logger.warning("Incomplete forecast data for %s", name)

    logger.info("Collected forecasts for %d cities", len(results))
    return results
