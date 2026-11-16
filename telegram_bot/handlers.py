"""
Handler dei comandi e messaggi Telegram.

Ogni handler segue lo schema:
  1. Verifica accesso (whitelist + rate limit)
  2. Estrae la query dal messaggio
  3. Invoca il client DIMEOGPT
  4. Formatta e invia la risposta
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes

from telegram_bot.dimeogpt_client import DimeogptClient, SearchMode
from telegram_bot.formatters import format_response, split_long_message
from telegram_bot.middleware import check_access
from telegram_bot.utils import format_user_tag

logger = logging.getLogger("telegram_bot.handlers")


# Il client viene iniettato da bot.py all'avvio
_client: Optional[DimeogptClient] = None


def set_client(client: DimeogptClient) -> None:
    """Inietta il client DIMEOGPT (chiamato da bot.py)."""
    global _client
    _client = client


def _get_client() -> DimeogptClient:
    """Restituisce il client o solleva errore se non inizializzato."""
    if _client is None:
        raise RuntimeError("DimeogptClient non inizializzato — chiamare set_client() prima")
    return _client


# ==============================================================================
# /start
# ==============================================================================

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Messaggio di benvenuto."""
    if not update.effective_message:
        return
    await update.effective_message.reply_text(
        "👋 *Benvenuto in DIMEOGPT Telegram!*\n\n"
        "Sono il bridge verso il Knowledge Graph accademico della Magistrale.\n\n"
        "📌 *Comandi disponibili:*\n"
        "• `/ask <domanda>` — Ricerca standard\n"
        "• `/deep <domanda>` — Ricerca approfondita\n"
        "• `/thesis <domanda>` — Ricerca tesi/macro\n"
        "• `/status` — Stato del Knowledge Graph\n"
        "• `/help` — Mostra questo messaggio\n\n"
        "💡 Puoi anche scrivere direttamente la domanda senza comando "
        "(verrà trattata come `/ask`).",
        parse_mode=ParseMode.MARKDOWN,
    )


# ==============================================================================
# /help
# ==============================================================================

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Spiega i comandi disponibili."""
    if not update.effective_message:
        return
    await update.effective_message.reply_text(
        "📖 *Guida ai comandi DIMEOGPT Telegram*\n\n"
        "🔍 *Ricerca nel Knowledge Graph:*\n"
        "• `/ask <domanda>` — Ricerca standard (`academic_context`, k=5)\n"
        "  _Es: `/ask WEP authentication`_\n\n"
        "• `/deep <domanda>` — Ricerca approfondita multi-tier (`deep_research`, k dinamico 8-20)\n"
        "  _Es: `/deep Zero Knowledge Proofs sicurezza`_\n\n"
        "• `/thesis <domanda>` — Ricerca estesa per tesi (`thesis_research`, k=28)\n"
        "  _Es: `/thesis Raft consensus protocol confronto Paxos`_\n\n"
        "📊 *Stato e info:*\n"
        "• `/status` — Stato del Knowledge Graph e statistiche\n"
        "• `/help` — Mostra questa guida\n\n"
        "💡 *Tip:* Scrivi direttamente una domanda senza comando per una ricerca standard.\n\n"
        "⚡ *Rate limit:* max 3 richieste al minuto per evitare sovraccarico.",
        parse_mode=ParseMode.MARKDOWN,
    )


# ==============================================================================
# /ask — Ricerca standard
# ==============================================================================

async def ask_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ricerca standard (academic_context, k=5)."""
    await _search_handler(update, context, SearchMode.STANDARD, "Ricerca Standard", top_k=5)


# ==============================================================================
# /deep — Ricerca approfondita
# ==============================================================================

