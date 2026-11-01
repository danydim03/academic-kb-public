"""
Academic KB Voice Studio — Gemini Live API Bidirectional Bridge Service.
Manages full-duplex WebSocket streaming between browser clients and Gemini Live API
(supporting google-genai SDK, raw WebSockets, and mock mode for offline testing).
Strictly adheres to specifications in ORIGINAL_REQUEST.md and PROJECT.md.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import os
import struct
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("academic_kb.voice.bridge")

# ------------------------------------------------------------------------------
# Audio Protocol Constants
# ------------------------------------------------------------------------------

CLIENT_SAMPLE_RATE = 16000      # 16kHz Int16 mono PCM
CLIENT_CHUNK_SAMPLES = 1024     # 1024 samples = 64ms frame
CLIENT_FRAME_BYTES = 2048       # 1024 samples * 2 bytes/sample

SERVER_SAMPLE_RATE = 24000      # 24kHz Int16 mono PCM
SERVER_CHUNK_SAMPLES = 1200     # 1200 samples = 50ms frame
SERVER_FRAME_BYTES = 2400       # 1200 samples * 2 bytes/sample

DEFAULT_LIVE_MODEL = "gemini-3.8-live"
DEFAULT_LIVE_VOICE = "Charon"  # Male voice (calm, authoritative, professional academic tone)


# ------------------------------------------------------------------------------
# Normalized Live Events
# ------------------------------------------------------------------------------

@dataclass
class LiveAudioEvent:
    """Raw 24,000Hz 16-bit mono Little-Endian PCM audio chunk from Gemini Live."""
    data: bytes


@dataclass
class LiveTranscriptEvent:
    """Transcription event for user or model speech."""
    role: str  # "user" | "model"
    text: str
    is_final: bool = False


@dataclass
class LiveInterruptedEvent:
    """Barge-in signal indicating user speech interrupted model playback."""
    pass


@dataclass
class LiveTurnCompleteEvent:
    """Signal indicating model completed speaking current conversational turn."""
    pass


@dataclass
class LiveToolCallEvent:
    """Non-blocking function call request issued by the model."""
    call_id: str
    name: str
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LiveToolCancellationEvent:
    """Cancellation notification for ongoing tool execution calls."""
    call_ids: List[str] = field(default_factory=list)


@dataclass
class LiveErrorEvent:
    """Error event occurring during live session processing."""
    message: str
    fatal: bool = False


LiveEvent = Union[
    LiveAudioEvent,
    LiveTranscriptEvent,
    LiveInterruptedEvent,
    LiveTurnCompleteEvent,
    LiveToolCallEvent,
    LiveToolCancellationEvent,
    LiveErrorEvent,
]


# ------------------------------------------------------------------------------
# System Instructions for Strict Grounding
# ------------------------------------------------------------------------------

DEFAULT_LIVE_SYSTEM_INSTRUCTION = """
Sei DIMEOGPT Voice Assistant, l'assistente vocale accademico di livello magistrale (Tor Vergata) integrato in DIMEOGPT Study Studio.
Comunichi a voce in lingua italiana in modo naturale, didattico, approfondito e autorevole.

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

from engine.voice.grounding import GROUNDING_TOOL_SCHEMA

QUERY_ACADEMIC_KB_TOOL_SCHEMA: Dict[str, Any] = GROUNDING_TOOL_SCHEMA


# ------------------------------------------------------------------------------
# Session Configuration
# ------------------------------------------------------------------------------

@dataclass
class VoiceBridgeConfig:
    """Configuration container for Gemini Live voice bridge session."""
    model: str = DEFAULT_LIVE_MODEL
    voice_name: str = DEFAULT_LIVE_VOICE  # Aoede, Puck, Charon, Fenrir, Kore
    api_key: Optional[str] = None
    system_instruction: str = DEFAULT_LIVE_SYSTEM_INSTRUCTION
    input_sample_rate: int = CLIENT_SAMPLE_RATE
    output_sample_rate: int = SERVER_SAMPLE_RATE
    tools: List[Dict[str, Any]] = field(default_factory=lambda: [QUERY_ACADEMIC_KB_TOOL_SCHEMA])
    mock_mode: bool = False


# ------------------------------------------------------------------------------
# Safe WebSocket Sender (Concurrency Protection)
# ------------------------------------------------------------------------------

