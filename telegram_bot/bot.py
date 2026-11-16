"""
DIMEOGPT Telegram Bot — Entry point.

Configura l'Application python-telegram-bot, registra gli handler,
e avvia il polling.

Usage:
    python -m telegram_bot.bot
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

from dotenv import load_dotenv

# Carica le variabili d'ambiente da telegram_bot/.env e dal .env del progetto parent
_BOT_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_BOT_DIR)
load_dotenv(os.path.join(_PARENT_DIR, ".env"))
load_dotenv(os.path.join(_BOT_DIR, ".env"), override=True)

# Assicura che la root del progetto sia in sys.path
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from telegram_bot.config import load_config
from telegram_bot.dimeogpt_client import DimeogptClient
from telegram_bot.handlers import (
    ask_handler,
    deep_handler,
    help_handler,
    set_client,
    start_handler,
    status_handler,
    text_handler,
    thesis_handler,
)
from telegram_bot.middleware import init_middleware
from telegram_bot.utils import setup_logging


logger: logging.Logger  # inizializzato in main()


def build_application(token: str) -> Application:
    """Costruisce l'Application Telegram con tutti gli handler registrati."""
    app = Application.builder().token(token).build()

    # Comandi
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("ask", ask_handler))
    app.add_handler(CommandHandler("deep", deep_handler))
    app.add_handler(CommandHandler("thesis", thesis_handler))
    app.add_handler(CommandHandler("status", status_handler))

    # Messaggi di testo senza comando → ricerca standard
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    return app


def main() -> None:
    """Entry point principale del bot Telegram."""
    global logger

    # 1. Configurazione
    config = load_config()
    logger = setup_logging(config)

    logger.info("🚀 Avvio DIMEOGPT Telegram Bot...")
    logger.info("   Rate limit: %d req / %ds", config.rate_limit_max_requests, config.rate_limit_window_seconds)
    if config.allowed_users:
        logger.info("   Whitelist: %s", config.allowed_users)
    else:
        logger.info("   Whitelist: disabilitata (open mode)")

    # 2. Middleware
    init_middleware(config)

    # 3. Client DIMEOGPT
    client = DimeogptClient(config)
    set_client(client)

    # 4. Applicazione Telegram
    app = build_application(config.telegram_token)

    # 5. Avvio polling
    logger.info("✅ Bot pronto — in ascolto su Telegram (polling)")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message"],
    )

    logger.info("🛑 Bot arrestato.")


if __name__ == "__main__":
    main()
