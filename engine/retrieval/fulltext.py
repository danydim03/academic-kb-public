import logging
import re
from typing import List, Dict, Any, Optional
from core.database import Neo4jManager

logger = logging.getLogger(__name__)

# Lucene special characters: + - && || ! ( ) { } [ ] ^ " ~ * ? : \ /
LUCENE_SPECIAL_CHARS = re.compile(r'([+\-!(){}\[\]^"~*?:\\/]|&&|\|\|)')


def sanitize_lucene_query(query: str) -> str:
    r"""
    Sanitizes a user query for Lucene fulltext search:
    - Strips whitespace
    - Escapes Lucene special characters (+ - && || ! ( ) { } [ ] ^ " ~ * ? : \ /)
    - Returns empty string for blank/whitespace input
    """
    if not query:
        return ""
    q = query.strip()
    if not q:
        return ""

    # First escape backslashes, then the rest of special characters
    # Or escape single characters with leading backslash
    def _escape_match(match):
        token = match.group(0)
        if token in ("&&", "||"):
            return " "  # replace boolean operators with space
        return f"\\{token}"

    sanitized = LUCENE_SPECIAL_CHARS.sub(_escape_match, q)
    return sanitized.strip()


class FulltextRetriever:
    def __init__(self, db: Neo4jManager, index_name: str = "chunk_text"):
        self.db = db
        self.index_name = index_name

    def search(self, query: str, top_k: int = 5, tier_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        if not query or not str(query).strip():
            return []

        sanitized_query = sanitize_lucene_query(query)
        if not sanitized_query:
            return []

        tier_clause = "AND doc.source_tier = $tier_filter" if tier_filter else ""
        cypher = f"""
        CALL db.index.fulltext.queryNodes($index_name, $query) YIELD node AS chunk, score
        MATCH (doc:Document)-[:HAS_CHUNK]->(chunk)
        WHERE 1=1 {tier_clause}
        RETURN chunk.id AS chunk_id,
               chunk.text AS text,
               chunk.page AS page,
               doc.title AS source_title,
               doc.source_type AS source_type,
               doc.source_tier AS source_tier,
               doc.course AS course,
               score
        LIMIT $top_k
        """
        params = {
            "index_name": self.index_name,
            "query": sanitized_query,
            "top_k": top_k
        }
        if tier_filter:
            params["tier_filter"] = tier_filter

        try:
            return self.db.execute_query(cypher, params)
        except Exception as e:
            logger.warning(f"Fulltext search error for sanitized query '{sanitized_query}': {e}")
            return []
