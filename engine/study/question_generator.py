"""
Academic KB Question Generator Module.

Generates academic study questions (open, multiple-choice, single answer, exercise)
grounded in knowledge graph chunks with configurable difficulty, count, and deduplication.
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional

from engine.study.llm_client import LLMClient, get_llm_client, extract_json_payload
from engine.retrieval.hybrid import HybridRetriever

logger = logging.getLogger(__name__)

DIFFICULTY_MAP = {
    "facile": "easy",
    "easy": "easy",
    "media": "medium",
    "medium": "medium",
    "difficile": "hard",
    "hard": "hard",
    "misto": "mixed",
    "mixed": "mixed",
}


class QuestionGenerator:
    """
    LLM-driven question generator for academic study sessions.
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        retriever: Optional[HybridRetriever] = None,
    ):
        self.llm_client = llm_client or get_llm_client()
        self.retriever = retriever

    def generate_questions(
        self,
        topic: str,
        difficulty: str = "medium",
        question_type: str = "mixed",
        count: int = 5,
        custom_instructions: Optional[str] = None,
        course: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generates study questions for a given topic.

        Args:
            topic: Natural language topic or lecture concept.
            difficulty: 'easy'/'facile', 'medium'/'media', 'hard'/'difficile', or 'mixed'.
            question_type: 'multiple_choice', 'open', 'single_answer', 'exercise', or 'mixed'.
            count: Number of questions to generate (1-20).

        Returns:
            List of question dictionaries conforming to the schema.
        """
        if not topic or not str(topic).strip():
            return []

        clean_topic = str(topic).strip()
        if count <= 0:
            return []

        requested_count = min(20, max(1, int(count)))
        norm_diff = DIFFICULTY_MAP.get(difficulty.lower(), difficulty)
        norm_type = question_type.lower().strip()

        # Retrieve relevant KB context if retriever is provided
        context_chunks: List[str] = []
        source_chunk_ids: List[str] = []
        if self.retriever:
            try:
                hits = self.retriever.search(clean_topic, top_k=5)
                for h in hits:
                    cid = h.get("chunk_id") or h.get("id") or ""
                    if cid:
                        source_chunk_ids.append(cid)
                    text = h.get("text", "")
                    if text:
                        # Mandiamo tutto il testo utile, non solo i primi 300 char
                        context_chunks.append(text)
            except Exception as e:
                logger.warning(f"Retriever search failed during question generation: {e}")

        if not source_chunk_ids:
            source_chunk_ids = [f"chunk_{clean_topic[:10].lower().replace(' ', '_')}_01"]

        # Prompt construction migliorato
        system_prompt = (
            "Sei un docente universitario esperto che crea materiale di studio e prove d'esame. "
            "Il tuo compito è generare domande di verifica di altissima qualità accademica, "
            "basandoti **strettamente ed esclusivamente** sul materiale fornito nei 'Context chunks'.\n"
            "- Non inventare informazioni non presenti nel testo.\n"
            "- Se i chunk non contengono informazioni sufficienti sull'argomento richiesto, genera domande basate su quello che c'è.\n"
            "- NOTAZIONE MATEMATICA E FORMULE: Se l'argomento contiene formule, simboli matematici, matrici, vettori, insiemi, spazi vettoriali, relazioni o notazioni algebriche/probabilistiche (es. R^n, Bil(R^n), x^T A y, Q_g(x), matrici, sommatorie, integrali), DEVI SEMPRE scriverle in formato standard LaTeX racchiuso tra delimitatori '$' per formule inline (es. $Q: \\text{Bil}(\\mathbb{R}^n) \\to \\text{Quad}(\\mathbb{R}^n)$, $x^\\top A y$, $A = \\begin{pmatrix} 1 & 2 \\\\ 2 & 1 \\end{pmatrix}$, $Q_g(x) = g(x,x)$) o '$$...$$' per formule display in blocco.\n"
            "- TIPOLOGIE DI DOMANDE:\n"
            "  * Se TIPO DOMANDE è 'multi_select' (o se lo studente vuole domande a più risposte corrette):\n"
            "    imposta 'type': 'multi_select', 'is_multi': true, fornisci 4 o 5 opzioni e 'correct_options': ['Opzione 1', 'Opzione 3'] (includi ALMENO 2 risposte corrette e almeno 1 errata/distrattore). Il testo della domanda deve esplicitamente richiedere di selezionare tutte le risposte/affermazioni corrette o vere (es. 'Quali delle seguenti affermazioni sono corrette? (Seleziona tutte le opzioni vere)').\n"
            "  * Se TIPO DOMANDE è 'multiple_choice': imposta 'type': 'multiple_choice', fornisci 4 opzioni e 'correct_option': 'La sola stringa corretta'.\n"
            "Devi rispondere ESCLUSIVAMENTE con un JSON valido (no markdown code block o altro testo) che rispetti questo formato esatto:\n"
            "{\n"
            '  "questions": [\n'
            "    {\n"
            '      "question": "testo della domanda (esplicita se ci sono più risposte corrette)",\n'
            '      "answer": "risposta dettagliata e spiegazione",\n'
            '      "type": "open|multiple_choice|multi_select|single_answer|exercise",\n'
            '      "difficulty": "easy|medium|hard",\n'
            '      "options": ["Opzione 1", "Opzione 2", "Opzione 3", "Opzione 4"],\n'
            '      "correct_option": "La stringa esatta della risposta corretta (se singola)",\n'
            '      "correct_options": ["Opzione 1", "Opzione 3"],\n'
            '      "is_multi": true\n'
            "    }\n"
            "  ]\n"
            "}"
        )

        context_text = "\n\n--- CHUNK DI CONTESTO ---\n" + "\n\n".join(context_chunks[:5])

        extra_inst = f"\nISTRUZIONI / FOCUS PERSONALIZZATO DELLO STUDENTE: '{custom_instructions.strip()}'\n" if custom_instructions and custom_instructions.strip() else ""

        user_prompt = (
            f"ARGOMENTO (Topic): '{clean_topic}'\n"
            f"DIFFICOLTA RICHIESTA: {norm_diff}\n"
            f"NUMERO DOMANDE RICHIESTE: {requested_count}\n"
            f"TIPO DOMANDE: {norm_type}\n"
            f"{extra_inst}"
            f"{context_text}\n\n"
            f"Genera ora {requested_count} domande JSON valide estraendo nozioni, differenze chiave o definizioni presenti nel testo. Usa la lingua italiana."
        )

        raw_response = self.llm_client.generate(user_prompt, system_prompt=system_prompt)

        parsed_questions: List[Dict[str, Any]] = []
        try:
            payload = extract_json_payload(raw_response)
            data = json.loads(payload)
            if isinstance(data, list):
                parsed_questions = data
            elif isinstance(data, dict):
                parsed_questions = data.get("questions") or data.get("items") or [data]
        except Exception as e:
            logger.error(f"Fallito parse JSON domande (Risposta: {raw_response[:100]}...): {e}")
            return []

        # Normalization and schema compliance (senza iniettare spazzatura)
        results: List[Dict[str, Any]] = []
        seen_texts = set()

        for idx, item in enumerate(parsed_questions):
            if not isinstance(item, dict):
                continue

            q_text = str(item.get("question") or "").strip()
            if not q_text or len(q_text) < 5:
                continue

            # Ensure distinct questions
            lower_q = q_text.lower()
            if lower_q in seen_texts:
                continue
            seen_texts.add(lower_q)

            ans_text = str(item.get("answer") or item.get("explanation") or "").strip()
            q_item_type = item.get("type", norm_type)
            options = item.get("options") or item.get("choices")
            
            # Se la domanda è a scelta multipla o multi-select e mancano le opzioni, scartiamola
            is_multi = (str(q_item_type).lower() == "multi_select") or bool(item.get("is_multi")) or (isinstance(item.get("correct_options"), list) and len(item.get("correct_options")) > 1)
            if ("multiple" in str(q_item_type).lower() or is_multi) and (not options or len(options) < 2):
                continue

            raw_corr_opts = item.get("correct_options")
            if not raw_corr_opts:
                if item.get("correct_option"):
                    raw_corr_opts = [item.get("correct_option")]
                elif options:
                    raw_corr_opts = [options[0]]
                else:
                    raw_corr_opts = []
            elif isinstance(raw_corr_opts, str):
                raw_corr_opts = [raw_corr_opts]

            assigned_course = item.get("course") or (course if course and course != "ALL" else "MAGISTRALE")
            norm_obj = {
                "id": item.get("id") or f"q_{idx + 1}",
                "course": assigned_course,
                "topic": item.get("topic") or clean_topic,
                "question": q_text,
                "answer": ans_text,
                "type": "multi_select" if is_multi else q_item_type,
                "difficulty": item.get("difficulty") or norm_diff,
                "options": options,
                "correct_option": item.get("correct_option") or (", ".join(raw_corr_opts) if raw_corr_opts else ""),
                "correct_options": raw_corr_opts,
                "is_multi": is_multi,
                "explanation": ans_text,
                "source_chunks": source_chunk_ids,
            }
            results.append(norm_obj)

            if len(results) >= requested_count:
                break

        return results
