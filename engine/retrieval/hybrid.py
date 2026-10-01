from typing import List, Dict, Any
from engine.retrieval.vector import VectorRetriever
from engine.retrieval.fulltext import FulltextRetriever
from core.database import Neo4jManager


class HybridRetriever:
    def __init__(self, vector_retriever: VectorRetriever, fulltext_retriever: FulltextRetriever):
        self.vector_retriever = vector_retriever
        self.fulltext_retriever = fulltext_retriever
        self.db = vector_retriever.db

    def search(self, query: str, top_k: int = 5, rrf_k: int = 60, expand_graph: bool = True) -> List[Dict[str, Any]]:
        """
        Hybrid search con Reciprocal Rank Fusion + espansione grafo semantico.

        Se expand_graph=True, dopo la ricerca ibrida standard, espande i risultati
        con chunk collegati tramite SIMILAR_TO (cross-document).
        """
        # Get results from both retrieval methods
        vec_results = self.vector_retriever.search(query, top_k=top_k * 2)
        ft_results = self.fulltext_retriever.search(query, top_k=top_k * 2)

        # Reciprocal Rank Fusion (RRF)
        scores_map = {}
        chunks_map = {}

        for rank, res in enumerate(vec_results):
            chunk_id = res['chunk_id']
            chunks_map[chunk_id] = res
            scores_map[chunk_id] = scores_map.get(chunk_id, 0.0) + (1.0 / (rrf_k + rank + 1))

        for rank, res in enumerate(ft_results):
            chunk_id = res['chunk_id']
            chunks_map[chunk_id] = res
            scores_map[chunk_id] = scores_map.get(chunk_id, 0.0) + (1.0 / (rrf_k + rank + 1))

        # Sort by RRF score
        sorted_ids = sorted(scores_map.keys(), key=lambda x: scores_map[x], reverse=True)

        # Take initial top results
        initial_top = sorted_ids[:top_k]

        if not expand_graph or not initial_top:
            return self._build_results(initial_top, chunks_map, scores_map, top_k)

        # Graph expansion: find related chunks via SIMILAR_TO
        expanded_chunks = self._expand_via_semantic_links(initial_top, chunks_map, scores_map, rrf_k)

        # Merge expanded into results
        all_ids = set(sorted_ids) | set(expanded_chunks.keys())
        for cid, data in expanded_chunks.items():
            if cid not in chunks_map:
                chunks_map[cid] = data["chunk"]
                scores_map[cid] = data["score"]

        # Re-sort with expanded results
        final_sorted = sorted(all_ids, key=lambda x: scores_map.get(x, 0), reverse=True)

        return self._build_results(final_sorted, chunks_map, scores_map, top_k)

    def _expand_via_semantic_links(
        self, seed_chunk_ids: List[str], chunks_map: dict, scores_map: dict, rrf_k: int
    ) -> Dict[str, Any]:
        """
        Dato un set di chunk iniziali, trova chunk collegati tramite SIMILAR_TO
        che provengono da documenti diversi. Questo arricchisce il contesto con
        materiale cross-documento e cross-corso.
        """
        expanded = {}

        try:
            neighbors = self.db.execute_query("""
                UNWIND $seed_ids AS seed_id
                MATCH (seed:Chunk {id: seed_id})-[sim:SIMILAR_TO]-(neighbor:Chunk)
                WHERE NOT neighbor.id IN $seed_ids
                MATCH (doc:Document)-[:HAS_CHUNK]->(neighbor)
                RETURN DISTINCT
                    neighbor.id AS chunk_id,
                    neighbor.text AS text,
                    neighbor.page AS page,
                    doc.title AS source_title,
                    doc.source_type AS source_type,
                    doc.course AS course,
                    max(sim.score) AS sim_score,
                    seed_id AS from_chunk
                ORDER BY sim_score DESC
                LIMIT 6
            """, {"seed_ids": seed_chunk_ids})

            for row in neighbors:
                cid = row["chunk_id"]
                if cid not in chunks_map and cid not in expanded:
                    # Score boosted by semantic similarity but lower than direct hits
                    boosted_score = row["sim_score"] * (1.0 / (rrf_k + len(chunks_map) + 1))
                    expanded[cid] = {
                        "chunk": {
                            "chunk_id": cid,
                            "text": row["text"],
                            "page": row["page"],
                            "source_title": row["source_title"],
                            "source_type": row["source_type"],
                            "course": row["course"],
                            "via_semantic_link": True,
                            "link_score": row["sim_score"]
                        },
                        "score": boosted_score
                    }
        except Exception:
            # Se non ci sono relazioni SIMILAR_TO, non espandere
            pass

        return expanded

    def _build_results(
        self, sorted_ids: list, chunks_map: dict, scores_map: dict, top_k: int
    ) -> List[Dict[str, Any]]:
        """Costruisce la lista finale di risultati ordinata per score."""
        results = []
        for cid in sorted_ids[:top_k]:
            if cid in chunks_map:
                item = chunks_map[cid].copy()
                item['rrf_score'] = scores_map.get(cid, 0)
                results.append(item)
        return results
