import re
import unicodedata
from typing import List, Dict, Any, Optional
from engine.retrieval.vector import VectorRetriever
from engine.retrieval.fulltext import FulltextRetriever
from core.database import Neo4jManager


def infer_query_profile(query: str, requested_k: Optional[int] = None) -> Dict[str, Any]:
    """
    Analizza la query in modo deterministico (0ms latenza) per calcolare:
    1. k_tot dinamico (da 8 per factual/definizioni fino a 20 per trattazioni complesse).
    2. Ripartizione dinamica delle quote tra Libri (teoria), Paper (ricerca) e Slide (esame).
    """
    norm_q = "".join(
        c for c in unicodedata.normalize("NFKD", str(query).lower())
        if not unicodedata.combining(c)
    ).strip()
    words = re.findall(r"\b\w+\b", norm_q)
    word_count = len(words)

    has_word = lambda pattern: bool(re.search(r"\b(?:" + pattern + r")\b", norm_q))

    # ── 1. SCOPE & AMPIEZZA RICHIESTA (k_tot dinamico) ─────────────────────
    is_thesis_or_macro = has_word(r"tesi|dissertazione|stato dell\s*arte|literature review|capitolo tesi|quadro completo|macro ricerca|rassegna bibliografica|monografia")

    is_short_factual = (
        word_count <= 4 or
        has_word(r"cos\s*e|cosa\s*e|definizione|significato|acronimo|formula|sintassi|valore|porta")
    ) and not has_word(r"approfondisci|dettagli|completa|tutti|confronto|panoramica|tesi")

    is_deep_comprehensive = (
        word_count >= 10 or
        has_word(r"approfondisci|approfondimento|completo|completa|dettagliata|dettagliato|trattazione|panoramica|relazione|dimostrazione|comparativa|confronto|tutto|tutti|differenze")
    )

    if requested_k is not None:
        k_tot = max(5, min(int(requested_k), 35))
        scope_desc = f"Personalizzato (k={k_tot})"
    elif is_thesis_or_macro:
        k_tot = 28
        scope_desc = "Tesi / Macro Ricerca (k=28)"
    elif is_short_factual:
        k_tot = 8
        scope_desc = "Conciso / Mirato (k=8)"
    elif is_deep_comprehensive:
        k_tot = 18
        scope_desc = "Approfondito / Esaustivo (k=18)"
    else:
        k_tot = 14
        scope_desc = "Standard / Concettuale (k=14)"

    # ── 2. INTENT & ALLOCAZIONE DINAMICA TRA I TIER (Libri vs Paper vs Slide) ──
    is_theory = has_word(r"dimostrazione|dimostra|teorema|formula|matematica|matematico|formale|rigore|rigoroso|derivazione|manuale|libro|testo|fondamenti|teoria|teorico|algoritmo")
    is_paper  = has_word(r"paper|articolo|articoli|vulnerabilita|attacco|exploit|stato dell\s*arte|benchmark|prestazioni|sperimentale|pubblicazione|autore|proposta originale")
    is_exam   = has_word(r"esame|prof|professore|docente|lezione|lezioni|slide|appunti|notion|orale|domanda d\s*esame|domande|sintesi")

    if is_thesis_or_macro:
        profile_name = "Tesi & Stato dell'Arte (Libri + Paper heavy)"
        ratios = {"resource": 0.45, "article": 0.35, "primary": 0.20}
    elif is_theory and not is_paper:
        profile_name = "Teoria & Formalismo (Libri-heavy)"
        ratios = {"resource": 0.50, "article": 0.25, "primary": 0.25}
    elif is_paper and not is_theory:
        profile_name = "Ricerca & Paper (Articoli-heavy)"
        ratios = {"resource": 0.25, "article": 0.50, "primary": 0.25}
    elif is_exam:
        profile_name = "Focus Esame (Slide-heavy)"
        ratios = {"resource": 0.20, "article": 0.20, "primary": 0.60}
    else:
        profile_name = "Bilanciato Multidisciplinare"
        ratios = {"resource": 0.40, "article": 0.30, "primary": 0.30}

    quota_res = max(1, int(round(k_tot * ratios["resource"])))
    quota_art = max(1, int(round(k_tot * ratios["article"])))
    quota_pri = k_tot - quota_res - quota_art

    return {
        "k_tot": k_tot,
        "scope": scope_desc,
        "profile": profile_name,
        "quotas": {"resource": quota_res, "article": quota_art, "primary": quota_pri}
    }


