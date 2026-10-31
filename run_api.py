from fastapi import FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import uvicorn
import json
import logging
import os
import re
from starlette.websockets import WebSocketState
from engine.voice.bridge import GeminiLiveBridge, VoiceBridgeConfig, SafeWebSocketSender
from engine.voice.grounding import AcademicGroundingBridge, GROUNDING_TOOL_SCHEMA

logger = logging.getLogger("academic_kb.api")

from core.database import Neo4jManager
from engine.study.question_generator import QuestionGenerator
from engine.study.flashcard_engine import FlashcardEngine
from engine.study.gap_detector import GapDetector
from engine.study.exam_linker import ExamLinker
from engine.study.learning_path import LearningPathEngine
from engine.study.thesis_assistant import ThesisAssistant
from engine.study.llm_client import get_llm_client
from engine.retrieval.vector import VectorRetriever
from engine.retrieval.fulltext import FulltextRetriever
from engine.retrieval.hybrid import HybridRetriever
from engine.embeddings.provider import EmbeddingProvider

from config.settings import get_settings
settings = get_settings()

app = FastAPI(title="Academic KB - Study Engine API")

# --- TOKEN SECURITY MIDDLEWARE (MAX ZERO-TRUST) ---
AUTH_TOKEN = os.environ.get("ACADEMIC_KB_TOKEN", "dev-token-academic-kb")

class SecurityAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow localhost / loopback calls without token
        client_host = request.client.host if request.client else ""
        if client_host in ("127.0.0.1", "::1", "localhost"):
            return await call_next(request)

        # For external connections (LAN / Tailscale), check token or cookie
        token_param = request.query_params.get("token")
        cookie_token = request.cookies.get("academic_kb_token")
        header_token = request.headers.get("x-token")

        has_valid_token = (
            (token_param and token_param == AUTH_TOKEN) or
            (cookie_token and cookie_token == AUTH_TOKEN) or
            (header_token and header_token == AUTH_TOKEN)
        )

        if not has_valid_token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: valid token required"}
            )

        response = await call_next(request)

        # Set cookie if authenticated via query param for smooth navigation
        if token_param and token_param == AUTH_TOKEN:
            response.set_cookie(
                key="academic_kb_token",
                value=AUTH_TOKEN,
                max_age=31536000,
                httponly=True,
                samesite="lax",
                path="/"
            )
        return response