class SafeWebSocketSender:
    """
    Thread-safe and task-safe wrapper around FastAPI WebSocket sends.
    Serializes outbound binary and JSON frames via an asyncio.Lock to avoid
    concurrent ASGI frame collisions between downstream audio, transcripts, and pings.
    """

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self._lock = asyncio.Lock()

    async def send_bytes(self, data: bytes) -> None:
        async with self._lock:
            state = getattr(self.ws, "client_state", None)
            if state and getattr(state, "name", "") != "CONNECTED":
                return
            try:
                await self.ws.send_bytes(data)
            except Exception as e:
                logger.debug(f"Error sending bytes over WebSocket: {e}")

    async def send_json(self, data: Dict[str, Any]) -> None:
        async with self._lock:
            state = getattr(self.ws, "client_state", None)
            if state and getattr(state, "name", "") != "CONNECTED":
                return
            try:
                await self.ws.send_json(data)
            except Exception as e:
                logger.debug(f"Error sending JSON over WebSocket: {e}")


# ------------------------------------------------------------------------------
# Abstract Live Session Driver
# ------------------------------------------------------------------------------

class LiveSessionDriver(ABC):
    """Abstract interface decoupling bridge logic from specific transport/SDK."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish bidirectional session with Gemini Live API."""
        pass

    @abstractmethod
    async def send_audio(self, pcm_bytes: bytes) -> None:
        """Send 16kHz Int16 mono PCM chunk to Gemini Live."""
        pass

    @abstractmethod
    async def send_text(self, text: str) -> None:
        """Send text input frame."""
        pass

    @abstractmethod
    async def send_audio_stream_end(self) -> None:
        """Send Hybrid VAD turn end signal."""
        pass

    @abstractmethod
    async def send_tool_response(self, call_id: str, name: str, response: Dict[str, Any]) -> None:
        """Send tool execution response back to Gemini Live."""
        pass

    @abstractmethod
    async def receive_events(self) -> AsyncIterator[LiveEvent]:
        """Stream normalized server events."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close live connection and release resources."""
        pass


# ------------------------------------------------------------------------------
# Driver 1: Google GenAI SDK (Primary Production Driver)
# ------------------------------------------------------------------------------

