from core.database import Neo4jManager

class GraphSchemaManager:
    def __init__(self, db: Neo4jManager):
        self.db = db

    def setup_schema(self, vector_dimension: int = 768):
        self.db.ensure_constraints()
        self.db.create_vector_index(
            index_name="chunk_embeddings",
            label="Chunk",
            property_name="embedding",
            dimensions=vector_dimension
        )
        self.db.create_fulltext_index(
            index_name="chunk_text",
            labels=["Chunk"],
            properties=["text"]
        )
        self.db.create_fulltext_index(
            index_name="concept_text",
            labels=["Concept"],
            properties=["name", "aliases"]
        )