app.add_middleware(SecurityAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database instance
db = Neo4jManager(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)
embedder = EmbeddingProvider(
    settings.embedding_provider, settings.embedding_model,
    settings.embedding_dimension, settings.embedding_api_key,
    settings.embedding_base_url
)
vector_retriever = VectorRetriever(db, embedder)
fulltext_retriever = FulltextRetriever(db)
hybrid_retriever = HybridRetriever(vector_retriever, fulltext_retriever)

llm_client = get_llm_client(settings)
question_gen = QuestionGenerator(llm_client, hybrid_retriever)
flashcard_eng = FlashcardEngine(db=db, llm_client=llm_client)
gap_detector_eng = GapDetector(db)
learning_path_eng = LearningPathEngine(db, llm_client)
grounding_bridge = AcademicGroundingBridge(db=db, retriever=hybrid_retriever)

# --- API ENDPOINTS ---

KNOWN_COURSES = {
    "CNS": {
        "id": "CNS",
        "code": "CNS",
        "name": "Network Security",
        "icon": "🛡️",
        "tagClass": "tag-cns",
        "color": "#38bdf8",
        "topics": [
            "TLS 1.3 Handshake",
            "PFS & DHE/ECDHE",
            "WEP FMS Attack",
            "Kerberos AS & TGS",
            "IPsec ESP vs AH",
            "Diffie-Hellman Man-in-the-Middle"
        ]
    },
    "SDCC": {
        "id": "SDCC",
        "code": "SDCC",
        "name": "Distributed Cloud",
        "icon": "☁️",
        "tagClass": "tag-sdcc",
        "color": "#c084fc",
        "topics": [
            "Consensus Raft & Safety",
            "SAGA Choreography & Orchestration",
            "2PC Two-Phase Commit",
            "Paxos & Quorum",
            "CAP & PACELC Theorem",
            "Linearizability vs Sequential Consistency"
        ]
    },
    "ML": {
        "id": "ML",
        "code": "ML",
        "name": "Machine Learning",
        "icon": "🤖",
        "tagClass": "tag-ml",
        "color": "#00ff88",
        "topics": [
            "Backpropagation & Chain Rule",
            "Gradient Descent & Adam",
            "Cross-Entropy Loss",
            "Overfitting & Regularization L1/L2",
            "Transformer Self-Attention",
            "Batch Normalization"
        ]
    },
    "SE": {
        "id": "SE",
        "code": "SE",
        "name": "Software Security",
        "icon": "🔒",
        "tagClass": "tag-se",
        "color": "#f87171",
        "topics": [
            "Buffer Overflow & Stack Canary",
            "SQL Injection & Prepared Statements",
            "XSS & CSRF Defense",
            "Control Flow Integrity (CFI)",
            "Race Conditions & TOCTOU",
            "OAuth2 & JWT Security"
        ]
    },
    "GEOMETRIA AROSIO": {
        "id": "GEOMETRIA AROSIO",
        "code": "GEOMETRIA",
        "name": "Geometria (Arosio)",
        "icon": "📐",
        "tagClass": "tag-geometria",
        "color": "#818cf8",
        "topics": [
            "Applicazioni Lineari",
            "Spazi Vettoriali & Basi",
            "Forme Bilineari & Quadratiche",
            "Matrici & Sistemi Lineari",
            "Autovalori, Autovettori & Diagonalizzazione",
            "Forma Canonica di Jordan",
            "Teorema Spettrale",
            "Nucleo e Immagine (Nullità più Rango)"
        ]
    },
    "SERT": {
        "id": "SERT",
        "code": "SERT",
        "name": "Sistemi Embedded & Real-Time",
        "icon": "⏱️",
        "tagClass": "tag-sert",
        "color": "#f97316",
        "topics": [
            "Scheduling Real-Time Rate Monotonic",
            "Earliest Deadline First (EDF)",
            "Priority Inversion & PIP/PCP",
            "Sistemi Embedded Low Power",
            "Timer & Interrupt Latency"
        ]
    },
    "MAGISTRALE": {
        "id": "MAGISTRALE",
        "code": "MAGISTRALE",
        "name": "Generale Magistrale",
        "icon": "🎓",
        "tagClass": "tag-magistrale",
        "color": "#fbbf24",
        "topics": [
            "Forme Quadratiche & Bilineari",
            "Complessità Computazionale P vs NP",
            "Distributed Systems Consistency",
            "Algoritmi di Approssimazione & Vertex Cover"
        ]
    }
}

DYNAMIC_PALETTE = ["#38bdf8", "#00ff88", "#c084fc", "#f87171", "#fbbf24", "#818cf8", "#f97316", "#2dd4bf", "#e879f9", "#34d399", "#f43f5e"]

def _infer_course_icon(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ["geom", "mat", "alg", "calc", "linear", "analis"]): return "📐"
    if any(k in n for k in ["sec", "cryp", "cns", "cyb", "priv"]): return "🛡️"
    if any(k in n for k in ["cloud", "distrib", "net", "sdcc"]): return "☁️"
    if any(k in n for k in ["ml", "ai", "deep", "learn", "data"]): return "🤖"
    if any(k in n for k in ["embed", "rt", "sert", "hard", "arch"]): return "⏱️"
    if any(k in n for k in ["soft", "dev", "code", "prog", "web"]): return "💻"
    return "📚"

@app.get("/api/courses")
async def api_get_courses():
    """
    Rileva dinamicamente i corsi dalla directory principale su disco (magistrale_courses_dir)
    e dal database Neo4j. Se domani l'utente aggiunge una nuova cartella corso, questa
    viene immediatamente riconosciuta e resa disponibile con metadati, icona e argomenti.
    """
    try:
        courses_dir = settings.magistrale_courses_dir
        disk_courses = {}
        disk_topics = {}

        if os.path.exists(courses_dir):
            for entry in sorted(os.listdir(courses_dir)):
                p = os.path.join(courses_dir, entry)
                if not entry.startswith(".") and os.path.isdir(p):
                    pdf_files = []
                    for root, _, files in os.walk(p):
                        for f in files:
                            if f.lower().endswith(".pdf") and not f.startswith("."):
                                pdf_files.append(f)
                    disk_courses[entry] = len(pdf_files)

                    cleaned = []
                    for pf in pdf_files:
                        base = re.sub(r"\.pdf$", "", pf, flags=re.I)
                        base = re.sub(r"^(Capitolo\s*\d+\s*[-_]?\s*|\d+[-_]\s*|lez[-_][a-zA-Z0-9]+[-_]?\s*)", "", base, flags=re.I)
                        base = base.replace("_", " ").strip()
                        if len(base) > 3 and base not in cleaned and not base.isdigit():
                            cleaned.append(base)
                    disk_topics[entry] = cleaned[:8]

        db_courses = {}
        try:
            db.connect()
            db_res = db.execute_query("MATCH (d:Document) RETURN d.course as course, count(d) as docs")
            db_courses = {r["course"]: r["docs"] for r in db_res if r.get("course")}
        except Exception:
            pass
        finally:
            db.close()

        all_course_ids = set(disk_courses.keys()) | set(db_courses.keys())

        preferred_order = ["CNS", "SDCC", "ML", "SE", "GEOMETRIA AROSIO", "SERT", "MAGISTRALE"]
        sorted_ids = [cid for cid in preferred_order if cid in all_course_ids]
        for cid in sorted(all_course_ids):
            if cid not in sorted_ids:
                sorted_ids.append(cid)

        result = []
        for idx, cid in enumerate(sorted_ids):
            total_docs = max(db_courses.get(cid, 0), disk_courses.get(cid, 0))
            if cid in KNOWN_COURSES:
                info = dict(KNOWN_COURSES[cid])
                info["doc_count"] = total_docs
                result.append(info)
            else:
                clean_name = cid.replace("_", " ").title()
                code = cid[:6].upper()
                icon = _infer_course_icon(cid)
                color = DYNAMIC_PALETTE[idx % len(DYNAMIC_PALETTE)]
                topics = disk_topics.get(cid) or [
                    "Introduzione e Fondamenti",
                    "Architettura e Concetti Chiave",
                    "Metodologie e Standard",
                    "Casi di Studio Applicativi"
                ]
                result.append({
                    "id": cid,
                    "code": code,
                    "name": clean_name,
                    "icon": icon,
                    "tagClass": "tag-custom",
                    "color": color,
                    "topics": topics,
                    "doc_count": total_docs
                })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync_courses")
async def api_sync_courses():
    """
    Esegue una scansione e ingestione incrementale della directory principale per nuovi corsi/file.
    """
    try:
        from engine.graph.schema import GraphSchemaManager
        from engine.ingestion.chunking import TextChunker
        from engine.ingestion.pipeline import IngestionPipeline
        from connectors.files.pdf import PDFConnector
        
        db.connect()
        schema_mgr = GraphSchemaManager(db)
        schema_mgr.setup_schema(vector_dimension=settings.embedding_dimension)
        chunker = TextChunker(chunk_size=1000, chunk_overlap=200)
        pipeline = IngestionPipeline(db, embedder, chunker)
        connector = PDFConnector(directory=settings.magistrale_courses_dir, course_name="auto")
        pipeline.run(connector, force=False)
        return {"status": "ok", "message": "Sincronizzazione corsi completata con successo"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/search")
async def search_kb(q: str = Query(..., description="Query di ricerca")):
    try:
        db.connect()
        results = hybrid_retriever.search(q, top_k=8)
        
        # Formattiamo i risultati per la UI
        formatted = []
        for r in results:
            formatted.append({
                "id": r.get("chunk_id") or r.get("id"),
                "label": r.get("source_title", "Documento senza titolo"),
                "snippet": r.get("text", "")[:120] + "...",
                "course": r.get("course", "MAGISTRALE"),
                "type": r.get("source_type", "chunk")
            })
        return formatted
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

class QuestionRequest(BaseModel):
    topic: str
    difficulty: str = "medium"
    question_type: str = "mixed"
    count: int = 5
    custom_instructions: Optional[str] = None
    course: Optional[str] = "ALL"

@app.post("/api/generate_questions")
async def api_generate_questions(req: QuestionRequest):
    try:
        db.connect()
        results = question_gen.generate_questions(
            topic=req.topic, 
            difficulty=req.difficulty, 
            question_type=req.question_type, 
            count=req.count,
            custom_instructions=req.custom_instructions,
            course=req.course
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

class StepChatRequest(BaseModel):
    topic: str
    step_title: str
    step_description: str
    message: str
    history: List[Dict[str, str]] = []

@app.post("/api/chat_step")
async def api_chat_step(req: StepChatRequest):
    try:
        db.connect()
        # Retrieve context from Knowledge Graph
        search_query = f"{req.step_title} {req.message}"
        hits = hybrid_retriever.search(search_query, top_k=4)
        context_chunks = []
        sources = []
        for h in hits:
            sources.append({
                "title": h.get("source_title") or "Doc",
                "page": h.get("page") or 1,
                "course": h.get("course") or "MAGISTRALE"
            })
            text = h.get("text", "")
            if text:
                context_chunks.append(f"[{h.get('source_title', 'Doc')} p.{h.get('page', 1)}]: {text[:400]}")

        context_str = "\n".join(context_chunks) if context_chunks else "Nessun chunk specifico trovato."

        system_prompt = (
            "Sei DIMEOGPT, l'assistente accademico di Tor Vergata (Cyber Security & Sistemi Distribuiti). "
            f"Stai affiancando lo studente nello studio del percorso su '{req.topic}', nello specifico sullo STEP: '{req.step_title}'.\n"
            f"Descrizione dello step: '{req.step_description}'.\n"
            "Rispondi con competenza magistrale, spiegando i concetti in modo chiaro, rigoroso e pratico. "
            "Se ci sono chunk di contesto, fanne riferimento citando le fonti.\n\n"
            f"--- CHUNKS DAL GRAFO ACCADEMICO ---\n{context_str}"
        )

        history_prompts = []
        for h in req.history[-6:]:
            role = "Utente" if h.get("role") == "user" else "DIMEOGPT"
            history_prompts.append(f"{role}: {h.get('content')}")

        full_prompt = "\n".join(history_prompts)
        if full_prompt:
            full_prompt += f"\nUtente: {req.message}\nDIMEOGPT:"
        else:
            full_prompt = f"Domanda dello studente: {req.message}"

        reply = llm_client.generate(full_prompt, system_prompt=system_prompt)
        return {
            "reply": reply,
            "sources": sources
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

class ExplainQuestionRequest(BaseModel):
    course: Optional[str] = "MAGISTRALE"
    topic: Optional[str] = "Studio Accademico"
    question: str
    options: Optional[List[str]] = []
    selected_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    is_correct: Optional[bool] = False

@app.post("/api/explain_question")
async def api_explain_question(req: ExplainQuestionRequest):
    try:
        db.connect()
        search_query = f"{req.topic} {req.question}"
        hits = hybrid_retriever.search(search_query, top_k=4)
        context_chunks = []
        sources = []
        for h in hits:
            sources.append({
                "title": h.get("source_title") or "Doc",
                "page": h.get("page") or 1,
                "course": h.get("course") or req.course or "MAGISTRALE"
            })
            text = h.get("text", "")
            if text:
                context_chunks.append(f"[{h.get('source_title', 'Doc')} p.{h.get('page', 1)}]: {text[:400]}")

        context_str = "\n".join(context_chunks) if context_chunks else "Nessun chunk specifico estratto dal grafo."
        status_text = "CORRETTA" if req.is_correct else "ERRATA"
        opt_str = "\n".join([f"- {o}" for o in req.options]) if req.options else "N/D"

        system_prompt = (
            "Sei DIMEOGPT, l'esperto accademico e tutor didattico di livello magistrale (Tor Vergata).\n"
            "Uno studente ti sottopone un quesito d'esame a cui ha risposto, chiedendoti un'analisi formale e rigorosa.\n"
            "DEVI strutturare la spiegazione in modo impeccabile, con formule matematiche in notazione standard LaTeX ($ ... $ e $$ ... $$), "
            "dimostrazioni formali, disamina concettuale dell'errore commesso e chiarimento di tutti i distrattori.\n\n"
            f"--- MATERIALE DIDATTICO DAL GRAFO ACCADEMICO ---\n{context_str}"
        )

        user_prompt = (
            f"Corso: {req.course}\n"
            f"Argomento: {req.topic}\n\n"
            f"DOMANDA D'ESAME:\n{req.question}\n\n"
            f"OPZIONI DISPONIBILI:\n{opt_str}\n\n"
            f"RISPOSTA FORNITA DALLO STUDENTE:\n{req.selected_answer or 'Non indicata'} (Esito: {status_text})\n\n"
            f"RISPOSTA CORRETTA UFFICIALE:\n{req.correct_answer or 'N/D'}\n\n"
            f"SPIEGAZIONE SINTETICA DI PARTENZA:\n{req.explanation or 'N/D'}\n\n"
            "Forniscimi una spiegazione didattica e accademica approfondita, articolata nei seguenti punti:\n"
            "1. **Analisi Critica della Risposta Fornita dallo Studente**: perché è errata (o perché è corretta), qual è l'equivoco concettuale tipico e quale proprietà fondamentale è stata trascurata.\n"
            "2. **Dimostrazione e Giustificazione Teorico-Matematica Formale**: passaggi logici rigorosi con formule LaTeX, definizioni e teoremi di riferimento.\n"
            "3. **Disamina Dettagliata di Tutte le Altre Alternative**: perché ciascun distrattore non è corretto.\n"
            "4. **Esempio Numerico / Controesempio Pratico**: un caso concreto (es. matrici esplicite in R^2/R^3 o scenario di fallimento) per consolidare il concetto in vista della prova orale."
        )

        reply = llm_client.generate(user_prompt, system_prompt=system_prompt)
        return {
            "reply": reply,
            "sources": sources
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/api/flashcards")
async def api_get_flashcards(course: str = None, topic: str = None):
    try:
        db.connect()
        cards = flashcard_eng.get_flashcards(topic=topic, course=course)
        return cards
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

class FlashcardGenerateRequest(BaseModel):
    topic: str
    course: str = "GENERAL"
    count: int = 5

@app.post("/api/generate_flashcards")
async def api_generate_flashcards(req: FlashcardGenerateRequest):
    try:
        db.connect()
        cards = flashcard_eng.create_flashcards_from_topic(
            topic=req.topic, 
            course=req.course, 
            count=req.count
        )
        return cards
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/api/update_flashcard_review")
async def api_update_flashcard(payload: dict):
    try:
        db.connect()
        flashcard_id = payload.get("id")
        quality = payload.get("quality", 3)
        updated = flashcard_eng.update_flashcard_review(flashcard_id=flashcard_id, quality=quality)
        if not updated:
            raise HTTPException(status_code=404, detail="Flashcard not found")
        return updated
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/detect_knowledge_gaps")
async def api_detect_gaps(course: str):
    try:
        db.connect()
        report = gap_detector_eng.detect_knowledge_gaps(course=course)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/generate_learning_path")
async def api_generate_path(topic: str):
    try:
        db.connect()
        path = learning_path_eng.generate_learning_path(topic=topic)
        return path
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# --- GEMINI LIVE VOICE STREAMING WEBSOCKET ENDPOINT ---

async def _safe_close_websocket(ws: WebSocket, code: int = status.WS_1000_NORMAL_CLOSURE, reason: str = "") -> None:
    """Safely closes WebSocket connection if still in CONNECTED application state."""
    app_state = getattr(ws, "application_state", None)
    if app_state == WebSocketState.CONNECTED:
        try:
            await ws.close(code=code, reason=reason)
            logger.info(f"Closed WebSocket session (code={code}, reason='{reason}').")
        except Exception as e:
            logger.debug(f"Ignored exception during WebSocket close (code={code}): {e}")

@app.websocket("/api/live_voice")
async def websocket_live_voice_endpoint(
    websocket: WebSocket,
    course: Optional[str] = Query(None),
    voice: Optional[str] = Query(None)
):
    """
    Bidirectional voice streaming endpoint for DIMEOGPT Study Studio.
    Handles 16kHz PCM audio upload, 24kHz PCM audio download, Hybrid VAD,
    barge-in interruption, and strict grounding retrieval.
    """
    # 1. Zero-Trust Security Handshake
    client_host = websocket.client.host if websocket.client else ""
    is_loopback = client_host in ("127.0.0.1", "::1", "localhost", "testclient")

    if not is_loopback:
        token_param = websocket.query_params.get("token")
        cookie_token = websocket.cookies.get("academic_kb_token")
        header_token = websocket.headers.get("x-token")
        has_valid_token = (
            (token_param and token_param == AUTH_TOKEN) or
            (cookie_token and cookie_token == AUTH_TOKEN) or
            (header_token and header_token == AUTH_TOKEN)
        )
        if not has_valid_token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
            return

    # Accept the connection
    await websocket.accept()
    sender = SafeWebSocketSender(websocket)

    # Ensure Neo4j connection is active for grounding queries
    try:
        db.connect()
    except Exception as e:
        logger.warning(f"Neo4j connection check: {e}")

    # 2. Configuration & Driver Selection
    from dotenv import load_dotenv
    load_dotenv(override=True)
    gemini_key = (
        os.getenv("GEMINI_API_KEY")
        or getattr(settings, "gemini_api_key", None)
        or (getattr(settings, "llm_api_key", None) if (getattr(settings, "llm_provider", "") or "").lower() == "gemini" else None)
    )
    is_mock = (getattr(settings, "llm_provider", "") == "mock") or not gemini_key

    selected_voice = voice or os.getenv("GEMINI_LIVE_VOICE") or getattr(settings, "gemini_live_voice", "Charon")

    bridge_config = VoiceBridgeConfig(
        model=getattr(settings, "gemini_live_model", "gemini-3.8-live"),
        voice_name=selected_voice,
        api_key=gemini_key,
        system_instruction=grounding_bridge.get_system_instructions(course=course),
        tools=[GROUNDING_TOOL_SCHEMA],
        mock_mode=is_mock
    )

    # 3. Non-blocking Tool Handler Wrapper (Strict Grounding via AcademicGroundingBridge)
    bridge = GeminiLiveBridge(config=bridge_config, tool_handler=grounding_bridge.handle_tool_call)

    # 4. Bridge Execution and Graceful Lifecycle Management
    clean_exit = False
    try:
        await bridge.run(client_ws=websocket, course=course or "CNS", sender=sender)
        clean_exit = True
    except WebSocketDisconnect as e:
        code = getattr(e, "code", status.WS_1000_NORMAL_CLOSURE)
        if code in (status.WS_1000_NORMAL_CLOSURE, status.WS_1001_GOING_AWAY):
            logger.info(f"WebSocket client disconnected cleanly (code={code}).")
        else:
            logger.warning(f"WebSocket client disconnected abnormally (code={code}).")
    except Exception as e:
        logger.error(f"Unexpected error in live voice session: {e}", exc_info=True)
        try:
            await sender.send_json({"type": "error", "message": f"Session error: {str(e)}"})
        except Exception:
            pass
        await _safe_close_websocket(websocket, code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")
    finally:
        try:
            await bridge.close()
        except Exception as e:
            logger.warning(f"Error during bridge close: {e}")
        if clean_exit:
            await _safe_close_websocket(websocket, code=status.WS_1000_NORMAL_CLOSURE, reason="Session completed normally")

# --- SERVING FILE STATICI SECURE (HTML/CSS/JS) ---

ALLOWED_ROOT_FILES = {
    "index.html",
    "study.html", 
    "graph_3d.html",
    "graph_search.html",
    "graph_3d_data.json",
    "tesla_roadster_gen2.glb",
    "tesla_roadster_gen2.obj",
    "aermacchi_m345_frecce_tricolori.glb",
}

@app.get("/")
async def root():
    return FileResponse("index.html")

@app.get("/{filename}")
async def serve_root_file(filename: str):
    if filename in ALLOWED_ROOT_FILES:
        headers = {}
        if filename.endswith(".html"):
            headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            headers["Pragma"] = "no-cache"
            headers["Expires"] = "0"
        return FileResponse(filename, headers=headers)
    raise HTTPException(status_code=404, detail="File not found")

# Monta SOLO la cartella static (css/immagini) per evitare di esporre .env o .py
import os
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    host = os.environ.get("ACADEMIC_KB_HOST", "127.0.0.1")
    port = int(os.environ.get("ACADEMIC_KB_PORT", 8000))
    print(f"🚀 Avvio del Study Engine API Server (Secure Mode on {host}:{port})...")
    uvicorn.run("run_api:app", host=host, port=port, reload=True)