class GenAILiveDriver(LiveSessionDriver):
    """Production driver utilizing official `google-genai` SDK."""

    def __init__(self, config: VoiceBridgeConfig):
        self.config = config
        self._client: Any = None
        self._session_ctx: Any = None
        self._session: Any = None
        self._connected: bool = False

    async def connect(self) -> None:
        try:
            from google import genai
            from google.genai import types
        except ImportError as e:
            raise RuntimeError("google-genai is not installed in the environment") from e

        if not self.config.api_key:
            raise ValueError("GEMINI_API_KEY must be provided for GenAILiveDriver")

        self._client = genai.Client(api_key=self.config.api_key)

        # Convert tool schemas into types.Tool with FunctionDeclaration
        func_declarations = []
        for t in self.config.tools:
            decl = types.FunctionDeclaration(
                name=t["name"],
                description=t.get("description", ""),
                parameters=t.get("parameters"),
                behavior="BLOCKING",
            )
            func_declarations.append(decl)

        connect_config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            system_instruction=types.Content(
                parts=[types.Part(text=self.config.system_instruction)]
            ),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=self.config.voice_name
                    )
                )
            ),
            tools=[types.Tool(function_declarations=func_declarations)],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )

        model_name = self.config.model
        self._session_ctx = self._client.aio.live.connect(
            model=model_name, config=connect_config
        )
        self._session = await self._session_ctx.__aenter__()
        self._connected = True
        logger.info(f"Connected to Gemini Live API via google-genai ({model_name})")

    async def send_audio(self, pcm_bytes: bytes) -> None:
        if not self._session or not self._connected:
            return
        from google.genai import types
        await self._session.send_realtime_input(
            audio=types.Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000")
        )

    async def send_text(self, text: str) -> None:
        if not self._session or not self._connected:
            return
        from google.genai import types
        try:
            # Use turn-based client_content with turn_complete=True so Gemini Live responds immediately with audio & transcript
            await self._session.send_client_content(
                turns=[types.Content(role="user", parts=[types.Part.from_text(text=text)])],
                turn_complete=True
            )
        except Exception as e:
            logger.warning(f"send_client_content fallback to realtime input: {e}")
            await self._session.send_realtime_input(text=text)
            await self._session.send_realtime_input(audio_stream_end=True)

    async def send_audio_stream_end(self) -> None:
        if not self._session or not self._connected:
            return
        await self._session.send_realtime_input(audio_stream_end=True)

    async def send_tool_response(self, call_id: str, name: str, response: Dict[str, Any]) -> None:
        if not self._session or not self._connected:
            return
        from google.genai import types
        func_resp = types.FunctionResponse(id=call_id, name=name, response=response)
        await self._session.send_tool_response(function_responses=[func_resp])

    async def receive_events(self) -> AsyncIterator[LiveEvent]:
        while self._connected and self._session:
            try:
                async for response in self._session.receive():
                    if not self._connected:
                        break
                    server_content = getattr(response, "server_content", None)
                    if server_content:
                        # 1. Interruption (Server Barge-In)
                        if getattr(server_content, "interrupted", False):
                            yield LiveInterruptedEvent()

                        # 2. Spoken Audio Chunks
                        model_turn = getattr(server_content, "model_turn", None)
                        if model_turn and getattr(model_turn, "parts", None):
                            for part in model_turn.parts:
                                inline_data = getattr(part, "inline_data", None)
                                if inline_data and getattr(inline_data, "data", None):
                                    audio_data = inline_data.data
                                    if isinstance(audio_data, str):
                                        audio_data = base64.b64decode(audio_data)
                                    yield LiveAudioEvent(data=audio_data)

                        # 3. Transcriptions
                        in_tx = getattr(server_content, "input_transcription", None)
                        if in_tx and getattr(in_tx, "text", None):
                            yield LiveTranscriptEvent(role="user", text=in_tx.text, is_final=True)

                        out_tx = getattr(server_content, "output_transcription", None)
                        if out_tx and getattr(out_tx, "text", None):
                            yield LiveTranscriptEvent(role="model", text=out_tx.text, is_final=False)

                        # 4. Turn Complete
                        if getattr(server_content, "turn_complete", False):
                            yield LiveTurnCompleteEvent()

                    # 5. Non-blocking Tool Call Request
                    tool_call = getattr(response, "tool_call", None)
                    if tool_call and getattr(tool_call, "function_calls", None):
                        for call in tool_call.function_calls:
                            yield LiveToolCallEvent(
                                call_id=getattr(call, "id", "") or str(uuid.uuid4()),
                                name=getattr(call, "name", ""),
                                args=getattr(call, "args", {}) or {}
                            )

                    # 6. Tool Call Cancellation
                    cancellation = getattr(response, "tool_call_cancellation", None)
                    if cancellation and getattr(cancellation, "ids", None):
                        yield LiveToolCancellationEvent(call_ids=list(cancellation.ids))
            except Exception as e:
                if not self._connected:
                    break
                logger.debug(f"Live session turn receive ended: {e}")
                await asyncio.sleep(0.05)

    async def close(self) -> None:
        self._connected = False
        if self._session_ctx:
            try:
                await self._session_ctx.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing GenAILiveDriver session: {e}")
            finally:
                self._session = None
                self._session_ctx = None


# ------------------------------------------------------------------------------
# Driver 2: Raw WebSocket Live Driver (Direct Transport Fallback)
# ------------------------------------------------------------------------------

