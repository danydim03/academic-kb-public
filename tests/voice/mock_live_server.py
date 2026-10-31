"""
Academic KB Voice Studio — Mock Gemini Live Server & Protocol Reference Harness
Provides deterministic simulation of Google Gemini Live WebSocket API and FastAPI /api/live_voice bridge.
Strictly adheres to interface contracts in PROJECT.md.
"""

import math
import struct
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple, AsyncGenerator
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Protocol Constants (Authoritative from PROJECT.md)
# ---------------------------------------------------------------------------

CLIENT_SAMPLE_RATE = 16000     # 16kHz Int16 mono
CLIENT_CHUNK_SAMPLES = 1024    # 1024 samples = 64ms
CLIENT_FRAME_BYTES = 2048      # 1024 samples * 2 bytes/sample

SERVER_SAMPLE_RATE = 24000     # 24kHz Int16 mono
SERVER_CHUNK_SAMPLES = 1200    # 1200 samples = 50ms
SERVER_FRAME_BYTES = 2400      # 1200 samples * 2 bytes/sample

MODEL_NAME = "gemini-3.8-live"

AVATAR_IMAGE_WIDTH = 636
AVATAR_IMAGE_HEIGHT = 1024
AVATAR_CANVAS_WIDTH = 318
AVATAR_CANVAS_HEIGHT = 512
AVATAR_MOUTH_X_START = 250
AVATAR_MOUTH_X_END = 380
AVATAR_LIP_FISSURE_Y = 424     # 41.41% of 1024
AVATAR_MAX_JAW_OFFSET_PX = 8.0
AVATAR_RMS_JAW_MULTIPLIER = 28.0
AVATAR_ORAL_CAVITY_COLOR = "rgba(25, 8, 12, 0.95)"
AVATAR_CYBER_GLOW_COLOR = "#00ff88"

GROUNDING_TOOL_SCHEMA = {
    "name": "query_academic_kb",
    "description": "Searches the local university course knowledge base for slides, documents, notes, and academic materials. Must be used whenever the student asks questions about course content.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "The specific academic concept or search query"
            },
            "course": {
                "type": "STRING",
                "description": "Optional course code filter (e.g. CNS, ML, BD, etc.)"
            }
        },
        "required": ["query"]
    },
    "behavior": "NON_BLOCKING"
}


# ---------------------------------------------------------------------------
# Audio Synthesis & Verification Utilities
# ---------------------------------------------------------------------------

def generate_pcm_16k(duration_ms: int = 64, frequency: float = 440.0, amplitude: float = 0.5) -> bytes:
    """Generates 16kHz Int16 PCM mono audio bytes."""
    num_samples = int(CLIENT_SAMPLE_RATE * (duration_ms / 1000.0))
    buffer = bytearray(num_samples * 2)
    max_int16 = 32767
    for i in range(num_samples):
        t = float(i) / CLIENT_SAMPLE_RATE
        val = int(amplitude * max_int16 * math.sin(2.0 * math.pi * frequency * t))
        val = max(-32768, min(32767, val))
        struct.pack_into("<h", buffer, i * 2, val)
    return bytes(buffer)


def generate_silence_16k(duration_ms: int = 64) -> bytes:
    """Generates 16kHz Int16 PCM mono silence (zeros)."""
    num_samples = int(CLIENT_SAMPLE_RATE * (duration_ms / 1000.0))
    return b"\x00" * (num_samples * 2)


def generate_pcm_24k(duration_ms: int = 50, frequency: float = 300.0, amplitude: float = 0.6) -> bytes:
    """Generates 24kHz Int16 PCM mono audio bytes."""
    num_samples = int(SERVER_SAMPLE_RATE * (duration_ms / 1000.0))
    buffer = bytearray(num_samples * 2)
    max_int16 = 32767
    for i in range(num_samples):
        t = float(i) / SERVER_SAMPLE_RATE
        val = int(amplitude * max_int16 * math.sin(2.0 * math.pi * frequency * t))
        val = max(-32768, min(32767, val))
        struct.pack_into("<h", buffer, i * 2, val)
    return bytes(buffer)


def calculate_rms(pcm_bytes: bytes) -> float:
    """Calculates normalized RMS amplitude [0.0 .. 1.0] from Int16 PCM bytes."""
    if not pcm_bytes or len(pcm_bytes) < 2:
        return 0.0
    num_samples = len(pcm_bytes) // 2
    sum_sq = 0.0
    for i in range(num_samples):
        sample = struct.unpack_from("<h", pcm_bytes, i * 2)[0]
        norm = sample / 32768.0
        sum_sq += norm * norm
    mean_sq = sum_sq / num_samples
    return math.sqrt(mean_sq)


