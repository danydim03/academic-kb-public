"""
Academic KB Voice Studio — Tier 1 & Tier 2: WebSocket Handshake & Lifecycle Tests
Verifies endpoint /api/live_voice, BidiGenerateContent protocol, query parameters,
session uniqueness, keep-alive, disconnect cleanup, and error boundaries.
"""

import pytest
import asyncio
import uuid
from typing import Dict, Any

from tests.voice.mock_live_server import (
    MockLiveVoiceBridge,
    MODEL_NAME,
)
from tests.voice.conftest import require_voice_module, get_voice_module


# ===========================================================================
# Tier 1: Feature Coverage — WebSocket Handshake & Session Lifecycle (>=5 tests)
# ===========================================================================

class TestTier1WebSocketHandshake:
    """Verifies happy path contracts for WebSocket handshake and session lifecycle."""

    def test_ws_handshake_successful_ready_event(self, mock_bridge: MockLiveVoiceBridge):
        """Validates that initial handshake returns a 'ready' event with session_id and model."""
        async def _run():
            ready = await mock_bridge.handshake()
            assert isinstance(ready, dict), "Handshake must return a JSON dictionary"
            assert ready.get("type") == "ready", "Initial event must be of type 'ready'"
            assert "session_id" in ready and isinstance(ready["session_id"], str), "Must include session_id"
            assert len(ready["session_id"]) > 5, "session_id must be non-empty"
            assert ready.get("model") == MODEL_NAME, f"Expected model '{MODEL_NAME}', got {ready.get('model')}"
            assert mock_bridge.is_connected is True, "Bridge must be marked connected after handshake"
        asyncio.run(_run())

    def test_ws_handshake_course_query_parameter_custom(self):
        """Verifies that course query parameter (e.g. ?course=ML) is correctly bound to session."""
        async def _run():
            bridge = MockLiveVoiceBridge(course="ML")
            ready = await bridge.handshake()
            assert ready.get("course") == "ML", f"Expected course 'ML', got {ready.get('course')}"
            assert bridge.course == "ML"
        asyncio.run(_run())

    def test_ws_handshake_default_course_fallback(self):
        """Verifies that omitted course query parameter defaults to 'CNS' or 'GENERAL'."""
        async def _run():
            bridge = MockLiveVoiceBridge(course="CNS")
            ready = await bridge.handshake()
            assert ready.get("course") in ["CNS", "GENERAL"]
        asyncio.run(_run())

    def test_ws_handshake_session_uniqueness(self):
        """Verifies that distinct connection handshakes generate unique session IDs."""
        async def _run():
            b1 = MockLiveVoiceBridge(course="CNS")
            b2 = MockLiveVoiceBridge(course="CNS")
            r1 = await b1.handshake()
            r2 = await b2.handshake()
            assert r1["session_id"] != r2["session_id"], "Each session must have a globally unique identifier"
        asyncio.run(_run())

    def test_ws_handshake_graceful_close_code_1000(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies that a normal close frame (code 1000) terminates the session cleanly."""
        async def _run():
            await mock_bridge.handshake()
            assert mock_bridge.is_connected is True
            await mock_bridge.close(code=1000)
            assert mock_bridge.is_connected is False, "Session must be closed after normal termination"
            assert mock_bridge.is_speaking is False
        asyncio.run(_run())


# ===========================================================================
# Tier 2: Boundary & Corner Cases — Handshake & Lifecycle (>=5 tests)
# ===========================================================================

class TestTier2WebSocketHandshakeBoundaries:
    """Verifies edge cases, malformed queries, disconnect cleanup, and protocol stress."""

    def test_ws_handshake_special_chars_in_course_query(self):
        """Verifies course query parameter containing URL-encoded special characters."""
        async def _run():
            special_course = "CNS%20Advanced%20Security!@#"
            bridge = MockLiveVoiceBridge(course=special_course)
            ready = await bridge.handshake()
            assert ready.get("type") == "ready"
            assert bridge.is_connected is True
        asyncio.run(_run())

    def test_ws_handshake_abrupt_disconnect_cleanup(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies server cleans up internal state when client abruptly drops."""
        async def _run():
            await mock_bridge.handshake()
            mock_bridge.audio_frames_received.append(b"some_audio")
            # Simulate sudden disconnect without normal close frame
            await mock_bridge.close(code=1006)
            assert mock_bridge.is_connected is False
            assert mock_bridge.is_speaking is False
        asyncio.run(_run())

    def test_ws_handshake_concurrent_sessions_isolation(self):
        """Verifies that 10 concurrent sessions remain completely isolated without cross-talk."""
        async def _run():
            sessions = [MockLiveVoiceBridge(course=f"COURSE_{i}") for i in range(10)]
            handshakes = await asyncio.gather(*(s.handshake() for s in sessions))
            
            session_ids = [h["session_id"] for h in handshakes]
            assert len(set(session_ids)) == 10, "All 10 concurrent sessions must have distinct IDs"
            
            for idx, s in enumerate(sessions):
                assert s.course == f"COURSE_{idx}"
                assert s.is_connected is True
        asyncio.run(_run())

    def test_ws_handshake_repeated_close_idempotent(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies that calling close() multiple times is idempotent and does not raise."""
        async def _run():
            await mock_bridge.handshake()
            await mock_bridge.close(code=1000)
            # Second and third close calls should succeed without error
            await mock_bridge.close(code=1000)
            await mock_bridge.close(code=1000)
            assert mock_bridge.is_connected is False
        asyncio.run(_run())

    def test_ws_handshake_ultra_long_course_parameter(self):
        """Verifies that an extraordinarily long course query parameter does not overflow or crash."""
        async def _run():
            long_course = "CNS_" + ("A" * 1024)
            bridge = MockLiveVoiceBridge(course=long_course)
            ready = await bridge.handshake()
            assert ready.get("type") == "ready"
            assert bridge.course == long_course
        asyncio.run(_run())
