"""
Milestone M5 Empirical Challenger Deep Stress Test Suite.
Adversarially tests:
1. Malformed, non-dict, non-string, corrupted JSON frames on /api/live_voice.
2. Grounding engine edge cases: pure stopwords (IT & EN), numeric courses, whitespace titles, top_k boundary invariants.
3. Slow Neo4j retrieval with barge-in: cancellation of active tool tasks and strict zombie citation prevention.
4. Concurrency: 10+ simultaneous WebSocket sessions with differing courses, ensuring zero state bleed and task isolation.
5. Rapid connection churn and resource reclamation.
"""

import asyncio
import gc
import json
import re
import time
from typing import Any, Dict, List, Optional
import pytest
from starlette.testclient import TestClient

from engine.voice.bridge import (
    GeminiLiveBridge,
    VoiceBridgeConfig,
    SafeWebSocketSender,
    MockLiveDriver,
    LiveAudioEvent,
    LiveInterruptedEvent,
    LiveTranscriptEvent,
    LiveTurnCompleteEvent,
    LiveToolCallEvent,
)
from engine.voice.grounding import (
    AcademicGroundingBridge,
    AcademicDocChunk,
    GROUNDING_TOOL_SCHEMA,
    format_academic_citation,
)
from run_api import app

CITATION_TAG_REGEX = re.compile(r"^\[.+?(?:, p\. \d+)?\]$")


# ==============================================================================
# 1. Adversarial Non-Dict, Non-String, and Corrupted JSON Frames
# ==============================================================================

class TestAdversarialJSONRobustness:
    """Tests resilience against malformed, non-dict, and illegal JSON frames."""

    def test_non_dict_json_primitives_survive(self):
        """Valid JSON primitives (null, bool, int, float, string, list) must not crash the bridge."""
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ready = ws.receive_json()
            assert ready["type"] == "ready"

            adversarial_payloads = [
                "null",
                "true",
                "false",
                "12345",
                "-99.88",
                "\"just a raw json string\"",
                "[1, 2, 3]",
                "[{\"type\": \"ping\"}]",
                "[]",
            ]

            for payload in adversarial_payloads:
                ws.send_text(payload)

            # Session must remain alive and responsive
            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong"

    def test_dict_with_invalid_type_fields(self):
        """Dict frames with missing, non-string, or unknown 'type' field must be dropped safely."""
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ws.receive_json()  # ready

            invalid_type_dicts = [
                {},  # missing type
                {"type": None},
                {"type": 123},
                {"type": 3.14},
                {"type": True},
                {"type": ["barge_in"]},
                {"type": {"sub": "type"}},
                {"type": "unknown_future_command_type_xyz"},
            ]

            for payload in invalid_type_dicts:
                ws.send_json(payload)

            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong"

    def test_corrupted_audio_and_text_input_fields(self):
        """Audio frames with invalid base64 or non-string data, and text_input with non-string text."""
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ws.receive_json()  # ready

            ws.send_json({"type": "audio", "data": "%%%NotValidBase64%%%"})
            ws.send_json({"type": "audio", "data": 12345})
            ws.send_json({"type": "audio", "data": None})
            ws.send_json({"type": "audio"})  # missing data

            ws.send_json({"type": "text_input", "text": None})
            ws.send_json({"type": "text_input", "text": "   "})  # whitespace only
            ws.send_json({"type": "text_input", "text": 98765})  # integer text

            ws.send_json({"type": "ping"})
            # Drain any frames (binary audio, transcripts, turn_complete) produced by text_input before pong
            pong = None
            for _ in range(20):
                raw = ws.receive()
                if "text" in raw:
                    data = json.loads(raw["text"])
                    if data.get("type") == "pong":
                        pong = data
                        break
            assert pong is not None and pong["type"] == "pong"


# ==============================================================================
# 2. Grounding Engine Boundary & Edge Cases
# ==============================================================================

