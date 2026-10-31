"""
Academic KB Intelligent Study Engine — E2E Test Suite Conftest
Shared fixtures, environment helpers, database mocks, and dynamic module loaders.
"""

import os
import sys
import uuid
import pytest
import importlib
from typing import Generator, List, Dict, Any, Optional
from datetime import datetime, timezone

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Force offline mock provider by default for test deterministic isolation
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_PROVIDER", "mock")

from config.settings import get_settings, Settings
from core.database import Neo4jManager


# ---------------------------------------------------------------------------
# Dynamic Module Loader Helpers (Progressive Testability)
# ---------------------------------------------------------------------------

def get_study_module(module_name: str):
    """
    Dynamically loads an engine.study module if available, or returns None.
    Supports progressive testability across implementation milestones.
    """
    full_name = f"engine.study.{module_name}"
    try:
        if full_name in sys.modules:
            return sys.modules[full_name]
        return importlib.import_module(full_name)
    except (ImportError, ModuleNotFoundError):
        return None


def require_study_module(module_name: str, milestone: str = "M3"):
    """
    Skips the current test if the requested engine.study module is not yet implemented.
    """
    mod = get_study_module(module_name)
    if mod is None:
        pytest.skip(f"engine.study.{module_name} is not yet implemented ({milestone})")
    return mod


