import re
import unicodedata
from typing import List, Dict, Any, Optional
from engine.retrieval.vector import VectorRetriever
from engine.retrieval.fulltext import FulltextRetriever
from core.database import Neo4jManager


# Mappa dei tier realmente disponibili per ciascun corso nel Knowledge Graph
COURSE_AVAILABLE_TIERS = {
    "GEOMETRIA AROSIO": {"primary"},
    "SE": {"primary"},
    "SERT": {"primary"},
    "MAGISTRALE": {"primary"},
    "SDCC": {"primary", "article"},
    "CNS": {"primary", "resource", "article"},
    "ML": {"primary", "resource", "article"},
}

# Parole chiave esplicite per il routing rapido verso il corso di riferimento
COURSE_KEYWORDS = {
    "GEOMETRIA AROSIO": [
        r"geometria", r"arosio", r"forme\s+bilineari", r"forma\s+bilineare",
        r"forme\s+quadratiche", r"forma\s+quadratica", r"matrice\s+di\s+gram",
        r"sylvester", r"segnatura", r"prodotto\s+scalare", r"spazi\s+vettoriali",
        r"diagonalizzazione", r"autovalor\w*", r"autovettor\w*", r"spazio\s+duale",
        r"prodotto\s+interno", r"cauchy[- ]schwarz", r"indipendenza\s+lineare"
    ],
    "CNS": [
        r"cns\b", r"crittografia", r"bleichenbacher", r"cifrar\w*", r"rsa\b",
        r"diffie[- ]hellman", r"aes\b", r"des\b", r"sha\d*", r"autenticazione",
        r"radius", r"diameter", r"kerberos", r"tls\b", r"ssl\b", r"wep\b", r"wpa",
        r"padding\s+oracle", r"hmac", r"firma\s+digitale", r"certificat\w*", r"pki\b"
    ],
    "SDCC": [
        r"sdcc\b", r"sistemi\s+distribuiti", r"cloud", r"paxos", r"raft",
        r"consensus", r"docker", r"kubernetes", r"mapreduce", r"kafka",
        r"grpc", r"rpc\b", r"vector\s+clock", r"lamport", r"cap\s+theorem",
        r"serverless", r"consistent\s+hashing", r"microservi\w*"
    ],
    "ML": [
        r"\bml\b", r"machine\s+learning", r"deep\s+learning", r"backpropagation",
        r"gradient\s+descent", r"gradiente\s+discendente", r"neural\s+network",
        r"reti\s+neurali", r"svm\b", r"clustering", r"random\s+forest",
        r"overfitting", r"underfitting", r"regolarizzazione", r"bias[- ]variance"
    ],
    "SERT": [
        r"sert\b", r"real[- ]time", r"tempo\s+reale", r"rate\s+monotonic",
        r"earliest\s+deadline", r"edf\b", r"priority\s+inversion", r"priority\s+ceiling",
        r"wcet\b", r"schedulabilit\w*"
    ],
    "SE": [
        r"sistemi\s+embedded", r"embedded\s+system\w*"
    ]
}


