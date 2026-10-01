import logging
from core.database import Neo4jManager
from engine.embeddings.provider import EmbeddingProvider

logger = logging.getLogger(__name__)

class VectorRetriever:
    def __init__(self, db: Neo4jManager, embedder: EmbeddingProvider, index_name: str = "chunk_embeddings"):
        self.db = db
        self.embedder = embedder
        self.index_name = index_name

    def search(self, query: str, top_k: int = 5):
        query_embedding = self.embedder.get_embeddings([query])[0]
        
        # Cypher query for vector search using cosine similarity
        cypher = f"""
        CALL db.index.vector.queryNodes($index_name, $top_k, $query_embedding)
        YIELD node AS chunk, score
        MATCH (doc:Document)-[:HAS_CHUNK]->(chunk)
        RETURN chunk.id AS chunk_id,
               chunk.text AS text,
               chunk.page AS page,
               doc.title AS source_title,
               doc.source_type AS source_type,
               doc.course AS course,
               score
        """
        
        results = self.db.execute_query(cypher, {
            "index_name": self.index_name,
            "top_k": top_k,
            "query_embedding": query_embedding
        })
        
        return results
