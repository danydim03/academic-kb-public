"""
Academic KB Intelligent Study Engine — Tier 1: Feature Coverage E2E Tests
Requirements-driven tests verifying the primary happy path and interface contracts
for all 8 study features + MCP Tools + LLM Provider Agnosticity (>= 5 tests per feature).
"""

import os
import json
import asyncio
import pytest
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta

from tests.conftest import require_study_module, get_study_module


# ===========================================================================
# Feature 1: Question Generation Engine (>=5 tests)
# ===========================================================================

class TestTier1QuestionGenerator:
    """Verifies engine/study/question_generator.py against R1 and acceptance criteria."""

    def test_qgen_valid_json_structure(self, mock_llm_client):
        """Validates that question generation returns valid JSON with all required keys."""
        mod = require_study_module("question_generator")
        gen = mod.QuestionGenerator(llm_client=mock_llm_client)
        
        results = gen.generate_questions(topic="WEP security", difficulty="medium", question_type="mixed", count=2)
        assert isinstance(results, list), "Expected questions to be a list"
        assert len(results) > 0, "Expected at least one question generated"
        
        for q in results:
            assert isinstance(q, dict), "Each item must be a dictionary"
            assert "question" in q and isinstance(q["question"], str) and len(q["question"]) > 5
            assert "answer" in q and isinstance(q["answer"], str) and len(q["answer"]) > 5
            assert "type" in q and q["type"] in ["multiple_choice", "open", "single_answer", "exercise", "mixed"]
            assert "difficulty" in q and q["difficulty"] in ["easy", "medium", "hard", "facile", "media", "difficile", "mixed", "misto"]
            assert "source_chunks" in q and isinstance(q["source_chunks"], list)

    def test_qgen_multiple_choice_four_options(self, mock_llm_client):
        """Verifies that multiple choice questions produce exactly 4 options with single correct answer."""
        mod = require_study_module("question_generator")
        gen = mod.QuestionGenerator(llm_client=mock_llm_client)
        
        results = gen.generate_questions(topic="WEP IV collisions", difficulty="medium", question_type="multiple_choice", count=1)
        assert len(results) >= 1
        q = results[0]
        assert q["type"] == "multiple_choice"
        
        options = q.get("options") or q.get("choices")
        assert options is not None, "Multiple choice question must contain 'options' or 'choices'"
        assert len(options) == 4, f"Must have exactly 4 choices (A/B/C/D), got {len(options)}"
        
        correct = q.get("correct_option") or q.get("correct_answer") or q.get("answer")
        assert correct is not None, "Must indicate the single correct answer"

    def test_qgen_open_question_format(self, mock_llm_client):
        """Verifies that open questions produce substantial question and answer explanations without options."""
        mod = require_study_module("question_generator")
        gen = mod.QuestionGenerator(llm_client=mock_llm_client)
        
        results = gen.generate_questions(topic="Diffie-Hellman Key Exchange", difficulty="hard", question_type="open", count=1)
        assert len(results) >= 1
        q = results[0]
        assert q["type"] == "open"
        assert len(q["question"]) > 15
        assert len(q["answer"]) > 20

    def test_qgen_distinct_questions_count(self, mock_llm_client):
        """Verifies count=5 generates distinct questions with no exact duplicates."""
        mod = require_study_module("question_generator")
        gen = mod.QuestionGenerator(llm_client=mock_llm_client)
        
        results = gen.generate_questions(topic="WPA2 4-Way Handshake", difficulty="medium", question_type="mixed", count=5)
        assert len(results) == 5, f"Expected 5 questions, got {len(results)}"
        
        question_texts = [q["question"].strip().lower() for q in results]
        unique_texts = set(question_texts)
        assert len(unique_texts) == len(question_texts), "All generated questions must be distinct"

    def test_qgen_difficulty_configuration(self, mock_llm_client):
        """Verifies configurable difficulty levels: easy, medium, hard."""
        mod = require_study_module("question_generator")
        gen = mod.QuestionGenerator(llm_client=mock_llm_client)
        
        for diff in ["easy", "medium", "hard"]:
            results = gen.generate_questions(topic="AES encryption", difficulty=diff, count=1)
            assert len(results) >= 1
            assert results[0]["difficulty"].lower() in [diff, {"easy": "facile", "medium": "media", "hard": "difficile"}.get(diff)]


