"""
Academic Knowledge Base — MCP Server
Espone il Knowledge Graph accademico via protocollo MCP (stdio).
Compatibile con Claude Desktop, Cursor, Pi, e qualsiasi agent MCP-compatibile.
"""
import sys
import os
import json
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.mcpserver import MCPServer

from config.settings import get_settings
from core.database import Neo4jManager
from engine.embeddings.provider import EmbeddingProvider
from engine.retrieval.vector import VectorRetriever
from engine.retrieval.fulltext import FulltextRetriever
from engine.retrieval.hybrid import HybridRetriever
from engine.context.builder import ContextBuilder

# Study Engine modules
from engine.study.llm_client import get_llm_client
from engine.study.question_generator import QuestionGenerator
from engine.study.flashcard_engine import FlashcardEngine
from engine.study.gap_detector import GapDetector
from engine.study.exam_linker import ExamLinker
from engine.study.learning_path import LearningPathEngine
from engine.study.thesis_assistant import ThesisAssistant

# Initialize server
mcp = MCPServer(
    "academic-kb",
    version="1.0.0",
    instructions=(
        "Academic Knowledge Base per la Magistrale di Tor Vergata. "
        "Contiene PDF delle lezioni, libri e appunti Notion per i corsi: SDCC, CNS, ML, SE. "
        "REQUISITO FONDAMENTALE DI STILE E CITAZIONE: "
        "Per OGNI risposta estratta dal Knowledge Graph, l'assistente DEVE inserire all'inizio "
        "della risposta il blocco di metadati con la tipologia di ricerca (Standard o Approfondita) "
        "e il conteggio esatto dei k utilizzati suddivisi tra Slide + Notion, Libri e Articoli. "
        "Inoltre, DEVE obbligatoriamente indicare inline il documento preciso "
        "e la pagina da cui proviene l'informazione (es. '[NomeDocumento.pdf, p. 12]'). "
        "Non devono mai essere fornite affermazioni o spiegazioni senza la relativa citazione documentale."
    )
)

# Global instances
settings = get_settings()
db = Neo4jManager(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)
embedder = EmbeddingProvider(
    settings.embedding_provider, settings.embedding_model,
    settings.embedding_dimension, settings.embedding_api_key,
    settings.embedding_base_url
)
vector_retriever = VectorRetriever(db, embedder)
fulltext_retriever = FulltextRetriever(db)
hybrid_retriever = HybridRetriever(vector_retriever, fulltext_retriever)
context_builder = ContextBuilder()

# Study engine instances with dependency injection
llm_client = get_llm_client(settings)
question_gen = QuestionGenerator(llm_client=llm_client, retriever=hybrid_retriever)
flashcard_eng = FlashcardEngine(db=db, llm_client=llm_client)
gap_detector = GapDetector(db=db)
exam_linker = ExamLinker(db=db, retriever=hybrid_retriever, llm_client=llm_client)
learning_path_eng = LearningPathEngine(db=db, llm_client=llm_client)
thesis_asst = ThesisAssistant(retriever=hybrid_retriever, llm_client=llm_client)


# ==============================================================================
# Existing Core MCP Tools
# ==============================================================================

@mcp.tool()
def academic_context(query: str, top_k: int = 5) -> str:
    """
    Cerca nel Knowledge Graph accademico usando Hybrid Search (vettoriale + full-text).
    Restituisce i chunk più rilevanti dai PDF e dagli appunti Notion della Magistrale.

    Gerarchia a 3 livelli:
      ⭐⭐⭐ Slides e appunti Notion (fonti primarie, sempre cercate per prime)
      ⭐⭐  Libri di testo da resources/ (fallback se le primarie non bastano)
      ⭐    Articoli scientifici / paper (ultimo fallback, solo se insufficienti)

    Args:
        query: La domanda o l'argomento da cercare (es. 'WEP authentication vulnerabilities')
        top_k: Numero di risultati da restituire (default: 5)
    """
    db.connect()
    try:
        results = hybrid_retriever.search(query, top_k=top_k)
        return context_builder.format_mcp_response(query, results, search_type="standard")
    finally:
        db.close()