class RawWebSocketLiveDriver(LiveSessionDriver):
    """Direct WebSocket client driver (bypasses SDK overhead via standard websockets)."""

    def __init__(self, config: VoiceBridgeConfig):
        self.config = config
        self._ws: Any = None
        self._connected: bool = False

    async def connect(self) -> None:
        try:
            import websockets
        except ImportError as e:
            raise RuntimeError("websockets is not installed in the environment") from e

        if not self.config.api_key:
            raise ValueError("GEMINI_API_KEY must be provided for RawWebSocketLiveDriver")

        url = (
            f"wss://generativelanguage.googleapis.com/ws/"
            f"google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
            f"?key={self.config.api_key}"
        )

        model_name = self.config.model
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"

        setup_msg = {
            "setup": {
                "model": model_name,
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": self.config.voice_name
                            }
                        }
                    }
                },
                "systemInstruction": {
                    "parts": [{"text": self.config.system_instruction}]
                },
                "tools": [{"functionDeclarations": self.config.tools}],
                "contextWindowCompression": {
                    "slidingWindow": {"targetTokens": 12000},
                    "triggerTokens": 25000
                },
                "sessionResumption": {}
            }
        }

        self._ws = await websockets.connect(url, max_size=10 * 1024 * 1024)
        await self._ws.send(json.dumps(setup_msg))
        ack_raw = await self._ws.recv()
        ack = json.loads(ack_raw)
        if "setupComplete" not in ack:
            raise RuntimeError(f"Unexpected handshake response: {ack}")

        self._connected = True
        logger.info(f"Connected to Gemini Live API via raw WebSocket ({model_name})")

    async def send_audio(self, pcm_bytes: bytes) -> None:
        if not self._ws or not self._connected:
            return
        b64_audio = base64.b64encode(pcm_bytes).decode("ascii")
        msg = {
            "realtimeInput": {
                "audio": {
                    "mimeType": "audio/pcm;rate=16000",
                    "data": b64_audio
                }
            }
        }
        await self._ws.send(json.dumps(msg))

    async def send_text(self, text: str) -> None:
        if not self._ws or not self._connected:
            return
        msg = {
            "clientContent": {
                "turns": [
                    {
                        "role": "user",
                        "parts": [{"text": text}]
                    }
                ],
                "turnComplete": True
            }
        }
        await self._ws.send(json.dumps(msg))

    async def send_audio_stream_end(self) -> None:
        if not self._ws or not self._connected:
            return
        msg = {"realtimeInput": {"audioStreamEnd": True}}
        await self._ws.send(json.dumps(msg))

    async def send_tool_response(self, call_id: str, name: str, response: Dict[str, Any]) -> None:
        if not self._ws or not self._connected:
            return
        msg = {
            "toolResponse": {
                "functionResponses": [
                    {"id": call_id, "name": name, "response": response}
                ]
            }
        }
        await self._ws.send(json.dumps(msg))

    async def receive_events(self) -> AsyncIterator[LiveEvent]:
        if not self._ws or not self._connected:
            return

        async for raw_msg in self._ws:
            try:
                payload = json.loads(raw_msg)
            except Exception:
                continue

            server_content = payload.get("serverContent")
            if server_content:
                if server_content.get("interrupted"):
                    yield LiveInterruptedEvent()

                model_turn = server_content.get("modelTurn")
                if model_turn:
                    for part in model_turn.get("parts", []):
                        inline = part.get("inlineData")
                        if inline and inline.get("data"):
                            raw_pcm = base64.b64decode(inline["data"])
                            yield LiveAudioEvent(data=raw_pcm)

                in_tx = server_content.get("inputTranscription")
                if in_tx and in_tx.get("text"):
                    yield LiveTranscriptEvent(role="user", text=in_tx["text"], is_final=True)

                out_tx = server_content.get("outputTranscription")
                if out_tx and out_tx.get("text"):
                    yield LiveTranscriptEvent(role="model", text=out_tx["text"], is_final=False)

                if server_content.get("turnComplete"):
                    yield LiveTurnCompleteEvent()

            tool_call = payload.get("toolCall")
            if tool_call:
                for fn in tool_call.get("functionCalls", []):
                    yield LiveToolCallEvent(
                        call_id=fn.get("id", "") or str(uuid.uuid4()),
                        name=fn.get("name", ""),
                        args=fn.get("args", {}) or {}
                    )

            tool_cancellation = payload.get("toolCallCancellation")
            if tool_cancellation:
                yield LiveToolCancellationEvent(call_ids=tool_cancellation.get("ids", []))

    async def close(self) -> None:
        self._connected = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception as e:
                logger.warning(f"Error closing RawWebSocketLiveDriver: {e}")
            finally:
                self._ws = None


# ------------------------------------------------------------------------------
# Driver 3: Mock Live Driver (Offline Testing & CI/CD)
# ------------------------------------------------------------------------------

