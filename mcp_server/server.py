"""
Academic Knowledge Base — MCP Server
Espone il Knowledge Graph accademico via protocollo MCP (stdio).
Compatibile con Claude Desktop, Cursor, Pi, e qualsiasi agent MCP-compatibile.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.mcpserver import MCPServer

from config.settings import get_settings
from core.database import Neo4jManager
from engine.embeddings.provider import EmbeddingProvider
from engine.retrieval.vector import VectorRetriever
from engine.retrieval.fulltext import FulltextRetriever
from engine.retrieval.hybrid import HybridRetriever
from engine.context.builder import ContextBuilder

# Initialize server
mcp = MCPServer(
    "academic-kb",
    version="1.0.0",
    instructions=(
        "Academic Knowledge Base per la Magistrale di Tor Vergata. "
        "Contiene PDF delle lezioni, libri e appunti Notion per i corsi: "
        "SDCC, CNS, ML, SE. Usa 'academic_context' per cercare materiale accademico "
        "e 'academic_health' per verificare lo stato del sistema."
    )
)

# Global instances
settings = get_settings()
db = Neo4jManager(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)
embedder = EmbeddingProvider(
    settings.embedding_provider, settings.embedding_model,
    settings.embedding_dimension, settings.embedding_api_key,
    settings.embedding_base_url
)
vector_retriever = VectorRetriever(db, embedder)
fulltext_retriever = FulltextRetriever(db)
hybrid_retriever = HybridRetriever(vector_retriever, fulltext_retriever)
context_builder = ContextBuilder()


@mcp.tool()
def academic_context(query: str, top_k: int = 5) -> str:
    """
    Cerca nel Knowledge Graph accademico usando Hybrid Search (vettoriale + full-text).
    Restituisce i chunk più rilevanti dai PDF e dagli appunti Notion della Magistrale.

    Args:
        query: La domanda o l'argomento da cercare (es. 'WEP authentication vulnerabilities')
        top_k: Numero di risultati da restituire (default: 5)
    """
    db.connect()
    try:
        results = hybrid_retriever.search(query, top_k=top_k)
        return context_builder.format_mcp_response(query, results)
    finally:
        db.close()


@mcp.tool()
def academic_health() -> str:
    """Verifica lo stato del Knowledge Graph Neo4j e restituisce le statistiche."""
    try:
        db.connect()
        stats = db.execute_query("MATCH (n) RETURN count(n) as node_count")
        doc_count = db.execute_query("MATCH (d:Document) RETURN count(d) as c")[0]["c"]
        chunk_count = db.execute_query("MATCH (c:Chunk) RETURN count(c) as c")[0]["c"]
        courses = db.execute_query(
            "MATCH (d:Document) RETURN d.course as course, count(d) as docs ORDER BY docs DESC"
        )
        db.close()

        course_list = "\n".join([f"  • {c['course']}: {c['docs']} documenti" for c in courses])
        return (
            f"✅ Academic KB is HEALTHY\n"
            f"Nodi totali: {stats[0]['node_count']}\n"
            f"Documenti: {doc_count}\n"
            f"Chunk: {chunk_count}\n"
            f"Embedding Provider: {settings.embedding_provider} ({settings.embedding_model})\n"
            f"\nCorsi:\n{course_list}"
        )
    except Exception as e:
        return f"❌ Academic KB is DOWN: {str(e)}"


@mcp.tool()
def academic_courses() -> str:
    """Elenca tutti i corsi disponibili nel Knowledge Graph con i relativi documenti."""
    db.connect()
    try:
        courses = db.execute_query("""
            MATCH (d:Document)
            RETURN d.course as course, d.source_type as tipo, count(d) as n,
                   collect(d.title)[..5] as sample_titles
            ORDER BY course, tipo
        """)
        lines = []
        for c in courses:
            icon = "📄" if c["tipo"] == "pdf" else "📝"
            titles = ", ".join(c["sample_titles"][:3])
            lines.append(f"{icon} {c['course']} [{c['tipo']}]: {c['n']} documenti (es: {titles})")
        return "\n".join(lines)
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run(transport="stdio")
