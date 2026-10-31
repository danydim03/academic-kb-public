"""
Academic KB Voice Studio — Engine Voice Package.
Provides real-time bidirectional audio streaming bridge with Gemini Live API,
strict grounding retrieval, and audio-reactive voice session coordination.
"""

from engine.voice.bridge import (
    GeminiLiveBridge,
    VoiceBridgeConfig,
    SafeWebSocketSender,
    LiveSessionDriver,
    GenAILiveDriver,
    RawWebSocketLiveDriver,
    MockLiveDriver,
    LiveAudioEvent,
    LiveTranscriptEvent,
    LiveInterruptedEvent,
    LiveTurnCompleteEvent,
    LiveToolCallEvent,
    LiveToolCancellationEvent,
    LiveErrorEvent,
    DEFAULT_LIVE_SYSTEM_INSTRUCTION,
    QUERY_ACADEMIC_KB_TOOL_SCHEMA,
)

from engine.voice.grounding import (
    AcademicGroundingBridge,
    AcademicDocChunk,
    GROUNDING_TOOL_SCHEMA,
    format_academic_citation,
)

__all__ = [
    "GeminiLiveBridge",
    "VoiceBridgeConfig",
    "SafeWebSocketSender",
    "LiveSessionDriver",
    "GenAILiveDriver",
    "RawWebSocketLiveDriver",
    "MockLiveDriver",
    "LiveAudioEvent",
    "LiveTranscriptEvent",
    "LiveInterruptedEvent",
    "LiveTurnCompleteEvent",
    "LiveToolCallEvent",
    "LiveToolCancellationEvent",
    "LiveErrorEvent",
    "DEFAULT_LIVE_SYSTEM_INSTRUCTION",
    "QUERY_ACADEMIC_KB_TOOL_SCHEMA",
    "AcademicGroundingBridge",
    "AcademicDocChunk",
    "GROUNDING_TOOL_SCHEMA",
    "format_academic_citation",
]