async def deep_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ricerca approfondita (deep_research, k dinamico)."""
    await _search_handler(update, context, SearchMode.DEEP, "Ricerca Approfondita", top_k=None)


# ==============================================================================
# /thesis — Ricerca tesi
# ==============================================================================

async def thesis_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ricerca tesi/macro (thesis_research, k=28)."""
    await _search_handler(update, context, SearchMode.THESIS, "Ricerca Tesi", top_k=28)


import re

async def _safe_reply(message, text: str, parse_mode: Optional[str] = ParseMode.HTML) -> None:
    """Invia un messaggio provando con parse_mode specificato (default HTML);
    in caso di errore di parsing fa fallback inviando il testo pulito dai tag.
    """
    try:
        await message.reply_text(text, parse_mode=parse_mode)
    except Exception as exc:
        logger.warning("Invio con %s fallito (%s) — invio come testo semplice", parse_mode, exc)
        clean = re.sub(r"<[^>]+>", "", text)
        await message.reply_text(clean)


# ==============================================================================
# /status — Stato del KG
# ==============================================================================

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra lo stato del Knowledge Graph."""
    if not update.effective_message:
        return
    if not await check_access(update, context):
        return

    user = update.effective_user
    logger.info("📊 /status da %s", format_user_tag(user.id if user else 0, user.username if user else None))

    await update.effective_message.chat.send_action(ChatAction.TYPING)

    try:
        client = _get_client()
        result = await client.health()
        await _safe_reply(
            update.effective_message,
            f"<b>📊 Stato DIMEOGPT</b>\n\n{result}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        logger.error("Errore /status: %s", exc)
        await _safe_reply(
            update.effective_message,
            f"❌ Errore nel controllo dello stato:\n{exc}",
            parse_mode=None,
        )


# ==============================================================================
# Messaggi senza comando → ricerca standard
# ==============================================================================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce messaggi di testo senza comando → ricerca standard."""
    await _search_handler(update, context, SearchMode.STANDARD, "Ricerca Standard", top_k=5)


# ==============================================================================
# Handler generico di ricerca (DRY)
# ==============================================================================

async def _search_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    mode: SearchMode,
    mode_label: str,
    top_k: Optional[int],
) -> None:
    """Handler generico che gestisce tutte le modalità di ricerca."""
    if not update.effective_message:
        return
    if not await check_access(update, context):
        return

    user = update.effective_user
    message = update.effective_message

    # Estrai la query: se è un comando, prendi il testo dopo il comando
    text = message.text or ""
    if text.startswith("/"):
        parts = text.split(maxsplit=1)
        query = parts[1].strip() if len(parts) > 1 else ""
    else:
        query = text.strip()

    if not query:
        await message.reply_text(
            f"⚠️ Specifica una domanda dopo il comando.\n"
            f"_Es:_ `/{mode.value.replace('academic_', '').replace('_research', '')} Come funziona WEP?`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    user_tag = format_user_tag(user.id if user else 0, user.username if user else None)
    logger.info("🔎 [%s] %s — query: %s", mode_label, user_tag, query[:100])

    # Invia azione "typing..."
    await message.chat.send_action(ChatAction.TYPING)

    t0 = time.monotonic()
    try:
        client = _get_client()
        raw_result = await client.search(query, mode=mode, top_k=top_k)
        elapsed = time.monotonic() - t0
        logger.info("✅ Risposta %s in %.1fs (%d chars)", mode_label, elapsed, len(raw_result))

        # Formatta esclusivamente la risposta finale in HTML
        formatted = format_response(raw_result)
        chunks = split_long_message(formatted)

        for chunk in chunks:
            await _safe_reply(message, chunk, parse_mode=ParseMode.HTML)

    except Exception as exc:
        elapsed = time.monotonic() - t0
        logger.error("❌ Errore %s dopo %.1fs: %s", mode_label, elapsed, exc)
        await _safe_reply(
            message,
            f"❌ Errore durante la ricerca:\n{exc}\n\n"
            "Verifica che il Knowledge Graph sia attivo con `/status`.",
            parse_mode=None,
        )
