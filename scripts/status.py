#!/usr/bin/env python3
"""
Diagnostica Academic KB — Mostra lo stato completo del grafo Neo4j
Uso: .venv/bin/python scripts/status.py
"""
import os
import sys

# Aggiungi root del progetto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import get_settings
from core.database import Neo4jManager

def main():
    s = get_settings()
    db = Neo4jManager(s.neo4j_uri, s.neo4j_username, s.neo4j_password)
    db.connect()

    docs = db.execute_query("MATCH (d:Document) RETURN count(d) as tot")[0]["tot"]
    chunks = db.execute_query("MATCH (c:Chunk) RETURN count(c) as tot")[0]["tot"]

    print("\n" + "=" * 60)
    print("  ACADEMIC KB — DIAGNOSTICA GRAFO")
    print("=" * 60)
    print(f"  Documenti totali nel grafo:  {docs}")
    print(f"  Chunk totali nel grafo:      {chunks}")
    print("=" * 60)

    # Per corso e sorgente
    courses = db.execute_query(
        "MATCH (d:Document) RETURN d.course as course, d.source_type as tipo, count(d) as n ORDER BY course, tipo"
    )
    print("\n📚 Ripartizione per Corso e Sorgente:")
    for c in courses:
        icon = "📄" if c["tipo"] == "pdf" else "📝"
        print(f"  {icon} {c['course']:15s} [{c['tipo']:6s}]: {c['n']} documenti")

    # Documenti senza chunk
    no_chunks = db.execute_query(
        "MATCH (d:Document) WHERE NOT (d)-[:HAS_CHUNK]->() RETURN d.title as title, d.source_type as tipo, d.course as course"
    )
    print("\n🔍 Documenti SENZA chunk (possibili problemi):")
    if no_chunks:
        for d in no_chunks:
            print(f"  ⚠️  {d['title']} [{d['tipo']}] ({d['course']})")
    else:
        print("  ✅ Nessuno! Tutti i documenti hanno almeno un chunk.")

    # Stato embedding
    null_emb = db.execute_query("MATCH (c:Chunk) WHERE c.embedding IS NULL RETURN count(c) as n")[0]["n"]
    has_emb = db.execute_query("MATCH (c:Chunk) WHERE c.embedding IS NOT NULL RETURN count(c) as n")[0]["n"]
    print(f"\n🧬 Stato Embedding:")
    print(f"  Chunk CON embedding:    {has_emb}")
    print(f"  Chunk SENZA embedding:  {null_emb}")
    if null_emb > 0:
        print(f"  ⚠️  Ci sono {null_emb} chunk senza vettore! Esegui: ./sync.sh --force")
    else:
        print(f"  ✅ Tutti i chunk hanno un vettore di embedding.")

    # Confronto disco vs grafo (solo PDF)
    courses_dir = s.magistrale_courses_dir
    if os.path.exists(courses_dir):
        disk_count = 0
        missing_files = []
        graph_titles_raw = db.execute_query("MATCH (d:Document {source_type: 'pdf'}) RETURN d.title as t")
        graph_titles = {r["t"] for r in graph_titles_raw}

        for root, dirs, files in os.walk(courses_dir):
            for f in files:
                if f.lower().endswith(".pdf"):
                    disk_count += 1
                    name = os.path.splitext(f)[0]
                    if f not in graph_titles and name not in graph_titles:
                        if not any(name in t for t in graph_titles):
                            rel = os.path.relpath(os.path.join(root, f), courses_dir)
                            missing_files.append(rel)

        graph_pdf_count = db.execute_query("MATCH (d:Document {source_type: 'pdf'}) RETURN count(d) as n")[0]["n"]

        print(f"\n📁 Confronto Disco vs Grafo (PDF):")
        print(f"  PDF su disco:   {disk_count}")
        print(f"  PDF nel grafo:  {graph_pdf_count}")
        if missing_files:
            print(f"  ❌ {len(missing_files)} file NON indicizzati:")
            for mf in missing_files:
                print(f"      • {mf}")
        else:
            print(f"  ✅ Tutti i PDF su disco sono indicizzati nel grafo!")

    # Notion
    notion_count = db.execute_query("MATCH (d:Document {source_type: 'notion'}) RETURN count(d) as n")[0]["n"]
    print(f"\n🌐 Pagine Notion nel grafo: {notion_count}")

    # Provider attuale
    print(f"\n⚙️  Configurazione attuale:")
    print(f"  Embedding Provider: {s.embedding_provider} ({s.embedding_model})")
    print(f"  Dimensione vettori: {s.embedding_dimension}")
    print(f"  Neo4j URI:          {s.neo4j_uri}")
    print("=" * 60 + "\n")

    db.close()

if __name__ == "__main__":
    main()