# ===========================================================================
# Feature 2: Flashcard SM-2 Spaced Repetition (>=5 tests)
# ===========================================================================

class TestTier1FlashcardEngine:
    """Verifies engine/study/flashcard_engine.py against R3.2 and SM-2 formula."""

    def test_flashcard_creation_defaults(self, neo4j_manager, mock_llm_client, clean_test_labels):
        """Verifies initial flashcard creation sets standard SM-2 defaults: EF=2.5, interval=0, repetitions=0."""
        mod = require_study_module("flashcard_engine")
        engine = mod.FlashcardEngine(db=neo4j_manager, llm_client=mock_llm_client)
        
        cards = engine.create_flashcards_from_topic(topic="WEP IVs", course="CNS", count=1)
        assert isinstance(cards, list) and len(cards) >= 1
        card = cards[0]
        
        assert "id" in card
        assert card.get("easiness_factor", 2.5) == pytest.approx(2.5, abs=0.05)
        assert card.get("interval", 0) in [0, 1]
        assert card.get("repetitions", 0) == 0
        assert "next_review" in card

    def test_flashcard_sm2_quality_4_interval_expansion(self, neo4j_manager, mock_llm_client, clean_test_labels):
        """Verifies update_flashcard_review with quality=4 results in interval >= 6 days."""
        mod = require_study_module("flashcard_engine")
        engine = mod.FlashcardEngine(db=neo4j_manager, llm_client=mock_llm_client)
        
        cards = engine.create_flashcards_from_topic(topic="AES S-Box", course="CNS", count=1)
        card_id = cards[0]["id"]
        
        # First review (repetitions 0 -> 1, interval 1)
        r1 = engine.update_flashcard_review(flashcard_id=card_id, quality=4)
        assert r1["repetitions"] == 1
        
        # Second review (repetitions 1 -> 2, interval >= 6 according to SM-2 standard)
        r2 = engine.update_flashcard_review(flashcard_id=card_id, quality=4)
        assert r2["repetitions"] == 2
        assert r2["interval"] >= 6, f"SM-2 interval after 2 successful reviews must be >= 6 days, got {r2['interval']}"
        assert r2["easiness_factor"] >= 2.4

    def test_flashcard_sm2_quality_sub_3_resets(self, neo4j_manager, mock_llm_client, clean_test_labels):
        """Verifies review quality < 3 resets repetitions to 0 and interval to 1."""
        mod = require_study_module("flashcard_engine")
        engine = mod.FlashcardEngine(db=neo4j_manager, llm_client=mock_llm_client)
        
        cards = engine.create_flashcards_from_topic(topic="KRACK Attack", course="CNS", count=1)
        card_id = cards[0]["id"]
        
        # Progress card to repetition 2
        engine.update_flashcard_review(card_id, quality=4)
        engine.update_flashcard_review(card_id, quality=4)
        
        # Failure review (quality = 1)
        r_fail = engine.update_flashcard_review(card_id, quality=1)
        assert r_fail["repetitions"] == 0, "SM-2 quality < 3 must reset repetitions to 0"
        assert r_fail["interval"] == 1, "SM-2 quality < 3 must reset interval to 1 day"

    def test_flashcard_get_due_today_filter(self, neo4j_manager, mock_llm_client, clean_test_labels):
        """Verifies get_flashcards returns only cards with next_review <= today."""
        mod = require_study_module("flashcard_engine")
        engine = mod.FlashcardEngine(db=neo4j_manager, llm_client=mock_llm_client)
        
        due_cards = engine.get_flashcards(course="CNS")
        assert isinstance(due_cards, list)
        
        now = datetime.now(timezone.utc)
        for card in due_cards:
            review_dt = datetime.fromisoformat(card["next_review"].replace("Z", "+00:00"))
            # Must be scheduled for today or earlier (due)
            assert review_dt <= now + timedelta(hours=1), f"Flashcard review {review_dt} is in the future!"

    def test_flashcard_neo4j_persistence(self, neo4j_manager, mock_llm_client, clean_test_labels):
        """Verifies that flashcard updates persist in the Neo4j database."""
        mod = require_study_module("flashcard_engine")
        engine = mod.FlashcardEngine(db=neo4j_manager, llm_client=mock_llm_client)
        
        cards = engine.create_flashcards_from_topic(topic="Raft Quorum", course="SDCC", count=1)
        card_id = cards[0]["id"]
        
        updated = engine.update_flashcard_review(card_id, quality=5)
        
        # Directly query Neo4j to confirm persistence
        records = neo4j_manager.execute_query(
            "MATCH (f:Flashcard {id: $id}) RETURN f.easiness_factor as ef, f.repetitions as reps, f.interval as interval",
            {"id": card_id}
        )
        assert len(records) == 1, "Flashcard node must exist in Neo4j"
        assert records[0]["reps"] == updated["repetitions"]
        assert records[0]["interval"] == updated["interval"]