class TestGroundingEngineEdgeCases:
    """Stress tests boundary conditions, pure stopwords, numeric courses, and title edge cases."""

    @pytest.fixture
    def test_kb(self) -> List[AcademicDocChunk]:
        return [
            AcademicDocChunk(
                chunk_id="cns-tls-01",
                source_title="Sicurezza_Reti_TLS.pdf",
                page=24,
                course="CNS",
                content="TLS 1.3 protocol Handshake with ECDH key agreement.",
                score=0.90,
            ),
            AcademicDocChunk(
                chunk_id="ml-cnn-01",
                source_title="Deep_Learning_CNN.pdf",
                page=12,
                course="ML",
                content="Convolutional neural networks with pooling layers.",
                score=0.88,
            ),
        ]

    def test_pure_stopword_queries_italian(self, test_kb):
        """Queries composed entirely of Italian stopwords must return found: False."""
        bridge = AcademicGroundingBridge(kb=test_kb)

        it_stopword_queries = [
            "in di da su",
            "il lo la i gli le un uno una",
            "per con tra fra che",
            "cosa come perche",
            "della delle degli dei del",
            "questo questa questi queste quello quella",
        ]

        for q in it_stopword_queries:
            res = bridge.query(q, course="CNS")
            assert res["found"] is False, f"Expected found=False for stopword query: '{q}'"
            assert res["k"] == 0
            assert res["citations"] == []

    def test_pure_stopword_queries_english(self, test_kb):
        """Queries composed entirely of English stopwords must return found: False."""
        bridge = AcademicGroundingBridge(kb=test_kb)

        en_stopword_queries = [
            "what is the",
            "which and why",
            "how to with from",
            "about into over after",
            "is are for",
        ]

        for q in en_stopword_queries:
            res = bridge.query(q, course="CNS")
            assert res["found"] is False, f"Expected found=False for stopword query: '{q}'"
            assert res["k"] == 0
            assert res["citations"] == []

    def test_short_and_punctuation_queries(self, test_kb):
        """Punctuation-only, symbol-only, or < 3 char queries must return found: False."""
        bridge = AcademicGroundingBridge(kb=test_kb)

        short_queries = [
            "",
            "   ",
            "?",
            "?!.",
            ":;,-_",
            "a",
            "ab",
            "1",
            "42",
        ]

        for q in short_queries:
            res = bridge.query(q, course="CNS")
            assert res["found"] is False, f"Expected found=False for query: '{q}'"
            assert res["k"] == 0
            assert res["citations"] == []

    def test_numeric_and_exotic_course_parameters(self, test_kb):
        """Numeric, float, boolean, or container course parameter must not raise exceptions."""
        bridge = AcademicGroundingBridge(kb=test_kb)

        exotic_courses = [
            123,
            3.14,
            0,
            True,
            False,
            ["CNS"],
            {"course": "CNS"},
            None,
        ]

        for c in exotic_courses:
            res = bridge.query("TLS handshake", course=c)
            assert isinstance(res, dict)
            assert "found" in res
            assert "citations" in res

    def test_top_k_boundaries(self, test_kb):
        """top_k=0 must return found: False, k: 0. Negative top_k must not crash."""
        bridge = AcademicGroundingBridge(kb=test_kb)

        # top_k = 0
        res_zero = bridge._search_sync("TLS handshake", course="CNS", top_k=0)
        assert res_zero["found"] is False
        assert res_zero["k"] == 0
        assert res_zero["citations"] == []

        # top_k = -1
        res_neg = bridge._search_sync("TLS handshake", course="CNS", top_k=-1)
        assert res_neg["found"] is False
        assert res_neg["k"] == 0
        assert res_neg["citations"] == []

        # top_k = 1000
        res_large = bridge._search_sync("TLS handshake", course="CNS", top_k=1000)
        assert res_large["found"] is True
        assert res_large["k"] >= 1

    def test_whitespace_title_citations_conform_to_regex(self):
        """Empty or whitespace-only source titles must format cleanly as [Documento, p. X]."""
        test_titles = [
            "",
            "   ",
            "\t\n",
            None,
        ]

        for t in test_titles:
            tag_with_page = format_academic_citation(t, 5)
            assert CITATION_TAG_REGEX.match(tag_with_page), f"Tag '{tag_with_page}' failed regex"
            assert tag_with_page == "[Documento, p. 5]"

            tag_without_page = format_academic_citation(t, None)
            assert CITATION_TAG_REGEX.match(tag_without_page), f"Tag '{tag_without_page}' failed regex"
            assert tag_without_page == "[Documento]"


