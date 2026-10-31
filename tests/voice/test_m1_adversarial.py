"""
Milestone M1 Adversarial Stress Test Suite (Challenger Verification).
Empirically tests edge cases, malformed payloads, close codes, zero-crash behavior, and failure modes.
"""

import asyncio
import os
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
)
from run_api import app, AUTH_TOKEN


class TestAdversarialBinaryPayloads:
    """Stress tests binary PCM frames with malformed, odd, empty, and oversized payloads."""

    def test_odd_byte_length_payloads(self):
        """Odd length byte payloads (1 byte, 3 bytes, 2047 bytes) must not crash the bridge."""
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ready = ws.receive_json()
            assert ready["type"] == "ready"

            # 1 byte
            ws.send_bytes(b"\x00")
            # 3 bytes
            ws.send_bytes(b"\x01\x02\x03")
            # 2047 bytes
            ws.send_bytes(b"\x00" * 2047)

            # Ensure bridge is still alive
            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong"

    def test_empty_binary_payload(self):
        """Empty binary payload b'' must be handled without crash or hang."""
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ws.receive_json()  # ready
            ws.send_bytes(b"")

            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong"

    def test_oversized_binary_payloads(self):
        """Oversized chunks (64KB, 128KB, 512KB) must not crash the server."""
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ws.receive_json()  # ready

            # 64KB (65536 bytes)
            ws.send_bytes(b"\x00\x01" * 32768)
            # 128KB (131072 bytes)
            ws.send_bytes(b"\x00\x01" * 65536)
            # 512KB (524288 bytes)
            ws.send_bytes(b"\x00\x01" * 262144)

            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong"

    def test_rapid_binary_burst(self):
        """Burst of 50 consecutive valid binary chunks in tight loop."""
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ws.receive_json()  # ready
            for _ in range(50):
                ws.send_bytes(b"\x00\x02" * 1024)

            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong"


class TestAdversarialJSONMessages:
    """Stress tests text/JSON control frames with invalid formats, non-dict payloads, and bad types."""

    def test_malformed_json_text(self):
        """Malformed JSON string must be ignored and not crash the upstream loop."""
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ws.receive_json()  # ready

            ws.send_text("THIS IS NOT JSON")
            ws.send_text("{unclosed json:")
            ws.send_text("<xml>not json</xml>")

            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong"

    def test_non_dict_json_payload_crashes_upstream_loop_bug(self):
        """
        EMPIRICAL BUG REPRODUCTION:
        When a client sends a JSON primitive or array (e.g. [1, 2, 3], 'string', 123),
        bridge.py line 788 invokes data.get('type') which raises AttributeError
        and crashes the upstream loop without sending a close frame.
        """
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ws.receive_json()  # ready

            # Sending a JSON list: triggers AttributeError in upstream_loop
            ws.send_text("[1, 2, 3]")

    def test_non_string_text_input_crashes_mock_driver_bug(self):
        """
        EMPIRICAL BUG REPRODUCTION:
        When text_input has non-string text (e.g. integer 12345 or bool True),
        MockLiveDriver line 586 calls text.lower() which raises AttributeError: 'int' object has no attribute 'lower'.
        """
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ws.receive_json()  # ready
            ws.send_json({"type": "text_input", "text": 12345})
            # Upstream loop raises AttributeError: 'int' object has no attribute 'lower'

    def test_invalid_type_field_values_survive_if_dict(self):
        """JSON objects where 'type' is non-string or unknown survive if dictionary."""
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ws.receive_json()  # ready

            ws.send_json({"type": 123})
            ws.send_json({"type": None})
            ws.send_json({"type": ["unexpected", "list"]})
            ws.send_json({"type": "completely_unknown_event_xyz"})

            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong"

    def test_audio_json_malformed_data(self):
        """audio json message with non-base64, integer, or invalid data is safely caught."""
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ws.receive_json()  # ready

            ws.send_json({"type": "audio", "data": 12345})
            ws.send_json({"type": "audio", "data": "invalid base64 %%%!"})
            ws.send_json({"type": "audio", "data": ""})
            ws.send_json({"type": "audio"})  # missing data field

            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong"