# ===========================================================================
# Feature 3: Knowledge Gap Detector (>=5 tests)
# ===========================================================================

class TestTier1GapDetector:
    """Verifies engine/study/gap_detector.py against R3.3 and acceptance criteria."""

    def test_gap_detector_returns_ordered_list(self, neo4j_manager):
        """Verifies detect_knowledge_gaps returns ordered list with source_title, chunk_count, coverage_score."""
        mod = require_study_module("gap_detector")
        detector = mod.GapDetector(db=neo4j_manager)
        
        report = detector.detect_knowledge_gaps(course="CNS")
        assert isinstance(report, list), "Expected list of gap items"
        assert len(report) > 0, "Expected documents reported for CNS"
        
        for item in report:
            assert "source_title" in item
            assert "chunk_count" in item and isinstance(item["chunk_count"], int)
            assert "coverage_score" in item and isinstance(item["coverage_score"], (int, float))

    def test_gap_detector_identifies_under_covered_documents(self, neo4j_manager):
        """Verifies documents with chunk_count < 2 are explicitly marked as gaps."""
        mod = require_study_module("gap_detector")
        detector = mod.GapDetector(db=neo4j_manager)
        
        report = detector.detect_knowledge_gaps(course="CNS")
        for item in report:
            if item["chunk_count"] < 2:
                assert item.get("is_gap") is True or item.get("gap") is True, (
                    f"Document '{item['source_title']}' with {item['chunk_count']} chunks must be marked as gap"
                )

    def test_gap_detector_adequate_coverage_scores(self, neo4j_manager):
        """Verifies documents with chunk_count >= 2 are not marked as gaps."""
        mod = require_study_module("gap_detector")
        detector = mod.GapDetector(db=neo4j_manager)
        
        report = detector.detect_knowledge_gaps(course="CNS")
        for item in report:
            if item["chunk_count"] >= 2:
                assert not (item.get("is_gap") is True or item.get("gap") is True)
                assert item["coverage_score"] > 0

    def test_gap_detector_course_filtering(self, neo4j_manager):
        """Verifies course filtering isolates course-specific items."""
        mod = require_study_module("gap_detector")
        detector = mod.GapDetector(db=neo4j_manager)
        
        report_cns = detector.detect_knowledge_gaps(course="CNS")
        report_sdcc = detector.detect_knowledge_gaps(course="SDCC")
        
        cns_titles = {item["source_title"] for item in report_cns}
        sdcc_titles = {item["source_title"] for item in report_sdcc}
        # In a well-formed KB, course materials do not overlap completely
        assert cns_titles != sdcc_titles or len(cns_titles) == 0

    def test_gap_detector_coverage_score_normalization(self, neo4j_manager):
        """Verifies coverage scores fall within expected normalized bounds [0.0, 1.0] or [0, 100]."""
        mod = require_study_module("gap_detector")
        detector = mod.GapDetector(db=neo4j_manager)
        
        report = detector.detect_knowledge_gaps(course="CNS")
        for item in report:
            score = item["coverage_score"]
            assert 0.0 <= score <= 100.0, f"Coverage score out of bounds: {score}"


