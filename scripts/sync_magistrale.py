import os
import sys
import argparse
import logging
from config.settings import get_settings
from core.database import Neo4jManager
from engine.graph.schema import GraphSchemaManager
from engine.embeddings.provider import EmbeddingProvider
from engine.ingestion.chunking import TextChunker
from engine.ingestion.pipeline import IngestionPipeline
from connectors.files.pdf import PDFConnector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("sync_magistrale")

def main():
    parser = argparse.ArgumentParser(description="Synchronize MAGISTRALE Knowledge into Academic KB Graph")
    parser.add_argument("--dir", type=str, default=None, help="Root directory to scan (defaults to MAGISTRALE/Corsi)")
    parser.add_argument("--course", type=str, default="auto", help="Course name filter (default: 'auto' based on subfolders)")
    parser.add_argument("--force", action="store_true", help="Force reindexing of all files (ignore checksum cache)")

    args = parser.parse_args()
    settings = get_settings()

    target_dir = args.dir or settings.magistrale_courses_dir
    target_dir = os.path.abspath(target_dir)

    if not os.path.exists(target_dir):
        logger.error(f"Errore: La cartella non esiste: {target_dir}")
        sys.exit(1)

    print("\n" + "="*60)
    print("  ACADEMIC KNOWLEDGE ENGINE - MAGISTRALE AUTO-SYNC")
    print("="*60)
    print(f"Directory sorgente: {target_dir}")
    print(f"Provider Embedding: {settings.embedding_provider} ({settings.embedding_model})")
    print(f"Neo4j URI:          {settings.neo4j_uri}")
    print("="*60 + "\n")

    # Connect to DB and ensure indexes
    db = Neo4jManager(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)
    db.connect()

    try:
        schema_mgr = GraphSchemaManager(db)
        schema_mgr.setup_schema(vector_dimension=settings.embedding_dimension)

        if args.force:
            logger.warning("Modalita --force attiva: pulizia cache checksum precedenti...")
            # If force is true, we could clear checksums or let pipeline handle it

        embedder = EmbeddingProvider(settings.embedding_provider, settings.embedding_model, settings.embedding_dimension, settings.embedding_api_key, settings.embedding_base_url)
        chunker = TextChunker(chunk_size=1000, chunk_overlap=200)
        pipeline = IngestionPipeline(db, embedder, chunker)

        # Auto-prune files that were renamed, moved, or deleted from disk
        stale_docs = db.execute_query("MATCH (d:Document) RETURN d.id as id, d.title as title, d.uri as uri, d.source_type as source_type")
        pruned_count = 0
        for doc in stale_docs:
            if doc.get("source_type") == "pdf":
                uri = doc.get("uri", "")
                if uri.startswith("file://"):
                    path = uri[7:]
                    if not os.path.exists(path):
                        logger.info(f"[PRUNE - File rimosso o spostato] {doc['title']}")
                        db.execute_query(
                            "MATCH (d:Document {id: $id}) OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk) DETACH DELETE c, d",
                            {"id": doc["id"]}
                        )
                        pruned_count += 1
        if pruned_count > 0:
            logger.info(f"Puliti {pruned_count} documenti obsoleti non piu presenti sul disco.")

        connector = PDFConnector(directory=target_dir, course_name=args.course)
        logger.info(f"Avvio scansione ricorsiva...")
        pipeline.run(connector, force=args.force)

        # Automatic Notion Sync if credentials are configured in .env
        if settings.notion_api_key and settings.notion_root_database_id:
            logger.info(f"Rilevate credenziali Notion nel file .env: avvio sincronizzazione Notion...")
            try:
                from connectors.notion.client import NotionConnector
                notion_connector = NotionConnector(settings.notion_api_key, settings.notion_root_database_id)
                pipeline.run(notion_connector, force=args.force)
            except Exception as ne:
                logger.error(f"Errore durante la sincronizzazione Notion: {ne}")

        # Output final statistics
        doc_count = db.execute_query("MATCH (d:Document) RETURN count(d) as c")[0]["c"]
        chunk_count = db.execute_query("MATCH (c:Chunk) RETURN count(c) as c")[0]["c"]
        courses = db.execute_query("MATCH (d:Document) RETURN DISTINCT d.course as course, count(d) as docs")

        print("\n" + "="*60)
        print("  SINCRONIZZAZIONE COMPLETATA CON SUCCESSO! 🎉")
        print("="*60)
        print(f"Documenti totali indicizzati: {doc_count}")
        print(f"Paragrafi (Chunk) nel grafo: {chunk_count}")
        print("\nRipartizione per corso:")
        for row in courses:
            print(f"  • {row['course']}: {row['docs']} documenti")
        print("="*60 + "\n")

    finally:
        db.close()

if __name__ == "__main__":
    main()