# ---------------------------------------------------------------------------
# Fixtures: Settings & Database
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Provides test-configured settings instance."""
    settings = get_settings()
    return settings


@pytest.fixture(scope="session")
def neo4j_manager(test_settings) -> Generator[Neo4jManager, None, None]:
    """
    Provides a connected Neo4jManager instance.
    Skips gracefully if Neo4j is offline.
    """
    db = Neo4jManager(
        uri=test_settings.neo4j_uri,
        user=test_settings.neo4j_username,
        password=test_settings.neo4j_password,
        database=test_settings.neo4j_database
    )
    try:
        db.connect()
    except Exception as e:
        pytest.skip(f"Neo4j is not reachable at {test_settings.neo4j_uri}: {e}")
    
    yield db
    
    try:
        db.close()
    except Exception:
        pass


@pytest.fixture(scope="function")
def test_id() -> str:
    """Generates unique test run identifier."""
    return f"test_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="function")
def clean_test_labels(neo4j_manager, test_id) -> Generator[str, None, None]:
    """
    Yields test_id and cleans up any nodes tagged with test_id after the test.
    """
    yield test_id
    try:
        neo4j_manager.execute_query(
            "MATCH (n) WHERE n.test_id = $test_id DETACH DELETE n",
            {"test_id": test_id}
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Fixtures: LLM Client
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def mock_llm_client():
    """
    Provides an LLMClient instance running MockProvider.
    Uses engine.study.llm_client if implemented, or fallback mock.
    """
    llm_module = get_study_module("llm_client")
    if llm_module and hasattr(llm_module, "MockProvider"):
        return llm_module.MockProvider()
    elif llm_module and hasattr(llm_module, "get_llm_client"):
        return llm_module.get_llm_client()
    
    # Fallback specification-compliant mock if M2 is still compiling
    class SpecMockLLMClient:
        def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
            lower = prompt.lower()
            if "domande" in lower or "question" in lower:
                return (
                    '[\n'
                    '  {\n'
                    '    "question": "What is the primary vulnerability in WEP?",\n'
                    '    "answer": "Reuse of RC4 Initialization Vectors (IVs) allowing key recovery.",\n'
                    '    "type": "multiple_choice",\n'
                    '    "difficulty": "medium",\n'
                    '    "source_chunks": ["chunk-wep-001"],\n'
                    '    "options": ["A. Short 24-bit IV reuse", "B. AES key exhaustion", "C. RSA padding oracle", "D. SHA-1 collision"],\n'
                    '    "correct_option": "A"\n'
                    '  }\n'
                    ']'
                )
            elif "flashcard" in lower:
                return (
                    '[\n'
                    '  {\n'
                    '    "question": "Explain WEP IV collision.",\n'
                    '    "answer": "A 24-bit IV means collisions occur within 2^12 frames (birthday paradox), exposing keystreams.",\n'
                    '    "source_chunk_id": "chunk-wep-001"\n'
                    '  }\n'
                    ']'
                )
            elif "concept" in lower:
                return (
                    '[\n'
                    '  {\n'
                    '    "name": "WEP",\n'
                    '    "description": "Wired Equivalent Privacy protocol",\n'
                    '    "aliases": ["802.11b Security"],\n'
                    '    "courses": ["CNS"]\n'
                    '  }\n'
                    ']'
                )
            elif "learning_path" in lower or "prerequisite" in lower:
                return (
                    '{\n'
                    '  "topic": "WPA3",\n'
                    '  "prerequisites": ["Symmetric Cryptography", "WEP Flaws", "WPA2 4-Way Handshake"],\n'
                    '  "steps": [\n'
                    '    {"order": 1, "concept": "Symmetric Cryptography", "description": "Stream and block ciphers"},\n'
                    '    {"order": 2, "concept": "WEP Flaws", "description": "IV collisions and FMS attack"},\n'
                    '    {"order": 3, "concept": "WPA2 4-Way Handshake", "description": "KRACK and offline dictionary attacks"},\n'
                    '    {"order": 4, "concept": "WPA3 SAE Handshake", "description": "Dragonfly key exchange"}\n'
                    '  ]\n'
                    '}'
                )
            elif "thesis" in lower or "outline" in lower:
                return (
                    '{\n'
                    '  "title": "Modern Wireless Security",\n'
                    '  "sections": [\n'
                    '    {\n'
                    '      "title": "1. Introduction to 802.11 Protocols",\n'
                    '      "subsections": ["1.1 Architecture", "1.2 Frame Types"],\n'
                    '      "citations": ["chunk-wep-001"],\n'
                    '      "draft": "Wireless networks communicate via radio frames requiring link-layer encryption."\n'
                    '    }\n'
                    '  ]\n'
                    '}'
                )
            elif "expand" in lower or "synonym" in lower:
                return '["WEP", "802.11b", "RC4 stream cipher", "IV collisions", "Fluhrer-Mantin-Shamir"]'
            return "{}"

    return SpecMockLLMClient()


# ---------------------------------------------------------------------------
# Fixtures: Sample KB Data
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def sample_study_chunks() -> List[Dict[str, Any]]:
    """Realistic academic KB chunks across multiple courses."""
    return [
        {
            "id": "chunk_cns_001",
            "course": "CNS",
            "source_title": "CNS_Lec04_Wireless_Security.pdf",
            "source_tier": "primary",
            "text": (
                "Wired Equivalent Privacy (WEP) uses the RC4 stream cipher with a 24-bit "
                "Initialization Vector (IV). Due to the birthday paradox, IV reuse occurs "
                "rapidly under heavy traffic, allowing Fluhrer-Mantin-Shamir (FMS) key recovery attacks."
            ),
            "concepts": ["WEP", "RC4", "Initialization Vector", "FMS Attack"]
        },
        {
            "id": "chunk_cns_002",
            "course": "CNS",
            "source_title": "CNS_Lec05_WPA2_WPA3.pdf",
            "source_tier": "primary",
            "text": (
                "WPA2 replaces WEP with CCMP based on AES-128. However, the 4-way handshake "
                "is vulnerable to offline dictionary attacks and the Key Reinstallation Attack (KRACK). "
                "WPA3 introduces Simultaneous Authentication of Equals (SAE) using the Dragonfly handshake."
            ),
            "concepts": ["WPA2", "CCMP", "AES", "KRACK", "WPA3", "SAE"]
        },
        {
            "id": "chunk_sdcc_001",
            "course": "SDCC",
            "source_title": "SDCC_Lec08_Consensus_Raft.pdf",
            "source_tier": "primary",
            "text": (
                "The Raft consensus algorithm decomposes state machine replication into "
                "leader election, log replication, and safety. A candidate requires votes from "
                "a majority quorum to become leader."
            ),
            "concepts": ["Raft", "Consensus", "Leader Election", "Quorum"]
        },
        {
            "id": "chunk_sdcc_002",
            "course": "SDCC",
            "source_title": "SDCC_Lec09_Paxos.pdf",
            "source_tier": "primary",
            "text": (
                "Paxos achieves consensus in asynchronous networks with crash failures through "
                "Prepare/Promise and Propose/Accept phases. Paxos guarantees safety but can suffer from "
                "dueling proposers (livelock)."
            ),
            "concepts": ["Paxos", "Consensus", "Livelock", "Quorum"]
        },
        {
            "id": "chunk_gap_sparse",
            "course": "CNS",
            "source_title": "CNS_Lec12_Quantum_Crypto.pdf",
            "source_tier": "primary",
            "text": "Introductory note on Quantum Key Distribution BB84.",
            "concepts": ["QKD", "BB84"]
        }
    ]
