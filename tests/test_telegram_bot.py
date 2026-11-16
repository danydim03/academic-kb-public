"""
Unit tests per il componente Telegram Bot bridge (DIMEOGPT).
"""
import time
import pytest
from telegram_bot.config import BotConfig, _parse_allowed_users
from telegram_bot.middleware import RateLimiter, AuthWhitelist
from telegram_bot.formatters import format_response, split_long_message


def test_config_parse_allowed_users(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "12345, 67890, invalid, 111")
    users = _parse_allowed_users()
    assert users == [12345, 67890, 111]

    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "")
    assert _parse_allowed_users() == []


def test_rate_limiter():
    limiter = RateLimiter(max_requests=2, window_seconds=1)
    user_id = 999

    # 1a richiesta ok
    allowed, retry_after = limiter.check(user_id)
    assert allowed is True
    assert retry_after is None

    # 2a richiesta ok
    allowed, retry_after = limiter.check(user_id)
    assert allowed is True
    assert retry_after is None

    # 3a richiesta bloccata
    allowed, retry_after = limiter.check(user_id)
    assert allowed is False
    assert retry_after is not None and retry_after >= 1

    # Attendi reset finestra
    time.sleep(1.1)
    allowed, retry_after = limiter.check(user_id)
    assert allowed is True


def test_auth_whitelist():
    # Whitelist aperta
    open_wl = AuthWhitelist([])
    assert open_wl.is_allowed(123) is True
    assert open_wl.is_allowed(456) is True

    # Whitelist ristretta
    closed_wl = AuthWhitelist([123, 456])
    assert closed_wl.is_allowed(123) is True
    assert closed_wl.is_allowed(456) is True
    assert closed_wl.is_allowed(789) is False


def test_format_response_and_split():
    raw_text = "- **Tipologia**: Standard\n- Riga 1\nRiga 2 con **grassetto** e $x_1$"
    formatted = format_response(raw_text)
    assert "<b>Tipologia</b>" in formatted
    assert "<b>grassetto</b>" in formatted
    assert "<code>x_1</code>" in formatted

    # Test splitting di messaggio lungo
    long_text = "Linea di testo accademico lunga.\n" * 200
    chunks = split_long_message(long_text, max_length=500)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 500


def test_format_clean_separators():
    dirty = "Titolo\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n\n\nTesto con **parola**"
    clean = format_response(dirty)
    assert "━━━━━━━━" not in clean
    assert "\n\n\n\n" not in clean
    assert "<b>parola</b>" in clean
