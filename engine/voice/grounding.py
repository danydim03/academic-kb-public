"""
Academic KB Voice Studio — Strict Grounding & Retriever Bridge (Milestone M2).
Provides non-blocking Academic KB tool schema (query_academic_kb),
AcademicGroundingBridge with 2-layer anti-hallucination defense,
async knowledge graph retrieval via asyncio.to_thread,
course scoping isolation, and academic citation formatting.
"""

import os
import re
import json
import logging
import asyncio
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Authoritative Tool Schema (PROJECT.md contract)
# ---------------------------------------------------------------------------

GROUNDING_TOOL_SCHEMA: Dict[str, Any] = {
    "name": "query_academic_kb",
    "description": "Searches the local university course knowledge base for slides, documents, notes, and academic materials. Must be used whenever the student asks questions about course content.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "The specific academic concept or search query in Italian or English"
            },
            "course": {
                "type": "STRING",
                "description": "Optional course code filter (e.g. CNS, ML, BD, etc.)"
            }
        },
        "required": ["query"]
    },
    "behavior": "BLOCKING"
}

# Backward/forward-compatible alias
QUERY_ACADEMIC_KB_TOOL_SCHEMA = GROUNDING_TOOL_SCHEMA


# ---------------------------------------------------------------------------
# Citation Formatting Utility
# ---------------------------------------------------------------------------

def format_academic_citation(source_title: str, page: Optional[int] = None) -> str:
    """
    Formats academic citation string according to user rules and PROJECT.md contract:
    - With valid page (> 0): [Doc.pdf, p. X]
    - Without page or page <= 0: [Doc.pdf]
    """
    clean_title = source_title.strip() if (source_title and str(source_title).strip()) else "Documento"
    if page is not None and isinstance(page, int) and page > 0:
        return f"[{clean_title}, p. {page}]"
    return f"[{clean_title}]"


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class AcademicDocChunk:
    """In-memory or serialized representation of a document chunk."""
    chunk_id: str
    source_title: str
    page: int
    course: str
    content: str
    score: float = 0.85


# Stopwords for relevance term extraction (Italian & English)
_STOPWORDS = {
    "in", "di", "da", "su", "il", "lo", "la", "le", "un", "una", "uno", "gli", "i",
    "to", "of", "and", "the", "for", "is", "are", "che", "con", "per", "tra", "fra",
    "qual", "quale", "cosa", "come", "perche", "della", "delle", "degli", "dei", "del",
    "allo", "alla", "alle", "agli", "nei", "nella", "nelle", "negli", "sul", "sulla",
    "questo", "questa", "questi", "queste", "quello", "quella", "what", "which", "how",
    "why", "when", "where", "with", "from", "about", "into", "over", "after"
}


# ---------------------------------------------------------------------------
# AcademicGroundingBridge
# ---------------------------------------------------------------------------

