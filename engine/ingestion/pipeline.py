import logging
from typing import List
from connectors.base import BaseConnector
from engine.ingestion.chunking import TextChunker
from engine.embeddings.provider import EmbeddingProvider
from core.database import Neo4jManager
from core.models import Document, Chunk

logger = logging.getLogger(__name__)

class IngestionPipeline:
    def __init__(self, db: Neo4jManager, embedder: EmbeddingProvider, chunker: TextChunker):
        self.db = db
        self.embedder = embedder
        self.chunker = chunker

    def run(self, connector: BaseConnector, force: bool = False):
        for doc in connector.extract():
            # Incremental sync: check if document already exists with identical checksum
            existing = self.db.execute_query(
                "MATCH (d:Document {id: $id}) RETURN d.checksum as checksum",
                {"id": doc.id}
            )
            if not force and existing and existing[0].get("checksum") == doc.checksum:
                logger.info(f"[SKIP - Invariato] {doc.title} (Course: {doc.course})")
                continue

            logger.info(f"[INDEX - Nuovo o Modificato] {doc.title} (Course: {doc.course})")
            
            # If document was previously indexed with different checksum, remove old chunks
            if existing:
                self.db.execute_query(
                    "MATCH (d:Document {id: $id})-[r:HAS_CHUNK]->(c:Chunk) DETACH DELETE c",
                    {"id": doc.id}
                )

            self._save_document(doc)
            
            chunks = self.chunker.chunk_document(doc)
            if not chunks:
                continue
                
            texts = [c.text for c in chunks]
            embeddings = self.embedder.get_embeddings(texts)
            
            for chunk, emb in zip(chunks, embeddings):
                chunk.embedding = emb
                self._save_chunk(chunk, doc)
                
            logger.info(f"Ingested {len(chunks)} chunks for {doc.title}")

    def _save_document(self, doc: Document):
        query = """
        MERGE (d:Document {id: $id})
        SET d.title = $title,
            d.source_type = $source_type,
            d.uri = $uri,
            d.course = $course,
            d.checksum = $checksum,
            d.updated_at = datetime()
        """
        self.db.execute_query(query, doc.model_dump())

    def _save_chunk(self, chunk: Chunk, doc: Document):
        # We save the chunk and link it to the Document
        query = """
        MATCH (d:Document {id: $doc_id})
        MERGE (c:Chunk {id: $id})
        SET c.text = $text,
            c.index = $index,
            c.embedding = $embedding,
            c.page = $page
        MERGE (d)-[:HAS_CHUNK]->(c)
        """
        self.db.execute_query(query, {
            "doc_id": doc.id,
            "id": chunk.id,
            "text": chunk.text,
            "index": chunk.index,
            "embedding": chunk.embedding,
            "page": chunk.page
        })