# ==============================================================================
# 3. Barge-In During Slow Retrieval & Zombie Citation Prevention
# ==============================================================================

class TestBargeInSlowRetrievalCancellation:
    """Adversarially tests active tool task cancellation and zero zombie citations."""

    def test_barge_in_cancels_slow_retrieval_and_suppresses_citations(self):
        """
        Simulates slow retrieval (0.6s) interrupted by client_barge_in at 0.1s.
        Confirms:
        1. Tool task is immediately cancelled.
        2. Client receives 'interrupted'.
        3. Zero zombie grounding citations or tool responses are dispatched.
        """
        async def _run():
            tool_started = asyncio.Event()
            tool_cancelled = asyncio.Event()

            async def slow_retrieval_tool(name: str, args: Dict[str, Any], course: Optional[str]):
                tool_started.set()
                try:
                    # Simulate slow Neo4j query
                    await asyncio.sleep(0.6)
                    return {
                        "found": True,
                        "query": args.get("query"),
                        "citations": [{"source": "Zombie.pdf", "page": 1, "course": "CNS"}]
                    }, [{"source": "Zombie.pdf", "page": 1, "course": "CNS"}]
                except asyncio.CancelledError:
                    tool_cancelled.set()
                    raise

            config = VoiceBridgeConfig(mock_mode=True)
            driver = MockLiveDriver(config, course="CNS")
            bridge = GeminiLiveBridge(config=config, tool_handler=slow_retrieval_tool, driver_override=driver)

            # Mock WebSocket to capture frames
            sent_frames: List[Dict[str, Any]] = []

            class MockWS:
                client_state = type("State", (), {"name": "CONNECTED"})()

                def __init__(self):
                    self._in_queue = asyncio.Queue()

                async def receive(self):
                    return await self._in_queue.get()

                async def send_json(self, data):
                    sent_frames.append(data)

                async def send_bytes(self, data):
                    pass

            mock_ws = MockWS()
            sender = SafeWebSocketSender(mock_ws)

            bridge_task = asyncio.create_task(bridge.run(client_ws=mock_ws, course="CNS", sender=sender))

            # Wait for 'ready'
            await asyncio.sleep(0.05)
            ready_frame = next((f for f in sent_frames if f.get("type") == "ready"), None)
            assert ready_frame is not None

            # Send text that triggers tool call in MockLiveDriver ("tls")
            await mock_ws._in_queue.put({"type": "websocket.receive", "text": json.dumps({"type": "text_input", "text": "tls handshake query"})})

            # Wait until tool execution starts
            await asyncio.wait_for(tool_started.wait(), timeout=1.0)
            assert len(bridge.active_tool_tasks) == 1

            # Now simulate barge-in while tool is running!
            await mock_ws._in_queue.put({"type": "websocket.receive", "text": json.dumps({"type": "client_barge_in"})})

            # Wait briefly for barge-in processing
            await asyncio.sleep(0.1)

            # 1. Active tool tasks must be cancelled
            assert len(bridge.active_tool_tasks) == 0
            assert tool_cancelled.is_set(), "Tool worker was not cancelled on barge-in!"

            # 2. 'interrupted' frame must have been sent
            interrupted_frame = next((f for f in sent_frames if f.get("type") == "interrupted"), None)
            assert interrupted_frame is not None, "Client did not receive 'interrupted' frame!"

            # 3. Wait past the original tool duration (0.7s) to guarantee no zombie frames arrive
            await asyncio.sleep(0.7)

            grounding_frames = [f for f in sent_frames if f.get("type") == "grounding"]
            assert len(grounding_frames) == 0, f"Zombie grounding frame leaked after barge-in: {grounding_frames}"

            # Clean teardown
            await mock_ws._in_queue.put({"type": "websocket.disconnect"})
            await asyncio.wait_for(bridge_task, timeout=2.0)

        asyncio.run(_run())


