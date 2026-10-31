"""
Milestone M1 Integration & Verification Suite: Live Voice Bridge & Endpoint.
Tests SafeWebSocketSender, MockLiveDriver, GenAILiveDriver, RawWebSocketLiveDriver,
GeminiLiveBridge, and FastAPI /api/live_voice WebSocket route.
"""

import asyncio
import base64
import json
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from engine.voice.bridge import (
    GeminiLiveBridge,
    VoiceBridgeConfig,
    SafeWebSocketSender,
    MockLiveDriver,
    GenAILiveDriver,
    RawWebSocketLiveDriver,
    LiveAudioEvent,
    LiveTranscriptEvent,
    LiveInterruptedEvent,
    LiveTurnCompleteEvent,
    LiveToolCallEvent,
    CLIENT_FRAME_BYTES,
    SERVER_FRAME_BYTES,
)
from run_api import app, AUTH_TOKEN


class TestSafeWebSocketSender:
    """Verifies that SafeWebSocketSender safely locks and dispatches concurrent sends."""

    def test_safe_sender_initialization(self):
        class DummyWS:
            client_state = type("State", (), {"name": "CONNECTED"})()
            def __init__(self):
                self.sent_bytes = []
                self.sent_json = []
            async def send_bytes(self, b):
                self.sent_bytes.append(b)
            async def send_json(self, j):
                self.sent_json.append(j)

        dummy = DummyWS()
        sender = SafeWebSocketSender(dummy)
        
        async def _run():
            tasks = [
                sender.send_bytes(b"\x00" * 2400),
                sender.send_json({"type": "ping"}),
                sender.send_bytes(b"\x01" * 2400),
                sender.send_json({"type": "pong"}),
            ]
            await asyncio.gather(*tasks)
            assert len(dummy.sent_bytes) == 2
            assert len(dummy.sent_json) == 2

        asyncio.run(_run())


class TestVoiceDrivers:
    """Verifies LiveSessionDriver implementations."""

    def test_mock_live_driver_lifecycle(self):
        config = VoiceBridgeConfig(model="gemini-3.8-live", mock_mode=True)
        driver = MockLiveDriver(config, course="CNS")

        async def _run():
            await driver.connect()
            assert driver.is_connected is True

            # Send audio chunk
            pcm_chunk = b"\x00\x01" * 1024
            await driver.send_audio(pcm_chunk)
            assert len(driver.audio_frames_received) == 1

            # Test text without academic keywords
            await driver.send_text("Hello assistant")
            events = []
            async for ev in driver.receive_events():
                events.append(ev)
                if isinstance(ev, LiveTurnCompleteEvent):
                    break

            user_tx = [e for e in events if isinstance(e, LiveTranscriptEvent) and e.role == "user"]
            model_tx = [e for e in events if isinstance(e, LiveTranscriptEvent) and e.role == "model"]
            audio_evs = [e for e in events if isinstance(e, LiveAudioEvent)]

            assert len(user_tx) == 1
            assert len(model_tx) == 1
            assert len(audio_evs) == 3
            assert len(audio_evs[0].data) == SERVER_FRAME_BYTES

            # Test barge-in
            await driver.handle_barge_in()
            assert driver.is_interrupted is True

            await driver.close()
            assert driver.is_connected is False

        asyncio.run(_run())

    def test_genai_live_driver_missing_key_raises(self):
        config = VoiceBridgeConfig(api_key=None)
        driver = GenAILiveDriver(config)
        with pytest.raises(ValueError, match="GEMINI_API_KEY must be provided"):
            asyncio.run(driver.connect())

    def test_raw_websocket_driver_missing_key_raises(self):
        config = VoiceBridgeConfig(api_key=None)
        driver = RawWebSocketLiveDriver(config)
        with pytest.raises(ValueError, match="GEMINI_API_KEY must be provided"):
            asyncio.run(driver.connect())


class TestLiveVoiceEndpoint:
    """Verifies FastAPI /api/live_voice endpoint integration."""

    def test_endpoint_handshake_loopback(self):
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ready = ws.receive_json()
            assert ready.get("type") == "ready"
            assert ready.get("model") == "gemini-3.8-live"
            assert ready.get("voice") in ("Charon", "Aoede")
            assert ready.get("course") == "CNS"
            assert "session_id" in ready

    def test_endpoint_handshake_male_voice(self):
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS&voice=Charon") as ws:
            ready = ws.receive_json()
            assert ready.get("type") == "ready"
            assert ready.get("voice") == "Charon"

    def test_endpoint_ping_pong(self):
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ws.receive_json()  # ready
            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong.get("type") == "pong"

    def test_endpoint_audio_frame_and_barge_in(self):
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ws.receive_json()  # ready
            # Send 16kHz audio frame
            ws.send_bytes(b"\x00\x02" * 1024)
            # Send client barge-in
            ws.send_json({"type": "client_barge_in"})
            interrupted = ws.receive_json()
            assert interrupted.get("type") == "interrupted"

    def test_endpoint_zero_trust_security_rejection(self):
        # Non-loopback without token must be closed with WS 1008
        client = TestClient(app, client=("10.0.0.5", 12345))
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/api/live_voice?course=CNS"):
                pass
        assert exc.value.code == 1008

    def test_endpoint_zero_trust_security_authorized(self):
        # Non-loopback with token must succeed
        client = TestClient(app, client=("10.0.0.5", 12345))
        with client.websocket_connect(f"/api/live_voice?course=CNS&token={AUTH_TOKEN}") as ws:
            ready = ws.receive_json()
            assert ready.get("type") == "ready"