@mcp.tool()
def deep_research(query: str, top_k: Optional[int] = None) -> str:
    """
    Ricerca Approfondita Multi-Tier con k Dinamico e Quote Adattive.

    Determina automaticamente sia il numero totale di chunk necessari (k dinamico tra 8 e 20)
    in base alla complessità e all'ampiezza della query, sia la ripartizione interna tra:
      - 📖 Libri di testo (maggior peso su teorie, formule, dimostrazioni e formalismi)
      - 📄 Paper/Articoli (maggior peso su attacchi, vulnerabilità, protocolli originali, benchmark)
      - 🎓 Slide/Appunti (maggior peso su domande d'esame, sintesi del docente, concetti chiave)

    Rialloca dinamicamente le quote se un corso non possiede un determinato tier (es. corsi senza libri).

    Args:
        query: L'argomento su cui fare ricerca approfondita
        top_k: (Opzionale) Forza un numero specifico di risultati (range consentito: 5-24).
               Se omesso o None, il valore k e le quote per tier vengono calcolati in modo completamente dinamico.
    """
    db.connect()
    try:
        results = hybrid_retriever.deep_research(query, top_k=top_k)
        body = context_builder.format_mcp_response(query, results, search_type="deep_research")
        return (
            "🔬 DEEP RESEARCH MODE — Dynamic Scope & Multi-Tier Allocation\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            + body
        )
    finally:
        db.close()


@mcp.tool()
def thesis_research(query: str, top_k: Optional[int] = 28) -> str:
    """
    Ricerca Estesa ad Alto Volume per Tesi, Rassegne Bibliografiche e Macro-Sintesi (25-30 chunk).

    Campiona in modo stratificato ad ampio raggio su Libri di testo accademici, Paper scientifici
    e Slide dei corsi, restituendo un contesto approfondito di 25-30 chunk ideale per tesi magistrali,
    dissertazioni, rassegne dello stato dell'arte e capitoli monografici.

    Args:
        query: L'argomento o titolo della tesi / rassegna da esplorare.
        top_k: Numero di risultati (range consentito: 20-35, default: 28).
    """
    db.connect()
    try:
        k_val = max(20, min(int(top_k or 28), 35))
        results = hybrid_retriever.thesis_research(query, top_k=k_val)
        body = context_builder.format_mcp_response(query, results, search_type="thesis_research")
        return (
            "🎓 THESIS RESEARCH MODE — Extended Literature & Macro Synthesis (25-30 Chunks)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            + body
        )
    finally:
        db.close()


@mcp.tool()
def academic_health() -> str:
    """Verifica lo stato del Knowledge Graph Neo4j e restituisce le statistiche."""
    try:
        db.connect()
        stats = db.execute_query("MATCH (n) RETURN count(n) as node_count")
        doc_count = db.execute_query("MATCH (d:Document) RETURN count(d) as c")[0]["c"]
        chunk_count = db.execute_query("MATCH (c:Chunk) RETURN count(c) as c")[0]["c"]
        courses = db.execute_query(
            "MATCH (d:Document) RETURN d.course as course, count(d) as docs ORDER BY docs DESC"
        )
        db.close()

        course_list = "\n".join([f"  • {c['course']}: {c['docs']} documenti" for c in courses])
        return (
            f"✅ Academic KB is HEALTHY\n"
            f"Nodi totali: {stats[0]['node_count']}\n"
            f"Documenti: {doc_count}\n"
            f"Chunk: {chunk_count}\n"
            f"Embedding Provider: {settings.embedding_provider} ({settings.embedding_model})\n"
            f"\nCorsi:\n{course_list}"
        )
    except Exception as e:
        return f"❌ Academic KB is DOWN: {str(e)}"


