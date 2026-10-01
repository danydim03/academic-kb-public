from typing import List, Dict, Any
import json


class ContextBuilder:
    def format_mcp_response(self, query: str, hybrid_results: List[Dict[str, Any]]) -> str:
        """
        Formats retrieved chunks into a dense, token-efficient text for Pi Coding Agent.
        Distinguishes between direct search results and graph-expanded results.
        """
        context_parts = [f"Query: {query}\n\n--- ACADEMIC CONTEXT ---"]

        for idx, res in enumerate(hybrid_results):
            source_info = f"[{res['source_type'].upper()}] {res['source_title']}"
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

        context_parts.append("--- END ACADEMIC CONTEXT ---")
        return "\n".join(context_parts)
