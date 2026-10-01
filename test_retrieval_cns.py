from config.settings import get_settings
from core.database import Neo4jManager
from engine.embeddings.provider import EmbeddingProvider
from engine.retrieval.vector import VectorRetriever
from engine.retrieval.fulltext import FulltextRetriever
from engine.retrieval.hybrid import HybridRetriever
from engine.context.builder import ContextBuilder

settings = get_settings()
db = Neo4jManager(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)
db.connect()

embedder = EmbeddingProvider(settings.embedding_provider, settings.embedding_model, settings.embedding_dimension, settings.embedding_api_key, settings.embedding_base_url)
vector = VectorRetriever(db, embedder)
ft = FulltextRetriever(db)
hybrid = HybridRetriever(vector, ft)

results = hybrid.search("WEP authentication", top_k=2)
ctx = ContextBuilder().format_mcp_response("WEP authentication", results)
print("FINAL CONTEXT FOR PI:")
print(ctx)

db.close()
