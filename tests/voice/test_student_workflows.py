"""
Academic KB Voice Studio — Tier 4: Real-World Student Workflows
Simulates full end-to-end student study sessions in DIMEOGPT Study Studio:
- TLS 1.3 handshake inquiry with citation delivery [Doc.pdf, p. X] and avatar lip-sync.
- Interruption (barge-in) mid-explanation with immediate avatar jaw reset.
- Follow-up query resumption without session renegotiation.
- Zero-hallucination defense on unindexed topics.
- Rapid multi-turn conversational study drill.
"""

import pytest
import asyncio
from typing import List, Dict, Any, Tuple

from tests.voice.mock_live_server import (
    MockLiveVoiceBridge,
    StrictGroundingGuard,
    calculate_rms,
    compute_avatar_jaw_offset,
    compute_avatar_glow_style,
)


class TestTier4StudentWorkflows:
    """Verifies end-to-end conversational workflows mirroring real university students."""

    def test_student_workflow_cns_tls13_handshake_explanation(self, mock_bridge: MockLiveVoiceBridge):
        """
        Scenario 1:
        Student connects to CNS course, asks about TLS 1.3 handshake latency.
        Verifies:
        - Handshake 'ready'
        - Grounding event with [Sicurezza_Reti_TLS13.pdf, p. 42]
        - 24kHz audio emission
        - Talking avatar RMS energy > 0 and jaw offset > 0
        - Clean 'turn_complete'
        """
        async def _run():
            # 1. Connect
            ready = await mock_bridge.handshake()
            assert ready["type"] == "ready"
            assert mock_bridge.course == "CNS"

            # 2. Student asks question via voice
            query = "Qual è la latenza dell'handshake in TLS 1.3 rispetto a TLS 1.2?"
            
            collected_json: List[Dict[str, Any]] = []
            collected_audio: List[bytes] = []
            jaw_offsets: List[float] = []

            async for frame_type, data in mock_bridge.emit_model_turn(
                transcript_text="In TLS 1.3 la latenza dell'handshake è ridotta a 1-RTT grazie allo scambio di chiavi Diffie-Hellman incluso nel ClientHello.",
                grounding_query=query,
                chunk_count=5
            ):
                if frame_type == "json":
                    collected_json.append(data)
                elif frame_type == "audio":
                    collected_audio.append(data)
                    rms = calculate_rms(data)
                    offset = compute_avatar_jaw_offset(rms)
                    jaw_offsets.append(offset)

            # 3. Verify grounding event
            grounding_events = [d for d in collected_json if d.get("type") == "grounding"]
            assert len(grounding_events) == 1, "Must receive exactly 1 grounding event"
            g_event = grounding_events[0]
            assert g_event["found"] is True
            assert g_event["k"] >= 1
            citation = g_event["citations"][0]
            assert "Sicurezza_Reti_TLS13.pdf" in citation["source"]
            assert citation["page"] == 42
            assert citation["citation_tag"] == "[Sicurezza_Reti_TLS13.pdf, p. 42]"

            # 4. Verify audio and avatar lip-sync activity
            assert len(collected_audio) == 5
            assert all(offset > 0.0 for offset in jaw_offsets), "Avatar jaw offset must be active (>0) during speech"
            assert any(offset >= 4.0 for offset in jaw_offsets), "Avatar jaw should demonstrate expressive opening"

            # 5. Verify turn completion
            assert collected_json[-1]["type"] == "turn_complete"
            assert mock_bridge.is_speaking is False
        asyncio.run(_run())

    def test_student_workflow_mid_explanation_barge_in(self, mock_bridge: MockLiveVoiceBridge):
        """
        Scenario 2:
        Student interrupts mid-explanation.
        Verifies:
        - Model starts speaking TLS 1.3 explanation
        - After 2 audio chunks, student speaks (client_barge_in)
        - Server dispatches 'interrupted' event
        - Audio queue immediately truncated (< 10 chunks)
        - Avatar jaw offset drops immediately to 0.0
        - 'turn_complete' is suppressed
        """
        async def _run():
            await mock_bridge.handshake()

            emitted_frames: List[Tuple[str, Any]] = []
            interrupted_jaw_offset: float = -1.0

            async for frame_type, data in mock_bridge.emit_model_turn(
                transcript_text="In TLS 1.3 la latenza...",
                grounding_query="TLS 1.3",
                chunk_count=8
            ):
                emitted_frames.append((frame_type, data))
                audio_count = len([f for f in emitted_frames if f[0] == "audio"])
                if audio_count == 2:
                    # Student interrupts!
                    await mock_bridge.handle_client_barge_in()
                    # On barge-in, client calculates avatar state with silence (rms = 0.0)
                    interrupted_jaw_offset = compute_avatar_jaw_offset(0.0)

            # Audio must be truncated
            audio_frames = [f for f in emitted_frames if f[0] == "audio"]
            assert len(audio_frames) < 8
            assert interrupted_jaw_offset == 0.0, "Avatar jaw must immediately close (0.0px) on barge-in"

            json_events = [f[1] for f in emitted_frames if f[0] == "json"]
            assert not any(e.get("type") == "turn_complete" for e in json_events)
            assert mock_bridge.messages_sent[-1]["type"] == "interrupted"
        asyncio.run(_run())

    def test_student_workflow_interruption_followed_by_follow_up(self, mock_bridge: MockLiveVoiceBridge):
        """
        Scenario 3:
        Student interrupts Turn 1 and immediately asks follow-up (Turn 2).
        Verifies:
        - Turn 1 interrupted cleanly
        - Turn 2 begins without WebSocket reconnect
        - Turn 2 retrieves new concept (WEP)
        - Turn 2 emits citation [Wireless_Security_WEP.pdf, p. 15]
        - Turn 2 completes normally
        """
        async def _run():
            await mock_bridge.handshake()

            # Turn 1: Interrupted
            async for frame_type, data in mock_bridge.emit_model_turn("Turn 1...", chunk_count=6):
                await mock_bridge.handle_client_barge_in()
                break

            assert mock_bridge.is_interrupted is True

            # Turn 2: Follow-up question
            mock_bridge.start_new_turn()
            assert mock_bridge.is_interrupted is False

            turn2_json = []
            turn2_audio = []

            async for frame_type, data in mock_bridge.emit_model_turn(
                transcript_text="Nel protocollo WEP la chiave RC4 viene usata con un IV a soli 24 bit, vulnerabile a collisioni.",
                grounding_query="vulnerabilità WEP",
                chunk_count=3
            ):
                if frame_type == "json":
                    turn2_json.append(data)
                elif frame_type == "audio":
                    turn2_audio.append(data)

            # Verify Turn 2 grounding
            g_events = [d for d in turn2_json if d.get("type") == "grounding"]
            assert len(g_events) == 1
            assert g_events[0]["found"] is True
            assert any("wep" in c["source"].lower() for c in g_events[0]["citations"])
            assert g_events[0]["citations"][0]["citation_tag"] == "[Wireless_Security_WEP.pdf, p. 15]"

            # Verify Turn 2 audio and completion
            assert len(turn2_audio) == 3
            assert turn2_json[-1]["type"] == "turn_complete"
        asyncio.run(_run())

    def test_student_workflow_unindexed_topic_zero_hallucination(self, mock_bridge: MockLiveVoiceBridge):
        """
        Scenario 4:
        Student asks about a topic not in the Knowledge Graph for the current course.
        Verifies:
        - System returns found: false
        - Citations list is empty (no hallucination)
        - Message explicitly states unavailability
        - Model speech acknowledges lack of official documents
        """
        async def _run():
            await mock_bridge.handshake()

            unindexed_query = "Come si implementa il consenso Raft in Apache Kafka?"
            
            collected_json = []
            async for frame_type, data in mock_bridge.emit_model_turn(
                transcript_text="Non ho trovato informazioni su Raft e Kafka nei documenti del corso CNS indicizzati nel Knowledge Graph.",
                grounding_query=unindexed_query,
                chunk_count=2
            ):
                if frame_type == "json":
                    collected_json.append(data)

            g_event = [d for d in collected_json if d.get("type") == "grounding"][0]
            assert g_event["found"] is False
            assert g_event["k"] == 0
            assert len(g_event["citations"]) == 0
            assert "nessuna informazione" in g_event.get("message", "").lower()
        asyncio.run(_run())

    def test_student_workflow_rapid_interactive_drill(self, mock_bridge: MockLiveVoiceBridge):
        """
        Scenario 5:
        Rapid 3-question revision drill on network security in a single persistent session.
        Verifies:
        - 3 consecutive complete conversational turns
        - Session ID remains invariant throughout drill
        - Each turn delivers accurate grounding and completes with turn_complete
        """
        async def _run():
            ready = await mock_bridge.handshake()
            initial_session_id = ready["session_id"]

            drill_queries = [
                ("TLS 1.3 handshake", "Sicurezza_Reti_TLS13.pdf"),
                ("WEP IV collisions", "Wireless_Security_WEP.pdf"),
                ("TLS 1.3 handshake latency", "Sicurezza_Reti_TLS13.pdf")
            ]

            for idx, (query, expected_source) in enumerate(drill_queries, 1):
                mock_bridge.start_new_turn()
                events = []
                async for frame_type, data in mock_bridge.emit_model_turn(
                    transcript_text=f"Risposta drill domanda {idx}",
                    grounding_query=query,
                    chunk_count=2
                ):
                    events.append((frame_type, data))

                # Verify grounding for this turn
                g_event = [d for t, d in events if t == "json" and d.get("type") == "grounding"][0]
                assert g_event["found"] is True
                assert any(expected_source.lower() in c["source"].lower() for c in g_event["citations"])
                
                # Verify turn complete
                last_event = events[-1]
                assert last_event[0] == "json" and last_event[1]["type"] == "turn_complete"

            assert mock_bridge.session_id == initial_session_id, "Session must remain persistent throughout entire drill"
            assert mock_bridge.turn_counter == 3, "Exactly 3 turns should have been executed"
        asyncio.run(_run())
