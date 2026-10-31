"""
Academic KB Voice Studio — Voice Test Suite Conftest & Fixtures
Provides fixtures, progressive testability module loaders, and audio mock factories.
"""

import os
import sys
import importlib
import pytest
import asyncio
from typing import Optional, Dict, Any, Generator

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.voice.mock_live_server import (
    MockLiveVoiceBridge,
    StrictGroundingGuard,
    generate_pcm_16k,
    generate_silence_16k,
    generate_pcm_24k,
    CLIENT_FRAME_BYTES,
    SERVER_FRAME_BYTES,
    AVATAR_IMAGE_WIDTH,
    AVATAR_IMAGE_HEIGHT,
)


def get_voice_module(module_name: str):
    """
    Dynamically loads an engine.voice module if available, or returns None.
    Supports progressive testability across implementation milestones M1-M4.
    """
    full_name = f"engine.voice.{module_name}"
    try:
        if full_name in sys.modules:
            return sys.modules[full_name]
        return importlib.import_module(full_name)
    except (ImportError, ModuleNotFoundError):
        return None


def require_voice_module(module_name: str, milestone: str = "M1"):
    """
    Skips the current test if the requested engine.voice module is not yet implemented.
    """
    mod = get_voice_module(module_name)
    if mod is None:
        pytest.skip(f"engine.voice.{module_name} is not yet implemented ({milestone})")
    return mod


@pytest.fixture
def mock_bridge() -> MockLiveVoiceBridge:
    """Provides a fresh MockLiveVoiceBridge instance."""
    return MockLiveVoiceBridge(course="CNS")


@pytest.fixture
def grounding_guard() -> StrictGroundingGuard:
    """Provides a fresh StrictGroundingGuard instance with standard test knowledge."""
    return StrictGroundingGuard()


@pytest.fixture
def pcm_16k_chunk() -> bytes:
    """Provides standard 16kHz Int16 PCM audio frame (2048 bytes)."""
    return generate_pcm_16k(duration_ms=64, frequency=440.0)


@pytest.fixture
def pcm_16k_silence() -> bytes:
    """Provides standard 16kHz Int16 PCM silence frame (2048 bytes)."""
    return generate_silence_16k(duration_ms=64)


@pytest.fixture
def pcm_24k_chunk() -> bytes:
    """Provides standard 24kHz Int16 PCM audio frame (2400 bytes)."""
    return generate_pcm_24k(duration_ms=50, frequency=300.0)


@pytest.fixture
def avatar_image_path() -> str:
    """Returns absolute path to static/voice_avatar.png."""
    path = os.path.join(PROJECT_ROOT, "static", "voice_avatar.png")
    assert os.path.exists(path), f"Avatar image must exist at {path}"
    return path


@pytest.fixture
def study_html_path() -> str:
    """Returns absolute path to study.html."""
    path = os.path.join(PROJECT_ROOT, "study.html")
    assert os.path.exists(path), f"study.html must exist at {path}"
    return path