def compute_avatar_jaw_offset(rms: float) -> float:
    """Computes lower jaw vertical pixel offset using PROJECT.md contract formula."""
    if math.isnan(rms) or rms < 0.0:
        return 0.0
    return min(AVATAR_MAX_JAW_OFFSET_PX, rms * AVATAR_RMS_JAW_MULTIPLIER)


def compute_avatar_glow_style(rms: float) -> str:
    """Computes avatar cyber glow box-shadow string using PROJECT.md contract formula."""
    blur_px = 12.0 + (rms * 40.0)
    alpha = 0.25 + (rms * 0.65)
    return f"0 0 {blur_px:.1f}px rgba(0, 255, 136, {alpha:.2f})"


def format_academic_citation(source_title: str, page: Optional[int] = None) -> str:
    """Formats academic citation according to user rules and PROJECT.md: [Doc.pdf, p. X]."""
    clean_title = source_title.strip()
    if page is not None and page > 0:
        return f"[{clean_title}, p. {page}]"
    return f"[{clean_title}]"


# ---------------------------------------------------------------------------
# Strict Grounding & Anti-Hallucination Knowledge Engine Simulator
# ---------------------------------------------------------------------------

@dataclass
class AcademicDocChunk:
    chunk_id: str
    source_title: str
    page: int
    course: str
    content: str
    score: float = 0.85


DEFAULT_MOCK_KB: List[AcademicDocChunk] = [
    AcademicDocChunk(
        chunk_id="chunk-cns-tls-001",
        source_title="Sicurezza_Reti_TLS13.pdf",
        page=42,
        course="CNS",
        content="In TLS 1.3, the handshake latency is reduced to 1-RTT. Key exchange uses (EC)DH with Diffie-Hellman parameters sent in the ClientHello.",
        score=0.92
    ),
    AcademicDocChunk(
        chunk_id="chunk-cns-wep-002",
        source_title="Wireless_Security_WEP.pdf",
        page=15,
        course="CNS",
        content="WEP uses RC4 with a 24-bit Initialization Vector (IV). The short IV length leads to keystream reuse and FMS attacks.",
        score=0.88
    ),
    AcademicDocChunk(
        chunk_id="chunk-ml-svm-001",
        source_title="Machine_Learning_Support_Vectors.pdf",
        page=77,
        course="ML",
        content="Support Vector Machines optimize the maximum margin hyperplane separating classes using quadratic programming.",
        score=0.85
    )
]


class StrictGroundingGuard:
    """
    Two-layer strict grounding defense:
    Layer 1: Cosine/relevance threshold guard (threshold = 0.60)
    Layer 2: Unavailability declaration when found: false (zero hallucination)
    """

    def __init__(self, kb: Optional[List[AcademicDocChunk]] = None, relevance_threshold: float = 0.60):
        self.kb = kb or list(DEFAULT_MOCK_KB)
        self.relevance_threshold = relevance_threshold

    def query(self, query_str: str, course: Optional[str] = None) -> Dict[str, Any]:
        q_lower = query_str.lower()
        candidates: List[AcademicDocChunk] = []

        for chunk in self.kb:
            if course and course.upper() != "GENERAL" and chunk.course.upper() != course.upper():
                continue

            # Check keyword relevance with punctuation-stripped tokens and stopword filtering
            import re
            stopwords = {"in", "di", "da", "su", "il", "lo", "la", "le", "un", "una", "uno", "to", "of", "and", "the", "for", "is", "are"}
            terms = [t for t in re.findall(r"\w+", q_lower) if len(t) >= 3 and t not in stopwords]
            match_count = sum(1 for t in terms if t in chunk.content.lower() or t in chunk.source_title.lower())
            if match_count > 0:
                candidates.append(chunk)

        # Filter by threshold
        valid_chunks = [c for c in candidates if c.score >= self.relevance_threshold]

        if not valid_chunks:
            return {
                "found": False,
                "query": query_str,
                "course": course,
                "citations": [],
                "message": "Nessuna informazione accademica pertinente trovata nei documenti ufficiali del Knowledge Graph per questa richiesta.",
                "k": 0
            }

        citations = []
        for c in valid_chunks:
            citations.append({
                "source": c.source_title,
                "page": c.page,
                "course": c.course,
                "snippet": c.content[:150],
                "citation_tag": format_academic_citation(c.source_title, c.page)
            })

        return {
            "found": True,
            "query": query_str,
            "course": course,
            "k": len(citations),
            "citations": citations,
            "message": f"Trovati {len(citations)} frammenti documentali accreditati."
        }