class HybridRetriever:
    def __init__(self, vector_retriever: VectorRetriever, fulltext_retriever: FulltextRetriever):
        self.vector_retriever = vector_retriever
        self.fulltext_retriever = fulltext_retriever
        self.db = vector_retriever.db

    def search(
        self,
        query: str,
        top_k: int = 5,
        rrf_k: int = 60,
        expand_graph: bool = True,
        # Fallback settings: se le fonti primarie trovano meno di min_primary_hits
        # risultati con buona similarità, integriamo con i tier inferiori
        min_primary_hits: int = 3,
        enable_fallback: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Cascaded Hybrid Search a 3 livelli con Source Tier Fallback.

        Gerarchia di priorità:
          ⭐⭐⭐  primary  — slide, appunti, Notion  (sempre cercate per prime)
          ⭐⭐    resource — libri di testo da resources/  (fallback livello 1)
          ⭐      article  — articoli scientifici / paper  (fallback livello 2)

        Stage 1: cerca SOLO nelle fonti primarie (slide, appunti, notion).
        Stage 2: se i risultati primari sono insufficienti (< min_primary_hits),
                 integra con i libri (resource).
        Stage 3: se i risultati sono ancora insufficienti dopo Stage 2,
                 integra con gli articoli scientifici (article).
        """
        # ── STAGE 1: FONTI PRIMARIE (slides, appunti) ────────────────────────
        primary_results = self._run_hybrid(query, top_k=top_k, rrf_k=rrf_k,
                                           tier_filter="primary", expand_graph=expand_graph)

        if not enable_fallback or len(primary_results) >= min_primary_hits:
            return primary_results

        # ── STAGE 2: FALLBACK LIBRI (resource) ───────────────────────────────
        resource_results = self._run_hybrid(query, top_k=top_k // 2, rrf_k=rrf_k,
                                            tier_filter="resource", expand_graph=False)

        merged = {r["chunk_id"]: r for r in primary_results}
        for r in resource_results:
            cid = r["chunk_id"]
            if cid not in merged:
                r["from_fallback"] = True
                r["fallback_tier"] = "resource"
                merged[cid] = r

        all_results = sorted(merged.values(), key=lambda x: x["rrf_score"], reverse=True)

        if len(all_results) >= min_primary_hits:
            return all_results[:top_k]

        # ── STAGE 3: FALLBACK ARTICOLI (article) ─────────────────────────────
        article_results = self._run_hybrid(query, top_k=top_k // 2, rrf_k=rrf_k,
                                           tier_filter="article", expand_graph=False)

        for r in article_results:
            cid = r["chunk_id"]
            if cid not in merged:
                r["from_fallback"] = True
                r["fallback_tier"] = "article"
                merged[cid] = r

        all_results = sorted(merged.values(), key=lambda x: x["rrf_score"], reverse=True)
        return all_results[:top_k]

    def deep_research(
        self,
        query: str,
        top_k: Optional[int] = None,
        rrf_k: int = 60,
        expand_graph: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Ricerca Approfondita Multi-Tier con k Dinamico e Quote Adattive.

        Calcola automaticamente:
          1. k_tot in base all'ampiezza richiesta (da 8 per factual secche a 18-20 per trattazioni ampie).
          2. Quote interne dinamiche tra Libri (teoria), Paper (ricerca) e Slide (esame).
          3. Dynamic Reallocation: se un corso non ha libri o paper, gli slot liberi
             vengono istantaneamente redistribuiti agli altri tier disponibili.
        """
        profile = infer_query_profile(query, requested_k=top_k)
        k_tot = profile["k_tot"]
        quotas = profile["quotas"]

        quota_resource = quotas["resource"]
        quota_article  = quotas["article"]
        quota_primary  = quotas["primary"]

        # 1. Recupero candidati per ciascun tier separatamente
        res_resource = self._run_hybrid(query, top_k=quota_resource * 2, rrf_k=rrf_k,
                                         tier_filter="resource", expand_graph=False)
        res_article  = self._run_hybrid(query, top_k=quota_article * 2, rrf_k=rrf_k,
                                         tier_filter="article", expand_graph=False)
        res_primary  = self._run_hybrid(query, top_k=quota_primary * 2, rrf_k=rrf_k,
                                         tier_filter="primary", expand_graph=True)

        selected_resource = res_resource[:quota_resource]
        selected_article  = res_article[:quota_article]
        selected_primary  = res_primary[:quota_primary]

        # 2. Dynamic Availability Reallocation (deficit transfer)
        shortfall = (quota_resource - len(selected_resource)) + (quota_article - len(selected_article))

        added_extras = []
        if shortfall > 0:
            used_ids = {r["chunk_id"] for r in (selected_resource + selected_article + selected_primary)}
            surplus_pool = []
            for r in (res_primary[quota_primary:] + res_article[quota_article:] + res_resource[quota_resource:]):
                if r["chunk_id"] not in used_ids:
                    surplus_pool.append(r)
                    used_ids.add(r["chunk_id"])

            if len(surplus_pool) < shortfall:
                extra_open = self._run_hybrid(query, top_k=shortfall * 2, rrf_k=rrf_k,
                                              tier_filter=None, expand_graph=False)
                for r in extra_open:
                    if r["chunk_id"] not in used_ids:
                        surplus_pool.append(r)
                        used_ids.add(r["chunk_id"])

            surplus_pool.sort(key=lambda x: x.get("rrf_score", 0), reverse=True)
            added_extras = surplus_pool[:shortfall]

        final_chunks = selected_resource + selected_article + selected_primary + added_extras
        final_chunks.sort(key=lambda x: x.get("rrf_score", 0), reverse=True)
        results = final_chunks[:k_tot]

        # Annotiamo i metadati del profilo sui chunk per il ContextBuilder
        for r in results:
            r["_query_profile"] = profile

        return results

    def thesis_research(
        self,
        query: str,
        top_k: int = 28,
        rrf_k: int = 60,
        expand_graph: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Ricerca Estesa per Tesi, Dissertazioni e Macro-Sintesi Accademiche (25-30 chunk).
        Campiona stratificatamente su Libri, Articoli scientifici e Slide,
        garantendo un'ampia copertura bibliografica con k esteso.
        """
        k_target = max(20, min(int(top_k), 35))
        return self.deep_research(query=query, top_k=k_target, rrf_k=rrf_k, expand_graph=expand_graph)


    def _run_hybrid(
        self,
        query: str,
        top_k: int,
        rrf_k: int,
        tier_filter: str,        # "primary" | "resource" | None (tutti)
        expand_graph: bool,
    ) -> List[Dict[str, Any]]:
        """
        Esegue la ricerca ibrida (Vector + Fulltext + RRF) filtrando per source_tier.
        """
        # Recupera i risultati da entrambi i retriever, passando il filtro tier
        vec_results = self.vector_retriever.search(query, top_k=top_k * 2,
                                                    tier_filter=tier_filter)
        ft_results  = self.fulltext_retriever.search(query, top_k=top_k * 2,
                                                      tier_filter=tier_filter)

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

        sorted_ids = sorted(scores_map.keys(), key=lambda x: scores_map[x], reverse=True)
        initial_top = sorted_ids[:top_k]

        if not expand_graph or not initial_top:
            return self._build_results(initial_top, chunks_map, scores_map, top_k)

        # Espansione grafo semantico via SIMILAR_TO
        expanded_chunks = self._expand_via_semantic_links(initial_top, chunks_map, scores_map, rrf_k)

        all_ids = set(sorted_ids) | set(expanded_chunks.keys())
        for cid, data in expanded_chunks.items():
            if cid not in chunks_map:
                chunks_map[cid] = data["chunk"]
                scores_map[cid] = data["score"]

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