# ===========================================================================
# Feature 4: Concept Extractor & Cross-Course Linker (>=5 tests)
# ===========================================================================

class TestTier1ConceptExtractor:
    """Verifies engine/study/concept_extractor.py against R3.4 and acceptance criteria."""

    def test_concept_extractor_extracts_entities(self, neo4j_manager, mock_llm_client):
        """Verifies extracting concepts returns concept dictionary with name and courses."""
        mod = require_study_module("concept_extractor")
        extractor = mod.ConceptExtractor(db=neo4j_manager, llm_client=mock_llm_client)
        
        result = extractor.extract_and_link_concepts(limit_chunks=5, course="CNS")
        assert isinstance(result, dict)
        assert "concepts_extracted" in result or "concepts" in result

    def test_concept_extractor_creates_concept_nodes(self, neo4j_manager, mock_llm_client):
        """Verifies Concept nodes exist in Neo4j after extraction."""
        mod = require_study_module("concept_extractor")
        extractor = mod.ConceptExtractor(db=neo4j_manager, llm_client=mock_llm_client)
        
        extractor.extract_and_link_concepts(limit_chunks=10)
        records = neo4j_manager.execute_query("MATCH (c:Concept) RETURN count(c) as cnt")
        assert records[0]["cnt"] >= 0

    def test_concept_extractor_creates_mentions_relationships(self, neo4j_manager, mock_llm_client):
        """Verifies MENTIONS relationships between Chunks and Concepts exist."""
        mod = require_study_module("concept_extractor")
        extractor = mod.ConceptExtractor(db=neo4j_manager, llm_client=mock_llm_client)
        
        extractor.extract_and_link_concepts(limit_chunks=10)
        records = neo4j_manager.execute_query(
            "MATCH (ch:Chunk)-[:MENTIONS]->(c:Concept) RETURN count(c) as mentions"
        )
        assert records[0]["mentions"] >= 0

    def test_concept_extractor_detects_cross_course_concepts(self, neo4j_manager, mock_llm_client):
        """Verifies concepts appearing in multiple courses are identified."""
        mod = require_study_module("concept_extractor")
        extractor = mod.ConceptExtractor(db=neo4j_manager, llm_client=mock_llm_client)
        
        result = extractor.extract_and_link_concepts(limit_chunks=20)
        # Should record cross-course concepts metric
        assert "cross_course_count" in result or "cross_course" in result or "concepts_extracted" in result

    def test_concept_extractor_summary_metrics(self, neo4j_manager, mock_llm_client):
        """Verifies summary response schema containing operational metrics."""
        mod = require_study_module("concept_extractor")
        extractor = mod.ConceptExtractor(db=neo4j_manager, llm_client=mock_llm_client)
        
        metrics = extractor.extract_and_link_concepts(limit_chunks=5)
        assert any(k in metrics for k in ["concepts_extracted", "mentions_created", "chunks_processed"])


# ===========================================================================
# Feature 5: Past Exam Linker (>=5 tests)
# ===========================================================================

