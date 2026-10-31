from typing import List, Dict, Any
import json


class ContextBuilder:
    def format_mcp_response(self, query: str, hybrid_results: List[Dict[str, Any]], search_type: str = "standard") -> str:
        """
        Formats retrieved chunks into a dense, token-efficient text for Pi Coding Agent.
        Includes search metadata (type, k distribution across slides/notion, books, articles)
        and strict response preamble instructions.
        """
        n_pri = sum(1 for r in hybrid_results if r.get("source_tier") == "primary")
        n_res = sum(1 for r in hybrid_results if r.get("source_tier") == "resource")
        n_art = sum(1 for r in hybrid_results if r.get("source_tier") == "article")
        tot = len(hybrid_results)

        prof = hybrid_results[0].get("_query_profile", {}) if (hybrid_results and "_query_profile" in hybrid_results[0]) else {}
        is_thesis = (search_type == "thesis_research") or ("Tesi" in prof.get("scope", ""))
        is_deep = (search_type == "deep_research") or bool(prof)

        if is_thesis:
            tipo_label = "Tesi / Macro Ricerca (thesis_research)"
        elif is_deep:
            tipo_label = "Approfondita (deep_research)"
        else:
            tipo_label = "Standard (academic_context)"

        profile_header = (
            f"📊 METADATI RETRIEVAL:\n"
            f"• Tipologia Ricerca: {tipo_label}\n"
            f"• Ripartizione k utilizzata: 🎓 Slide + Notion: {n_pri} | 📖 Libri: {n_res} | 📄 Articoli: {n_art} (Totale k={tot})\n"
        )
        if prof:
            profile_header += f"• Scope Rilevato: {prof.get('scope', 'Dinamico')} | Profilo: {prof.get('profile', 'Bilanciato')}\n"

        profile_header += "\n"

        context_parts = [f"Query: {query}\n\n{profile_header}--- ACADEMIC CONTEXT ---"]

        tier_badges = {
            "resource": "📖 [LIBRO DI TESTO]",
            "article": "📄 [ARTICOLO/PAPER]",
            "primary": "🎓 [SLIDE/APPUNTI]"
        }

        for idx, res in enumerate(hybrid_results):
            tier = res.get('source_tier', 'primary')
            badge = tier_badges.get(tier, "📄 [DOCUMENTO]")
            source_info = f"{badge} [{res['source_type'].upper()}] {res['source_title']}"
            if res.get('page'):
                source_info += f" (Page {res['page']})"
            if res.get('course'):
                source_info += f" | Course: {res['course']}"

            # Indica se il chunk è stato trovato tramite link semantico
            if res.get('via_semantic_link'):
                source_info += f" | 🔗 Via semantic link (sim: {res.get('link_score', 0):.2f})"

            text = res['text'].strip()

            chunk_str = f"Source {idx+1}: {source_info}\nContent:\n{text}\n"
            context_parts.append(chunk_str)

        context_parts.append(
            "\n📌 REQUISITO MANDATORIO DI FORMATTAZIONE RISPOSTA PER L'ASSISTENTE:\n"
            "All'inizio della tua risposta, DEVI OBBLIGATORIAMENTE inserire questo blocco di intestazione:\n"
            f"- **Tipologia di Ricerca**: {tipo_label}\n"
            f"- **Fonti Interrogate (k)**: 🎓 Slide + Notion: {n_pri} | 📖 Libri: {n_res} | 📄 Articoli: {n_art} (Totale k={tot})\n\n"
            "Subito dopo l'intestazione, esponi la spiegazione citando OBBLIGATORIAMENTE la sorgente esatta "
            "tra parentesi quadre indicando documento e pagina per ogni concetto, ad esempio:\n"
            "  `[NomeDocumento.pdf, p. X]` (o `[Notion: TitoloNota]`)\n"
            "Non esporre nozioni senza indicare precisamente da quale Source del contesto provengono.\n"
            "--- END ACADEMIC CONTEXT ---"
        )
        return "\n".join(context_parts)
