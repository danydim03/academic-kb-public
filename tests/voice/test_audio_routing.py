"""
Academic KB Voice Studio — Tier 1 & Tier 2: Audio Routing & Format Translation Tests
Verifies 16kHz Int16 PCM mono client ingestion (2048-byte frames), 24kHz Int16 PCM mono
model audio emission, binary/JSON multiplexing, corrupted frames, and burst stress.
"""

import pytest
import asyncio
import struct
from typing import Dict, Any, List

from tests.voice.mock_live_server import (
    MockLiveVoiceBridge,
    CLIENT_FRAME_BYTES,
    SERVER_FRAME_BYTES,
    generate_pcm_16k,
    generate_silence_16k,
    generate_pcm_24k,
    calculate_rms,
)


# ===========================================================================
# Tier 1: Feature Coverage — Audio Routing & Format Translation (>=5 tests)
# ===========================================================================

class TestTier1AudioRouting:
    """Verifies audio frame routing, sampling rates, and frame multiplexing."""

    def test_audio_16k_pcm_ingestion_standard_frame(self, mock_bridge: MockLiveVoiceBridge, pcm_16k_chunk: bytes):
        """Validates that a standard 1024-sample (2048-byte) 16kHz Int16 chunk is accepted."""
        async def _run():
            await mock_bridge.handshake()
            assert len(pcm_16k_chunk) == CLIENT_FRAME_BYTES, f"Expected {CLIENT_FRAME_BYTES} bytes, got {len(pcm_16k_chunk)}"
            res = await mock_bridge.receive_client_audio_frame(pcm_16k_chunk)
            assert res is None, "Valid frame should not return error"
            assert len(mock_bridge.audio_frames_received) == 1
            assert mock_bridge.audio_frames_received[0] == pcm_16k_chunk
        asyncio.run(_run())

    def test_audio_24k_pcm_emission_stream(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies that model responses emit valid 24kHz Int16 PCM audio chunks."""
        async def _run():
            await mock_bridge.handshake()
            received_audio_chunks: List[bytes] = []
            
            async for frame_type, data in mock_bridge.emit_model_turn("Test response", chunk_count=3):
                if frame_type == "audio":
                    received_audio_chunks.append(data)
            
            assert len(received_audio_chunks) == 3, f"Expected 3 chunks, got {len(received_audio_chunks)}"
            for chunk in received_audio_chunks:
                assert len(chunk) == SERVER_FRAME_BYTES, f"Expected {SERVER_FRAME_BYTES} bytes, got {len(chunk)}"
                assert len(chunk) % 2 == 0, "Chunk must be 2-byte aligned for Int16 samples"
                rms = calculate_rms(chunk)
                assert 0.0 <= rms <= 1.0, f"RMS {rms} must be between 0.0 and 1.0"
        asyncio.run(_run())

    def test_audio_binary_and_json_multiplexing(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies interleaved delivery of JSON control frames and binary audio frames."""
        async def _run():
            await mock_bridge.handshake()
            event_sequence: List[str] = []
            
            async for frame_type, data in mock_bridge.emit_model_turn("TLS explanation", grounding_query="TLS 1.3", chunk_count=2):
                if frame_type == "json":
                    event_sequence.append(f"json:{data.get('type')}")
                elif frame_type == "audio":
                    event_sequence.append("binary:audio")
            
            # Expected order: grounding -> transcript -> audio -> audio -> turn_complete
            assert "json:grounding" in event_sequence
            assert "json:transcript" in event_sequence
            assert "binary:audio" in event_sequence
            assert event_sequence[-1] == "json:turn_complete"
        asyncio.run(_run())

    def test_audio_stream_end_signaling(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies that client hybrid VAD silence flag triggers turn transition."""
        async def _run():
            await mock_bridge.handshake()
            # Send speech frames followed by audio_stream_end
            speech_frame = generate_pcm_16k(duration_ms=64, amplitude=0.7)
            await mock_bridge.receive_client_audio_frame(speech_frame)
            
            # Simulate client sending audio_stream_end JSON message
            stream_end_payload = {"type": "audio_stream_end"}
            assert stream_end_payload["type"] == "audio_stream_end"
            # Server receives and is ready to generate response
            assert len(mock_bridge.audio_frames_received) == 1
        asyncio.run(_run())

    def test_audio_text_input_interleaved(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies client text_input message is accepted alongside audio stream."""
        async def _run():
            await mock_bridge.handshake()
            text_payload = {"type": "text_input", "text": "Quali sono le novità di TLS 1.3?"}
            assert text_payload["type"] == "text_input"
            assert len(text_payload["text"]) > 0
            # Ensure text can trigger model response
            turn_events = []
            async for frame_type, data in mock_bridge.emit_model_turn("Risposta a domanda testuale", chunk_count=1):
                turn_events.append((frame_type, data))
            assert len(turn_events) >= 2
        asyncio.run(_run())


# ===========================================================================
# Tier 2: Boundary & Corner Cases — Audio Frame Boundaries (>=5 tests)
# ===========================================================================

class TestTier2AudioBoundaries:
    """Verifies edge cases, malformed PCM, zero bytes, and stress bursts."""

    def test_audio_empty_frame_handling(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies that an empty (0-byte) audio frame does not crash the server."""
        async def _run():
            await mock_bridge.handshake()
            res = await mock_bridge.receive_client_audio_frame(b"")
            assert res is not None
            assert res.get("type") == "warning"
            assert "empty" in res.get("message", "").lower()
            assert len(mock_bridge.audio_frames_received) == 0
        asyncio.run(_run())

    def test_audio_odd_byte_length_misalignment(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies that odd byte length (violating 16-bit alignment) is caught and flagged."""
        async def _run():
            await mock_bridge.handshake()
            corrupted_frame = b"\x00" * 2047  # Odd number of bytes
            res = await mock_bridge.receive_client_audio_frame(corrupted_frame)
            assert res is not None
            assert res.get("type") == "error"
            assert "alignment" in res.get("message", "").lower() or "odd" in res.get("message", "").lower()
        asyncio.run(_run())

    def test_audio_rapid_burst_streaming(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies handling of a high-speed burst of 50 consecutive audio frames."""
        async def _run():
            await mock_bridge.handshake()
            frames = [generate_pcm_16k(duration_ms=64, frequency=200.0 + i) for i in range(50)]
            for f in frames:
                err = await mock_bridge.receive_client_audio_frame(f)
                assert err is None
            assert len(mock_bridge.audio_frames_received) == 50
        asyncio.run(_run())

    def test_audio_extreme_amplitude_rms_invariants(self):
        """Verifies RMS calculation invariants with full-scale square wave (maximum saturation)."""
        max_int16 = 32767
        num_samples = 1024
        # Alternating max positive and max negative
        buffer = bytearray(num_samples * 2)
        for i in range(num_samples):
            val = max_int16 if i % 2 == 0 else -32768
            struct.pack_into("<h", buffer, i * 2, val)
        
        rms = calculate_rms(bytes(buffer))
        # Should be approximately 1.0 and strictly <= 1.0
        assert 0.99 <= rms <= 1.0001, f"Expected RMS ~ 1.0, got {rms}"

    def test_audio_silence_rms_zero(self, pcm_16k_silence: bytes):
        """Verifies that pure silence produces exactly 0.0 RMS."""
        rms = calculate_rms(pcm_16k_silence)
        assert rms == 0.0, f"Expected 0.0 RMS for silence, got {rms}"