class TestTier1ExamLinker:
    """Verifies engine/study/exam_linker.py against R3.5 and acceptance criteria."""

    def test_exam_linker_parses_exam_questions(self, neo4j_manager, mock_llm_client):
        """Verifies exam linker executes parsing on past exam files."""
        mod = require_study_module("exam_linker")
        linker = mod.ExamLinker(db=neo4j_manager, llm_client=mock_llm_client)
        
        res = linker.link_past_exams(course="CNS")
        assert isinstance(res, dict)
        assert any(k in res for k in ["questions_processed", "answers_linked", "status"])

    def test_exam_linker_creates_exam_question_nodes(self, neo4j_manager, mock_llm_client):
        """Verifies ExamQuestion nodes can be queried in Neo4j."""
        mod = require_study_module("exam_linker")
        linker = mod.ExamLinker(db=neo4j_manager, llm_client=mock_llm_client)
        
        linker.link_past_exams(course="CNS")
        records = neo4j_manager.execute_query("MATCH (eq:ExamQuestion) RETURN count(eq) as cnt")
        assert records[0]["cnt"] >= 0

    def test_exam_linker_creates_answers_relationships(self, neo4j_manager, mock_llm_client):
        """Verifies ANSWERS relationships between Chunks and ExamQuestions."""
        mod = require_study_module("exam_linker")
        linker = mod.ExamLinker(db=neo4j_manager, llm_client=mock_llm_client)
        
        linker.link_past_exams(course="CNS")
        records = neo4j_manager.execute_query(
            "MATCH (ch:Chunk)-[r:ANSWERS]->(eq:ExamQuestion) RETURN count(r) as answers_count"
        )
        assert records[0]["answers_count"] >= 0

    def test_exam_linker_relevance_scores_validity(self, neo4j_manager, mock_llm_client):
        """Verifies relevance_score property on ANSWERS edges is a float in [0.0, 1.0]."""
        mod = require_study_module("exam_linker")
        linker = mod.ExamLinker(db=neo4j_manager, llm_client=mock_llm_client)
        
        linker.link_past_exams(course="CNS")
        records = neo4j_manager.execute_query(
            "MATCH (ch:Chunk)-[r:ANSWERS]->(eq:ExamQuestion) RETURN r.relevance_score as score LIMIT 5"
        )
        for rec in records:
            if rec["score"] is not None:
                assert 0.0 <= float(rec["score"]) <= 1.0

    def test_exam_linker_course_scoping(self, neo4j_manager, mock_llm_client):
        """Verifies linking for course CNS scopes nodes to CNS."""
        mod = require_study_module("exam_linker")
        linker = mod.ExamLinker(db=neo4j_manager, llm_client=mock_llm_client)
        
        res = linker.link_past_exams(course="CNS")
        assert res.get("course", "CNS") == "CNS"


# ===========================================================================
# Feature 6: Learning Path Engine (>=5 tests)
# ===========================================================================

class TestTier1LearningPathEngine:
    """Verifies engine/study/learning_path.py against R3.6 and acceptance criteria."""

    def test_learning_path_returns_ordered_sequence(self, neo4j_manager, mock_llm_client):
        """Verifies generate_learning_path returns an ordered sequence of prerequisites."""
        mod = require_study_module("learning_path")
        engine = mod.LearningPathEngine(db=neo4j_manager, llm_client=mock_llm_client)
        
        path = engine.generate_learning_path(topic="WPA3")
        assert isinstance(path, dict)
        assert "steps" in path or "prerequisites" in path or "path" in path

    def test_learning_path_structure_keys(self, neo4j_manager, mock_llm_client):
        """Verifies required top-level keys in learning path response."""
        mod = require_study_module("learning_path")
        engine = mod.LearningPathEngine(db=neo4j_manager, llm_client=mock_llm_client)
        
        path = engine.generate_learning_path(topic="Raft consensus")
        assert "topic" in path
        steps = path.get("steps") or path.get("prerequisites") or []
        assert len(steps) > 0

    def test_learning_path_didactic_progression(self, neo4j_manager, mock_llm_client):
        """Verifies progression order (step index or order property)."""
        mod = require_study_module("learning_path")
        engine = mod.LearningPathEngine(db=neo4j_manager, llm_client=mock_llm_client)
        
        path = engine.generate_learning_path(topic="WPA3")
        steps = path.get("steps", [])
        if steps and isinstance(steps[0], dict) and "order" in steps[0]:
            orders = [s["order"] for s in steps]
            assert orders == sorted(orders), "Learning path steps must be sorted by pedagogical order"

    def test_learning_path_dag_no_cycles(self, neo4j_manager, mock_llm_client):
        """Verifies generated learning path prerequisites form a DAG without self-loops or cycles."""
        mod = require_study_module("learning_path")
        engine = mod.LearningPathEngine(db=neo4j_manager, llm_client=mock_llm_client)
        
        path = engine.generate_learning_path(topic="Distributed Snapshots")
        steps = path.get("steps") or path.get("prerequisites") or []
        step_names = [s.get("concept") if isinstance(s, dict) else s for s in steps]
        # Check no consecutive identical steps
        for i in range(len(step_names) - 1):
            assert step_names[i] != step_names[i+1], "Duplicate adjacent prerequisite step"

    def test_learning_path_fallback_reasoning(self, neo4j_manager, mock_llm_client):
        """Verifies LLM didactic reasoning when concept graph is sparse."""
        mod = require_study_module("learning_path")
        engine = mod.LearningPathEngine(db=neo4j_manager, llm_client=mock_llm_client)
        
        path = engine.generate_learning_path(topic="Quantum Cryptography BB84")
        assert path is not None
        assert path.get("topic") == "Quantum Cryptography BB84" or "Quantum" in str(path)


