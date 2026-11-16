"""
Client per comunicare con il backend DIMEOGPT.

Strategia di fallback a doppio livello:
  1. Import diretto delle funzioni MCP (più veloce, zero overhead di rete)
  2. Chiamata HTTP all'API FastAPI su localhost (se il modulo MCP non è caricabile)
"""
from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Any, Callable, Dict, Optional

import httpx

from telegram_bot.config import BotConfig

logger = logging.getLogger("telegram_bot.client")


class SearchMode(str, Enum):
    """Modalità di ricerca supportate da DIMEOGPT."""
    STANDARD = "academic_context"
    DEEP = "deep_research"
    THESIS = "thesis_research"


class DimeogptClient:
    """Client ibrido: import diretto MCP → fallback HTTP FastAPI."""

    def __init__(self, config: BotConfig) -> None:
        self._config = config
        self._mcp_functions: Dict[str, Callable[..., str]] = {}
        self._mcp_available: bool = False
        self._http_client: Optional[httpx.AsyncClient] = None
        self._init_mcp()

    # ------------------------------------------------------------------
    # Inizializzazione MCP (import diretto)
    # ------------------------------------------------------------------
    def _init_mcp(self) -> None:
        """Tenta di importare le funzioni MCP dal modulo server.py."""
        try:
            import sys
            import os
            # Aggiungi la root del progetto academic-kb al path
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)

            from mcp_server.server import (
                academic_context,
                academic_health,
                academic_courses,
                deep_research,
                thesis_research,
            )

            self._mcp_functions = {
                "academic_context": academic_context,
                "deep_research": deep_research,
                "thesis_research": thesis_research,
                "academic_health": academic_health,
                "academic_courses": academic_courses,
            }
            self._mcp_available = True
            logger.info("✅ Import diretto MCP riuscito — backend nativo attivo")
        except Exception as exc:
            logger.warning("⚠️  Import diretto MCP fallito (%s) — userò fallback HTTP", exc)
            self._mcp_available = False

    # ------------------------------------------------------------------
    # Client HTTP (lazy init)
    # ------------------------------------------------------------------
    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=self._config.fastapi_base_url,
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._http_client

    async def close(self) -> None:
        """Chiude eventuali risorse (HTTP client)."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # ------------------------------------------------------------------
    # Ricerca principale
    # ------------------------------------------------------------------
    async def search(self, query: str, mode: SearchMode, top_k: Optional[int] = None) -> str:
        """Esegue una ricerca nel Knowledge Graph.

        Prova prima via MCP diretto, poi via HTTP FastAPI.

        Args:
            query: La domanda dell'utente.
            mode: Modalità di ricerca (STANDARD, DEEP, THESIS).
            top_k: Numero di chunk da recuperare (se None, usa il default della funzione).

        Returns:
            Stringa con la risposta formattata dal backend.

        Raises:
            RuntimeError: Se sia MCP che HTTP falliscono.
        """
        # 1) Tentativo MCP diretto
        if self._mcp_available:
            try:
                return await self._call_mcp(mode.value, query, top_k)
            except Exception as exc:
                logger.warning("MCP diretto fallito per %s: %s — provo HTTP", mode.value, exc)

        # 2) Fallback HTTP
        try:
            return await self._call_http(query, mode, top_k)
        except Exception as exc:
            raise RuntimeError(f"Impossibile contattare DIMEOGPT: {exc}") from exc

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    async def health(self) -> str:
        """Controlla lo stato del Knowledge Graph."""
        if self._mcp_available:
            try:
                return await self._call_mcp_simple("academic_health")
            except Exception as exc:
                logger.warning("MCP health fallito: %s — provo HTTP", exc)

        client = self._get_http_client()
        resp = await client.get("/api/courses")
        resp.raise_for_status()
        data = resp.json()
        total = sum(c.get("doc_count", 0) for c in data)
        courses = ", ".join(c.get("id", "?") for c in data)
        return f"✅ Academic KB raggiungibile via API\nCorsi: {courses}\nDocumenti totali: {total}"

    # ------------------------------------------------------------------
    # Internals — MCP
    # ------------------------------------------------------------------
    async def _call_mcp(self, func_name: str, query: str, top_k: Optional[int]) -> str:
        """Esegue una funzione MCP in un thread executor (sono sincrone)."""
        fn = self._mcp_functions[func_name]
        loop = asyncio.get_running_loop()

        kwargs: Dict[str, Any] = {"query": query}
        if top_k is not None:
            kwargs["top_k"] = top_k

        result = await loop.run_in_executor(None, lambda: fn(**kwargs))
        if not result or not isinstance(result, str):
            raise ValueError(f"Risposta MCP vuota o non-stringa da {func_name}")
        return result

    async def _call_mcp_simple(self, func_name: str) -> str:
        """Chiama una funzione MCP senza argomenti (es. health, courses)."""
        fn = self._mcp_functions[func_name]
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, fn)
        return result if isinstance(result, str) else str(result)

    # ------------------------------------------------------------------
    # Internals — HTTP FastAPI
    # ------------------------------------------------------------------
    async def _call_http(self, query: str, mode: SearchMode, top_k: Optional[int]) -> str:
        """Chiama l'API FastAPI /api/search come fallback.

        Note: l'API espone /api/search con GET + query param `q`.
        Per deep_research e thesis_research non c'è un endpoint dedicato nella API corrente,
        quindi usiamo /api/search con top_k appropriato come best-effort.
        """
        client = self._get_http_client()

        # Determiniamo top_k in base alla modalità
        if top_k is None:
            top_k = {
                SearchMode.STANDARD: 5,
                SearchMode.DEEP: 15,
                SearchMode.THESIS: 28,
            }.get(mode, 8)

        params = {"q": query}
        resp = await client.get("/api/search", params=params, timeout=60.0)
        resp.raise_for_status()
        data = resp.json()

        # Formattiamo i risultati grezzi in testo leggibile
        if isinstance(data, list):
            lines = [f"📚 Risultati per: *{query}*\n"]
            for i, item in enumerate(data[:top_k], 1):
                title = item.get("label", "—")
                snippet = item.get("snippet", "")
                course = item.get("course", "")
                lines.append(f"{i}. **{title}** ({course})\n   {snippet}\n")
            return "\n".join(lines)
        return str(data)