# ---------------------------------------------------------------------------
# Mock Gemini Live Voice Session Bridge
# ---------------------------------------------------------------------------

class MockLiveVoiceBridge:
    """
    Opaque-box emulator of FastAPI /api/live_voice endpoint and Gemini Live session.
    Simulates bidirectional streaming, VAD, barge-in, grounding tool execution,
    and talking avatar audio emission.
    """

    def __init__(self, course: str = "CNS", grounding_guard: Optional[StrictGroundingGuard] = None):
        self.course = course
        self.grounding_guard = grounding_guard or StrictGroundingGuard()
        self.session_id = f"session-live-{id(self)}"
        self.is_connected = False
        self.is_speaking = False
        self.is_interrupted = False
        self.audio_frames_received: List[bytes] = []
        self.messages_sent: List[Dict[str, Any]] = []
        self.audio_frames_sent: List[bytes] = []
        self.turn_counter = 0

    async def handshake(self) -> Dict[str, Any]:
        """Performs initial BidiGenerateContent handshake."""
        self.is_connected = True
        ready_event = {
            "type": "ready",
            "session_id": self.session_id,
            "model": MODEL_NAME,
            "course": self.course
        }
        self.messages_sent.append(ready_event)
        return ready_event

    async def receive_client_audio_frame(self, pcm_chunk: bytes) -> Optional[Dict[str, Any]]:
        """Processes client Int16 16kHz PCM audio chunk."""
        if not self.is_connected:
            raise RuntimeError("Cannot receive audio on disconnected session")

        # Boundary checks
        if len(pcm_chunk) == 0:
            return {"type": "warning", "message": "Received empty audio frame"}
        if len(pcm_chunk) % 2 != 0:
            return {"type": "error", "message": "Corrupted PCM frame: odd byte length violates Int16 alignment"}

        self.audio_frames_received.append(pcm_chunk)
        return None

    async def handle_client_barge_in(self) -> Dict[str, Any]:
        """Handles client VAD barge-in notification."""
        self.is_interrupted = True
        self.is_speaking = False
        # Instantly flush pending audio buffer
        self.audio_frames_sent.clear()
        interrupted_event = {"type": "interrupted"}
        self.messages_sent.append(interrupted_event)
        return interrupted_event

    def start_new_turn(self) -> None:
        """Resets interruption state when a new user turn begins."""
        self.is_interrupted = False

    async def execute_grounding(self, query_text: str) -> Dict[str, Any]:
        """Executes non-blocking query_academic_kb tool."""
        res = self.grounding_guard.query(query_text, course=self.course)
        grounding_event = {
            "type": "grounding",
            "query": query_text,
            "k": res["k"],
            "found": res["found"],
            "citations": res["citations"],
            "message": res.get("message", "")
        }
        self.messages_sent.append(grounding_event)
        return grounding_event

    async def emit_model_turn(
        self,
        transcript_text: str,
        grounding_query: Optional[str] = None,
        chunk_count: int = 4
    ) -> AsyncGenerator[Tuple[str, Any], None]:
        """
        Simulates model speaking turn:
        Yields ('transcript', dict), ('grounding', dict), ('audio', bytes)... ('turn_complete', dict).
        Respects immediate interruption if barge-in occurs.
        """
        self.is_speaking = True
        self.turn_counter += 1

        if self.is_interrupted:
            self.is_speaking = False
            return

        # 1. Grounding if requested
        if grounding_query:
            g_event = await self.execute_grounding(grounding_query)
            yield ("json", g_event)

        if self.is_interrupted:
            self.is_speaking = False
            return

        # 2. User transcript acknowledgment & model transcript
        t_event = {
            "type": "transcript",
            "role": "model",
            "text": transcript_text,
            "is_final": True
        }
        self.messages_sent.append(t_event)
        yield ("json", t_event)

        # 3. Stream 24kHz audio chunks
        for idx in range(chunk_count):
            if self.is_interrupted:
                break
            audio_chunk = generate_pcm_24k(duration_ms=50, frequency=280.0 + (idx * 20))
            self.audio_frames_sent.append(audio_chunk)
            yield ("audio", audio_chunk)
            await asyncio.sleep(0.001)

        # 4. Turn complete if not interrupted
        self.is_speaking = False
        if not self.is_interrupted:
            tc_event = {"type": "turn_complete"}
            self.messages_sent.append(tc_event)
            yield ("json", tc_event)

    async def close(self, code: int = 1000) -> None:
        """Closes session gracefully."""
        self.is_connected = False
        self.is_speaking = False
