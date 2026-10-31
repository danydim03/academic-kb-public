"""
Academic KB Voice Studio — Tier 1 & Tier 2: Strict Grounding & Anti-Hallucination Tests
Verifies query_academic_kb tool schema (behavior: NON_BLOCKING), relevance threshold guard,
zero-hallucination declaration, citation delivery [Doc.pdf, p. X], and course isolation.
"""

import pytest
import asyncio
from typing import Dict, Any, List

from tests.voice.mock_live_server import (
    StrictGroundingGuard,
    AcademicDocChunk,
    GROUNDING_TOOL_SCHEMA,
    format_academic_citation,
)


# ===========================================================================
# Tier 1: Feature Coverage — Strict Grounding & Anti-Hallucination (>=5 tests)
# ===========================================================================

class TestTier1StrictGrounding:
    """Verifies tool declaration, citation schemas, formatting, and course isolation."""

    def test_grounding_tool_declaration_schema(self):
        """Validates that query_academic_kb tool declaration adheres to PROJECT.md."""
        schema = GROUNDING_TOOL_SCHEMA
        assert schema["name"] == "query_academic_kb"
        assert schema.get("behavior") == "NON_BLOCKING", "Must declare non-blocking behavior for audio stream safety"
        assert "description" in schema and len(schema["description"]) > 20
        
        params = schema["parameters"]
        assert params["type"] == "OBJECT"
        assert "query" in params["properties"]
        assert params["properties"]["query"]["type"] == "STRING"
        assert "course" in params["properties"]
        assert params["properties"]["course"]["type"] == "STRING"
        assert params["required"] == ["query"]

    def test_grounding_successful_retrieval_event(self, grounding_guard: StrictGroundingGuard):
        """Verifies that relevant query yields grounding event with valid citations and metadata."""
        res = grounding_guard.query("TLS 1.3 handshake latency", course="CNS")
        assert res["found"] is True
        assert res["k"] >= 1
        assert len(res["citations"]) == res["k"]
        
        c = res["citations"][0]
        assert "source" in c and c["source"].endswith(".pdf")
        assert "page" in c and isinstance(c["page"], int) and c["page"] > 0
        assert "course" in c and c["course"] == "CNS"
        assert "snippet" in c and len(c["snippet"]) > 10
        assert "citation_tag" in c

    def test_grounding_citation_formatting_with_page(self):
        """Verifies academic citation string format [Doc.pdf, p. X]."""
        tag = format_academic_citation("Sicurezza_Reti_TLS13.pdf", page=42)
        assert tag == "[Sicurezza_Reti_TLS13.pdf, p. 42]"

    def test_grounding_citation_formatting_without_page(self):
        """Verifies fallback citation string format [Doc.pdf] when page is omitted."""
        tag = format_academic_citation("Dispensa_Generale.pdf", page=None)
        assert tag == "[Dispensa_Generale.pdf]"
        
        tag_zero = format_academic_citation("Dispensa_Generale.pdf", page=0)
        assert tag_zero == "[Dispensa_Generale.pdf]"

    def test_grounding_course_scoping_isolation(self, grounding_guard: StrictGroundingGuard):
        """Verifies that querying with course='CNS' excludes chunks from 'ML' or other courses."""
        # Query a concept present in ML, but scoped to CNS
        res = grounding_guard.query("Support Vector Machines", course="CNS")
        # Should NOT return the ML chunk
        assert res["found"] is False or all(c["course"] == "CNS" for c in res["citations"])


# ===========================================================================
# Tier 2: Boundary & Corner Cases — Grounding & Anti-Hallucination (>=5 tests)
# ===========================================================================

class TestTier2StrictGroundingBoundaries:
    """Verifies zero-hallucination when knowledge is missing, low relevance, and edge queries."""

    def test_grounding_missing_concept_anti_hallucination(self, grounding_guard: StrictGroundingGuard):
        """Verifies that an unknown query explicitly returns found=False with zero hallucinated sources."""
        unknown_query = "Quantum warp drive propulsion in 802.11 beacons"
        res = grounding_guard.query(unknown_query, course="CNS")
        
        assert res["found"] is False
        assert res["k"] == 0
        assert len(res["citations"]) == 0
        assert "nessuna informazione" in res["message"].lower()

    def test_grounding_low_relevance_threshold_rejection(self):
        """Verifies that chunks below relevance threshold (0.60) are strictly pruned."""
        low_score_chunk = AcademicDocChunk(
            chunk_id="chunk-low-001",
            source_title="Unrelated_Doc.pdf",
            page=1,
            course="CNS",
            content="Some loosely related network words",
            score=0.45  # Below threshold 0.60
        )
        guard = StrictGroundingGuard(kb=[low_score_chunk], relevance_threshold=0.60)
        res = guard.query("network words", course="CNS")
        assert res["found"] is False
        assert res["k"] == 0

    def test_grounding_special_characters_in_query(self, grounding_guard: StrictGroundingGuard):
        """Verifies query handling with LaTeX math, punctuation, and Unicode Italian accents."""
        query_with_accents = "Qual è la proprietà fondamentale dell'IV in WEP?"
        res = grounding_guard.query(query_with_accents, course="CNS")
        assert isinstance(res, dict)
        assert "citations" in res
        # WEP chunk should be found
        assert res["found"] is True
        assert any("wep" in c["source"].lower() for c in res["citations"])

    def test_grounding_empty_query_string(self, grounding_guard: StrictGroundingGuard):
        """Verifies that empty or whitespace-only queries do not crash and return found=False."""
        res = grounding_guard.query("   ", course="CNS")
        assert res["found"] is False
        assert res["k"] == 0
        assert len(res["citations"]) == 0

    def test_grounding_citation_metadata_integrity(self, grounding_guard: StrictGroundingGuard):
        """Verifies that all retrieved citations have strictly valid structural types."""
        res = grounding_guard.query("WEP", course="CNS")
        assert res["found"] is True
        for c in res["citations"]:
            assert isinstance(c["source"], str) and len(c["source"]) > 0
            assert isinstance(c["page"], int) and c["page"] >= 1
            assert isinstance(c["course"], str) and len(c["course"]) > 0
            assert isinstance(c["snippet"], str) and len(c["snippet"]) > 0
            assert c["citation_tag"].startswith("[") and c["citation_tag"].endswith("]")