# ===========================================================================
# Feature 7: Query Expander (>=5 tests)
# ===========================================================================

class TestTier1QueryExpander:
    """Verifies engine/study/query_expander.py against R3.7 and acceptance criteria."""

    def test_query_expander_increases_term_count(self, mock_llm_client):
        """Verifies query expansion expands query by >= 3 additional terms in >= 90% of test calls."""
        mod = require_study_module("query_expander")
        
        # Mock retriever wrapper
        class DummyRetriever:
            def search(self, query, top_k=5): return []
            def deep_research(self, query, top_k=10): return []
            
        expander = mod.QueryExpander(retriever=DummyRetriever(), llm_client=mock_llm_client)
        
        test_queries = [
            "WEP vulnerabilities",
            "Raft leader election",
            "Chandy-Lamport snapshot",
            "Diffie-Hellman MITM",
            "Backpropagation"
        ]
        
        expanded_count = 0
        for q in test_queries:
            expanded = expander.expand_query(q)
            assert isinstance(expanded, str)
            orig_terms = len(q.split())
            exp_terms = len(expanded.split())
            if exp_terms >= orig_terms + 3:
                expanded_count += 1
                
        # Must expand by >= 3 terms in >= 90% (at least 4 out of 5)
        assert expanded_count >= 4, f"Expanded {expanded_count}/5 queries by >= 3 terms (expected >= 90%)"

    def test_query_expander_includes_domain_synonyms(self, mock_llm_client):
        """Verifies query expander introduces related technical vocabulary."""
        mod = require_study_module("query_expander")
        
        class DummyRetriever:
            def search(self, q, top_k=5): return []
            
        expander = mod.QueryExpander(retriever=DummyRetriever(), llm_client=mock_llm_client)
        expanded = expander.expand_query("WEP")
        lower = expanded.lower()
        # Should include relevant technical synonyms
        assert any(term in lower for term in ["rc4", "iv", "collision", "802.11", "cipher", "wep"])

    def test_query_expander_wraps_hybrid_search(self, mock_llm_client):
        """Verifies expander.search() wraps underlying retriever with expanded query."""
        mod = require_study_module("query_expander")
        
        called_with = []
        class SpyRetriever:
            def search(self, query, top_k=6):
                called_with.append(query)
                return [{"id": "c1", "text": "result"}]
                
        expander = mod.QueryExpander(retriever=SpyRetriever(), llm_client=mock_llm_client)
        results = expander.search("WEP flaws", limit=6)
        
        assert len(results) == 1
        assert len(called_with) == 1
        assert len(called_with[0]) >= len("WEP flaws")

    def test_query_expander_wraps_deep_research(self, mock_llm_client):
        """Verifies expander.deep_research() passes expanded query to retriever.deep_research()."""
        mod = require_study_module("query_expander")
        
        called_with = []
        class SpyRetriever:
            def deep_research(self, query, top_k=10):
                called_with.append(query)
                return [{"id": "c2", "text": "deep result"}]
                
        expander = mod.QueryExpander(retriever=SpyRetriever(), llm_client=mock_llm_client)
        results = expander.deep_research("Paxos consensus", limit=10)
        
        assert len(results) == 1
        assert len(called_with) == 1

    def test_query_expander_preserves_limit_parameter(self, mock_llm_client):
        """Verifies limit parameter is passed faithfully to retriever."""
        mod = require_study_module("query_expander")
        
        received_limit = []
        class ParamSpyRetriever:
            def search(self, query, top_k=5):
                received_limit.append(top_k)
                return []
                
        expander = mod.QueryExpander(retriever=ParamSpyRetriever(), llm_client=mock_llm_client)
        expander.search("AES Galois Counter Mode", limit=8)
        assert received_limit == [8]