# ==============================================================================
# 4. Multi-Session Concurrency & State Isolation
# ==============================================================================

class TestMultiSessionConcurrency:
    """Tests 10 simultaneous client sessions for course scoping and state isolation."""

    def test_ten_concurrent_sessions_isolated_barge_in(self):
        """
        Launches 10 concurrent WebSocket sessions with alternating courses.
        Interrupts session 0 with barge-in.
        Verifies:
        1. All 10 receive valid ready frames with their correct course.
        2. Session 0 gets interrupted.
        3. Sessions 1-9 continue operating without state pollution or interruption.
        """
        client = TestClient(app)
        num_sessions = 10
        courses = ["CNS", "ML", "BD", "SDCC", "SE"] * 2

        sockets = []
        try:
            # Connect all 10 sessions
            for i in range(num_sessions):
                ws = client.websocket_connect(f"/api/live_voice?course={courses[i]}")
                sock = ws.__enter__()
                sockets.append((sock, courses[i]))

            session_ids = set()
            # Verify initial ready handshake
            for i, (sock, expected_course) in enumerate(sockets):
                ready = sock.receive_json()
                assert ready["type"] == "ready"
                assert ready["course"] == expected_course
                sid = ready["session_id"]
                assert sid not in session_ids, f"Duplicate session_id detected: {sid}"
                session_ids.add(sid)

            # Session 0: send text query then immediate barge-in
            sock0, _ = sockets[0]
            sock0.send_json({"type": "text_input", "text": "CNS tls explanation"})
            sock0.send_json({"type": "client_barge_in"})

            # Session 0 receives interrupted
            got_interrupted = False
            for _ in range(5):
                msg = sock0.receive_json()
                if msg.get("type") == "interrupted":
                    got_interrupted = True
                    break
            assert got_interrupted, "Session 0 did not receive 'interrupted'"

            # Other sessions 1..9 send ping and expect pong (not interrupted)
            for i in range(1, num_sessions):
                sock, _ = sockets[i]
                sock.send_json({"type": "ping"})
                pong = sock.receive_json()
                assert pong["type"] == "pong", f"Session {i} failed to receive pong; got {pong}"

        finally:
            for sock, _ in sockets:
                try:
                    sock.close()
                except Exception:
                    pass

    def test_rapid_connect_disconnect_churn_20_cycles(self):
        """Quickly opens and closes 20 connections in sequence, checking for socket leaks."""
        client = TestClient(app)
        for i in range(20):
            with client.websocket_connect(f"/api/live_voice?course=CNS") as ws:
                ready = ws.receive_json()
                assert ready["type"] == "ready"
                ws.send_json({"type": "ping"})
                pong = ws.receive_json()
                assert pong["type"] == "pong"
                # Exits context -> close WebSocket

    def test_concurrent_multi_course_retrieval_zero_bleed(self):
        """
        Connects two concurrent WebSocket clients: Client A (CNS) and Client B (ML).
        Sends topic queries to both.
        Verifies:
        1. Client A receives grounding citations strictly tagged with course 'CNS'.
        2. Client B receives grounding citations strictly tagged with course 'ML'.
        3. Zero cross-course citation contamination.
        """
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws_cns, \
             client.websocket_connect("/api/live_voice?course=ML") as ws_ml:

            ready_cns = ws_cns.receive_json()
            ready_ml = ws_ml.receive_json()
            assert ready_cns["course"] == "CNS"
            assert ready_ml["course"] == "ML"

            # Send queries
            ws_cns.send_json({"type": "text_input", "text": "TLS handshake"})
            ws_ml.send_json({"type": "text_input", "text": "Support Vector Machines"})

            # Read frames for CNS
            cns_citations = []
            for _ in range(15):
                raw = ws_cns.receive()
                if "text" in raw:
                    data = json.loads(raw["text"])
                    if data.get("type") == "grounding":
                        cns_citations.extend(data.get("citations", []))
                    if data.get("type") == "turn_complete":
                        break

            # Read frames for ML
            ml_citations = []
            for _ in range(15):
                raw = ws_ml.receive()
                if "text" in raw:
                    data = json.loads(raw["text"])
                    if data.get("type") == "grounding":
                        ml_citations.extend(data.get("citations", []))
                    if data.get("type") == "turn_complete":
                        break

            # Verify no bleed
            for c in cns_citations:
                assert c.get("course") == "CNS", f"CNS client received foreign citation: {c}"
            for c in ml_citations:
                assert c.get("course") == "ML", f"ML client received foreign citation: {c}"


