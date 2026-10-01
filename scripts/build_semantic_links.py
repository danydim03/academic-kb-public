#!/usr/bin/env python3
"""
Build Semantic Links — Crea relazioni SIMILAR_TO tra chunk e RELATED_TO tra documenti.

Per ogni chunk, usa l'indice vettoriale di Neo4j per trovare i K chunk più simili
da ALTRI documenti e crea archi pesati con il cosine similarity score.
Poi aggrega le similarità a livello documento per creare relazioni RELATED_TO.

Uso:
    .venv/bin/python scripts/build_semantic_links.py [--threshold 0.82] [--top-k 5] [--clean]
"""
import os
import sys
import argparse
import logging
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import get_settings
from core.database import Neo4jManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("semantic_links")


def clean_existing_links(db: Neo4jManager):
    """Rimuove tutte le relazioni semantiche esistenti."""
    logger.info("Pulizia relazioni SIMILAR_TO esistenti...")
    db.execute_query("MATCH ()-[r:SIMILAR_TO]->() DELETE r")
    logger.info("Pulizia relazioni RELATED_TO esistenti...")
    db.execute_query("MATCH ()-[r:RELATED_TO]->() DELETE r")
    logger.info("Pulizia completata.")


def build_chunk_similarity(db: Neo4jManager, threshold: float = 0.82, top_k: int = 5):
    """
    Per ogni chunk, trova i top-K chunk più simili da ALTRI documenti
    e crea relazioni SIMILAR_TO con il similarity score.
    """
    # Conta chunk totali
    total = db.execute_query("MATCH (c:Chunk) WHERE c.embedding IS NOT NULL RETURN count(c) as n")[0]["n"]
    logger.info(f"Chunk con embedding: {total}")
    logger.info(f"Soglia similarità: {threshold} | Top-K per chunk: {top_k}")

    # Ottieni tutti i chunk IDs con il loro documento padre
    all_chunks = db.execute_query("""
        MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
        WHERE c.embedding IS NOT NULL
        RETURN c.id as chunk_id, d.id as doc_id
    """)

    chunk_to_doc = {row["chunk_id"]: row["doc_id"] for row in all_chunks}
    chunk_ids = list(chunk_to_doc.keys())

    logger.info(f"Inizio costruzione link semantici per {len(chunk_ids)} chunk...")

    created = 0
    skipped = 0
    processed = 0
    batch_size = 100
    start_time = time.time()

    for i in range(0, len(chunk_ids), batch_size):
        batch = chunk_ids[i:i + batch_size]

        for chunk_id in batch:
            doc_id = chunk_to_doc[chunk_id]

            # Usa l'indice vettoriale per trovare i chunk più simili
            # Chiediamo più risultati del necessario perché filtriamo quelli dello stesso documento
            neighbors = db.execute_query("""
                MATCH (source:Chunk {id: $chunk_id})
                CALL db.index.vector.queryNodes('chunk_embeddings', $search_k, source.embedding)
                YIELD node AS target, score
                WHERE target.id <> $chunk_id AND score >= $threshold
                MATCH (target_doc:Document)-[:HAS_CHUNK]->(target)
                WHERE target_doc.id <> $doc_id
                RETURN target.id AS target_id, score, target_doc.id AS target_doc_id
                LIMIT $top_k
            """, {
                "chunk_id": chunk_id,
                "search_k": top_k * 3,  # Cerchiamo di più per compensare i filtri
                "threshold": threshold,
                "top_k": top_k,
                "doc_id": doc_id
            })

            for neighbor in neighbors:
                # Crea relazione solo in una direzione (A->B dove A.id < B.id)
                # per evitare duplicati
                source_id = chunk_id
                target_id = neighbor["target_id"]

                if source_id < target_id:
                    db.execute_query("""
                        MATCH (a:Chunk {id: $source_id}), (b:Chunk {id: $target_id})
                        MERGE (a)-[r:SIMILAR_TO]->(b)
                        SET r.score = $score
                    """, {
                        "source_id": source_id,
                        "target_id": target_id,
                        "score": round(neighbor["score"], 4)
                    })
                    created += 1
                else:
                    # Controlla se la relazione inversa esiste già
                    existing = db.execute_query("""
                        MATCH (a:Chunk {id: $target_id})-[r:SIMILAR_TO]->(b:Chunk {id: $source_id})
                        RETURN r.score as score LIMIT 1
                    """, {"target_id": target_id, "source_id": source_id})

                    if not existing:
                        db.execute_query("""
                            MATCH (a:Chunk {id: $target_id}), (b:Chunk {id: $source_id})
                            MERGE (a)-[r:SIMILAR_TO]->(b)
                            SET r.score = $score
                        """, {
                            "target_id": target_id,
                            "source_id": source_id,
                            "score": round(neighbor["score"], 4)
                        })
                        created += 1
                    else:
                        skipped += 1

            processed += 1

        # Progress log ogni batch
        elapsed = time.time() - start_time
        pct = (processed / len(chunk_ids)) * 100
        rate = processed / elapsed if elapsed > 0 else 0
        eta = (len(chunk_ids) - processed) / rate if rate > 0 else 0
        logger.info(
            f"[{pct:5.1f}%] Processati {processed}/{len(chunk_ids)} chunk | "
            f"Link creati: {created} | Saltati: {skipped} | "
            f"Velocità: {rate:.1f} chunk/s | ETA: {eta:.0f}s"
        )

    logger.info(f"✅ Completato! Link SIMILAR_TO creati: {created}")
    return created


