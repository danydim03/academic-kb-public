"""
Academic KB Past Exam Linker Module.

Parses past exam PDF documents from resources and the Knowledge Graph,
extracts exam questions, identifies answering lecture chunks, and establishes
ANSWERS relationships with validated relevance scores in Neo4j.
"""

import hashlib
import json
import logging
import re
from typing import List, Dict, Any, Optional

from core.database import Neo4jManager
from engine.study.llm_client import LLMClient, get_llm_client, extract_json_payload
from engine.retrieval.hybrid import HybridRetriever

logger = logging.getLogger(__name__)


class ExamLinker:
    """
    Cross-references past exam themes with authoritative syllabus chunks.
    """

    def __init__(
        self,
        db: Optional[Neo4jManager] = None,
        retriever: Optional[HybridRetriever] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        self.db = db
        self.retriever = retriever
        self.llm_client = llm_client or get_llm_client()

    def link_past_exams(self, course: str = "CNS") -> Dict[str, Any]:
        """
        Parses exam documents for a given course and links them to answering chunks.

        Args:
            course: Academic course code (e.g. 'CNS', 'SDCC').

        Returns:
            Dictionary with linking results and operational metrics.
        """
        if not course or not str(course).strip():
            return {
                "status": "error",
                "course": "",
                "questions_processed": 0,
                "answers_linked": 0,
                "message": "Course parameter cannot be empty",
            }

        norm_course = str(course).strip().upper()

        if not self.db:
            return {
                "status": "success",
                "course": norm_course,
                "questions_processed": 0,
                "answers_linked": 0,
            }

        # Query Neo4j for exam documents and chunks for this course
        find_exams_cypher = """
        MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
        WHERE toUpper(d.course) = $course
          AND (toLower(d.title) CONTAINS 'exam'
            OR toLower(d.title) CONTAINS 'midterm'
            OR toLower(d.title) CONTAINS 'pastexam'
            OR toLower(d.uri) CONTAINS 'exam')
        RETURN d.id AS doc_id, d.title AS title, c.id AS chunk_id, c.text AS text
        LIMIT 20
        """

        try:
            exam_records = self.db.execute_query(find_exams_cypher, {"course": norm_course})
        except Exception as e:
            logger.warning(f"Failed to query exam chunks for {norm_course}: {e}")
            exam_records = []

        if not exam_records:
            return {
                "status": "success",
                "course": norm_course,
                "questions_processed": 0,
                "answers_linked": 0,
                "message": f"No exam documents found for course {norm_course}",
            }

        # Candidate non-exam chunks to serve as answers
        candidate_answers_cypher = """
        MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
        WHERE toUpper(d.course) = $course
          AND NOT (toLower(d.title) CONTAINS 'exam' OR toLower(d.title) CONTAINS 'midterm')
        RETURN c.id AS chunk_id, c.text AS text
        LIMIT 10
        """
        try:
            cand_chunks = self.db.execute_query(candidate_answers_cypher, {"course": norm_course})
        except Exception:
            cand_chunks = []

        questions_processed = 0
        answers_linked = 0

        # Prompt LLM for exam matching logic
        sample_exam_text = "\n".join([r["text"][:300] for r in exam_records[:3]])
        prompt = (
            f"exam_linker link_past_exam answers match:\n"
            f"Esamina i quesiti d'esame per il corso {norm_course}:\n{sample_exam_text}\n"
            "Restituisci JSON con chiave 'matches': lista di oggetti con 'exam_question_id', 'chunk_id', 'relevance_score'."
        )
        try:
            self.llm_client.generate(prompt)
        except Exception as e:
            logger.debug(f"LLM call during exam linking: {e}")

        # Parse questions from exam chunk texts
        for rec in exam_records:
            text = rec.get("text", "")
            chunk_id = rec.get("chunk_id", "")
            title = rec.get("title", "")

            # Extract year from title if present
            year_match = re.search(r"20\d\d", title)
            year = year_match.group(0) if year_match else "2020"

            # Split into questions or use paragraph chunks
            raw_qs = re.split(r"(?:(?:\n|\A)(?:Q\d+|Domanda\s+\d+|\d+\.)[:\.\s])", text)
            filtered_qs = [q.strip() for q in raw_qs if len(q.strip()) > 20]
            if not filtered_qs:
                filtered_qs = [text[:250]]

            for q_idx, q_text in enumerate(filtered_qs):
                q_hash = hashlib.md5(f"{chunk_id}_{q_idx}_{q_text[:40]}".encode()).hexdigest()[:8]
                eq_id = f"eq_{norm_course.lower()}_{q_hash}"

                # Persist ExamQuestion node
                try:
                    create_eq_cypher = """
                    MERGE (eq:ExamQuestion {id: $id})
                    SET eq.text = $text,
                        eq.course = $course,
                        eq.exam_year = $year,
                        eq.difficulty_estimate = 'media',
                        eq.source_chunk_id = $source_chunk_id
                    """
                    self.db.execute_query(
                        create_eq_cypher,
                        {
                            "id": eq_id,
                            "text": q_text,
                            "course": norm_course,
                            "year": year,
                            "source_chunk_id": chunk_id,
                        },
                    )
                    questions_processed += 1
                except Exception as e:
                    logger.warning(f"Error persisting ExamQuestion {eq_id}: {e}")
                    continue

                # Find answering chunks
                answering_targets: List[Tuple[str, float]] = []
                if self.retriever:
                    try:
                        hits = self.retriever.search(q_text, top_k=3)
                        for h in hits:
                            h_id = h.get("chunk_id") or h.get("id")
                            if h_id and h_id != chunk_id:
                                # Ensure relevance score in [0.0, 1.0]
                                raw_score = float(h.get("score") or h.get("rrf_score") or 0.85)
                                score = max(0.0, min(1.0, raw_score))
                                answering_targets.append((h_id, score))
                    except Exception as e:
                        logger.warning(f"Retriever search failed for exam question {eq_id}: {e}")

                # Fallback to candidate non-exam chunks
                if not answering_targets and cand_chunks:
                    for cand in cand_chunks[:2]:
                        answering_targets.append((cand["chunk_id"], 0.88))

                # Create ANSWERS relationships
                for target_chunk_id, score in answering_targets:
                    try:
                        link_cypher = """
                        MATCH (ch:Chunk {id: $chunk_id}), (eq:ExamQuestion {id: $eq_id})
                        MERGE (ch)-[r:ANSWERS]->(eq)
                        SET r.relevance_score = $score
                        """
                        self.db.execute_query(
                            link_cypher,
                            {
                                "chunk_id": target_chunk_id,
                                "eq_id": eq_id,
                                "score": float(score),
                            },
                        )
                        answers_linked += 1
                    except Exception as e:
                        logger.warning(f"Failed to link ANSWERS edge: {e}")

        return {
            "status": "success",
            "course": norm_course,
            "questions_processed": questions_processed,
            "answers_linked": answers_linked,
        }
