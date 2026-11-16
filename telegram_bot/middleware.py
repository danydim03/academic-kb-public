"""
Middleware: rate limiting e controllo whitelist utenti.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.config import BotConfig

logger = logging.getLogger("telegram_bot.middleware")


# ==============================================================================
# Rate Limiter
# ==============================================================================

@dataclass
class _UserBucket:
    """Finestra scorrevole per il rate limiting di un singolo utente."""
    timestamps: List[float] = field(default_factory=list)


class RateLimiter:
    """Rate limiter a finestra scorrevole, per utente.

    Ogni utente può effettuare al massimo ``max_requests`` richieste
    in ``window_seconds`` secondi. Se supera il limite la richiesta viene
    rifiutata con un messaggio esplicativo.
    """

    def __init__(self, max_requests: int = 3, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: Dict[int, _UserBucket] = defaultdict(_UserBucket)

    def check(self, user_id: int) -> Tuple[bool, Optional[int]]:
        """Verifica se l'utente può effettuare una richiesta.

        Returns:
            Tupla (allowed, retry_after_seconds).
            Se allowed è True, retry_after è None.
        """
        now = time.monotonic()
        bucket = self._buckets[user_id]

        # Rimuovi timestamp scaduti
        cutoff = now - self.window_seconds
        bucket.timestamps = [t for t in bucket.timestamps if t > cutoff]

        if len(bucket.timestamps) >= self.max_requests:
            oldest = bucket.timestamps[0]
            retry_after = int(oldest + self.window_seconds - now) + 1
            return False, retry_after

        bucket.timestamps.append(now)
        return True, None


# ==============================================================================
# Auth Whitelist
# ==============================================================================

class AuthWhitelist:
    """Controlla se un utente è nella whitelist configurata.

    Se la whitelist è vuota (nessun ID configurato), tutti gli utenti sono ammessi.
    Questo facilita lo sviluppo locale.
    """

    def __init__(self, allowed_ids: List[int]) -> None:
        self._allowed: frozenset[int] = frozenset(allowed_ids)
        if self._allowed:
            logger.info("🔒 Whitelist attiva: %d utenti autorizzati", len(self._allowed))
        else:
            logger.warning("⚠️  Whitelist vuota — tutti gli utenti sono ammessi (modalità sviluppo)")

    def is_allowed(self, user_id: int) -> bool:
        """True se l'utente è autorizzato."""
        if not self._allowed:
            return True  # open mode
        return user_id in self._allowed


# ==============================================================================
# Funzioni helper per gli handler
# ==============================================================================

_rate_limiter: Optional[RateLimiter] = None
_auth_whitelist: Optional[AuthWhitelist] = None


def init_middleware(config: BotConfig) -> None:
    """Inizializza rate limiter e whitelist globali."""
    global _rate_limiter, _auth_whitelist
    _rate_limiter = RateLimiter(
        max_requests=config.rate_limit_max_requests,
        window_seconds=config.rate_limit_window_seconds,
    )
    _auth_whitelist = AuthWhitelist(config.allowed_users)


async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Verifica whitelist + rate limit. Invia un messaggio di errore e restituisce False se negato."""
    user = update.effective_user
    if user is None:
        return False

    user_id = user.id

    # 1. Whitelist
    if _auth_whitelist and not _auth_whitelist.is_allowed(user_id):
        logger.warning("🚫 Accesso negato per user %d (@%s) — non in whitelist", user_id, user.username)
        if update.effective_message:
            await update.effective_message.reply_text(
                "🚫 Non sei autorizzato ad usare questo bot.\n"
                "Contatta l'amministratore per richiedere l'accesso."
            )
        return False

    # 2. Rate limiting
    if _rate_limiter:
        allowed, retry_after = _rate_limiter.check(user_id)
        if not allowed:
            logger.info("⏳ Rate limit raggiunto per user %d — retry dopo %ds", user_id, retry_after)
            if update.effective_message:
                await update.effective_message.reply_text(
                    f"⏳ Hai raggiunto il limite di richieste.\n"
                    f"Riprova tra *{retry_after}* secondi.",
                    parse_mode="Markdown",
                )
            return False

    return True