class MockLiveDriver(LiveSessionDriver):
    """
    Synthetic test driver for offline validation, unit testing, and CI/CD without API keys.
    Generates deterministic 24kHz Int16 mono PCM audio and validates tool interactions.
    """

    def __init__(self, config: VoiceBridgeConfig, course: str = "CNS"):
        self.config = config
        self.course = course
        self.is_connected = False
        self.is_speaking = False
        self.is_interrupted = False
        self.audio_frames_received: List[bytes] = []
        self._event_queue: asyncio.Queue[LiveEvent] = asyncio.Queue()

    async def connect(self) -> None:
        self.is_connected = True
        logger.info(f"Initialized MockLiveDriver in test mode (model={self.config.model})")

    async def send_audio(self, pcm_bytes: bytes) -> None:
        if not self.is_connected:
            raise RuntimeError("Cannot send audio on disconnected session")
        self.audio_frames_received.append(pcm_bytes)

    async def send_text(self, text: Any) -> None:
        if not self.is_connected:
            raise RuntimeError("Cannot send text on disconnected session")

        # Coerce text to string safely and ignore empty inputs
        text_str = str(text).strip() if text is not None else ""
        if not text_str:
            return

        self.is_interrupted = False

        # 1. User transcript
        await self._event_queue.put(LiveTranscriptEvent(role="user", text=text_str, is_final=True))

        # 2. Check if text looks like an academic query requiring grounding
        q_lower = text_str.lower()
        academic_keywords = ["tls", "wep", "svm", "cns", "sdcc", "ml", "rete", "sicurezza", "vulnerab", "handshake"]
        needs_grounding = any(k in q_lower for k in academic_keywords)

        if needs_grounding and self.config.tools:
            # Emit tool call
            call_id = f"mock-call-{uuid.uuid4().hex[:8]}"
            await self._event_queue.put(
                LiveToolCallEvent(
                    call_id=call_id,
                    name="query_academic_kb",
                    args={"query": text_str, "course": self.course}
                )
            )
        else:
            # Emit direct mock answer
            await self._emit_mock_answer(f"Risposta mock per: {text_str}. [Documento_Studio.pdf, p. 1]")

    async def send_audio_stream_end(self) -> None:
        if not self.is_connected:
            return
        if self.audio_frames_received:
            # Audio was sent, synthesize answer
            self.is_interrupted = False
            await self.send_text("Riassunto domanda vocale.")

    def start_new_turn(self) -> None:
        """Resets interruption flag for a new conversational turn."""
        self.is_interrupted = False

    async def send_tool_response(self, call_id: str, name: str, response: Dict[str, Any]) -> None:
        if not self.is_connected:
            return

        # GUARD: Discard tool responses for interrupted turns
        if self.is_interrupted:
            logger.info(f"Ignoring tool response for {call_id} because driver was interrupted.")
            return

        if response.get("found"):
            summary = "In base ai documenti del corso, le specifiche tecniche confermano l'argomento richiesto."
        else:
            summary = "Ho verificato nel Knowledge Graph accademico, ma questo argomento non è trattato nei materiali indicizzati del corso."

        await self._emit_mock_answer(summary)

    async def handle_barge_in(self) -> None:
        """Simulate barge-in event from client VAD."""
        self.is_interrupted = True
        self.is_speaking = False
        # Purge pending audio frames and events from queue
        while not self._event_queue.empty():
            try:
                self._event_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        # NOTE: Do NOT enqueue LiveInterruptedEvent here.
        # upstream_loop already sent {"type": "interrupted"} directly to the client.
        # Enqueueing it here causes downstream_loop to emit a duplicate frame.

    async def _emit_mock_answer(self, text: str) -> None:
        # GUARD: Do not speak if interrupted
        if self.is_interrupted:
            logger.info("Ignoring mock answer emission because driver is interrupted.")
            return

        self.is_speaking = True
        # NOTE: Do NOT reset self.is_interrupted = False here!
        # Interruption flag is only cleared when new user input starts a new turn.

        # Model transcript
        await self._event_queue.put(LiveTranscriptEvent(role="model", text=text, is_final=True))

        # Emit 3 chunks of 24kHz synthetic Int16 PCM (1200 samples = 2400 bytes each)
        for i in range(3):
            if self.is_interrupted:
                break
            chunk = self._generate_synthetic_pcm_24k(duration_ms=50, frequency=300.0 + (i * 20))
            await self._event_queue.put(LiveAudioEvent(data=chunk))

        self.is_speaking = False
        # Suppress turn_complete if interrupted mid-speech
        if not self.is_interrupted:
            await self._event_queue.put(LiveTurnCompleteEvent())

    @staticmethod
    def _generate_synthetic_pcm_24k(duration_ms: int = 50, frequency: float = 300.0) -> bytes:
        """Generates 24kHz Int16 PCM mono audio bytes."""
        num_samples = int(SERVER_SAMPLE_RATE * (duration_ms / 1000.0))
        buffer = bytearray(num_samples * 2)
        max_int16 = 32767
        amplitude = 0.5
        for i in range(num_samples):
            t = float(i) / SERVER_SAMPLE_RATE
            val = int(amplitude * max_int16 * math.sin(2.0 * math.pi * frequency * t))
            val = max(-32768, min(32767, val))
            struct.pack_into("<h", buffer, i * 2, val)
        return bytes(buffer)

    async def receive_events(self) -> AsyncIterator[LiveEvent]:
        while self.is_connected:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=0.2)
                yield event
            except asyncio.TimeoutError:
                continue

    async def close(self) -> None:
        self.is_connected = False
        self.is_speaking = False


