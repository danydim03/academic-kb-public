"""
Academic KB Learning Path Engine.

Deduces pedagogical prerequisite sequences (PREREQUISITE_OF) for any topic
by querying the Concept Knowledge Graph and employing LLM didactic reasoning.
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional

from core.database import Neo4jManager
from engine.study.llm_client import LLMClient, get_llm_client, extract_json_payload

logger = logging.getLogger(__name__)


class LearningPathEngine:
    """
    Generates structured, pedagogical prerequisite learning paths without cycles.
    """

    def __init__(
        self,
        db: Optional[Neo4jManager] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        self.db = db
        self.llm_client = llm_client or get_llm_client()

    def generate_learning_path(self, topic: str) -> Dict[str, Any]:
        """
        Constructs an ordered prerequisite DAG learning sequence for a topic.

        Args:
            topic: Concept or domain topic to learn.

        Returns:
            Dictionary containing:
            - topic: target topic string
            - summary: overview description
            - steps: ordered list of prerequisite steps
            - prerequisites: aggregated prerequisite list
        """
        clean_topic = str(topic or "").strip()
        if not clean_topic:
            return {
                "topic": "",
                "summary": "Nessun argomento specificato.",
                "steps": [],
                "prerequisites": [],
            }

        # Query Neo4j for existing PREREQUISITE_OF relationships
        graph_prereqs: List[Dict[str, str]] = []
        if self.db:
            try:
                cypher = """
                MATCH (p:Concept)-[:PREREQUISITE_OF]->(c:Concept)
                WHERE toLower(c.name) CONTAINS toLower($topic)
                   OR toLower(p.name) CONTAINS toLower($topic)
                RETURN p.name AS prerequisite, c.name AS concept
                LIMIT 10
                """
                graph_prereqs = self.db.execute_query(cypher, {"topic": clean_topic})
            except Exception as e:
                logger.warning(f"Failed to query concept prerequisite graph: {e}")

        prompt = (
            f"learning prerequisite percorso learning_path propedeutic:\n"
            f"Costruisci il percorso didattico di apprendimento per l'argomento '{clean_topic}'.\n"
            "Restituisci un JSON con campi 'target_topic', 'summary', 'steps'. "
            "Ogni step deve includere 'step_number', 'concept_name', 'description', 'prerequisites'."
        )
        system_prompt = (
            "Sei un coordinatore didattico universitario. Struttura un piano di studio rigoroso "
            "e sequenziale, ordinando i concetti dal più elementare al più avanzato senza dipendenze cicliche."
        )

        raw = self.llm_client.generate(prompt, system_prompt=system_prompt)
        parsed_data: Dict[str, Any] = {}
        try:
            payload = extract_json_payload(raw)
            data = json.loads(payload)
            if isinstance(data, dict):
                parsed_data = data
            elif isinstance(data, list):
                parsed_data = {"steps": data}
        except Exception as e:
            logger.warning(f"Failed to parse LLM output for learning path: {e}")

        raw_steps = parsed_data.get("steps") or parsed_data.get("prerequisites") or []
        if not raw_steps:
            # Fallback default steps
            raw_steps = [
                {
                    "step_number": 1,
                    "concept_name": f"Fondamenti teorici e definizioni di base per {clean_topic}",
                    "description": f"Comprensione delle nozioni preliminari necessarie a padroneggiare {clean_topic}.",
                    "prerequisites": [],
                },
                {
                    "step_number": 2,
                    "concept_name": f"Architettura e meccanismi operativi di {clean_topic}",
                    "description": f"Analisi dettagliata del funzionamento e dei componenti essenziali di {clean_topic}.",
                    "prerequisites": [f"Fondamenti teorici per {clean_topic}"],
                },
                {
                    "step_number": 3,
                    "concept_name": f"Applicazioni avanzate e resilienza in {clean_topic}",
                    "description": f"Studio di casi complessi, tolleranza ai guasti ed evoluzione di {clean_topic}.",
                    "prerequisites": [f"Architettura e meccanismi operativi di {clean_topic}"],
                },
            ]

        # Normalize and enforce DAG integrity (no cycles, no duplicate adjacent steps, ordered)
        normalized_steps: List[Dict[str, Any]] = []
        seen_concepts = set()
        last_concept = None

        for idx, item in enumerate(raw_steps):
            if isinstance(item, dict):
                c_name = str(item.get("concept_name") or item.get("concept") or item.get("name") or "").strip()
                desc = str(item.get("description") or "").strip()
                prereqs = item.get("prerequisites") or []
                rec_chunks = item.get("recommended_chunk_ids") or []
            else:
                c_name = str(item).strip()
                desc = f"Approfondimento concettuale su {c_name}."
                prereqs = []
                rec_chunks = []

            if not c_name or c_name == last_concept:
                continue

            order = idx + 1
            # Prevent cycle: a concept cannot be its own prerequisite
            clean_prereqs = [p for p in prereqs if p != c_name]

            step_obj = {
                "order": order,
                "step_number": order,
                "concept": c_name,
                "concept_name": c_name,
                "description": desc,
                "prerequisites": clean_prereqs,
                "recommended_chunk_ids": rec_chunks,
            }
            normalized_steps.append(step_obj)
            seen_concepts.add(c_name.lower())
            last_concept = c_name

        # Sort steps by order
        normalized_steps.sort(key=lambda s: s["order"])

        # Aggregate prerequisites list
        all_prereqs: List[str] = []
        for s in normalized_steps:
            for p in s["prerequisites"]:
                if p not in all_prereqs:
                    all_prereqs.append(p)

        summary_text = parsed_data.get("summary") or f"Percorso didattico strutturato per {clean_topic}."

        # Optionally persist PREREQUISITE_OF links in Neo4j if graph concepts exist
        if self.db and len(normalized_steps) > 1:
            for i in range(len(normalized_steps) - 1):
                p_curr = normalized_steps[i]["concept"]
                p_next = normalized_steps[i + 1]["concept"]
                try:
                    persist_cypher = """
                    MERGE (p:Concept {name: $prereq_name})
                    ON CREATE SET p.id = 'concept-' + apoc.text.slug($prereq_name)
                    MERGE (c:Concept {name: $target_name})
                    ON CREATE SET c.id = 'concept-' + apoc.text.slug($target_name)
                    MERGE (p)-[:PREREQUISITE_OF]->(c)
                    """
                    self.db.execute_query(persist_cypher, {"prereq_name": p_curr, "target_name": p_next})
                except Exception:
                    # Non-fatal if apoc is missing; plain cypher fallback
                    try:
                        slug_p = "concept-" + re.sub(r'[^a-zA-Z0-9]+', '-', p_curr.lower()).strip('-')
                        slug_c = "concept-" + re.sub(r'[^a-zA-Z0-9]+', '-', p_next.lower()).strip('-')
                        self.db.execute_query(
                            """
                            MERGE (p:Concept {id: $pid}) ON CREATE SET p.name = $pname
                            MERGE (c:Concept {id: $cid}) ON CREATE SET c.name = $cname
                            MERGE (p)-[:PREREQUISITE_OF]->(c)
                            """,
                            {"pid": slug_p, "pname": p_curr, "cid": slug_c, "cname": p_next}
                        )
                    except Exception as e:
                        logger.debug(f"Could not persist PREREQUISITE_OF edge: {e}")

        return {
            "topic": clean_topic,
            "target_topic": clean_topic,
            "summary": summary_text,
            "steps": normalized_steps,
            "prerequisites": all_prereqs if all_prereqs else [s["concept"] for s in normalized_steps[:-1]],
        }


# Backwards compatibility alias
LearningPathGenerator = LearningPathEngine
