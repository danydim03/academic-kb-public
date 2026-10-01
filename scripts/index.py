import os
import argparse
import logging
from config.settings import get_settings
from core.database import Neo4jManager
from engine.graph.schema import GraphSchemaManager
from engine.embeddings.provider import EmbeddingProvider
from engine.ingestion.chunking import TextChunker
from engine.ingestion.pipeline import IngestionPipeline
from connectors.files.pdf import PDFConnector
from connectors.notion.client import NotionConnector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Academic KB Ingestion Script")
    parser.add_argument("--pdf-dir", type=str, help="Directory containing PDF files")
    parser.add_argument("--notion", action="store_true", help="Sync from Notion")
    parser.add_argument("--course", type=str, default="General", help="Course name for PDFs")
    
    args = parser.parse_args()
    settings = get_settings()
    
    db = Neo4jManager(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)
    db.connect()
    
    try:
        # Setup schema
        schema_mgr = GraphSchemaManager(db)
        schema_mgr.setup_schema(vector_dimension=settings.embedding_dimension)
        
        # Init pipeline
        embedder = EmbeddingProvider(settings.embedding_provider, settings.embedding_model, settings.embedding_dimension, settings.embedding_api_key)
        chunker = TextChunker(chunk_size=1000, chunk_overlap=200)
        pipeline = IngestionPipeline(db, embedder, chunker)
        
        if args.pdf_dir:
            if not os.path.exists(args.pdf_dir):
                logger.error(f"PDF directory not found: {args.pdf_dir}")
                return
            logger.info(f"Ingesting PDFs from {args.pdf_dir}")
            connector = PDFConnector(directory=args.pdf_dir, course_name=args.course)
            pipeline.run(connector)
            
        if args.notion:
            if not settings.notion_api_key or not settings.notion_root_database_id:
                logger.error("Notion credentials missing in environment.")
                return
            logger.info("Ingesting from Notion")
            connector = NotionConnector(settings.notion_api_key, settings.notion_root_database_id)
            pipeline.run(connector)
            
        logger.info("Ingestion completed successfully.")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
