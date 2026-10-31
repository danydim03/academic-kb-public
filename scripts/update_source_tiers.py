"""
Aggiorna il campo source_tier dei Document già indicizzati in Neo4j
senza toccare embedding o chunk — solo ricalcolo tier dal filepath.

Uso: python scripts/update_source_tiers.py
"""
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import get_settings
from core.database import Neo4jManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("update_tiers")


def classify_tier(filepath: str) -> str:
    """Ricalcola il source_tier da un filepath — logica identica a pdf.py."""
    path_segments = filepath.lower().split(os.sep)
    filename_lower = os.path.basename(filepath).lower()

    is_in_articles_dir = any(seg in ("articles", "papers", "articoli") for seg in path_segments)
    is_in_resources = any(seg.endswith(" resources") or seg == "resources" for seg in path_segments)
    is_book_file = filename_lower.startswith("book -") or filename_lower.startswith("book-")

    if is_in_articles_dir:
        return "article"
    elif is_in_resources and not is_book_file:
        return "article"
    elif is_in_resources and is_book_file:
        return "resource"
    else:
        return "primary"


def main():
    settings = get_settings()
    db = Neo4jManager(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)
    db.connect()

    try:
        docs = db.execute_query(
            "MATCH (d:Document) RETURN d.id AS id, d.title AS title, d.uri AS uri, "
            "d.source_tier AS old_tier, d.source_type AS source_type"
        )

        print(f"\n{'='*70}")
        print("  SOURCE TIER UPDATE — Aggiornamento 3-Tier System")
        print(f"{'='*70}")
        print(f"Documenti trovati: {len(docs)}\n")

        updated = 0
        unchanged = 0
        skipped = 0

        for doc in docs:
            uri = doc.get("uri", "")
            if not uri.startswith("file://"):
                logger.debug(f"[SKIP - Non è un file locale] {doc['title']}")
                skipped += 1
                continue

            filepath = uri[7:]  # strip "file://"
            new_tier = classify_tier(filepath)
            old_tier = doc.get("old_tier", "primary")

            if new_tier != old_tier:
                db.execute_query(
                    "MATCH (d:Document {id: $id}) SET d.source_tier = $tier",
                    {"id": doc["id"], "tier": new_tier}
                )
                icon = {"primary": "⭐⭐⭐", "resource": "⭐⭐", "article": "⭐"}.get(new_tier, "?")
                logger.info(f"[UPDATE] {doc['title']:60s}  {old_tier:10s} → {new_tier:10s} {icon}")
                updated += 1
            else:
                unchanged += 1

        print(f"\n{'='*70}")
        print(f"  RISULTATO")
        print(f"{'='*70}")
        print(f"  Aggiornati:  {updated}")
        print(f"  Invariati:   {unchanged}")
        print(f"  Saltati:     {skipped}")
        print(f"{'='*70}\n")

        # Riepilogo per tier
        tier_stats = db.execute_query("""
            MATCH (d:Document)
            RETURN d.source_tier AS tier, count(d) AS n
            ORDER BY tier
        """)
        print("Distribuzione per tier:")
        tier_icons = {"primary": "⭐⭐⭐", "resource": "⭐⭐", "article": "⭐"}
        for row in tier_stats:
            t = row["tier"] or "null"
            icon = tier_icons.get(t, "?")
            print(f"  {icon} {t:10s}: {row['n']} documenti")
        print()

    finally:
        db.close()


if __name__ == "__main__":
    main()