def infer_query_profile(query: str, requested_k: Optional[int] = None, detected_course: Optional[str] = None) -> Dict[str, Any]:
    """
    Analizza la query in modo deterministico (0ms latenza) per calcolare:
    1. k_tot dinamico (da 8 per factual/definizioni fino a 20 per trattazioni complesse).
    2. Ripartizione dinamica delle quote tra Libri (teoria), Paper (ricerca) e Slide (esame).
    3. Course-Affinity Gating: se il corso non ha libri o articoli nel Knowledge Graph,
       alloca automaticamente il 100% delle quote alle fonti primarie di quel corso.
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

    # ── 2. COURSE-AFFINITY GATING: Controllo disponibilità tier reali nel corso ─
    if detected_course and detected_course in COURSE_AVAILABLE_TIERS:
        avail = COURSE_AVAILABLE_TIERS[detected_course]
        # Se il corso NON ha libri né articoli (es. GEOMETRIA AROSIO, SE, SERT)
        if avail == {"primary"}:
            return {
                "k_tot": k_tot,
                "scope": f"{detected_course} Monocorso (k={k_tot})",
                "profile": f"Corso {detected_course} (100% Slide/Appunti)",
                "detected_course": detected_course,
                "quotas": {"resource": 0, "article": 0, "primary": k_tot}
            }
        # Se il corso ha articoli ma NON libri (es. SDCC)
        elif "resource" not in avail and "article" in avail:
            quota_art = int(round(k_tot * (0.50 if is_thesis_or_macro else 0.40)))
            quota_pri = k_tot - quota_art
            return {
                "k_tot": k_tot,
                "scope": f"{detected_course} (Slide + Paper, k={k_tot})",
                "profile": f"Corso {detected_course} (Slide + Articoli)",
                "detected_course": detected_course,
                "quotas": {"resource": 0, "article": quota_art, "primary": quota_pri}
            }

    # ── 3. INTENT & ALLOCAZIONE DINAMICA TRA I TIER (Libri vs Paper vs Slide) ──
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
        "detected_course": detected_course,
        "quotas": {"resource": quota_res, "article": quota_art, "primary": quota_pri}
    }


class HybridRetriever:
    def __init__(self, vector_retriever: VectorRetriever, fulltext_retriever: FulltextRetriever):
        self.vector_retriever = vector_retriever
        self.fulltext_retriever = fulltext_retriever
        self.db = vector_retriever.db

    @staticmethod
    def is_chunk_relevant(chunk: Dict[str, Any], detected_course: Optional[str] = None) -> bool:
        """
        Filtro di pertinenza intelligente a 3 livelli:
        1. Stesso corso di appartenenza: massima permissività per NON ignorare fonti primarie,
           libri o paper rilevanti (anche cross-lingua o molto specifici).
        2. Materiale generale o senza corso target dominante (es. query trasversali o MAGISTRALE).
        3. Cross-course gating: scarta candidati da altri corsi a meno che non abbiano un
           collegamento disciplinare forte e inequivocabile (BM25 >= 3.5 o Vector >= 0.62).
        """
        c_course = chunk.get("course")
        v_score = chunk.get("vector_score") or 0.0
        f_score = chunk.get("fulltext_score") or 0.0
        both = (v_score > 0.0 and f_score > 0.0)

        # 1. Stesso corso di riferimento: conserva sempre le fonti del corso
        if detected_course and c_course == detected_course:
            return (v_score >= 0.49 or f_score >= 0.5 or both)

        # 2. Materiale generale / cross-curriculare (senza corso o MAGISTRALE)
        if not detected_course or c_course == "MAGISTRALE":
            if f_score >= 1.5:
                return True
            if v_score >= 0.53:
                return True
            if both and v_score >= 0.50 and f_score >= 0.8:
                return True
            return False

        # 3. Candidato proveniente da un corso DIVERSO da quello rilevato:
        #    deve presentare una convergenza lessicale o semantica solida per non essere rumore.
        if f_score >= 3.5:
            return True
        if v_score >= 0.62:
            return True
        if both and v_score >= 0.56 and f_score >= 2.0:
            return True
        return False

    def detect_course_affinity(self, query: str) -> Optional[str]:
        """
        Rileva se la query appartiene in modo univoco o dominante a un corso del Knowledge Graph.
        1. Controlla prima le parole chiave esplicite (regex COURSE_KEYWORDS).
        2. Se non univoco, esegue un probe rapido (top 8) su Fulltext per verificare
           la convergenza verso un singolo corso (>= 60% di affinità).
        """
        norm_q = query.lower()
        # 1. Match euristico esplicito
        for course, patterns in COURSE_KEYWORDS.items():
            for pat in patterns:
                if re.search(r"\b" + pat + r"\b", norm_q):
                    return course

        # 2. Probe rapido tramite Fulltext
        try:
            probe_hits = self.fulltext_retriever.search(query, top_k=8)
            courses = [h["course"] for h in probe_hits if h.get("course") and h.get("course") != "MAGISTRALE"]
            if not courses:
                courses = [h["course"] for h in probe_hits if h.get("course")]
            if courses:
                from collections import Counter
                counts = Counter(courses)
                top_c, count = counts.most_common(1)[0]
                if count / len(courses) >= 0.60:
                    return top_c
        except Exception:
            pass

        return None

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
        detected_course = self.detect_course_affinity(query)

        # ── STAGE 1: FONTI PRIMARIE (slides, appunti) ────────────────────────
        primary_results = self._run_hybrid(query, top_k=top_k, rrf_k=rrf_k,
                                           tier_filter="primary", expand_graph=expand_graph,
                                           course_filter=detected_course)

        if not enable_fallback or len(primary_results) >= min_primary_hits:
            return primary_results

        # ── STAGE 2: FALLBACK LIBRI (resource) ───────────────────────────────
        # Se il corso non ha libri (es. GEOMETRIA, SDCC), salta il fallback libri
        avail = COURSE_AVAILABLE_TIERS.get(detected_course, set()) if detected_course else {"resource", "article"}
        resource_results = []
        if not detected_course or "resource" in avail:
            resource_results = self._run_hybrid(query, top_k=top_k // 2, rrf_k=rrf_k,
                                                tier_filter="resource", expand_graph=False,
                                                course_filter=detected_course if detected_course in ("CNS", "ML") else None)

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
        article_results = []
        if not detected_course or "article" in avail:
            article_results = self._run_hybrid(query, top_k=top_k // 2, rrf_k=rrf_k,
                                               tier_filter="article", expand_graph=False,
                                               course_filter=detected_course if detected_course in ("SDCC", "CNS", "ML") else None)

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
        course_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Ricerca Approfondita Multi-Tier con k Dinamico e Quote Adattive.

        Calcola automaticamente:
          1. k_tot in base all'ampiezza richiesta (da 8 per factual secche a 18-20 per trattazioni ampie).
          2. Course-Affinity Gating: identifica se la query appartiene a un corso specifico.
             Se il corso non ha libri o articoli nel grafo, alloca il 100% dei chunk
             alle fonti primarie del corso senza sconfinare in altri corsi.
          3. Dynamic Reallocation: se un tier non ha chunk sufficienti, gli slot liberi
             vengono istantaneamente redistribuiti agli altri tier disponibili.
        """
        detected_course = course_filter or self.detect_course_affinity(query)
        profile = infer_query_profile(query, requested_k=top_k, detected_course=detected_course)
        k_tot = profile["k_tot"]
        quotas = profile["quotas"]

        quota_resource = quotas["resource"]
        quota_article  = quotas["article"]
        quota_primary  = quotas["primary"]

        # 1. Recupero candidati per ciascun tier (isolando per corso se rilevato)
        res_resource = []
        if quota_resource > 0:
            c_filter = detected_course if detected_course in ("CNS", "ML") else None
            res_resource = self._run_hybrid(query, top_k=quota_resource * 2, rrf_k=rrf_k,
                                             tier_filter="resource", expand_graph=False,
                                             course_filter=c_filter)

        res_article = []
        if quota_article > 0:
            c_filter = detected_course if detected_course in ("SDCC", "CNS", "ML") else None
            res_article  = self._run_hybrid(query, top_k=quota_article * 2, rrf_k=rrf_k,
                                             tier_filter="article", expand_graph=False,
                                             course_filter=c_filter)

        res_primary = []
        if quota_primary > 0:
            res_primary  = self._run_hybrid(query, top_k=quota_primary * 2, rrf_k=rrf_k,
                                             tier_filter="primary", expand_graph=True,
                                             course_filter=detected_course)

        # Smart Relevance Gate: preserva documenti e libri legittimi, scarta il rumore fuori dominio
        valid_resource = [r for r in res_resource if self.is_chunk_relevant(r, detected_course)]
        valid_article  = [r for r in res_article if self.is_chunk_relevant(r, detected_course)]
        valid_primary  = [r for r in res_primary if self.is_chunk_relevant(r, detected_course)]

        selected_resource = valid_resource[:quota_resource]
        selected_article  = valid_article[:quota_article]
        selected_primary  = valid_primary[:quota_primary]

        # 2. Dynamic Availability & Relevance Reallocation (deficit transfer)
        shortfall = (quota_resource - len(selected_resource)) + (quota_article - len(selected_article))

        added_extras = []
        if shortfall > 0:
            used_ids = {r["chunk_id"] for r in (selected_resource + selected_article + selected_primary)}
            surplus_pool = []
            for r in (valid_primary[quota_primary:] + valid_article[quota_article:] + valid_resource[quota_resource:]):
                if r["chunk_id"] not in used_ids:
                    surplus_pool.append(r)
                    used_ids.add(r["chunk_id"])

            if len(surplus_pool) < shortfall:
                extra_open = self._run_hybrid(query, top_k=shortfall * 3, rrf_k=rrf_k,
                                              tier_filter="primary" if detected_course else None,
                                              expand_graph=False,
                                              course_filter=detected_course)
                for r in extra_open:
                    if r["chunk_id"] not in used_ids and self.is_chunk_relevant(r, detected_course):
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
        course_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Ricerca Estesa per Tesi, Dissertazioni e Macro-Sintesi Accademiche (25-30 chunk).
        Campiona stratificatamente su Libri, Articoli scientifici e Slide,
        garantendo un'ampia copertura bibliografica con k esteso.
        """
        k_target = max(20, min(int(top_k), 35))
        return self.deep_research(query=query, top_k=k_target, rrf_k=rrf_k, expand_graph=expand_graph, course_filter=course_filter)


    def _run_hybrid(
        self,
        query: str,
        top_k: int,
        rrf_k: int,
        tier_filter: Optional[str],        # "primary" | "resource" | "article" | None (tutti)
        expand_graph: bool,
        course_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Esegue la ricerca ibrida (Vector + Fulltext + RRF) filtrando per source_tier e course_filter.
        """
        # Recupera i risultati da entrambi i retriever, passando i filtri
        vec_results = self.vector_retriever.search(query, top_k=top_k * 2,
                                                    tier_filter=tier_filter,
                                                    course_filter=course_filter)
        ft_results  = self.fulltext_retriever.search(query, top_k=top_k * 2,
                                                      tier_filter=tier_filter,
                                                      course_filter=course_filter)

        # Reciprocal Rank Fusion (RRF)
        scores_map = {}
        chunks_map = {}

        for rank, res in enumerate(vec_results):
            chunk_id = res['chunk_id']
            if chunk_id not in chunks_map:
                chunks_map[chunk_id] = res.copy()
            chunks_map[chunk_id]['vector_score'] = res.get('score', 0.0)
            scores_map[chunk_id] = scores_map.get(chunk_id, 0.0) + (1.0 / (rrf_k + rank + 1))

        for rank, res in enumerate(ft_results):
            chunk_id = res['chunk_id']
            if chunk_id not in chunks_map:
                chunks_map[chunk_id] = res.copy()
            chunks_map[chunk_id]['fulltext_score'] = res.get('score', 0.0)
            scores_map[chunk_id] = scores_map.get(chunk_id, 0.0) + (1.0 / (rrf_k + rank + 1))

        sorted_ids = sorted(scores_map.keys(), key=lambda x: scores_map[x], reverse=True)
        initial_top = sorted_ids[:top_k]

        if not expand_graph or not initial_top:
            return self._build_results(initial_top, chunks_map, scores_map, top_k)

        # Espansione grafo semantico via SIMILAR_TO
        expanded_chunks = self._expand_via_semantic_links(initial_top, chunks_map, scores_map, rrf_k, course_filter=course_filter)

        all_ids = set(sorted_ids) | set(expanded_chunks.keys())
        for cid, data in expanded_chunks.items():
            if cid not in chunks_map:
                chunks_map[cid] = data["chunk"]
                scores_map[cid] = data["score"]

        final_sorted = sorted(all_ids, key=lambda x: scores_map.get(x, 0), reverse=True)
        return self._build_results(final_sorted, chunks_map, scores_map, top_k)


    def _expand_via_semantic_links(
        self, seed_chunk_ids: List[str], chunks_map: dict, scores_map: dict, rrf_k: int,
        course_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dato un set di chunk iniziali, trova chunk collegati tramite SIMILAR_TO
        che provengono da documenti diversi.
        """
        expanded = {}

        try:
            course_clause = "AND doc.course = $course_filter" if course_filter else ""
            params = {"seed_ids": seed_chunk_ids}
            if course_filter:
                params["course_filter"] = course_filter

            neighbors = self.db.execute_query(f"""
                UNWIND $seed_ids AS seed_id
                MATCH (seed:Chunk {id: seed_id})-[sim:SIMILAR_TO]-(neighbor:Chunk)
                WHERE NOT neighbor.id IN $seed_ids
                MATCH (doc:Document)-[:HAS_CHUNK]->(neighbor)
                WHERE 1=1 {course_clause}
                RETURN DISTINCT
                    neighbor.id AS chunk_id,
                    neighbor.text AS text,
                    neighbor.page AS page,
                    doc.title AS source_title,
                    doc.source_type AS source_type,
                    doc.source_tier AS source_tier,
                    doc.course AS course,
                    max(sim.score) AS sim_score,
                    seed_id AS from_chunk
                ORDER BY sim_score DESC
                LIMIT 6
            """, params)

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
