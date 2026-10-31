"""
Academic KB Knowledge Gap Detector Module.

Analyzes document chunk coverage for courses in the Neo4j knowledge graph,
identifying under-represented topics and flagging knowledge gaps (chunk_count < 2).
"""

import logging
from typing import List, Dict, Any, Optional

from core.database import Neo4jManager

logger = logging.getLogger(__name__)


class GapDetector:
    """
    Evaluates course curriculum coverage and pinpoints knowledge gaps.
    """

    def __init__(self, db: Optional[Neo4jManager] = None):
        self.db = db

    def detect_knowledge_gaps(self, course: str) -> List[Dict[str, Any]]:
        """
        Detects curriculum documents with inadequate chunk coverage for a specified course.

        Args:
            course: Course code (e.g. 'CNS', 'SDCC'). Case-insensitive.

        Returns:
            Ordered list of document coverage records:
            - source_title: str
            - chunk_count: int
            - coverage_score: float (0.0 to 100.0)
            - is_gap: bool (True if chunk_count < 2)
            - gap: bool (alias for is_gap)
        """
        if not course or not str(course).strip():
            return []

        clean_course = str(course).strip()

        if not self.db:
            return []

        cypher = """
        MATCH (d:Document)
        WHERE toUpper(d.course) = toUpper($course)
        OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
        WITH d.title AS source_title, d.id AS doc_id, count(c) AS chunk_count
        ORDER BY chunk_count ASC, source_title ASC
        RETURN source_title, doc_id, chunk_count
        """

        try:
            records = self.db.execute_query(cypher, {"course": clean_course})
        except Exception as e:
            logger.warning(f"Neo4j query failed in detect_knowledge_gaps: {e}")
            return []

        results: List[Dict[str, Any]] = []
        for r in records:
            count = int(r.get("chunk_count", 0))
            title = r.get("source_title") or f"Document {r.get('doc_id', '')}"
            is_gap = count < 2

            if count == 0:
                score = 0.0
            elif count == 1:
                score = 25.0
            else:
                score = min(100.0, round(50.0 + (count - 2) * 5.0, 2))

            item = {
                "source_title": title,
                "doc_id": r.get("doc_id"),
                "chunk_count": count,
                "coverage_score": score,
                "is_gap": is_gap,
                "gap": is_gap,
            }
            results.append(item)

        # Ensure ordered by chunk_count ascending
        results.sort(key=lambda x: (x["chunk_count"], x["source_title"]))
        return results
