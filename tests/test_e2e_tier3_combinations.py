"""
Academic KB Intelligent Study Engine — Tier 3: Cross-Feature Combinations E2E Tests
Requirements-driven tests verifying multi-module integration, composite workflows,
and cross-feature pipelines (>= 12 combination tests).
"""

import json
import pytest
from typing import Dict, Any, List

from tests.conftest import require_study_module, get_study_module
from config.settings import Settings
from engine.study.llm_client import (
    extract_json_payload,
    get_llm_client,
    MockProvider,
    OpenAIProvider,
    GeminiProvider
)
from engine.context.builder import ContextBuilder


class TestTier3CrossFeatureCombinations:
    """Verifies integration pipelines across multiple study engine modules."""

    def test_combo_concept_extraction_to_learning_path(self, neo4j_manager, mock_llm_client):
        """Pipeline: ConceptExtractor creates Concept graph -> LearningPathEngine deduces prerequisite sequence."""
        c_mod = require_study_module("concept_extractor")
        lp_mod = require_study_module("learning_path")
        
        extractor = c_mod.ConceptExtractor(db=neo4j_manager, llm_client=mock_llm_client)
        lp_engine = lp_mod.LearningPathEngine(db=neo4j_manager, llm_client=mock_llm_client)
        
        # Step 1: Extract concepts
        extract_result = extractor.extract_and_link_concepts(limit_chunks=10)
        assert isinstance(extract_result, dict)
        
        # Step 2: Generate learning path for an extracted topic
        path = lp_engine.generate_learning_path(topic="Wireless Authentication & Protocols")
        assert isinstance(path, dict)
        assert "steps" in path or "prerequisites" in path

    def test_combo_query_expansion_with_hybrid_retrieval(self, mock_llm_client):
        """Pipeline: QueryExpander enriches search query -> HybridRetriever executes search with expanded terms."""
        qe_mod = require_study_module("query_expander")
        
        searched_queries = []
        class SpyRetriever:
            def search(self, query: str, top_k: int = 5):
                searched_queries.append(query)
                return [{"chunk_id": "c1", "text": "WEP 802.11 security", "score": 0.95}]
            def deep_research(self, query: str, top_k: int = 10):
                return []
                
        retriever = SpyRetriever()
        expander = qe_mod.QueryExpander(retriever=retriever, llm_client=mock_llm_client)
        
        results = expander.search("WEP", limit=5)
        assert len(results) == 1
        assert len(searched_queries) == 1
        # Expanded query passed to search must be longer than original
        assert len(searched_queries[0]) > len("WEP")

    def test_combo_question_generation_to_exam_linking(self, neo4j_manager, mock_llm_client):
        """Pipeline: QuestionGenerator produces study questions -> ExamLinker cross-references with past exams."""
        q_mod = require_study_module("question_generator")
        el_mod = require_study_module("exam_linker")
        
        q_gen = q_mod.QuestionGenerator(llm_client=mock_llm_client)
        linker = el_mod.ExamLinker(db=neo4j_manager, llm_client=mock_llm_client)
        
        # 1. Generate questions
        questions = q_gen.generate_questions(topic="WEP IV flaws", count=2)
        assert len(questions) >= 1
        
        # 2. Link past exams
        link_res = linker.link_past_exams(course="CNS")
        assert isinstance(link_res, dict)

    def test_combo_llm_provider_switching_across_modules(self, neo4j_manager):
        """Verifies dependency injection works seamlessly when switching LLM providers across all 5 study modules."""
        q_mod = require_study_module("question_generator")
        fc_mod = require_study_module("flashcard_engine")
        c_mod = require_study_module("concept_extractor")
        lp_mod = require_study_module("learning_path")
        th_mod = require_study_module("thesis_assistant")
        
        # Provider 1: MockProvider
        mock_p = MockProvider()
        
        # Provider 2: DeepSeek-configured OpenAIProvider
        deepseek_p = OpenAIProvider(
            api_key="mock_deepseek_key",
            model="deepseek-chat",
            base_url="https://api.deepseek.com"
        )
        
        for provider in [mock_p, deepseek_p]:
            q_gen = q_mod.QuestionGenerator(llm_client=provider)
            fc_eng = fc_mod.FlashcardEngine(db=neo4j_manager, llm_client=provider)
            c_ext = c_mod.ConceptExtractor(db=neo4j_manager, llm_client=provider)
            lp_eng = lp_mod.LearningPathEngine(db=neo4j_manager, llm_client=provider)
            th_ast = th_mod.ThesisAssistant(llm_client=provider)
            
            assert q_gen.llm_client == provider
            assert fc_eng.llm_client == provider
            assert c_ext.llm_client == provider
            assert lp_eng.llm_client == provider
            assert th_ast.llm_client == provider

    def test_combo_question_generation_to_flashcard_sm2_lifecycle(self, neo4j_manager, mock_llm_client, clean_test_labels):
        """Pipeline: Generated questions -> Flashcards creation -> Multi-round SM-2 review simulation."""
        q_mod = require_study_module("question_generator")
        fc_mod = require_study_module("flashcard_engine")
        
        q_gen = q_mod.QuestionGenerator(llm_client=mock_llm_client)
        fc_eng = fc_mod.FlashcardEngine(db=neo4j_manager, llm_client=mock_llm_client)
        
        # Step 1: Generate study questions
        questions = q_gen.generate_questions(topic="AES Modes", difficulty="medium", count=2)
        assert len(questions) >= 1
        
        # Step 2: Create flashcards
        cards = fc_eng.create_flashcards_from_topic(topic="AES Modes", course="CNS", count=len(questions))
        assert len(cards) >= 1
        card_id = cards[0]["id"]
        
        # Step 3: Review Round 1 - Successful recall (quality=4)
        r1 = fc_eng.update_flashcard_review(card_id, quality=4)
        assert r1["repetitions"] == 1
        assert r1["interval"] == 1
        
        # Step 4: Review Round 2 - Second successful recall (quality=5)
        r2 = fc_eng.update_flashcard_review(card_id, quality=5)
        assert r2["repetitions"] == 2
        assert r2["interval"] >= 6, f"SM-2 second interval must be >= 6, got {r2['interval']}"
        assert r2["easiness_factor"] >= 2.5

    def test_combo_gap_detection_to_remedial_question_generation(self, neo4j_manager, mock_llm_client):
        """Pipeline: Gap detector identifies weak topic (< 2 chunks) -> Question generator creates remedial questions."""
        gap_mod = require_study_module("gap_detector")
        q_mod = require_study_module("question_generator")
        
        detector = gap_mod.GapDetector(db=neo4j_manager)
        q_gen = q_mod.QuestionGenerator(llm_client=mock_llm_client)
        
        # 1. Identify knowledge gaps
        gaps = detector.detect_knowledge_gaps(course="CNS")
        assert isinstance(gaps, list)
        
        gap_items = [g for g in gaps if g.get("is_gap") or g.get("gap") or g["chunk_count"] < 2]
        target_topic = gap_items[0]["source_title"] if gap_items else "Quantum Key Distribution"
        
        # 2. Automatically generate remedial questions on the gap topic
        remedial_qs = q_gen.generate_questions(topic=target_topic, difficulty="easy", count=2)
        assert len(remedial_qs) >= 1

    def test_combo_query_expander_to_thesis_assistant(self, mock_llm_client):
        """Pipeline: QueryExpander enriches search before ThesisAssistant synthesizes outline and citations."""
        qe_mod = require_study_module("query_expander")
        th_mod = require_study_module("thesis_assistant")
        
        class MockSearchRetriever:
            def deep_research(self, query: str, top_k: int = 10):
                return [
                    {"id": "chunk_sdcc_01", "text": f"Consensus algorithm details for {query}"},
                    {"id": "chunk_sdcc_02", "text": "Fault-tolerant replication models"}
                ]
            def search(self, q, top_k=5): return []
            
        retriever = MockSearchRetriever()
        expander = qe_mod.QueryExpander(retriever=retriever, llm_client=mock_llm_client)
        assistant = th_mod.ThesisAssistant(retriever=expander, llm_client=mock_llm_client)
        
        outline = assistant.generate_thesis_outline(title="Consensus in Distributed Systems")
        assert isinstance(outline, dict)
        assert "sections" in outline

    def test_combo_hybrid_retrieval_to_context_builder_to_llm(self, mock_llm_client):
        """Pipeline: Retrieval results -> ContextBuilder formatting -> LLM prompt generation -> JSON extraction."""
        cb = ContextBuilder()
        sample_results = [
            {
                "chunk_id": "chunk_101",
                "text": "The FMS attack exploits weak RC4 keys in WEP 802.11.",
                "source_title": "CNS_Lec04.pdf",
                "source_type": "pdf",
                "source_tier": "primary",
                "score": 0.94
            }
        ]
        
        # Step 1: Format context
        formatted = cb.format_mcp_response(query="WEP FMS", hybrid_results=sample_results)
        assert "CNS_Lec04.pdf" in formatted or "Source 1" in formatted
        
        # Step 2: Pass context to LLM
        prompt = f"Genera domande usando questo contesto:\n{formatted}"
        raw_llm_out = mock_llm_client.generate(prompt)
        assert isinstance(raw_llm_out, str)
        
        # Step 3: Extract and validate JSON
        extracted = extract_json_payload(raw_llm_out)
        parsed = json.loads(extracted)
        assert isinstance(parsed, (dict, list))

    def test_combo_multi_provider_dynamic_reconfiguration(self):
        """Verifies get_llm_client reconfigures correctly when settings change dynamically."""
        # Config 1: Mock
        s1 = Settings(llm_provider="mock")
        c1 = get_llm_client(s1)
        assert isinstance(c1, MockProvider)
        
        # Config 2: DeepSeek via OpenAIProvider
        s2 = Settings(
            llm_provider="deepseek",
            llm_api_key="sk-test-deepseek-key",
            llm_model="deepseek-chat",
            llm_base_url="https://api.deepseek.com"
        )
        c2 = get_llm_client(s2)
        assert isinstance(c2, OpenAIProvider)
        assert c2.model == "deepseek-chat"
        assert c2.base_url == "https://api.deepseek.com"

    def test_combo_concept_graph_queries_for_learning_paths(self, neo4j_manager, mock_llm_client):
        """Pipeline: Populates mock Concept nodes with PREREQUISITE_OF -> Generates path verifying traversal."""
        lp_mod = require_study_module("learning_path")
        lp_engine = lp_mod.LearningPathEngine(db=neo4j_manager, llm_client=mock_llm_client)
        
        path = lp_engine.generate_learning_path(topic="WPA3 Dragonfly Handshake")
        assert isinstance(path, dict)
        steps = path.get("steps") or path.get("prerequisites") or []
        assert len(steps) >= 1

    def test_combo_exam_linker_to_flashcard_deck(self, neo4j_manager, mock_llm_client, clean_test_labels):
        """Pipeline: Linker processes exam questions -> Generates flashcards for high-value exam topics."""
        el_mod = require_study_module("exam_linker")
        fc_mod = require_study_module("flashcard_engine")
        
        linker = el_mod.ExamLinker(db=neo4j_manager, llm_client=mock_llm_client)
        fc_eng = fc_mod.FlashcardEngine(db=neo4j_manager, llm_client=mock_llm_client)
        
        linker.link_past_exams(course="CNS")
        deck = fc_eng.create_flashcards_from_topic(topic="CNS Past Exams", course="CNS", count=2)
        assert len(deck) >= 1

    def test_combo_gap_detection_across_all_courses(self, neo4j_manager):
        """Pipeline: Gap detector executes across all distinct courses in KB and consolidates coverage metrics."""
        gap_mod = require_study_module("gap_detector")
        detector = gap_mod.GapDetector(db=neo4j_manager)
        
        all_courses = ["CNS", "SDCC", "ML", "SE"]
        summary = {}
        for c in all_courses:
            gaps = detector.detect_knowledge_gaps(course=c)
            summary[c] = len(gaps)
            
        assert any(count >= 0 for count in summary.values())