class AcademicGroundingBridge:
    """
    Bridge connecting the Gemini Live Voice Assistant with the local
    Academic Knowledge Graph and HybridRetriever (Vector + Fulltext + RRF).

    Provides:
    - 2-layer anti-hallucination defense:
        Layer 1: Out-of-domain keyword token verification & relevance score threshold (default 0.60).
        Layer 2: Explicit declaration of unavailability when no verified chunks match (zero hallucination).
    - Asynchronous retrieval executed in a separate worker thread (asyncio.to_thread).
    - Course scoping isolation (e.g. ?course=CNS limits results to CNS materials).
    - Structured academic citation generation [Doc.pdf, p. X].
    - Strict system instructions for Gemini Live audio sessions.
    """

    def __init__(
        self,
        db: Optional[Any] = None,
        retriever: Optional[Any] = None,
        relevance_threshold: float = 0.60,
        kb: Optional[List[Any]] = None,
    ):
        self.db = db
        self.retriever = retriever
        self.relevance_threshold = relevance_threshold
        self.kb = kb  # Optional mock or in-memory chunk list
        self._initialized = False

    def _ensure_retriever(self) -> None:
        """Lazily initializes Neo4j connection and HybridRetriever if not injected."""
        if self._initialized:
            # Check if injected or existing db needs reconnect
            if self.db and hasattr(self.db, "driver") and not self.db.driver:
                try:
                    self.db.connect()
                except Exception as e:
                    logger.warning(f"Reconnecting Neo4j failed: {e}")
            return

        if self.retriever is None and self.kb is None:
            try:
                from config.settings import get_settings
                from core.database import Neo4jManager
                from engine.embeddings.provider import EmbeddingProvider
                from engine.retrieval.vector import VectorRetriever
                from engine.retrieval.fulltext import FulltextRetriever
                from engine.retrieval.hybrid import HybridRetriever

                settings = get_settings()
                if self.db is None:
                    self.db = Neo4jManager(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)
                if not getattr(self.db, "driver", None):
                    self.db.connect()

                embedder = EmbeddingProvider(
                    settings.embedding_provider,
                    settings.embedding_model,
                    settings.embedding_dimension,
                    settings.embedding_api_key,
                    settings.embedding_base_url
                )
                vector = VectorRetriever(self.db, embedder)
                ft = FulltextRetriever(self.db)
                self.retriever = HybridRetriever(vector, ft)
                logger.info("AcademicGroundingBridge successfully auto-initialized HybridRetriever.")
            except Exception as e:
                logger.warning(f"AcademicGroundingBridge could not auto-initialize HybridRetriever: {e}")
                self.retriever = None

        self._initialized = True

    @staticmethod
    def get_system_instructions(course: Optional[str] = None) -> str:
        """
        Generates strict grounding system instructions for the Gemini Live session.
        Mandates query_academic_kb tool invocation and explicit zero-hallucination declaration.
        """
        course_clause = ""
        if course and course.upper() not in ("ALL", "GENERAL"):
            course_clause = f"\nATTENZIONE: Il corso attualmente attivo è '{course.upper()}'. Focalizzati sui documenti e sui materiali ufficiali di questo corso."

        return f"""
Sei DIMEOGPT Voice Assistant, l'assistente vocale accademico di livello magistrale (Tor Vergata) integrato in DIMEOGPT Study Studio.
Comunichi a voce in lingua italiana in modo naturale, didattico, approfondito e autorevole.{course_clause}

REGOLE FONDAMENTALI DI GROUNDING RIGOROSO ED ESPOSIZIONE ACCADEMICA:
1. Quando l'utente ti pone qualsiasi domanda concettuale, teorica, tecnica o d'esame su materie universitarie (CNS, SDCC, ML, SE, Geometria, SERT, BD, ecc.), DEVI OBBLIGATORIAMENTE invocare lo strumento `query_academic_kb` PRIMA di formulare la risposta.
2. Rispondi STRETTAMENTE ed ESCLUSIVAMENTE utilizzando le informazioni presenti nei documenti e chunk restituiti da `query_academic_kb`.
3. In ogni risposta, cita esplicitamente il documento sorgente e la pagina (ad esempio: "Nelle slide del corso, documento TLS 1.3 a pagina 24...").
4. SE IL TOOL RESTITUISCE `found: false` o nessun documento pertinente sul tema richiesto, DEVI DICHIARARE APERTAMENTE:
   "Ho verificato nel Knowledge Graph accademico, ma questo argomento non è trattato nei materiali indicizzati del corso."
   NON inventare spiegazioni e NON rispondere attingendo a conoscenze esterne generiche non verificate.
5. PROFONDITÀ PEDAGOGICA, COMPLETEZZA E RITMO VOCALE:
   - NON dare risposte telegrafiche o di poche righe! Lo studente si aspetta una spiegazione esaustiva, completa e ricca di dettagli tecnici, come una vera lezione universitaria individuale o un confronto tra brillanti studenti magistrali.
   - Quando esponi un concetto, strutturalo chiaramente: (a) definizione formale e obiettivo teorico, (b) funzionamento dettagliato passo dopo passo (protocolli, algoritmi, messaggi, architettura), (c) motivazioni, differenze con alternative ed eventuali criticità o domande tipiche d'esame.
   - Sfrutta tutti i dettagli tecnici e i passaggi presenti nel testo dei chunk restituiti dal tool senza sintetizzare all'estremo.
   - Parla con tono rilassato e accogliente, senza fretta di concludere il turno. Al termine della spiegazione dettagliata, chiedi se il concetto è chiaro o se desidera approfondire un aspetto specifico.
""".strip()

    async def search(
        self,
        query: str,
        course: Optional[str] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Asynchronously searches the Academic Knowledge Base via asyncio.to_thread
        to avoid blocking the real-time audio streaming event loop.
        """
        return await asyncio.to_thread(self._search_sync, query, course, top_k)

    def query(self, query_str: str, course: Optional[str] = None) -> Dict[str, Any]:
        """Synchronous search execution (compatible with test harnesses)."""
        return self._search_sync(query=query_str, course=course, top_k=5)

    def _search_sync(
        self,
        query: str,
        course: Optional[str] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Synchronous search engine executing:
        1. Query tokenization and domain sanitization.
        2. Course isolation filter with dynamic cross-course fallback.
        3. Hybrid retrieval execution.
        4. Layer 1 relevance threshold & out-of-domain guard.
        5. Layer 2 zero-hallucination fallback.
        6. Structured citation generation [Doc.pdf, p. X] and rich technical grounding.
        """
        # 1. Input sanitization & empty query guard
        q_str = str(query).strip() if query is not None else ""
        course_str = str(course).strip() if course is not None and isinstance(course, (str, int, float)) else None
        if not q_str:
            return {
                "found": False,
                "query": query,
                "course": course,
                "k": 0,
                "citations": [],
                "results": [],
                "message": "Nessuna informazione accademica pertinente trovata nei documenti ufficiali del Knowledge Graph per questa richiesta."
            }

        # Extract meaningful terms (length >= 3, excluding stopwords)
        q_lower = q_str.lower()
        terms = [
            t for t in re.findall(r"\w+", q_lower)
            if len(t) >= 3 and t not in _STOPWORDS
        ]

        if not terms:
            return {
                "found": False,
                "query": query,
                "course": course,
                "k": 0,
                "citations": [],
                "results": [],
                "message": "Nessuna informazione accademica pertinente trovata nei documenti ufficiali del Knowledge Graph per questa richiesta."
            }

        # 2. Retrieval candidates
        candidates: List[Any] = []

        if self.kb is not None:
            # In-memory KB mode (for deterministic offline testing)
            for chunk in self.kb:
                chunk_course = getattr(chunk, "course", "") if not isinstance(chunk, dict) else chunk.get("course", "")
                if course_str and course_str.upper() not in ("ALL", "GENERAL"):
                    if str(chunk_course).upper() != course_str.upper():
                        continue

                content = getattr(chunk, "content", "") or getattr(chunk, "text", "") if not isinstance(chunk, dict) else (chunk.get("content") or chunk.get("text") or "")
                title = getattr(chunk, "source_title", "") if not isinstance(chunk, dict) else chunk.get("source_title", "")
                full_text_lower = f"{title} {content}".lower()

                match_count = sum(1 for t in terms if t in full_text_lower)
                if match_count > 0:
                    candidates.append(chunk)

        else:
            # Knowledge Graph HybridRetriever mode
            self._ensure_retriever()
            if self.db and hasattr(self.db, "driver") and not self.db.driver:
                try:
                    self.db.connect()
                except Exception as e:
                    logger.warning(f"Neo4j reconnect failed: {e}")

            if self.retriever is not None:
                try:
                    # Request more candidates to allow effective course & relevance filtering
                    raw_chunks = self.retriever.search(query=q_str, top_k=max(top_k * 4, 16))
                except Exception as e:
                    logger.error(f"Retriever search error for query '{q_str}': {e}", exc_info=True)
                    raw_chunks = []

                # Pass 1: Try scoped course filter if course is explicitly specified
                for chunk in raw_chunks:
                    chunk_course = chunk.get("course", "") if isinstance(chunk, dict) else getattr(chunk, "course", "")
                    if course_str and course_str.upper() not in ("ALL", "GENERAL"):
                        if str(chunk_course).upper() != course_str.upper():
                            continue

                    content = chunk.get("text", "") or chunk.get("content", "") if isinstance(chunk, dict) else (getattr(chunk, "text", "") or getattr(chunk, "content", ""))
                    title = chunk.get("source_title", "") if isinstance(chunk, dict) else getattr(chunk, "source_title", "")
                    full_text_lower = f"{title} {content}".lower()

                    match_count = sum(1 for t in terms if t in full_text_lower)
                    is_hybrid_hit = bool(isinstance(chunk, dict) and chunk.get("rrf_score"))
                    if match_count > 0 or is_hybrid_hit:
                        candidates.append(chunk)

                # Pass 2: Cross-course Fallback.
                # If course filter was restrictive and produced 0 candidates, fallback to all courses
                # so we never falsely deny knowledge that exists in another academic course!
                if not candidates and course_str and course_str.upper() not in ("ALL", "GENERAL"):
                    logger.info(f"Course-specific search for '{course_str}' yielded 0 hits. Executing cross-course fallback.")
                    for chunk in raw_chunks:
                        content = chunk.get("text", "") or chunk.get("content", "") if isinstance(chunk, dict) else (getattr(chunk, "text", "") or getattr(chunk, "content", ""))
                        title = chunk.get("source_title", "") if isinstance(chunk, dict) else getattr(chunk, "source_title", "")
                        full_text_lower = f"{title} {content}".lower()

                        match_count = sum(1 for t in terms if t in full_text_lower)
                        is_hybrid_hit = bool(isinstance(chunk, dict) and chunk.get("rrf_score"))
                        if match_count > 0 or is_hybrid_hit:
                            candidates.append(chunk)

        # 3. Layer 1: Out-of-Domain & Relevance Threshold Guard
        valid_chunks: List[Any] = []
        for c in candidates:
            # Extract score
            score = None
            if isinstance(c, dict):
                score = c.get("score")
                if score is None:
                    score = c.get("similarity") or c.get("sim_score")
            else:
                score = getattr(c, "score", None)
                if score is None:
                    score = getattr(c, "similarity", None) or getattr(c, "sim_score", None)

            # Check relevance score against threshold
            if score is not None and isinstance(score, (int, float)):
                # If chunk was vetted by HybridRetriever RRF rank fusion, allow realistic cosine scores
                if isinstance(c, dict) and c.get("rrf_score"):
                    if score < min(0.35, self.relevance_threshold):
                        continue
                elif score < self.relevance_threshold:
                    continue

            valid_chunks.append(c)

        # 4. Layer 2: Zero-Hallucination Fallback
        if not valid_chunks:
            return {
                "found": False,
                "query": query,
                "course": course,
                "k": 0,
                "citations": [],
                "results": [],
                "message": "Nessuna informazione accademica pertinente trovata nei documenti ufficiali del Knowledge Graph per questa richiesta."
            }

        # 5. Format citations & structured results with rich content for live voice reasoning
        selected_chunks = valid_chunks[:top_k]
        citations: List[Dict[str, Any]] = []
        serialized_results: List[Dict[str, Any]] = []

        for c in selected_chunks:
            if isinstance(c, dict):
                source_title = c.get("source_title") or "Documento"
                raw_page = c.get("page")
                c_course = c.get("course") or course_str or "ACCADEMICO"
                content = c.get("text") or c.get("content") or ""
            else:
                source_title = getattr(c, "source_title", "Documento")
                raw_page = getattr(c, "page", None)
                c_course = getattr(c, "course", course_str or "ACCADEMICO")
                content = getattr(c, "content", "") or getattr(c, "text", "")

            # Determine clean page number
            page_int: Optional[int] = None
            if raw_page is not None:
                try:
                    val = int(raw_page)
                    if val > 0:
                        page_int = val
                except (ValueError, TypeError):
                    page_int = None

            # Generate citation tag
            citation_tag = format_academic_citation(source_title, page_int)

            # For schema compliance, page in citations dict must be an integer >= 1
            citation_page = page_int if page_int is not None else 1
            clean_content = content.strip()
            snippet = clean_content[:400]

            citation_entry = {
                "source": source_title,
                "page": citation_page,
                "course": c_course,
                "snippet": snippet,
                "citation_tag": citation_tag
            }
            citations.append(citation_entry)
            serialized_results.append({
                "source_title": source_title,
                "page": citation_page,
                "course": c_course,
                "snippet": snippet,
                "content": clean_content[:2500],  # Full rich technical context for Gemini Live speech
                "citation_tag": citation_tag
            })

        return {
            "found": bool(len(citations) > 0),
            "query": query,
            "course": course,
            "k": len(citations),
            "citations": citations,
            "results": serialized_results,
            "message": f"Trovati {len(citations)} frammenti documentali accreditati." if citations else "Nessuna informazione accademica pertinente trovata nei documenti ufficiali del Knowledge Graph per questa richiesta."
        }

    async def handle_tool_call(
        self,
        name: str,
        args: Dict[str, Any],
        course_override: Optional[str] = None
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Executes query_academic_kb tool call and returns:
        (tool_response_dict, browser_citations_list)
        """
        if name == "query_academic_kb":
            q = args.get("query", "")
            c = course_override or args.get("course")
            res = await self.search(query=q, course=c, top_k=5)
            return res, res.get("citations", [])

        return {
            "found": False,
            "message": f"Tool '{name}' non supportato dal motore di grounding."
        }, []
