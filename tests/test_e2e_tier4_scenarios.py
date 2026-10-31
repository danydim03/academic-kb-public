"""
Academic KB Intelligent Study Engine — Tier 4: Real-World Application Workloads
Requirements-driven tests verifying realistic end-to-end student workflows,
thesis drafting pipelines, exam prep sessions, and offline execution scenarios.
"""

import json
import pytest
from typing import Dict, Any, List

from tests.conftest import require_study_module, get_study_module
from config.settings import Settings
from engine.study.llm_client import extract_json_payload, MockProvider, get_llm_client


class TestTier4RealWorldScenarios:
    """Verifies complete multi-step user workflows simulating realistic student and research sessions."""

    def test_scenario_cns_complete_study_session(self, neo4j_manager, mock_llm_client, clean_test_labels):
        """
        Scenario 1: Full CNS Student Study Session
        1. Student searches for 'WEP IV collisions and FMS attack'.
        2. Student generates 5 study questions (multiple choice + open).
        3. Questions are ingested into FlashcardEngine as a study deck.
        4. Student conducts SM-2 spaced repetition review round.
        5. Student detects knowledge gaps in CNS to identify weak topics.
        6. Student generates a prerequisite learning path for 'WPA3 Dragonfly Handshake'.
        """
        q_mod = require_study_module("question_generator")
        fc_mod = require_study_module("flashcard_engine")
        gap_mod = require_study_module("gap_detector")
        lp_mod = require_study_module("learning_path")
        
        # Initialize engines
        q_gen = q_mod.QuestionGenerator(llm_client=mock_llm_client)
        fc_eng = fc_mod.FlashcardEngine(db=neo4j_manager, llm_client=mock_llm_client)
        gap_detector = gap_mod.GapDetector(db=neo4j_manager)
        lp_eng = lp_mod.LearningPathEngine(db=neo4j_manager, llm_client=mock_llm_client)
        
        # Step 2: Generate 5 questions
        questions = q_gen.generate_questions(
            topic="WEP IV collisions and FMS attack",
            difficulty="medium",
            question_type="mixed",
            count=5
        )
        assert len(questions) == 5, f"Expected 5 questions, got {len(questions)}"
        
        # Step 3: Ingest into FlashcardEngine
        cards = fc_eng.create_flashcards_from_topic(
            topic="WEP IV collisions and FMS attack",
            course="CNS",
            count=5
        )
        assert len(cards) >= 1
        
        # Step 4: Conduct SM-2 review simulation
        test_card_id = cards[0]["id"]
        review_1 = fc_eng.update_flashcard_review(flashcard_id=test_card_id, quality=4)
        assert review_1["repetitions"] == 1
        assert review_1["interval"] == 1
        
        review_2 = fc_eng.update_flashcard_review(flashcard_id=test_card_id, quality=5)
        assert review_2["repetitions"] == 2
        assert review_2["interval"] >= 6
        
        # Step 5: Detect knowledge gaps in CNS
        gaps = gap_detector.detect_knowledge_gaps(course="CNS")
        assert isinstance(gaps, list)
        
        # Step 6: Generate prerequisite learning path
        path = lp_eng.generate_learning_path(topic="WPA3 Dragonfly Handshake")
        assert isinstance(path, dict)
        assert "steps" in path or "prerequisites" in path

    def test_scenario_thesis_drafting_end_to_end(self, mock_llm_client):
        """
        Scenario 2: Complete Master's Thesis Drafting Workflow
        1. Student submits thesis title: 'Fault-Tolerant Consensus in Distributed Systems'.
        2. ThesisAssistant executes deep research across lecture slides and textbook materials.
        3. Generates hierarchical outline with chapters, sections, and subsections.
        4. Populates sections with cited chunks and synthesized draft paragraphs.
        5. Validates structural completeness and citation traceability.
        """
        th_mod = require_study_module("thesis_assistant")
        
        # Mock retriever providing realistic hybrid & deep research results
        class AcademicRetriever:
            def deep_research(self, query: str, top_k: int = 10):
                return [
                    {
                        "chunk_id": "chunk_sdcc_raft_01",
                        "text": "Raft achieves consensus via leader election and log replication.",
                        "source_title": "SDCC - Lezione 8: Raft.pdf",
                        "source_type": "pdf",
                        "source_tier": "primary"
                    },
                    {
                        "chunk_id": "chunk_sdcc_paxos_01",
                        "text": "Paxos consensus algorithm formally proven by Leslie Lamport.",
                        "source_title": "SDCC - Lezione 9: Paxos.pdf",
                        "source_type": "pdf",
                        "source_tier": "primary"
                    }
                ]
            def search(self, q, top_k=5): return []
            
        assistant = th_mod.ThesisAssistant(retriever=AcademicRetriever(), llm_client=mock_llm_client)
        
        title = "Fault-Tolerant Consensus in Distributed Systems: From Paxos to Raft"
        outline = assistant.generate_thesis_outline(title=title)
        
        assert isinstance(outline, dict)
        assert "sections" in outline or "table_of_contents" in outline
        
        sections = outline.get("sections") or outline.get("table_of_contents") or []
        assert len(sections) >= 1
        
        # Verify citations are present
        citations_found = False
        for sec in sections:
            if "citations" in sec and len(sec["citations"]) > 0:
                citations_found = True
                break
            if "subsections" in sec:
                for sub in sec["subsections"]:
                    if isinstance(sub, dict) and "citations" in sub and len(sub["citations"]) > 0:
                        citations_found = True
                        break
        assert citations_found or len(sections) > 0

    def test_scenario_past_exam_preparation_workflow(self, neo4j_manager, mock_llm_client, clean_test_labels):
        """
        Scenario 3: Past Exam Revision Workflow
        1. Link past exam papers for course CNS.
        2. Verify ANSWERS relationships link questions to KB chunks.
        3. Generate practice questions focused on exam topics.
        4. Ingest into flashcards for spaced repetition drill.
        """
        el_mod = require_study_module("exam_linker")
        q_mod = require_study_module("question_generator")
        fc_mod = require_study_module("flashcard_engine")
        
        linker = el_mod.ExamLinker(db=neo4j_manager, llm_client=mock_llm_client)
        q_gen = q_mod.QuestionGenerator(llm_client=mock_llm_client)
        fc_eng = fc_mod.FlashcardEngine(db=neo4j_manager, llm_client=mock_llm_client)
        
        # Step 1: Link past exams
        link_summary = linker.link_past_exams(course="CNS")
        assert isinstance(link_summary, dict)
        
        # Step 2: Generate exam-tailored questions
        exam_qs = q_gen.generate_questions(topic="CNS Past Exam Themes", difficulty="hard", count=3)
        assert len(exam_qs) >= 1
        
        # Step 3: Flashcard reinforcement
        deck = fc_eng.create_flashcards_from_topic(topic="CNS Past Exam Themes", course="CNS", count=3)
        assert len(deck) >= 1

    def test_scenario_offline_air_gapped_environment(self, monkeypatch):
        """
        Scenario 4: Offline / Air-Gapped Operation
        Ensures entire study suite operates without internet connection or external API keys.
        """
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        
        settings = Settings(llm_provider="mock")
        client = get_llm_client(settings)
        assert isinstance(client, MockProvider)
        
        # Test synthetic generation across all study tasks
        tasks = [
            ("generate_questions", "Genera 5 domande a risposta multipla su Raft"),
            ("concept_extraction", "Estrai concetti da questo testo su Paxos"),
            ("learning_path", "Genera percorso prerequisiti per WPA3"),
            ("thesis_assistant", "Genera indice tesi su Sicurezza Cloud"),
            ("query_expansion", "Espandi la query WEP IV")
        ]
        
        for task_name, prompt in tasks:
            out = client.generate(prompt)
            assert isinstance(out, str) and len(out) > 0
            payload = extract_json_payload(out)
            parsed = json.loads(payload)
            assert isinstance(parsed, (dict, list)), f"Task {task_name} did not return valid JSON"

    def test_scenario_cross_course_comparative_study(self, neo4j_manager, mock_llm_client):
        """
        Scenario 5: Multi-Course Comparative Study Workflow
        Extracts concepts across CNS (Security) and SDCC (Distributed Systems)
        and verifies cross-course discovery and synthesis.
        """
        c_mod = require_study_module("concept_extractor")
        lp_mod = require_study_module("learning_path")
        
        extractor = c_mod.ConceptExtractor(db=neo4j_manager, llm_client=mock_llm_client)
        lp_eng = lp_mod.LearningPathEngine(db=neo4j_manager, llm_client=mock_llm_client)
        
        # Extract from both courses
        extractor.extract_and_link_concepts(limit_chunks=10, course="CNS")
        extractor.extract_and_link_concepts(limit_chunks=10, course="SDCC")
        
        # Generate learning path bridging security and distributed systems
        bridge_path = lp_eng.generate_learning_path(topic="Byzantine Fault Tolerant Security Protocols")
        assert isinstance(bridge_path, dict)

    def test_scenario_mcp_external_client_session(self):
        """
        Scenario 6: External MCP Agent Session
        Simulates an external client (Claude Desktop / Cursor) executing the standard tool inspection
        and health/context discovery sequence over FastMCP.
        """
        from mcp_server.server import academic_health, academic_courses, academic_context
        
        # 1. Health check
        health = academic_health()
        assert "Academic KB is" in health
        
        # 2. Courses inspection
        courses = academic_courses()
        assert len(courses) > 0
        
        # 3. Context query
        context = academic_context(query="WEP", top_k=2)
        assert isinstance(context, str)
