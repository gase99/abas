"""Unit tests for the filtering rules and weather code descriptions."""

from src.filters import (
    filter_items,
    filter_weather_items,
    is_weather_related,
    is_violent,
    matches_iran,
    matches_khuzestan,
)
from src.poster import format_message, format_weather_message, truncate
from src.weather import weather_code_to_description


def make_item(title, summary="", link="https://example.com/news/1", source="Test"):
    return {
        "title": title,
        "summary": summary,
        "link": link,
        "source": source,
        "published": "",
    }


def test_iran_news_is_accepted():
    item = make_item("افزایش صادرات غیرنفتی ایران در ماه گذشته")
    assert matches_iran(item) is True
    accepted = filter_items([item])
    assert len(accepted) == 1
    assert accepted[0]["is_khuzestan"] is False


def test_khuzestan_news_gets_tag():
    item = make_item("افتتاح طرح آبرسانی در اهواز")
    assert matches_khuzestan(item) is True
    accepted = filter_items([item])
    assert len(accepted) == 1
    assert accepted[0]["is_khuzestan"] is True
    assert "🔶 خوزستان" in format_message(accepted[0])


def test_violent_news_is_rejected():
    item = make_item("انفجار در یک کارگاه صنعتی ایران")
    assert is_violent(item) is True
    assert filter_items([item]) == []


def test_unrelated_news_is_rejected():
    item = make_item("نتایج مسابقات فوتبال باشگاه‌های آلمان")
    assert filter_items([item]) == []


def test_weather_news_is_detected():
    item = make_item(
        "هشدار هواشناسی خوزستان درباره سامانه بارشی و رگبار",
        "بارش شدید و تندباد در اهواز و آبادان پیش‌بینی می‌شود.",
    )
    assert is_weather_related(item) is True
    assert len(filter_weather_items([item])) == 1


def test_non_weather_news_is_not_weather_related():
    item = make_item("افزایش تولید محصولات کشاورزی در ایران")
    assert is_weather_related(item) is False
    assert filter_weather_items([item]) == []


def test_weather_news_outside_khuzestan_is_rejected():
    item = make_item("هشدار هواشناسی درباره بارش در شیراز")
    assert is_weather_related(item) is True
    assert filter_weather_items([item]) == []


def test_weather_code_descriptions():
    assert weather_code_to_description(0) == "صاف"
    assert weather_code_to_description(2) == "نیمه‌ابری"
    assert weather_code_to_description(45) == "مه"
    assert weather_code_to_description(53) == "نم‌نم باران"
    assert weather_code_to_description(65) == "باران"
    assert weather_code_to_description(73) == "برف"
    assert weather_code_to_description(81) == "رگبار"
    assert weather_code_to_description(95) == "رعدوبرق"
    assert weather_code_to_description(None) == "نامشخص"


def test_weather_message_format():
    forecast = [
        {
            "city": "اهواز",
            "temp_max": 34.3,
            "temp_min": 21.3,
            "precipitation_probability": 8,
            "weather_code": 3,
            "weather_description": "نیمه‌ابری",
        }
    ]
    text = format_weather_message(forecast)
    assert "پیش‌بینی آب و هوای خوزستان" in text
    assert "📍 اهواز" in text
    assert "بیشینه 34.3°C" in text
    assert "احتمال بارش 8%" in text
    assert "🔶 خوزستان" in text


def test_truncate_keeps_short_text():
    assert truncate("کوتاه", 300) == "کوتاه"
    assert len(truncate("a" * 400, 300)) == 300