@mcp.tool()
def academic_courses() -> str:
    """Elenca tutti i corsi disponibili nel Knowledge Graph con i relativi documenti."""
    db.connect()
    try:
        courses = db.execute_query("""
            MATCH (d:Document)
            RETURN d.course as course, d.source_type as tipo, count(d) as n,
                   collect(d.title)[..5] as sample_titles
            ORDER BY course, tipo
        """)
        lines = []
        for c in courses:
            icon = "📄" if c["tipo"] == "pdf" else "📝"
            titles = ", ".join(c["sample_titles"][:3])
            lines.append(f"{icon} {c['course']} [{c['tipo']}]: {c['n']} documenti (es: {titles})")
        return "\n".join(lines)
    finally:
        db.close()


# ==============================================================================
# New Study Engine MCP Tools (Milestone M4)
# ==============================================================================

@mcp.tool()
def generate_questions(
    topic: str,
    difficulty: str = "medium",
    question_type: str = "mixed",
    count: int = 5
) -> str:
    """
    Genera domande di studio Q&A strutturate (JSON) usando il Knowledge Graph e LLM.

    Args:
        topic: Argomento o titolo del documento/lezione da cui generare le domande.
        difficulty: Livello di difficoltà ('easy'/'facile', 'medium'/'media', 'hard'/'difficile', 'mixed'/'misto'). Default: 'medium'.
        question_type: Tipologia ('multiple_choice', 'open', 'single_answer', 'exercise', 'mixed'). Default: 'mixed'.
        count: Numero di domande da generare (1-20). Default: 5.

    Returns:
        Stringa JSON contenente una lista di domande con campi 'question', 'answer',
        'type', 'difficulty', 'source_chunks', ecc.
    """
    connected = False
    try:
        try:
            db.connect()
            connected = True
        except Exception:
            connected = False

        try:
            results = question_gen.generate_questions(
                topic=topic,
                difficulty=difficulty,
                question_type=question_type,
                count=count
            )
            return json.dumps(results, ensure_ascii=False, indent=2)
        finally:
            if connected:
                db.close()
    except Exception as e:
        return json.dumps({"error": str(e), "status": "failed"}, ensure_ascii=False)


@mcp.tool()
def get_flashcards(topic: Optional[str] = None, course: Optional[str] = None) -> str:
    """
    Restituisce le flashcard da ripassare oggi secondo l'algoritmo SM-2 per il corso/argomento specificato.

    Args:
        topic: Filtro opzionale per parola chiave nell'argomento o domanda. Default: None.
        course: Filtro opzionale per corso accademico (es. 'CNS', 'SDCC', 'ML', 'SE'). Default: None.

    Returns:
        Stringa JSON con lista di flashcard aventi 'next_review' <= oggi.
    """
    connected = False
    try:
        try:
            db.connect()
            connected = True
        except Exception:
            connected = False

        try:
            cards = flashcard_eng.get_flashcards(topic=topic, course=course)
            return json.dumps(cards, ensure_ascii=False, indent=2)
        finally:
            if connected:
                db.close()
    except Exception as e:
        return json.dumps({"error": str(e), "status": "failed"}, ensure_ascii=False)


@mcp.tool()
def update_flashcard_review(flashcard_id: str, quality: int) -> str:
    """
    Aggiorna lo stato di memorizzazione SM-2 di una flashcard dopo la revisione dello studente.

    Args:
        flashcard_id: Identificativo univoco del nodo Flashcard in Neo4j.
        quality: Valutazione della risposta dello studente da 0 a 5:
                 0: buco nero totale, 1: errata ricordata dopo,
                 2: errata ma familiare, 3: corretta con seria difficoltà,
                 4: corretta dopo esitazione, 5: risposta perfetta immediata.

    Returns:
        Stringa JSON con lo stato aggiornato della flashcard (interval, easiness_factor, next_review).
    """
    connected = False
    try:
        try:
            db.connect()
            connected = True
        except Exception:
            connected = False

        try:
            updated = flashcard_eng.update_flashcard_review(flashcard_id=flashcard_id, quality=quality)
            if updated is None:
                return json.dumps({"error": f"Flashcard '{flashcard_id}' not found", "status": "failed"}, ensure_ascii=False)
            return json.dumps(updated, ensure_ascii=False, indent=2)
        finally:
            if connected:
                db.close()
    except Exception as e:
        return json.dumps({"error": str(e), "status": "failed"}, ensure_ascii=False)