def build_document_relations(db: Neo4jManager, min_shared_links: int = 3):
    """
    Aggrega le relazioni SIMILAR_TO tra chunk per creare relazioni RELATED_TO
    tra documenti. Due documenti sono RELATED_TO se condividono almeno
    min_shared_links chunk simili.
    """
    logger.info(f"Costruzione relazioni RELATED_TO tra documenti (min link condivisi: {min_shared_links})...")

    result = db.execute_query("""
        MATCH (d1:Document)-[:HAS_CHUNK]->(c1:Chunk)-[sim:SIMILAR_TO]-(c2:Chunk)<-[:HAS_CHUNK]-(d2:Document)
        WHERE d1.id < d2.id
        WITH d1, d2,
             count(sim) AS shared_links,
             avg(sim.score) AS avg_similarity,
             max(sim.score) AS max_similarity,
             collect(DISTINCT d1.course)[0] AS course1,
             collect(DISTINCT d2.course)[0] AS course2
        WHERE shared_links >= $min_links
        MERGE (d1)-[r:RELATED_TO]->(d2)
        SET r.shared_links = shared_links,
            r.avg_similarity = round(avg_similarity, 4),
            r.max_similarity = round(max_similarity, 4),
            r.cross_course = (course1 <> course2)
        RETURN d1.title AS doc1, d2.title AS doc2,
               shared_links, round(avg_similarity, 3) AS avg_sim,
               course1, course2
        ORDER BY shared_links DESC
    """, {"min_links": min_shared_links})

    logger.info(f"✅ Relazioni RELATED_TO create: {len(result)}")

    if result:
        logger.info("\nTop relazioni tra documenti:")
        for row in result[:15]:
            cross = " 🔀 CROSS-COURSE" if row["course1"] != row["course2"] else ""
            logger.info(
                f"  [{row['course1']}] {row['doc1'][:40]:40s} ↔ "
                f"[{row['course2']}] {row['doc2'][:40]:40s} | "
                f"link: {row['shared_links']}, sim: {row['avg_sim']}{cross}"
            )

    return len(result)


def print_stats(db: Neo4jManager):
    """Stampa le statistiche finali del grafo arricchito."""
    sim_count = db.execute_query("MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) as n")[0]["n"]
    rel_count = db.execute_query("MATCH ()-[r:RELATED_TO]->() RETURN count(r) as n")[0]["n"]
    cross_count = db.execute_query(
        "MATCH ()-[r:RELATED_TO]->() WHERE r.cross_course = true RETURN count(r) as n"
    )[0]["n"]

    # Chunk più connessi
    top_connected = db.execute_query("""
        MATCH (c:Chunk)-[r:SIMILAR_TO]-()
        MATCH (d:Document)-[:HAS_CHUNK]->(c)
        WITH c, d, count(r) as connections
        RETURN c.text[..80] as text_preview, d.title as doc, d.course as course, connections
        ORDER BY connections DESC
        LIMIT 5
    """)

    print("\n" + "=" * 60)
    print("  SEMANTIC LINKS — STATISTICHE FINALI")
    print("=" * 60)
    print(f"  Relazioni SIMILAR_TO (chunk↔chunk): {sim_count}")
    print(f"  Relazioni RELATED_TO (doc↔doc):     {rel_count}")
    print(f"    di cui cross-corso:                {cross_count}")
    print("=" * 60)

    if top_connected:
        print("\n🔗 Chunk più connessi:")
        for row in top_connected:
            print(f"  [{row['course']}] {row['doc'][:30]} → \"{row['text_preview']}...\" ({row['connections']} link)")

    print()


def main():
    parser = argparse.ArgumentParser(description="Build semantic links between chunks and documents")
    parser.add_argument("--threshold", type=float, default=0.82,
                        help="Soglia minima di cosine similarity (default: 0.82)")
    parser.add_argument("--top-k", type=int, default=5,
                        help="Max link per chunk verso altri documenti (default: 5)")
    parser.add_argument("--min-doc-links", type=int, default=3,
                        help="Min chunk condivisi per creare RELATED_TO tra documenti (default: 3)")
    parser.add_argument("--clean", action="store_true",
                        help="Rimuovi tutti i link semantici esistenti prima di ricostruire")
    args = parser.parse_args()

    settings = get_settings()
    db = Neo4jManager(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)
    db.connect()

    print("\n" + "=" * 60)
    print("  ACADEMIC KB — SEMANTIC LINK BUILDER")
    print("=" * 60)
    print(f"  Soglia similarità:    {args.threshold}")
    print(f"  Max link per chunk:   {args.top_k}")
    print(f"  Min link per doc rel: {args.min_doc_links}")
    print("=" * 60 + "\n")

    try:
        if args.clean:
            clean_existing_links(db)

        # Step 1: Build chunk-to-chunk SIMILAR_TO
        sim_count = build_chunk_similarity(db, threshold=args.threshold, top_k=args.top_k)

        # Step 2: Build document-to-document RELATED_TO
        if sim_count > 0:
            rel_count = build_document_relations(db, min_shared_links=args.min_doc_links)

        # Step 3: Print final stats
        print_stats(db)

    finally:
        db.close()


if __name__ == "__main__":
    main()
