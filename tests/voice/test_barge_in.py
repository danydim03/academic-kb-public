"""
Academic KB Voice Studio — Tier 1, 2 & 3: Barge-In & Interruption Cancellation Tests
Verifies low-latency barge-in (<30ms), client VAD event 'client_barge_in', server 'interrupted'
notification, audio queue flushing, mid-retrieval cancellation, and conversational resumption.
"""

import pytest
import asyncio
import time
from typing import Dict, Any, List

from tests.voice.mock_live_server import (
    MockLiveVoiceBridge,
    calculate_rms,
)


# ===========================================================================
# Tier 1: Feature Coverage — Barge-In & Cancellation (>=5 tests)
# ===========================================================================

class TestTier1BargeIn:
    """Verifies primary barge-in contracts and playback interruption."""

    def test_barge_in_client_trigger_stops_model_speech(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies that client_barge_in sets is_interrupted and clears is_speaking."""
        async def _run():
            await mock_bridge.handshake()
            mock_bridge.is_speaking = True
            
            event = await mock_bridge.handle_client_barge_in()
            assert event.get("type") == "interrupted"
            assert mock_bridge.is_speaking is False
            assert mock_bridge.is_interrupted is True
        asyncio.run(_run())

    def test_barge_in_server_dispatches_interrupted_event(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies server appends 'interrupted' event to message stream."""
        async def _run():
            await mock_bridge.handshake()
            initial_count = len(mock_bridge.messages_sent)
            
            await mock_bridge.handle_client_barge_in()
            assert len(mock_bridge.messages_sent) == initial_count + 1
            assert mock_bridge.messages_sent[-1]["type"] == "interrupted"
        asyncio.run(_run())

    def test_barge_in_audio_queue_flushing(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies that pending audio frames are immediately purged when interrupted."""
        async def _run():
            await mock_bridge.handshake()
            
            emitted_frames: List[Any] = []
            
            async for frame_type, data in mock_bridge.emit_model_turn("Long speech", chunk_count=10):
                emitted_frames.append((frame_type, data))
                if len(emitted_frames) == 2:
                    # Mid-turn interruption!
                    await mock_bridge.handle_client_barge_in()
            
            # Since chunk_count was 10, total frames should be significantly less than 10 audio frames
            audio_frames = [f for f in emitted_frames if f[0] == "audio"]
            assert len(audio_frames) < 10, f"Expected audio stream truncated by barge-in, got {len(audio_frames)}"
        asyncio.run(_run())

    def test_barge_in_turn_complete_not_sent_when_interrupted(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies that interrupted turn does NOT emit 'turn_complete'."""
        async def _run():
            await mock_bridge.handshake()
            
            events = []
            async for frame_type, data in mock_bridge.emit_model_turn("Aborted turn", chunk_count=5):
                events.append((frame_type, data))
                if len(events) == 2:
                    await mock_bridge.handle_client_barge_in()
            
            json_types = [d.get("type") for t, d in events if t == "json"]
            assert "turn_complete" not in json_types, "Interrupted turn must not emit 'turn_complete'"
        asyncio.run(_run())

    def test_barge_in_immediate_turn_resumption(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies that after interruption, a subsequent student turn can start immediately."""
        async def _run():
            await mock_bridge.handshake()
            # Turn 1 interrupted
            await mock_bridge.handle_client_barge_in()
            assert mock_bridge.is_interrupted is True
            
            # Student initiates new turn
            mock_bridge.start_new_turn()
            assert mock_bridge.is_interrupted is False
            
            # Turn 2 initiated cleanly
            turn2_events = []
            async for frame_type, data in mock_bridge.emit_model_turn("New answer to follow-up", chunk_count=2):
                turn2_events.append((frame_type, data))
            
            assert mock_bridge.is_speaking is False
            json_types = [d.get("type") for t, d in turn2_events if t == "json"]
            assert "turn_complete" in json_types, "Turn 2 should successfully complete"
        asyncio.run(_run())


# ===========================================================================
# Tier 2 & Tier 3: Boundaries & Cross-Feature Combinations (>=5 tests)
# ===========================================================================

class TestTier3BargeInCombinations:
    """Verifies cross-feature combinations, mid-retrieval cancellation, and timing constraints."""

    def test_barge_in_low_latency_execution_timing(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies that barge-in processing executes in strictly < 30ms (PROJECT.md SLA)."""
        async def _run():
            await mock_bridge.handshake()
            mock_bridge.is_speaking = True
            
            t0 = time.perf_counter()
            await mock_bridge.handle_client_barge_in()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            
            assert elapsed_ms < 30.0, f"Barge-in latency SLA violation: took {elapsed_ms:.2f}ms (must be < 30ms)"
        asyncio.run(_run())

    def test_barge_in_during_active_kb_retrieval(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies user speaking while KB retrieval tool is in-flight cancels subsequent audio."""
        async def _run():
            await mock_bridge.handshake()
            
            # Simulate KB retrieval starting
            retrieval_task = asyncio.create_task(mock_bridge.execute_grounding("TLS Handshake"))
            # Barge-in happens while retrieval is executing
            await mock_bridge.handle_client_barge_in()
            grounding_result = await retrieval_task
            
            assert grounding_result["type"] == "grounding"
            assert mock_bridge.is_interrupted is True
            # No audio should play for interrupted turn
            audio_emitted = []
            async for frame_type, data in mock_bridge.emit_model_turn("Interrupted answer", chunk_count=5):
                if frame_type == "audio":
                    audio_emitted.append(data)
            assert len(audio_emitted) == 0, "No audio should be emitted when interrupted"
        asyncio.run(_run())

    def test_barge_in_concurrent_rapid_bursts(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies that 10 concurrent or rapid barge-in events are handled idempotently without crash."""
        async def _run():
            await mock_bridge.handshake()
            # Send 10 rapid barge-in requests
            results = await asyncio.gather(*(mock_bridge.handle_client_barge_in() for _ in range(10)))
            assert len(results) == 10
            for r in results:
                assert r["type"] == "interrupted"
            assert mock_bridge.is_interrupted is True
            assert mock_bridge.is_speaking is False
        asyncio.run(_run())

    def test_barge_in_while_model_idle_idempotent(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies that barge-in received while model is not speaking is safely handled."""
        async def _run():
            await mock_bridge.handshake()
            assert mock_bridge.is_speaking is False
            event = await mock_bridge.handle_client_barge_in()
            assert event["type"] == "interrupted"
            assert mock_bridge.is_speaking is False
        asyncio.run(_run())

    def test_barge_in_avatar_audio_energy_drop(self, mock_bridge: MockLiveVoiceBridge):
        """Verifies that upon interruption, audio emission ceases, ensuring RMS immediately drops to 0."""
        async def _run():
            await mock_bridge.handshake()
            received_chunks = []
            
            async for frame_type, data in mock_bridge.emit_model_turn("Streaming response", chunk_count=6):
                if frame_type == "audio":
                    received_chunks.append(data)
                if len(received_chunks) == 2:
                    await mock_bridge.handle_client_barge_in()
            
            # Verify stream stopped at 2
            assert len(received_chunks) == 2
            # Flushed buffer has 0 frames
            assert len(mock_bridge.audio_frames_sent) == 0
        asyncio.run(_run())
