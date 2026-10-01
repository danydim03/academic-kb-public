import logging
from core.database import Neo4jManager

logger = logging.getLogger(__name__)

class FulltextRetriever:
    def __init__(self, db: Neo4jManager, index_name: str = "chunk_text"):
        self.db = db
        self.index_name = index_name

    def search(self, query: str, top_k: int = 5):
        # We use Neo4j native fulltext search
        cypher = f"""
        CALL db.index.fulltext.queryNodes($index_name, $query) YIELD node AS chunk, score
        MATCH (doc:Document)-[:HAS_CHUNK]->(chunk)
        RETURN chunk.id AS chunk_id,
               chunk.text AS text,
               chunk.page AS page,
               doc.title AS source_title,
               doc.source_type AS source_type,
               doc.course AS course,
               score
        LIMIT $top_k
        """
        results = self.db.execute_query(cypher, {
            "index_name": self.index_name,
            "query": query,
            "top_k": top_k
        })
        return results
