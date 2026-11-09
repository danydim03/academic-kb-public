import logging
from core.database import Neo4jManager
from engine.embeddings.provider import EmbeddingProvider

logger = logging.getLogger(__name__)

class VectorRetriever:
    def __init__(self, db: Neo4jManager, embedder: EmbeddingProvider, index_name: str = "chunk_embeddings"):
        self.db = db
        self.embedder = embedder
        self.index_name = index_name

    def search(self, query: str, top_k: int = 5, tier_filter: str = None, course_filter: str = None):
        query_embedding = self.embedder.get_embeddings([query])[0]
        
        tier_clause = "AND doc.source_tier = $tier_filter" if tier_filter else ""
        course_clause = "AND doc.course = $course_filter" if course_filter else ""

        # Se sono presenti filtri su tier o corso, aumentiamo la dimensione del pool
        # di nodi vettoriali prima di applicare il filtro e la clausola LIMIT
        has_filter = bool(tier_filter or course_filter)
        pool_size = max(200, top_k * 15) if has_filter else top_k

        cypher = f"""
        CALL db.index.vector.queryNodes($index_name, $pool_size, $query_embedding)
        YIELD node AS chunk, score
        MATCH (doc:Document)-[:HAS_CHUNK]->(chunk)
        WHERE 1=1 {tier_clause} {course_clause}
        RETURN chunk.id AS chunk_id,
               chunk.text AS text,
               chunk.page AS page,
               doc.title AS source_title,
               doc.source_type AS source_type,
               doc.source_tier AS source_tier,
               doc.course AS course,
               score
        ORDER BY score DESC
        LIMIT $top_k
        """
        
        params = {
            "index_name": self.index_name,
            "pool_size": pool_size,
            "top_k": top_k,
            "query_embedding": query_embedding
        }
        if tier_filter:
            params["tier_filter"] = tier_filter
        if course_filter:
            params["course_filter"] = course_filter

        return self.db.execute_query(cypher, params)