# ------------------------------------------------------------------------------
# Gemini Live Bridge Coordinator
# ------------------------------------------------------------------------------

class GeminiLiveBridge:
    """
    Session orchestrator bridging a browser client WebSocket with the Gemini Live API.
    Manages upstream/downstream concurrent loops, task cancellation on barge-in,
    asynchronous non-blocking tool calling, and clean connection teardown.
    """

    def __init__(
        self,
        config: VoiceBridgeConfig,
        tool_handler: Optional[Callable[[str, Dict[str, Any], Optional[str]], Coroutine[Any, Any, Tuple[Dict[str, Any], List[Dict[str, Any]]]]]] = None,
        driver_override: Optional[LiveSessionDriver] = None,
    ):
        self.config = config
        self.tool_handler = tool_handler
        self.driver_override = driver_override

        self.session_id: str = str(uuid.uuid4())
        self.active_tool_tasks: Dict[str, asyncio.Task] = {}
        self._closing: bool = False
        self._active_driver: Optional[LiveSessionDriver] = None
        self._is_interrupted: bool = False
        self._last_interrupt_time: float = 0.0

    def _cancel_active_tools(self) -> int:
        """
        Immediately cancels all in-flight background tool tasks.
        Returns the number of cancelled tasks.
        """
        cancelled_count = 0
        for call_id, task in list(self.active_tool_tasks.items()):
            if not task.done():
                task.cancel()
                cancelled_count += 1
        self.active_tool_tasks.clear()
        if cancelled_count > 0:
            logger.info(f"Cancelled {cancelled_count} active tool task(s) on barge-in.")
        return cancelled_count

    def _create_driver(self, course: Optional[str] = None) -> LiveSessionDriver:
        if self.driver_override:
            return self.driver_override

        if self.config.mock_mode or not self.config.api_key:
            logger.info("Using MockLiveDriver (offline or missing GEMINI_API_KEY).")
            return MockLiveDriver(self.config, course=course or "CNS")

        # Attempt google-genai SDK first, fallback to raw WebSocket
        try:
            import google.genai
            return GenAILiveDriver(self.config)
        except ImportError:
            logger.warning("google-genai SDK not found; falling back to RawWebSocketLiveDriver.")
            return RawWebSocketLiveDriver(self.config)

    async def run(
        self,
        client_ws: WebSocket,
        course: Optional[str] = None,
        sender: Optional[SafeWebSocketSender] = None
    ) -> None:
        """
        Executes the bidirectional streaming lifecycle for client_ws.
        Runs concurrent upstream and downstream loops with structured cleanup.
        """
        safe_sender = sender or SafeWebSocketSender(client_ws)
        driver = self._create_driver(course=course)
        self._active_driver = driver

        try:
            await driver.connect()
        except Exception as e:
            logger.error(f"Failed to connect upstream Live driver: {e}", exc_info=True)
            await safe_sender.send_json({
                "type": "error",
                "message": f"Impossibile connettersi a Gemini Live API: {e}"
            })
            return

        # 1. Notify browser client of readiness
        await safe_sender.send_json({
            "type": "ready",
            "session_id": self.session_id,
            "model": self.config.model,
            "voice": self.config.voice_name,
            "course": course or "CNS",
        })

        # ----------------------------------------------------------------------
        # Concurrency Task A: Upstream Loop (Browser -> Gemini Live)
        # ----------------------------------------------------------------------
        async def upstream_loop():
            while not self._closing:
                try:
                    msg = await client_ws.receive()
                except WebSocketDisconnect:
                    logger.info("Browser disconnected in upstream loop.")
                    break
                except Exception as e:
                    logger.debug(f"Upstream receive error: {e}")
                    break

                # Disconnect frame from Starlette
                if msg.get("type") == "websocket.disconnect":
                    logger.info("WebSocket disconnect frame received.")
                    break

                # 1. Binary frames (Native 16kHz Int16 PCM mono)
                if msg.get("bytes"):
                    self._is_interrupted = False
                    raw_bytes = msg["bytes"]
                    if len(raw_bytes) > 0 and len(raw_bytes) % 2 == 0:
                        await driver.send_audio(raw_bytes)
                    elif len(raw_bytes) % 2 != 0:
                        logger.warning(f"Received odd byte length PCM audio: {len(raw_bytes)}")

                # 2. Text frames (JSON control / base64 audio / barge-in)
                elif msg.get("text"):
                    try:
                        data = json.loads(msg["text"])
                    except json.JSONDecodeError:
                        logger.warning("Received invalid JSON text frame.")
                        continue

                    # Guard against non-dict JSON payloads (list, int, str, bool, None)
                    if not isinstance(data, dict):
                        logger.warning(f"Received non-dict JSON frame: {type(data).__name__}")
                        continue

                    msg_type = data.get("type")
                    if not isinstance(msg_type, str):
                        logger.warning(f"Received JSON frame with invalid type field: {type(msg_type).__name__}")
                        continue

                    if msg_type == "audio" and data.get("data"):
                        try:
                            pcm_bytes = base64.b64decode(data["data"])
                            if len(pcm_bytes) > 0 and len(pcm_bytes) % 2 == 0:
                                await driver.send_audio(pcm_bytes)
                        except Exception as e:
                            logger.warning(f"Failed to decode base64 audio: {e}")

                    elif msg_type == "client_barge_in":
                        logger.info("Client-side VAD barge-in received.")
                        # 1. Cancel all active background tool tasks immediately
                        self._cancel_active_tools()

                        # 2. Update interruption state and record timestamp
                        now = asyncio.get_event_loop().time()
                        self._is_interrupted = True
                        self._last_interrupt_time = now

                        # 3. Send single notification to browser client
                        await safe_sender.send_json({"type": "interrupted"})

                        # 4. Notify driver to halt speech and flush internal queues
                        if hasattr(driver, "handle_barge_in"):
                            await driver.handle_barge_in()

                    elif msg_type == "audio_stream_end":
                        await driver.send_audio_stream_end()

                    elif msg_type == "text_input":
                        text_val = str(data.get("text", "")).strip() if data.get("text") is not None else ""
                        if text_val:
                            self._is_interrupted = False
                            await driver.send_text(text_val)

                    elif msg_type == "ping":
                        await safe_sender.send_json({"type": "pong"})

        # ----------------------------------------------------------------------
        # Concurrency Task B: Downstream Loop (Gemini Live -> Browser)
        # ----------------------------------------------------------------------
        async def downstream_loop():
            try:
                async for event in driver.receive_events():
                    if self._closing:
                        break

                    # 1. Audio event -> Dispatch as binary frame (24kHz Int16 PCM)
                    if isinstance(event, LiveAudioEvent):
                        await safe_sender.send_bytes(event.data)

                    # 2. Interruption event (Server-side VAD Barge-in)
                    elif isinstance(event, LiveInterruptedEvent):
                        logger.info("Server barge-in (interrupted: true) received.")
                        # 1. Cancel all active background tool tasks immediately
                        self._cancel_active_tools()

                        # 2. Deduplicate: if client_barge_in already dispatched 'interrupted' recently (<0.5s), suppress duplicate
                        now = asyncio.get_event_loop().time()
                        if not (self._is_interrupted and (now - self._last_interrupt_time) < 0.5):
                            self._is_interrupted = True
                            self._last_interrupt_time = now
                            await safe_sender.send_json({"type": "interrupted"})
                        else:
                            logger.debug("Suppressed duplicate server interrupted event (client barge-in already dispatched).")

                    # 3. Transcripts (User and Model)
                    elif isinstance(event, LiveTranscriptEvent):
                        await safe_sender.send_json({
                            "type": "transcript",
                            "role": event.role,
                            "text": event.text,
                            "is_final": event.is_final
                        })

                    # 4. Turn Complete
                    elif isinstance(event, LiveTurnCompleteEvent):
                        # Suppress premature turn_complete if background tool computation is in-flight
                        if not self.active_tool_tasks:
                            await safe_sender.send_json({"type": "turn_complete"})

                    # 5. Non-blocking Tool Call Execution
                    elif isinstance(event, LiveToolCallEvent):
                        self._dispatch_tool_call(event, driver, safe_sender, course)

                    # 6. Tool Call Cancellation
                    elif isinstance(event, LiveToolCancellationEvent):
                        for cid in event.call_ids:
                            task = self.active_tool_tasks.pop(cid, None)
                            if task and not task.done():
                                task.cancel()

                    # 7. Error Event
                    elif isinstance(event, LiveErrorEvent):
                        await safe_sender.send_json({
                            "type": "error",
                            "message": event.message
                        })
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Downstream loop error: {e}", exc_info=True)

        # Run upstream and downstream concurrently
        upstream_task = asyncio.create_task(upstream_loop(), name="live_ws_upstream")
        downstream_task = asyncio.create_task(downstream_loop(), name="live_ws_downstream")

        done, pending = await asyncio.wait(
            [upstream_task, downstream_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        for p in pending:
            p.cancel()

        # Teardown & cleanup
        await self._cleanup(driver)

    def _dispatch_tool_call(
        self,
        event: LiveToolCallEvent,
        driver: LiveSessionDriver,
        sender: SafeWebSocketSender,
        course_filter: Optional[str]
    ) -> None:
        """Launches non-blocking tool execution in a background task."""
        call_id = event.call_id
        name = event.name
        args = event.args

        async def _tool_worker():
            try:
                # Notify browser that grounding retrieval is executing
                await sender.send_json({
                    "type": "tool_calling",
                    "tool": name,
                    "query": args.get("query", ""),
                    "course": args.get("course") or course_filter
                })

                if self.tool_handler:
                    effective_course = args.get("course") or course_filter
                    handler_result = await self.tool_handler(name, args, effective_course)
                    if isinstance(handler_result, tuple) and len(handler_result) == 2:
                        tool_resp, citations = handler_result
                    elif isinstance(handler_result, dict):
                        tool_resp = handler_result
                        citations = handler_result.get("citations", [])
                    else:
                        tool_resp = {"found": False, "message": "Risposta tool non valida."}
                        citations = []
                else:
                    tool_resp = {
                        "found": False,
                        "message": "Nessun gestore tool registrato."
                    }
                    citations = []

                # If session was interrupted while tool was computing, drop the results
                if self._is_interrupted:
                    logger.info(f"Discarding tool {name} results because session was interrupted.")
                    return

                # Return tool response to Gemini Live
                await driver.send_tool_response(call_id, name, tool_resp)

                # Deliver grounding citation metadata to browser client
                if not self._is_interrupted:
                    await sender.send_json({
                        "type": "grounding",
                        "query": args.get("query", ""),
                        "k": len(citations),
                        "found": bool(tool_resp.get("found", len(citations) > 0)),
                        "citations": citations,
                        "message": tool_resp.get("message", "")
                    })

            except asyncio.CancelledError:
                logger.info(f"Tool call {call_id} cancelled during execution.")
            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}", exc_info=True)
                try:
                    await driver.send_tool_response(call_id, name, {"error": str(e)})
                except Exception:
                    pass

        task = asyncio.create_task(_tool_worker(), name=f"live_tool_{call_id}")
        self.active_tool_tasks[call_id] = task
        task.add_done_callback(lambda t: self.active_tool_tasks.pop(call_id, None))

    async def _cleanup(self, driver: LiveSessionDriver) -> None:
        self._closing = True
        # Cancel any active tool tasks
        self._cancel_active_tools()

        # Close upstream driver
        await driver.close()
        logger.info(f"Closed Gemini Live Bridge session {self.session_id}")

    async def close(self) -> None:
        """Explicitly terminates the bridge session."""
        self._closing = True
        if self._active_driver:
            await self._cleanup(self._active_driver)