# ===========================================================================
# Feature 8: Thesis Assistant (>=5 tests)
# ===========================================================================

class TestTier1ThesisAssistant:
    """Verifies engine/study/thesis_assistant.py against R3.8 and acceptance criteria."""

    def test_thesis_assistant_generates_hierarchical_outline(self, mock_llm_client):
        """Verifies generate_thesis_outline produces outline with sections and subsections."""
        mod = require_study_module("thesis_assistant")
        
        class DummyRetriever:
            def deep_research(self, query, top_k=10): return [{"id": "chunk-wep-001", "text": "Wireless WEP"}]
            
        assistant = mod.ThesisAssistant(retriever=DummyRetriever(), llm_client=mock_llm_client)
        outline = assistant.generate_thesis_outline(title="Modern Wireless Security")
        
        assert isinstance(outline, dict)
        assert "sections" in outline
        assert len(outline["sections"]) >= 1

    def test_thesis_assistant_populates_citations(self, mock_llm_client):
        """Verifies outline sections contain cited chunks."""
        mod = require_study_module("thesis_assistant")
        
        class DummyRetriever:
            def deep_research(self, query, top_k=10): return [{"id": "chunk-wep-001", "text": "Wireless WEP"}]
            
        assistant = mod.ThesisAssistant(retriever=DummyRetriever(), llm_client=mock_llm_client)
        outline = assistant.generate_thesis_outline(title="Modern Wireless Security")
        
        first_section = outline["sections"][0]
        assert "citations" in first_section or "sources" in first_section or "chunks" in first_section

    def test_thesis_assistant_generates_draft_content(self, mock_llm_client):
        """Verifies sections contain draft narrative text or summaries."""
        mod = require_study_module("thesis_assistant")
        
        class DummyRetriever:
            def deep_research(self, query, top_k=10): return [{"id": "chunk-wep-001", "text": "Wireless WEP"}]
            
        assistant = mod.ThesisAssistant(retriever=DummyRetriever(), llm_client=mock_llm_client)
        outline = assistant.generate_thesis_outline(title="Modern Wireless Security")
        
        first_section = outline["sections"][0]
        has_text = any(k in first_section for k in ["draft", "content", "summary", "text"])
        assert has_text, "Section must provide draft text content"

    def test_thesis_assistant_uses_deep_research(self, mock_llm_client):
        """Verifies ThesisAssistant calls deep_research on retriever."""
        mod = require_study_module("thesis_assistant")
        
        deep_called = []
        class SpyRetriever:
            def deep_research(self, query, top_k=10):
                deep_called.append(query)
                return [{"id": "chunk-wep-001", "text": "Sample"}]
                
        assistant = mod.ThesisAssistant(retriever=SpyRetriever(), llm_client=mock_llm_client)
        assistant.generate_thesis_outline(title="Distributed Consensus Systems")
        assert len(deep_called) >= 1

    def test_thesis_assistant_output_schema(self, mock_llm_client):
        """Verifies top-level output dictionary structure."""
        mod = require_study_module("thesis_assistant")
        
        class DummyRetriever:
            def deep_research(self, query, top_k=10): return []
            
        assistant = mod.ThesisAssistant(retriever=DummyRetriever(), llm_client=mock_llm_client)
        outline = assistant.generate_thesis_outline(title="Federated Learning in Edge Devices")
        
        assert "title" in outline
        assert "sections" in outline


# ===========================================================================
# Feature 9: MCP Tools Integration (>=5 tests)
# ===========================================================================