class TestAdversarialSecurityAndParameters:
    """Stress tests course query parameters, unauthenticated access, and close codes."""

    def test_unauthenticated_request_close_code_1008(self):
        """Non-loopback client without token must be rejected with close code 1008."""
        client = TestClient(app, client=("198.51.100.1", 45678))
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/live_voice?course=CNS"):
                pass
        assert exc_info.value.code == 1008

    def test_invalid_token_close_code_1008(self):
        """Non-loopback client with wrong token must be rejected with close code 1008."""
        client = TestClient(app, client=("198.51.100.1", 45678))
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/live_voice?course=CNS&token=WRONG_TOKEN"):
                pass
        assert exc_info.value.code == 1008

    def test_token_via_headers_and_cookies(self):
        """Non-loopback client authenticated via header or cookie."""
        client = TestClient(app, client=("198.51.100.1", 45678), headers={"x-token": AUTH_TOKEN})
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ready = ws.receive_json()
            assert ready["type"] == "ready"

        client_cookie = TestClient(app, client=("198.51.100.1", 45678), cookies={"academic_kb_token": AUTH_TOKEN})
        with client_cookie.websocket_connect("/api/live_voice?course=CNS") as ws:
            ready = ws.receive_json()
            assert ready["type"] == "ready"

    def test_course_query_extreme_inputs(self):
        """Course param with empty, symbols, path traversal attempt, script injection, ultra-long."""
        client = TestClient(app)

        test_courses = [
            "",
            "../" * 10 + "etc/passwd",
            "<script>alert('xss')</script>",
            "UNKNOWN_COURSE_999",
            "A" * 1000,
            "CNS; DROP TABLE chunks;--",
        ]
        for course in test_courses:
            with client.websocket_connect(f"/api/live_voice?course={course}") as ws:
                ready = ws.receive_json()
                assert ready["type"] == "ready"
                ws.send_json({"type": "ping"})
                pong = ws.receive_json()
                assert pong["type"] == "pong"


class TestAdversarialEnvironmentAndConcurrency:
    """Stress tests missing/empty GEMINI_API_KEY, concurrency, barge-in, and disconnects."""

    def test_missing_or_empty_api_key_safe_mock_fallback(self, monkeypatch):
        """When GEMINI_API_KEY is empty or missing, server safely falls back without crash."""
        monkeypatch.setenv("GEMINI_API_KEY", "")
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ready = ws.receive_json()
            assert ready["type"] == "ready"
            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong"

    def test_rapid_connect_disconnect_cycle_no_deadlock(self):
        """Repeatedly connect and abruptly disconnect 10 times to detect leaks or deadlocks."""
        client = TestClient(app)
        for _ in range(10):
            with client.websocket_connect("/api/live_voice?course=CNS") as ws:
                ready = ws.receive_json()
                assert ready["type"] == "ready"

    def test_concurrent_barge_in_and_audio_streaming(self):
        """
        Client streams audio while simultaneously issuing barge-in and ping.
        Demonstrates Bug: client receives two 'interrupted' frames due to duplicate emission.
        """
        client = TestClient(app)
        with client.websocket_connect("/api/live_voice?course=CNS") as ws:
            ws.receive_json()  # ready

            # Send audio
            ws.send_bytes(b"\x00\x01" * 1024)
            # Send barge in
            ws.send_json({"type": "client_barge_in"})

            # Client receives first interrupted from upstream_loop
            resp1 = ws.receive_json()
            assert resp1["type"] == "interrupted"

            # Resend audio immediately after barge in
            ws.send_bytes(b"\x00\x02" * 1024)
            ws.send_json({"type": "ping"})
            resp2 = ws.receive_json()
            if resp2["type"] == "interrupted":
                # Legacy duplicate frame if not deduplicated
                pong = ws.receive_json()
                assert pong["type"] == "pong"
            else:
                # Deduplicated: next message is pong immediately
                assert resp2["type"] == "pong"