@mcp.tool()
def detect_knowledge_gaps(course: str) -> str:
    """
    Analizza la copertura delle fonti primarie per un corso e identifica i gap di conoscenza (chunk_count < 2).

    Args:
        course: Il codice del corso da analizzare (es. 'CNS', 'SDCC', 'ML', 'SE').

    Returns:
        Stringa JSON contenente una lista ordinata di documenti con
        'source_title', 'chunk_count', 'coverage_score', 'is_gap'.
    """
    connected = False
    try:
        try:
            db.connect()
            connected = True
        except Exception:
            connected = False

        try:
            report = gap_detector.detect_knowledge_gaps(course=course)
            return json.dumps(report, ensure_ascii=False, indent=2)
        finally:
            if connected:
                db.close()
    except Exception as e:
        return json.dumps({"error": str(e), "status": "failed"}, ensure_ascii=False)


@mcp.tool()
def link_past_exams(course: str = "CNS") -> str:
    """
    Esegue l'exam linking per un corso: individua temi d'esame in resources/ e crea relazioni ANSWERS nel grafo verso i chunk più rilevanti.

    Args:
        course: Il corso di cui indicizzare e collegare i temi d'esame (default: 'CNS').

    Returns:
        Stringa JSON con statistiche di linking (questions_processed, answers_linked, etc.).
    """
    connected = False
    try:
        try:
            db.connect()
            connected = True
        except Exception:
            connected = False

        try:
            result = exam_linker.link_past_exams(course=course)
            return json.dumps(result, ensure_ascii=False, indent=2)
        finally:
            if connected:
                db.close()
    except Exception as e:
        return json.dumps({"error": str(e), "status": "failed"}, ensure_ascii=False)


@mcp.tool()
def generate_learning_path(topic: str) -> str:
    """
    Costruisce un percorso di studio ordinato con sequenza di prerequisiti (PREREQUISITE_OF)
    attraverso il Concept Graph e ragionamento didattico LLM.

    Args:
        topic: Il concetto o argomento target da apprendere (es. 'Zero-Knowledge Proofs', 'Raft Consensus').

    Returns:
        Stringa JSON con sequenza ordinata di passaggi didattici, concetti prerequisiti e sintesi.
    """
    connected = False
    try:
        try:
            db.connect()
            connected = True
        except Exception:
            connected = False

        try:
            path = learning_path_eng.generate_learning_path(topic=topic)
            return json.dumps(path, ensure_ascii=False, indent=2)
        finally:
            if connected:
                db.close()
    except Exception as e:
        return json.dumps({"error": str(e), "status": "failed"}, ensure_ascii=False)


@mcp.tool()
def thesis_assistant(title: str) -> str:
    """
    Genera un indice strutturato di tesi/relazione con sezioni e sottosezioni,
    popolando ciascuna con i chunk più rilevanti del KB come bozza di contenuto e citazioni accademiche.

    Args:
        title: Il titolo o argomento della tesi / relazione accademica.

    Returns:
        Stringa JSON con bozza strutturata, abstract, sezioni e citazioni KB.
    """
    connected = False
    try:
        try:
            db.connect()
            connected = True
        except Exception:
            connected = False

        try:
            outline = thesis_asst.generate_thesis_outline(title=title)
            return json.dumps(outline, ensure_ascii=False, indent=2)
        finally:
            if connected:
                db.close()
    except Exception as e:
        return json.dumps({"error": str(e), "status": "failed"}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