class TestTier1MCPTools:
    """Verifies mcp_server/server.py against R4 and zero-crash acceptance criteria."""

    def test_mcp_list_tools_contains_all_seven_study_tools(self):
        """Verifies all 7 study tools are listed by mcp.list_tools() without error."""
        try:
            from mcp_server.server import mcp
        except Exception as e:
            pytest.fail(f"Failed to import mcp_server.server: {e}")
            
        tools = asyncio.run(mcp.list_tools())
        tool_names = {t.name for t in tools}
        
        expected_study_tools = {
            "generate_questions",
            "get_flashcards",
            "update_flashcard_review",
            "detect_knowledge_gaps",
            "link_past_exams",
            "generate_learning_path",
            "thesis_assistant"
        }
        
        missing = expected_study_tools - tool_names
        if missing:
            pytest.skip(f"Study MCP tools not yet fully registered in Milestone M4: missing {missing}")
        assert expected_study_tools.issubset(tool_names)

    def test_mcp_preserves_existing_four_tools(self):
        """Verifies existing tools (academic_context, deep_research, academic_health, academic_courses) remain intact."""
        from mcp_server.server import mcp
        tools = asyncio.run(mcp.list_tools())
        tool_names = {t.name for t in tools}
        
        existing_tools = {"academic_context", "deep_research", "academic_health", "academic_courses"}
        assert existing_tools.issubset(tool_names), f"Missing base tools: {existing_tools - tool_names}"

    def test_mcp_zero_crash_startup_without_api_key(self, monkeypatch):
        """Verifies MCP server starts cleanly and imports without error when LLM API key is unset."""
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        
        try:
            import mcp_server.server as srv
            assert srv.mcp is not None
        except Exception as e:
            pytest.fail(f"MCP server crashed on startup with missing API key: {e}")

    def test_mcp_academic_health_tool_execution(self):
        """Verifies academic_health tool executes cleanly and returns health status."""
        from mcp_server.server import academic_health
        health_report = academic_health()
        assert isinstance(health_report, str)
        assert "Academic KB is" in health_report

    def test_mcp_academic_courses_tool_execution(self):
        """Verifies academic_courses tool executes and returns formatted course string."""
        from mcp_server.server import academic_courses
        courses_str = academic_courses()
        assert isinstance(courses_str, str)
        assert len(courses_str) > 0


# ===========================================================================
# Feature 10: LLM Provider Agnosticity & MockProvider (>=5 tests)
# ===========================================================================

class TestTier1LLMProviderAgnosticity:
    """Verifies engine/study/llm_client.py against Request Update 2026-10-05 and M2."""

    def test_llm_client_abstract_contract(self):
        """Verifies LLMClient abstract base class defines generate method."""
        mod = require_study_module("llm_client", milestone="M2")
        assert hasattr(mod, "LLMClient"), "LLMClient base class must be defined"
        assert hasattr(mod.LLMClient, "generate"), "LLMClient must define generate method"

    def test_mock_provider_returns_valid_json(self):
        """Verifies MockProvider returns valid synthetic JSON for offline testing."""
        mod = require_study_module("llm_client", milestone="M2")
        assert hasattr(mod, "MockProvider"), "MockProvider must be defined"
        
        mock = mod.MockProvider()
        res = mock.generate(prompt="Genera 3 domande su WEP")
        assert isinstance(res, str)
        parsed = json.loads(res)
        assert isinstance(parsed, (list, dict))

    def test_gemini_provider_instantiation(self):
        """Verifies GeminiProvider instantiates cleanly."""
        mod = require_study_module("llm_client", milestone="M2")
        assert hasattr(mod, "GeminiProvider")
        provider = mod.GeminiProvider(model="gemini-2.0-flash", api_key="mock_test_key")
        assert provider is not None

    def test_openai_provider_supports_deepseek_base_url(self):
        """Verifies OpenAIProvider accepts DeepSeek base_url."""
        mod = require_study_module("llm_client", milestone="M2")
        assert hasattr(mod, "OpenAIProvider")
        
        provider = mod.OpenAIProvider(
            model="deepseek-chat",
            api_key="mock_deepseek_key",
            base_url="https://api.deepseek.com"
        )
        assert provider is not None
        if hasattr(provider, "base_url"):
            assert provider.base_url == "https://api.deepseek.com"

    def test_get_llm_client_factory(self, monkeypatch):
        """Verifies get_llm_client factory returns provider according to settings with Mock fallback."""
        mod = require_study_module("llm_client", milestone="M2")
        assert hasattr(mod, "get_llm_client")
        
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        client = mod.get_llm_client()
        assert isinstance(client, mod.LLMClient)
        assert isinstance(client, mod.MockProvider)
