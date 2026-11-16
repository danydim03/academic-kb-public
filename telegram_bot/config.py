"""
Configurazione centralizzata — tutte le variabili lette da env vars.
NON inserire mai token, password o percorsi assoluti hardcoded.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional


def _env(name: str, default: Optional[str] = None, required: bool = False) -> str:
    """Legge una variabile d'ambiente. Se required=True e mancante, esce con errore."""
    value = os.environ.get(name, default)
    if required and not value:
        print(f"❌ Variabile d'ambiente obbligatoria mancante: {name}", file=sys.stderr)
        sys.exit(1)
    return value or ""


@dataclass(frozen=True)
class BotConfig:
    """Configurazione immutabile del bot Telegram."""

    # --- Telegram ---
    telegram_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN", required=True))
    allowed_users: List[int] = field(default_factory=lambda: _parse_allowed_users())

    # --- DIMEOGPT backend ---
    # Percorso relativo alla root del progetto academic-kb (usato per import diretto)
    mcp_server_module: str = field(default_factory=lambda: _env("MCP_SERVER_MODULE", "mcp_server.server"))
    # URL base dell'API FastAPI (fallback se l'import diretto fallisce)
    fastapi_base_url: str = field(default_factory=lambda: _env("FASTAPI_BASE_URL", "http://127.0.0.1:8000"))

    # --- Rate limiting ---
    rate_limit_max_requests: int = field(
        default_factory=lambda: int(_env("RATE_LIMIT_MAX_REQUESTS", "3"))
    )
    rate_limit_window_seconds: int = field(
        default_factory=lambda: int(_env("RATE_LIMIT_WINDOW_SECONDS", "60"))
    )

    # --- Risposta ---
    max_message_length: int = 4096  # limite Telegram
    typing_action: bool = True

    # --- Logging ---
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))


def _parse_allowed_users() -> List[int]:
    """Parsa la whitelist di user ID dalla env var TELEGRAM_ALLOWED_USERS.

    Se la variabile non è impostata o è vuota, restituisce una lista vuota
    che significa *tutti autorizzati* (open mode per sviluppo).
    """
    raw = os.environ.get("TELEGRAM_ALLOWED_USERS", "").strip()
    if not raw:
        return []
    ids: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


def load_config() -> BotConfig:
    """Carica la configurazione dal processo corrente (env vars devono essere già settate)."""
    return BotConfig()
