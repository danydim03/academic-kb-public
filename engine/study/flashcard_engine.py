"""
Academic KB Flashcard Engine (SM-2 Spaced Repetition).

Implements the SuperMemo-2 (SM-2) spaced repetition algorithm with Neo4j persistence,
due-date scheduling, and flashcard generation from academic topics.
"""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple

from core.database import Neo4jManager
from engine.study.llm_client import LLMClient, get_llm_client, extract_json_payload

logger = logging.getLogger(__name__)


class FlashcardEngine:
    """
    Spaced repetition flashcard management system powered by the SM-2 algorithm.
    """

    def __init__(
        self,
        db: Optional[Neo4jManager] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        self.db = db
        self.llm_client = llm_client or get_llm_client()
        self._in_memory_cards: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def compute_sm2(
        repetitions: int,
        interval: int,
        easiness_factor: float,
        quality: int,
    ) -> Tuple[int, int, float, datetime]:
        """
        Executes standard SuperMemo-2 (SM-2) interval calculation.

        Args:
            repetitions: Number of consecutive successful recall reviews.
            interval: Current interval in days.
            easiness_factor: Current easiness factor (EF >= 1.30).
            quality: Review recall rating (0 to 5).

        Returns:
            Tuple of (new_repetitions, new_interval, new_easiness_factor, next_review_datetime)
        """
        q = max(0, min(5, quality))

        if q >= 3:
            if repetitions == 0:
                new_interval = 1
            elif repetitions == 1:
                new_interval = 6
            else:
                new_interval = round(interval * easiness_factor)
            new_repetitions = repetitions + 1
        else:
            new_repetitions = 0
            new_interval = 1

        new_ef = easiness_factor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        new_ef = max(1.30, round(new_ef, 4))
        next_review_dt = datetime.now(timezone.utc) + timedelta(days=new_interval)

        return new_repetitions, new_interval, new_ef, next_review_dt

    def create_flashcards_from_topic(
        self,
        topic: str,
        course: Optional[str] = None,
        count: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Generates and saves flashcards for a specific topic and course.
        """
        clean_topic = str(topic or "").strip() or "General Academic Concepts"
        course_code = (course or "GENERAL").strip().upper()
        req_count = max(1, min(20, count))

        prompt = (
            f"Generate exactly {req_count} flashcards for topic '{clean_topic}' in course '{course_code}'.\n"
            "For all mathematical formulas, symbols, sets, matrices, and expressions, write them in standard LaTeX wrapped in '$...$' (inline) or '$$...$$' (display).\n"
            "Format as JSON with key 'flashcards': list of objects with 'question', 'answer', 'source_chunk_id'."
        )
        system_prompt = "You are an academic flashcard generator. Provide clear, precise Q/A pairs."

        raw = self.llm_client.generate(prompt, system_prompt=system_prompt)
        parsed_cards: List[Dict[str, Any]] = []
        try:
            payload = extract_json_payload(raw)
            data = json.loads(payload)
            if isinstance(data, list):
                parsed_cards = data
            elif isinstance(data, dict):
                parsed_cards = data.get("flashcards") or data.get("questions") or [data]
        except Exception as e:
            logger.warning(f"Failed to parse LLM response for flashcards: {e}")

        # Fallback templates if LLM returned fewer
        now_iso = datetime.now(timezone.utc).isoformat()
        results: List[Dict[str, Any]] = []

        for idx in range(req_count):
            if idx < len(parsed_cards) and isinstance(parsed_cards[idx], dict):
                item = parsed_cards[idx]
                q_text = str(item.get("question") or f"Cos'è {clean_topic}?").strip()
                a_text = str(item.get("answer") or f"Definizione accademica di {clean_topic}.").strip()
                chunk_id = item.get("source_chunk_id") or f"chunk_{clean_topic[:8].lower()}_{idx+1}"
            else:
                q_text = f"Spiegare i principi cardine di {clean_topic} (Card #{idx+1})"
                a_text = f"Concetti fondamentali e proprietà strutturali di {clean_topic}."
                chunk_id = f"chunk_{clean_topic[:8].lower()}_{idx+1}"

            card_id = f"fc_{uuid.uuid4().hex[:12]}"
            card = {
                "id": card_id,
                "question": q_text,
                "answer": a_text,
                "source_chunk_id": chunk_id,
                "course": course_code,
                "easiness_factor": 2.5,
                "interval": 0,
                "repetitions": 0,
                "next_review": now_iso,
                "created_at": now_iso,
            }

            self._in_memory_cards[card_id] = card
            results.append(card)

            # Persist to Neo4j if available
            if self.db:
                try:
                    cypher = """
                    MERGE (f:Flashcard {id: $id})
                    SET f.question = $question,
                        f.answer = $answer,
                        f.source_chunk_id = $source_chunk_id,
                        f.course = $course,
                        f.easiness_factor = $easiness_factor,
                        f.interval = $interval,
                        f.repetitions = $repetitions,
                        f.next_review = $next_review,
                        f.created_at = $created_at
                    """
                    self.db.execute_query(cypher, card)
                except Exception as e:
                    logger.warning(f"Failed to persist flashcard {card_id} in Neo4j: {e}")

        return results

    def get_flashcards(
        self,
        topic: Optional[str] = None,
        course: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves flashcards due for review (next_review <= today).
        """
        now = datetime.now(timezone.utc)
        now_iso = (now + timedelta(minutes=5)).isoformat()
        norm_course = course.strip().upper() if course and course.strip() else None
        clean_topic = topic.strip().lower() if topic and topic.strip() else None

        if self.db:
            try:
                where_clauses = ["f.next_review <= $now_iso"]
                params: Dict[str, Any] = {"now_iso": now_iso}

                if norm_course:
                    where_clauses.append("toUpper(f.course) = $course")
                    params["course"] = norm_course

                if clean_topic:
                    where_clauses.append("(toLower(f.question) CONTAINS $topic OR toLower(f.answer) CONTAINS $topic)")
                    params["topic"] = clean_topic

                where_str = " AND ".join(where_clauses)
                cypher = f"""
                MATCH (f:Flashcard)
                WHERE {where_str}
                RETURN f.id AS id,
                       f.question AS question,
                       f.answer AS answer,
                       f.source_chunk_id AS source_chunk_id,
                       f.course AS course,
                       f.easiness_factor AS easiness_factor,
                       f.interval AS interval,
                       f.repetitions AS repetitions,
                       f.next_review AS next_review
                ORDER BY f.next_review ASC
                LIMIT 50
                """
                records = self.db.execute_query(cypher, params)
                if records:
                    return records
            except Exception as e:
                logger.warning(f"Neo4j query failed in get_flashcards: {e}")

        # In-memory fallback
        matching: List[Dict[str, Any]] = []
        for card in self._in_memory_cards.values():
            if norm_course and card.get("course", "").upper() != norm_course:
                continue
            if clean_topic:
                q = card.get("question", "").lower()
                a = card.get("answer", "").lower()
                if clean_topic not in q and clean_topic not in a:
                    continue

            card_rev = card.get("next_review")
            if card_rev:
                try:
                    dt = datetime.fromisoformat(card_rev.replace("Z", "+00:00"))
                    if dt <= now + timedelta(minutes=5):
                        matching.append(card)
                except Exception:
                    matching.append(card)
            else:
                matching.append(card)

        return matching

    def update_flashcard_review(self, flashcard_id: str, quality: int) -> Optional[Dict[str, Any]]:
        """
        Updates a flashcard's SM-2 state after a user review rating (0-5).
        """
        if not flashcard_id or not str(flashcard_id).strip():
            return None

        # Clamp quality safely
        q = max(0, min(5, int(quality)))

        # Find existing card state
        current_card: Optional[Dict[str, Any]] = None
        if self.db:
            try:
                records = self.db.execute_query(
                    "MATCH (f:Flashcard {id: $id}) RETURN f.id AS id, f.question AS question, f.answer AS answer, "
                    "f.source_chunk_id AS source_chunk_id, f.course AS course, f.easiness_factor AS easiness_factor, "
                    "f.interval AS interval, f.repetitions AS repetitions, f.next_review AS next_review",
                    {"id": flashcard_id}
                )
                if records:
                    current_card = dict(records[0])
            except Exception as e:
                logger.warning(f"Failed to fetch flashcard from Neo4j: {e}")

        if not current_card:
            current_card = self._in_memory_cards.get(flashcard_id)

        if not current_card:
            return None

        reps = int(current_card.get("repetitions", 0))
        interval = int(current_card.get("interval", 0))
        ef = float(current_card.get("easiness_factor", 2.5))

        new_reps, new_interval, new_ef, next_rev_dt = self.compute_sm2(reps, interval, ef, q)
        next_rev_iso = next_rev_dt.isoformat()
        now_iso = datetime.now(timezone.utc).isoformat()

        updated_fields = {
            "id": flashcard_id,
            "quality": q,
            "repetitions": new_reps,
            "interval": new_interval,
            "easiness_factor": new_ef,
            "next_review": next_rev_iso,
            "last_reviewed": now_iso,
        }
        current_card.update(updated_fields)
        self._in_memory_cards[flashcard_id] = current_card

        if self.db:
            try:
                cypher = """
                MATCH (f:Flashcard {id: $id})
                SET f.repetitions = $repetitions,
                    f.interval = $interval,
                    f.easiness_factor = $easiness_factor,
                    f.next_review = $next_review,
                    f.last_reviewed = $last_reviewed
                RETURN f.id AS id, f.repetitions AS repetitions, f.interval AS interval,
                       f.easiness_factor AS easiness_factor, f.next_review AS next_review
                """
                self.db.execute_query(cypher, updated_fields)
            except Exception as e:
                logger.warning(f"Failed to update flashcard in Neo4j: {e}")

        return current_card
