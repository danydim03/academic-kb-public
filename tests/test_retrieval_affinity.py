import pytest
from engine.retrieval.hybrid import infer_query_profile, HybridRetriever

def test_course_affinity_monocourse():
    """Verifica che un corso senza libri o articoli allochi il 100% delle quote a primary."""
    prof_geom = infer_query_profile("spiegami le forme bilineari", requested_k=28, detected_course="GEOMETRIA AROSIO")
    assert prof_geom["quotas"]["resource"] == 0
    assert prof_geom["quotas"]["article"] == 0
    assert prof_geom["quotas"]["primary"] == 28

def test_course_affinity_sdcc_no_books():
    """Verifica che SDCC (privo di libri) allochi le quote solo su slide e articoli."""
    prof_sdcc = infer_query_profile("algoritmo di Paxos", requested_k=28, detected_course="SDCC")
    assert prof_sdcc["quotas"]["resource"] == 0
    assert prof_sdcc["quotas"]["article"] > 0
    assert prof_sdcc["quotas"]["primary"] > 0
    assert prof_sdcc["quotas"]["article"] + prof_sdcc["quotas"]["primary"] == 28

def test_smart_relevance_gate_same_course_preservation():
    """Verifica che fonti dello stesso corso (anche cross-lingua) non vengano mai scartate."""
    same_course_c = {"course": "ML", "vector_score": 0.51, "fulltext_score": None}
    assert HybridRetriever.is_chunk_relevant(same_course_c, detected_course="ML") is True

def test_smart_relevance_gate_cross_course_noise_dropped():
    """Verifica che chunk rumorosi da altri corsi con score bassi vengano scartati."""
    noise_c = {"course": "CNS", "vector_score": 0.52, "fulltext_score": 1.0}
    assert HybridRetriever.is_chunk_relevant(noise_c, detected_course="GEOMETRIA AROSIO") is False

def test_smart_relevance_gate_strong_cross_disciplinary_kept():
    """Verifica che documenti con forte legame tematico interdisciplinare non vengano ignorati."""
    cross_c = {"course": "SDCC", "vector_score": 0.58, "fulltext_score": 4.5}
    assert HybridRetriever.is_chunk_relevant(cross_c, detected_course="CNS") is True