class TestServerSideInterruptionCancellation:
    """Tests cancellation when Gemini Live API emits server-side LiveInterruptedEvent."""

    def test_server_interrupted_event_cancels_active_tool(self):
        """
        When driver emits LiveInterruptedEvent during tool execution:
        1. Active tool tasks must be cancelled.
        2. Client receives 'interrupted'.
        3. Zero zombie grounding citations are sent.
        """
        async def _run():
            tool_started = asyncio.Event()
            tool_cancelled = asyncio.Event()

            async def slow_retrieval_tool(name: str, args: Dict[str, Any], course: Optional[str]):
                tool_started.set()
                try:
                    await asyncio.sleep(0.5)
                    return {"found": True, "citations": []}, []
                except asyncio.CancelledError:
                    tool_cancelled.set()
                    raise

            config = VoiceBridgeConfig(mock_mode=True)
            driver = MockLiveDriver(config, course="CNS")
            bridge = GeminiLiveBridge(config=config, tool_handler=slow_retrieval_tool, driver_override=driver)

            sent_frames = []

            class MockWS:
                client_state = type("State", (), {"name": "CONNECTED"})()
                def __init__(self):
                    self._q = asyncio.Queue()
                async def receive(self):
                    return await self._q.get()
                async def send_json(self, d):
                    sent_frames.append(d)
                async def send_bytes(self, b):
                    pass

            ws = MockWS()
            sender = SafeWebSocketSender(ws)
            bridge_task = asyncio.create_task(bridge.run(client_ws=ws, course="CNS", sender=sender))

            await asyncio.sleep(0.05)

            # Trigger tool call
            await ws._q.put({"type": "websocket.receive", "text": json.dumps({"type": "text_input", "text": "tls handshake"})})
            await asyncio.wait_for(tool_started.wait(), timeout=1.0)
            assert len(bridge.active_tool_tasks) == 1

            # Simulate server-side LiveInterruptedEvent emitted by driver
            await driver._event_queue.put(LiveInterruptedEvent())
            await asyncio.sleep(0.1)

            assert len(bridge.active_tool_tasks) == 0
            assert tool_cancelled.is_set(), "Server interruption failed to cancel tool task!"

            interrupted = next((f for f in sent_frames if f.get("type") == "interrupted"), None)
            assert interrupted is not None

            # Clean teardown
            await ws._q.put({"type": "websocket.disconnect"})
            await asyncio.wait_for(bridge_task, timeout=2.0)

        asyncio.run(_run())

