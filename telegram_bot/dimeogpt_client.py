"""
Client per comunicare con il backend DIMEOGPT e il motore di sintesi LLM.

Pipeline a 2 fasi:
  1. Retrieval dal Knowledge Graph:
     - Import diretto delle funzioni MCP (zero latency)
     - Fallback HTTP verso FastAPI (se il modulo non è importabile)
  2. Sintesi Accademica LLM:
     - DIMEOGPT sintetizza una risposta autorevole, rigorosa e strutturata
     - Header obbligatorio con tipologia e fonti interrogate (k)
     - Citazioni puntuali inline [NomeDocumento.pdf, p. X]
     - Nessun dump grezzo di chunk
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
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
    """Client integrato: Retrieval (MCP/API) + Sintesi Accademica (LLM)."""

    def __init__(self, config: BotConfig) -> None:
        self._config = config
        self._mcp_functions: Dict[str, Callable[..., str]] = {}
        self._mcp_available: bool = False
        self._llm_client: Any = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._init_backend()

    # ------------------------------------------------------------------
    # Inizializzazione MCP e LLM
    # ------------------------------------------------------------------
    def _init_backend(self) -> None:
        """Inizializza le funzioni MCP native e il client LLM di studio."""
        # 1. MCP Functions
        try:
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
            logger.warning("⚠️ Import diretto MCP fallito (%s) — userò fallback HTTP", exc)
            self._mcp_available = False

        # 2. LLM Client per la sintesi
        try:
            from config.settings import get_settings
            from engine.study.llm_client import get_llm_client

            settings = get_settings()
            self._llm_client = get_llm_client(settings)
            logger.info(
                "✅ LLM Client inizializzato per sintesi DIMEOGPT (provider: %s, model: %s)",
                getattr(settings, "llm_provider", "default"),
                getattr(settings, "llm_model", "default"),
            )
        except Exception as exc:
            logger.warning("⚠️ Inizializzazione LLM fallita (%s) — fallback a testo grezzo", exc)
            self._llm_client = None

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
    # Ricerca e Sintesi Principale
    # ------------------------------------------------------------------
    async def search(self, query: str, mode: SearchMode, top_k: Optional[int] = None) -> str:
        """Esegue retrieval dal Knowledge Graph e sintetizza la risposta finale con l'LLM.

        Args:
            query: La domanda dell'utente.
            mode: Modalità di ricerca (STANDARD, DEEP, THESIS).
            top_k: Numero di chunk (se None, usa i default adattivi della modalità).

        Returns:
            La risposta accademica finale, formattata e citata puntualmente.
        """
        # Fase 1: Retrieval del contesto dal Knowledge Graph
        context_str = await self._retrieve_context(query, mode, top_k)

        # Fase 2: Sintesi LLM
        if self._llm_client:
            try:
                synthesized = await self._synthesize(query, context_str, mode)
                return synthesized
            except Exception as exc:
                logger.error("Sintesi LLM fallita: %s — fallback a contesto pulito", exc)

        # Fallback pulito se l'LLM non è disponibile (senza dump grezzo)
        return self._clean_context_fallback(context_str, query, mode)

    async def _retrieve_context(self, query: str, mode: SearchMode, top_k: Optional[int]) -> str:
        """Esegue il retrieval via MCP nativo o via HTTP FastAPI."""
        if self._mcp_available:
            try:
                return await self._call_mcp(mode.value, query, top_k)
            except Exception as exc:
                logger.warning("MCP diretto fallito per %s: %s — provo HTTP", mode.value, exc)

        try:
            return await self._call_http(query, mode, top_k)
        except Exception as exc:
            raise RuntimeError(f"Impossibile interrogare il Knowledge Graph: {exc}") from exc

    # ------------------------------------------------------------------
    # Sintesi LLM
    # ------------------------------------------------------------------
    async def _synthesize(self, query: str, context_str: str, mode: SearchMode) -> str:
        """Invia il contesto recuperato all'LLM e produce la risposta finale magistrale."""
        mode_labels = {
            SearchMode.STANDARD: "Standard (academic_context)",
            SearchMode.DEEP: "Approfondita (deep_research)",
            SearchMode.THESIS: "Tesi / Macro Ricerca (thesis_research)",
        }
        mode_label = mode_labels.get(mode, "Standard (academic_context)")

        # Estrai la ripartizione k esatta dal contesto
        k_match = re.search(r"• Ripartizione k utilizzata:\s*(.*)", context_str)
        if k_match:
            k_breakdown = k_match.group(1).strip()
        else:
            default_k = 28 if mode == SearchMode.THESIS else (12 if mode == SearchMode.DEEP else 5)
            k_breakdown = f"🎓 Slide + Notion: {default_k} | 📖 Libri: 0 | 📄 Articoli: 0 (Totale k={default_k})"

        system_prompt = f"""Sei DIMEOGPT, l'autorevole assistente accademico per gli studenti magistrali dell'Università di Roma Tor Vergata (Cyber Security, Sistemi Distribuiti, Machine Learning, Geometria).
Il tuo compito è rispondere alla domanda dello studente basandoti ESCLUSIVAMENTE sui contenuti del Knowledge Graph universitario forniti nel contesto.

REGOLE TASSATIVE DI FORMATTAZIONE E STILE:
1. PREAMBOLO METADATI (Le prime due righe esatte della risposta, senza alcun testo precedente):
- **Tipologia di Ricerca**: {mode_label}
- **Fonti Interrogate (k)**: {k_breakdown}

2. CORPO DELLA RISPOSTA (Solo risposta finale elaborata):
- Rispondi in italiano con tono accademico autorevole, chiaro, rigoroso e magistrale.
- Organizza la spiegazione con sezioni chiare ed esplicative (**Titolo Sezione** o ### Titolo), punti elenco (•) ed esempi concreti.
- Se sono presenti definizioni matematiche, formule, algoritmi o passaggi formali, esponili con la massima chiarezza e precisione.
- Per OGNI concetto, definizione, teorema o formula, DEVI obbligatoriamente inserire la citazione puntuale inline: [NomeDocumento.pdf, p. X] (o [NomeDocumento.pdf]).
- Se i documenti forniti non contengono informazioni pertinenti per rispondere alla domanda, dichiaralo esplicitamente con precisione e trasparenza metodologica.
- DIVIETO ASSOLUTO: NON riportare MAI scarti di testo grezzo, log interni, 'Source 1:', 'Content:', separatori '━━━━━━━━' o chunk spezzati. Restituisci SOLO ed esclusivamente la risposta finale pronta e ben formattata."""

        user_prompt = f"""CONTESTO ACCADEMICO ESTRATTO DAL KNOWLEDGE GRAPH:
{context_str}

DOMANDA DELLO STUDENTE:
{query}"""

        loop = asyncio.get_running_loop()
        answer = await loop.run_in_executor(
            None,
            lambda: self._llm_client.generate(user_prompt, system_prompt=system_prompt),
        )

        return answer.strip()

    def _clean_context_fallback(self, context_str: str, query: str, mode: SearchMode) -> str:
        """Fallback pulito se l'LLM non risponde: estrae le fonti e un sommario pulito."""
        mode_labels = {
            SearchMode.STANDARD: "Standard (academic_context)",
            SearchMode.DEEP: "Approfondita (deep_research)",
            SearchMode.THESIS: "Tesi / Macro Ricerca (thesis_research)",
        }
        mode_label = mode_labels.get(mode, "Standard")

        k_match = re.search(r"• Ripartizione k utilizzata:\s*(.*)", context_str)
        k_str = k_match.group(1).strip() if k_match else "k=5"

        lines = [
            f"- **Tipologia di Ricerca**: {mode_label}",
            f"- **Fonti Interrogate (k)**: {k_str}\n",
            f"<b>Risultati recuperati dal Knowledge Graph per:</b> <i>{query}</i>\n",
        ]

        # Estrai solo i titoli dei documenti trovati
        doc_matches = re.findall(r"Source\s+\d+:\s*(.+?)(?:\s*\(Page\s*(\d+)\))?\s*\|\s*Course:\s*([^\n]+)", context_str)
        if doc_matches:
            for doc, page, course in doc_matches[:6]:
                p_str = f", p. {page}" if page else ""
                lines.append(f"• <b>{doc.strip()}</b> ({course.strip()}{p_str})")
        else:
            lines.append("Consultazione diretta dei documenti del Knowledge Graph completata.")

        return "\n".join(lines)

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
        """Esegue una funzione MCP in un thread executor."""
        fn = self._mcp_functions[func_name]
        loop = asyncio.get_running_loop()

        kwargs: Dict[str, Any] = {"query": query}
        if top_k is not None:
            kwargs["top_k"] = top_k

        result = await loop.run_in_executor(None, lambda: fn(**kwargs))
        if not result or not isinstance(result, str):
            raise ValueError(f"Risposta MCP vuota da {func_name}")
        return result

    async def _call_mcp_simple(self, func_name: str) -> str:
        fn = self._mcp_functions[func_name]
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, fn)
        return result if isinstance(result, str) else str(result)

    # ------------------------------------------------------------------
    # Internals — HTTP FastAPI
    # ------------------------------------------------------------------
    async def _call_http(self, query: str, mode: SearchMode, top_k: Optional[int]) -> str:
        client = self._get_http_client()
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

        if isinstance(data, list):
            lines = [f"Query: {query}\n\n• Ripartizione k utilizzata: 🎓 Slide + Notion: {min(len(data), top_k)} | 📖 Libri: 0 | 📄 Articoli: 0\n\n--- ACADEMIC CONTEXT ---"]
            for i, item in enumerate(data[:top_k], 1):
                title = item.get("label", "Doc")
                snippet = item.get("snippet", "")
                course = item.get("course", "MAGISTRALE")
                lines.append(f"Source {i}: [PDF] {title} | Course: {course}\nContent:\n{snippet}\n")
            return "\n".join(lines)
        return str(data)
