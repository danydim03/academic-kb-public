"""
Utility generiche condivise tra i moduli del bot.
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

from telegram_bot.config import BotConfig


def setup_logging(config: BotConfig) -> logging.Logger:
    """Configura il logging strutturato per il bot Telegram."""
    level = getattr(logging, config.log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger("telegram_bot")
    root_logger.setLevel(level)
    # Evita handler duplicati su reload
    if not root_logger.handlers:
        root_logger.addHandler(handler)

    # Riduce la verbosità di httpx / httpcore usati da python-telegram-bot
    for noisy in ("httpx", "httpcore", "telegram.ext"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return root_logger


def truncate_message(text: str, max_length: int = 4096, suffix: str = "\n\n✂️ _...continua (risposta troncata)_") -> str:
    """Tronca un messaggio rispettando il limite di Telegram.

    Se il testo eccede ``max_length`` viene tagliato all'ultimo newline
    che precede il limite e viene aggiunto un suffisso.
    """
    if len(text) <= max_length:
        return text

    available = max_length - len(suffix)
    cut = text[:available]
    # Cerca l'ultimo newline per non tagliare a metà riga
    last_nl = cut.rfind("\n")
    if last_nl > available // 2:
        cut = cut[:last_nl]
    return cut + suffix


def escape_markdown_v2(text: str) -> str:
    """Escapes special characters for Telegram MarkdownV2.

    Usa MarkdownV2 che richiede escape di tutti i caratteri speciali tranne
    quelli che fanno parte della sintassi desiderata.
    """
    # Caratteri speciali MarkdownV2 da escapare
    special = r"_*[]()~`>#+-=|{}.!"
    escaped = []
    for ch in text:
        if ch in special:
            escaped.append(f"\\{ch}")
        else:
            escaped.append(ch)
    return "".join(escaped)


def format_user_tag(user_id: Optional[int], username: Optional[str] = None) -> str:
    """Genera una stringa leggibile per identificare un utente nei log."""
    if username:
        return f"@{username}(id={user_id})"
    return f"id={user_id}"
