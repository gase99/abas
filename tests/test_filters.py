"""Unit tests for the filtering rules and weather code descriptions."""

from unittest.mock import patch

from src.filters import (
    filter_items,
    filter_weather_items,
    is_weather_related,
    is_violent,
    matches_iran,
    matches_khuzestan,
)
from src.poster import (
    format_message,
    format_weather_message,
    send_to_telegram,
    truncate,
)
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
    assert weather_code_to_description(1) == "عمدتاً صاف"
    assert weather_code_to_description(2) == "نیمه‌ابری"
    assert weather_code_to_description(3) == "ابری"
    assert weather_code_to_description(45) == "مه"
    assert weather_code_to_description(48) == "مه"
    assert weather_code_to_description(51) == "نم‌ن باران"
    assert weather_code_to_description(53) == "نم‌ن باران"
    assert weather_code_to_description(55) == "نم‌ن باران"
    assert weather_code_to_description(56) == "نم‌ن باران یخ‌زده"
    assert weather_code_to_description(57) == "نم‌ن باران یخ‌زده"
    assert weather_code_to_description(61) == "باران"
    assert weather_code_to_description(63) == "باران"
    assert weather_code_to_description(65) == "باران"
    assert weather_code_to_description(66) == "باران یخ‌زده"
    assert weather_code_to_description(67) == "باران یخ‌زده"
    assert weather_code_to_description(71) == "برف"
    assert weather_code_to_description(73) == "برف"
    assert weather_code_to_description(75) == "برف"
    assert weather_code_to_description(77) == "دانه‌های برف"
    assert weather_code_to_description(80) == "رگبار باران"
    assert weather_code_to_description(81) == "رگبار باران"
    assert weather_code_to_description(82) == "رگبار باران"
    assert weather_code_to_description(85) == "رگبار برف"
    assert weather_code_to_description(86) == "رگبار برف"
    assert weather_code_to_description(95) == "رعدوبرق"
    assert weather_code_to_description(96) == "رعدوبرق همراه با تگرگ"
    assert weather_code_to_description(99) == "رعدوبرق همراه با تگرگ"
    # Gaps that were previously uncovered: 20-44, 97-98 and anything else.
    assert weather_code_to_description(20) == "نامشخص"
    assert weather_code_to_description(30) == "نامشخص"
    assert weather_code_to_description(44) == "نامشخص"
    assert weather_code_to_description(97) == "نامشخص"
    assert weather_code_to_description(98) == "نامشخص"
    assert weather_code_to_description(100) == "نامشخص"
    assert weather_code_to_description(-1) == "نامشخص"
    assert weather_code_to_description(None) == "نامشخص"
    assert weather_code_to_description("abc") == "نامشخص"



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
    messages = format_weather_message(forecast)
    assert isinstance(messages, list)
    text = messages[0]
    assert "پیش‌بینی آب و هوای خوزستان" in text
    assert "📍 اهواز" in text
    assert "بیشینه 34.3°C" in text
    assert "احتمال بارش 8%" in text
    assert "🔶 خوزستان" in text


def test_format_weather_message_splits_into_chunks():
    forecast = [
        {
            "city": f"شهر {index}",
            "temp_max": 30.0,
            "temp_min": 20.0,
            "precipitation_probability": 10,
            "weather_code": 3,
            "weather_description": "ابری",
        }
        for index in range(60)
    ]
    messages = format_weather_message(forecast)
    assert isinstance(messages, list)
    assert len(messages) >= 2
    assert all(len(message) <= 3500 for message in messages)
    assert all("پیش‌بینی آب و هوای خوزستان" in message for message in messages)


class _FakeResponse:
    def __init__(self, status_code, json_body=None, text=""):
        self.status_code = status_code
        self._json = json_body or {}
        self.text = text

    def json(self):
        return dict(self._json)


def test_send_to_telegram_retries_once_on_429():
    responses = [
        _FakeResponse(429, {"parameters": {"retry_after": 1}}),
        _FakeResponse(200, {"ok": True}),
    ]
    with patch("src.poster.requests.post", side_effect=responses), patch(
        "src.poster.time.sleep"
    ):
        assert send_to_telegram("سلام", token="1:DEMO", channel_id="-100") is True


def test_send_to_telegram_retries_on_5xx():
    responses = [
        _FakeResponse(500),
        _FakeResponse(500),
        _FakeResponse(200, {"ok": True}),
    ]
    with patch("src.poster.requests.post", side_effect=responses), patch(
        "src.poster.time.sleep"
    ):
        assert send_to_telegram("سلام", token="1:DEMO", channel_id="-100") is True


def test_send_to_telegram_no_retry_on_4xx():
    with patch("src.poster.requests.post", return_value=_FakeResponse(400)), patch(
        "src.poster.time.sleep"
    ):
        assert send_to_telegram("سلام", token="1:DEMO", channel_id="-100") is False


def test_send_to_telegram_accepts_list():
    responses = [
        _FakeResponse(200, {"ok": True}),
        _FakeResponse(200, {"ok": True}),
    ]
    with patch("src.poster.requests.post", side_effect=responses), patch(
        "src.poster.time.sleep"
    ):
        assert send_to_telegram(["یک", "دو"], token="1:DEMO", channel_id="-100") is True


def test_truncate_keeps_short_text():
    assert truncate("کوتاه", 300) == "کوتاه"
    assert len(truncate("a" * 400, 300)) == 300
