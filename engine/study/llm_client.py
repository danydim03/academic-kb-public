"""
Unified Provider-Agnostic LLM Client for Academic KB Study Engine.

Supports:
1. GeminiProvider: Google Gemini API (google-genai / google-generativeai SDKs with httpx REST fallback)
2. OpenAIProvider: OpenAI API and DeepSeek (deepseek-chat via base_url="https://api.deepseek.com")
3. MockProvider: Deterministic, realistic synthetic generator for offline testing without API keys
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import json
import logging
import re
import httpx

from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def extract_json_payload(raw_text: str) -> str:
    """
    Extracts the outermost JSON object or array from model responses,
    stripping markdown fences (```json ... ```) or conversational commentary.
    """
    cleaned = raw_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()
    else:
        first_brace = cleaned.find("{")
        first_bracket = cleaned.find("[")
        if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
            last_brace = cleaned.rfind("}")
            if last_brace != -1:
                cleaned = cleaned[first_brace:last_brace + 1]
        elif first_bracket != -1:
            last_bracket = cleaned.rfind("]")
            if last_bracket != -1:
                cleaned = cleaned[first_bracket:last_bracket + 1]
    return cleaned


class LLMClient(ABC):
    """
    Abstract Base Class for all LLM providers in the Academic KB.
    """

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate raw text from the configured LLM provider.

        Args:
            prompt: User/task prompt containing instructions and context chunks.
            system_prompt: Optional system prompt guiding persona or schema constraints.

        Returns:
            The raw string response from the language model.
        """
        pass


class GeminiProvider(LLMClient):
    """
    Google Gemini Provider.
    Supports official Google SDKs (google-genai or google-generativeai) with automatic
    resilient fallback to direct httpx REST calls (v1beta generateContent).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        if not api_key or not api_key.strip():
            raise ValueError("GeminiProvider requires a valid, non-empty API key.")
        self.api_key = api_key.strip()
        self.model = model or "gemini-2.0-flash"
        self.base_url = (base_url or "https://generativelanguage.googleapis.com").rstrip("/")
        self.timeout = timeout

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        # 1. Try google.genai SDK (v2+)
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=self.api_key)
            config = (
                types.GenerateContentConfig(
                    temperature=0.2,
                    system_instruction=system_prompt,
                )
                if system_prompt
                else types.GenerateContentConfig(temperature=0.2)
            )
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            if response and getattr(response, "text", None):
                return response.text
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"google.genai SDK invocation failed: {e}. Falling back to REST.")

        # 2. Try google.generativeai SDK (v1 legacy)
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model_inst = genai.GenerativeModel(
                model_name=self.model,
                system_instruction=system_prompt,
            )
            response = model_inst.generate_content(
                prompt,
                generation_config={"temperature": 0.2},
            )
            if response and getattr(response, "text", None):
                return response.text
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"google.generativeai SDK invocation failed: {e}. Falling back to REST.")

        # 3. Direct REST Fallback via httpx
        url = f"{self.base_url}/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        try:
            resp = httpx.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError(f"Gemini API returned no candidates: {data}")
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
            if not text:
                raise RuntimeError(f"Empty text in Gemini response candidate parts: {data}")
            return text
        except httpx.HTTPError as e:
            logger.error(f"Gemini REST API request failed: {e}")
            raise RuntimeError(f"Gemini API error ({url}): {e}") from e


class OpenAIProvider(LLMClient):
    """
    OpenAI-compatible Provider.
    Works for OpenAI models (e.g. gpt-4o), DeepSeek (deepseek-chat via base_url='https://api.deepseek.com'),
    and local OpenAI-compatible endpoints (Ollama /v1).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        if not api_key or not api_key.strip():
            raise ValueError("OpenAIProvider requires a valid, non-empty API key.")
        self.api_key = api_key.strip()
        self.model = model or "gpt-4o"
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.timeout = timeout

    def _get_chat_endpoint(self) -> str:
        """Constructs the exact chat/completions URL."""
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        if self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/chat/completions"

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # 1. Try openai SDK if installed
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            resp = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                timeout=self.timeout,
            )
            content = resp.choices[0].message.content
            return content or ""
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"openai SDK invocation failed: {e}. Falling back to REST.")

        # 2. Direct REST fallback via httpx
        url = self._get_chat_endpoint()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }

        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"] or ""
        except httpx.HTTPError as e:
            logger.error(f"OpenAI REST API request failed: {e}")
            raise RuntimeError(f"OpenAI API error ({url}): {e}") from e


class MockProvider(LLMClient):
    """
    Deterministic & Dynamic Mock Provider for offline testing and graceful degradation.
    Returns valid, domain-grounded synthetic JSON responses conforming strictly
    to the Pydantic schemas across all study features.
    """

    def __init__(self, fallback_reason: Optional[str] = None):
        self.fallback_reason = fallback_reason

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        full_text = f"{prompt} {system_prompt or ''}".lower()

        # 1. QUERY EXPANSION
        if any(k in full_text for k in ["expand", "espandi", "query_expand", "sinonim", "synonym"]):
            return self._generate_mock_query_expansion(prompt)

        # 2. THESIS ASSISTANT
        if any(k in full_text for k in ["thesis", "tesi", "outline", "dissertation", "indice"]):
            return self._generate_mock_thesis_outline(prompt)

        # 3. QUESTION GENERATION
        if any(k in full_text for k in ["question", "domand", "generate_question", "quiz", "multiple_choice", "quesito", "exercise", "esercizio"]):
            return self._generate_mock_questions(prompt)

        # 4. LEARNING PATH GENERATION
        if any(k in full_text for k in ["learning", "prerequisite", "percorso", "learning_path", "propedeutic"]):
            return self._generate_mock_learning_path(prompt)

        # 5. CONCEPT EXTRACTION
        if any(k in full_text for k in ["concept", "concett", "extract_concept", "mentions", "entità"]):
            return self._generate_mock_concepts(prompt)

        # 6. PAST EXAM LINKER
        if (
            any(k in full_text for k in ["exam_linker", "link_past_exam", "answers"])
            or (
                any(k in full_text for k in ["exam", "esame", "midterm"])
                and any(k in full_text for k in ["match", "link", "corrispond", "valuta pertinenza", "relevance"])
            )
        ):
            return self._generate_mock_exam_matches(prompt)

        # Generic Fallback
        return json.dumps({
            "status": "mock_success",
            "fallback_reason": self.fallback_reason,
            "message": "MockProvider generated synthetic response successfully."
        }, ensure_ascii=False)

    def _generate_mock_questions(self, prompt: str) -> str:
        # Parse requested count (default 5)
        count = 5
        count_match = re.search(r"(?:generate|genera|esattamente|count[:=]?)\s*(\d+)", prompt, re.IGNORECASE)
        if count_match:
            try:
                count = max(1, min(20, int(count_match.group(1))))
            except ValueError:
                count = 5

        # Detect requested question type
        p_lower = prompt.lower()
        forced_type = None
        if "multiple_choice" in p_lower or "scelta multipla" in p_lower:
            forced_type = "multiple_choice"
        elif "open" in p_lower or "domanda aperta" in p_lower:
            forced_type = "open"
        elif "exercise" in p_lower or "esercizio" in p_lower:
            forced_type = "exercise"
        elif "single_answer" in p_lower or "single_choice" in p_lower or "risposta singola" in p_lower:
            forced_type = "single_answer"

        # Detect difficulty
        difficulty = "medium"
        if "easy" in p_lower or "facile" in p_lower:
            difficulty = "easy"
        elif "hard" in p_lower or "difficile" in p_lower:
            difficulty = "hard"

        # Extract topic keyword from prompt if present
        topic_match = re.search(r"topic\s*['\"]?([^'\"\n,]+)['\"]?", prompt, re.IGNORECASE)
        topic = topic_match.group(1).strip() if topic_match else "Sistemi e Sicurezza delle Reti"

        # Question template pool ensuring 100% distinct strings
        question_templates = [
            {
                "type": "multiple_choice",
                "question": f"Qual è la vulnerabilità fondamentale legata all'uso dell'algoritmo RC4 nel protocollo {topic}?",
                "options": [
                    "A) Riutilizzo del vettore di inizializzazione (IV) a 24 bit con conseguente collisione di keystream",
                    "B) Mancanza di integrità tramite hash crittografico HMAC-SHA256",
                    "C) Dimensione eccessiva della chiave simmetrica negoziata",
                    "D) Mancata autenticazione del server mediante certificati X.509"
                ],
                "answer": "A) Riutilizzo del vettore di inizializzazione (IV) a 24 bit con conseguente collisione di keystream",
                "explanation": "L'IV ridotto a 24 bit causa collisioni rapide di keystream tramite il paradosso del compleanno.",
                "source_chunks": ["chunk_cns_wep_01"]
            },
            {
                "type": "open",
                "question": f"Descrivere il meccanismo di elezione del Leader e la gestione dei term in relazione a {topic}.",
                "options": None,
                "answer": "Quando un nodo follower registra un election timeout, incrementa il proprio term, passa allo stato candidate e invia richieste RequestVote. L'elezione richiede il quorum di maggioranza.",
                "explanation": "Garantisce che esista al più un unico leader legittimo per ciascun term logico.",
                "source_chunks": ["chunk_sdcc_raft_01"]
            },
            {
                "type": "exercise",
                "question": f"Calcolare la probabilità di collisione dell'IV in un sistema associato a {topic} dopo la trasmissione di 4096 pacchetti (assumendo spazio IV pari a 2^24).",
                "options": None,
                "answer": "P(collisione) ≈ 1 - exp(-k^2 / (2 * N)) ≈ 1 - exp(-(4096^2) / (2 * 16777216)) ≈ 39.3%",
                "explanation": "Applicazione diretta dell'approssimazione del paradosso del compleanno con N = 2^24 e k = 2^12.",
                "source_chunks": ["chunk_cns_wep_02"]
            },
            {
                "type": "multiple_choice",
                "question": f"Nell'ambito di {topic}, quale proprietà formale distingue il modello di consistenza Linearizable da quello Sequential?",
                "options": [
                    "A) Linearizable vincola l'ordine delle operazioni al tempo reale globale (real-time order)",
                    "B) Sequential garantisce la serializzabilità delle transazioni concorrenti con lock a 2 fasi",
                    "C) Linearizable consente la lettura di stati stantii se certificati dal quorum di lettura",
                    "D) Sequential richiede sincronizzazione hardware dei clock tramite protocollo PTP"
                ],
                "answer": "A) Linearizable vincola l'ordine delle operazioni al tempo reale globale (real-time order)",
                "explanation": "La linearizzabilità è una proprietà di composizione che rispetta l'ordine di tempo reale tra chiamate e risposte.",
                "source_chunks": ["chunk_sdcc_consistency_01"]
            },
            {
                "type": "single_answer",
                "question": f"Quale struttura crittografica viene utilizzata in {topic} per garantire autenticazione e integrità combinando una chiave segreta con una funzione di hash iterata?",
                "options": None,
                "answer": "HMAC (Keyed-Hash Message Authentication Code)",
                "explanation": "Definito in RFC 2104, protegge contro attacchi di estensione della lunghezza grazie al doppio hashing.",
                "source_chunks": ["chunk_cns_hmac_01"]
            },
            {
                "type": "multiple_choice",
                "question": f"Come mitiga TLS 1.3 gli attacchi di tipo Downgrade e Padding Oracle rispetto alle versioni precedenti di {topic}?",
                "options": [
                    "A) Eliminando i cifrari CBC non autenticati e firmando l'intero transcript dell'handshake",
                    "B) Raddoppiando la dimensione dei blocchi AES a 256 bit in modalità CBC",
                    "C) Obbligando l'uso di chiavi RSA statiche senza forward secrecy",
                    "D) Utilizzando cookie stateless senza verifica di integrità client-side"
                ],
                "answer": "A) Eliminando i cifrari CBC non autenticati e firmando l'intero transcript dell'handshake",
                "explanation": "TLS 1.3 consente unicamente modalità AEAD (GCM, CCM, Poly1305) eliminando le falle legate al padding.",
                "source_chunks": ["chunk_cns_tls_01"]
            },
            {
                "type": "exercise",
                "question": f"In una rete basata su {topic}, determinare il numero minimo di nodi necessari per tollerare f guasti arbitrari (bizantini) in un algoritmo di consenso sincrono.",
                "options": None,
                "answer": "N >= 3f + 1 nodi (risultato classico di Lamport, Shostak e Pease).",
                "explanation": "Per superare i messaggi contraddittori dei nodi traditori serve una maggioranza qualificata di almeno 2f+1 nodi corretti.",
                "source_chunks": ["chunk_sdcc_byzantine_01"]
            },
            {
                "type": "open",
                "question": f"Spiegare perché il padding PKCS#1 v1.5 per RSA risulta vulnerabile all'attacco di Bleichenbacher nel contesto di {topic}.",
                "options": None,
                "answer": "L'oracolo risponde differenziando gli errori se il decifrato inizia o meno con i byte corretti '00 02', consentendo all'attaccante di restringere progressivamente l'intervallo del messaggio in chiaro.",
                "explanation": "Un attacco adaptive chosen-ciphertext basato sulla risposta temporale o sui messaggi di errore del server.",
                "source_chunks": ["chunk_cns_rsa_01"]
            },
            {
                "type": "multiple_choice",
                "question": f"Quale meccanismo di checkpointing e garbage collection viene impiegato per prevenire la crescita infinita del log in {topic}?",
                "options": [
                    "A) Snapshotting dello stato applicativo con compattazione del log",
                    "B) Cancellazione periodica e incondizionata dei primi 100 record",
                    "C) Spostamento asincrono dei dati su storage non ridondante",
                    "D) Riduzione della dimensione del cluster mediante rimozione temporanea di nodi"
                ],
                "answer": "A) Snapshotting dello stato applicativo con compattazione del log",
                "explanation": "Lo stato del log viene consolidato in uno snapshot immutabile e i record applicati vengono eliminati.",
                "source_chunks": ["chunk_sdcc_raft_snapshot_01"]
            },
            {
                "type": "single_answer",
                "question": f"Quale algoritmo vettoriale consente di tracciare le relazioni di causalità parziale tra eventi in {topic} senza richiedere clock fisici sincronizzati?",
                "options": None,
                "answer": "Vector Clocks (Orologi Vettoriali di Mattern e Fidge)",
                "explanation": "Ciascun processo mantiene un vettore di interi che riflette lo stato di conoscenza causale degli altri nodi.",
                "source_chunks": ["chunk_sdcc_clocks_01"]
            }
        ]

        questions = []
        for i in range(count):
            tpl = question_templates[i % len(question_templates)]
            q_type = forced_type or tpl["type"]

            # If user explicitly forced multiple_choice but template is open/exercise, convert it
            options = tpl["options"]
            answer = tpl["answer"]
            if q_type == "multiple_choice" and not options:
                options = [
                    f"A) {answer}",
                    f"B) Approccio non deterministico senza garanzie formali per {topic}",
                    f"C) Ridondanza passiva limitata ad architetture single-tenant",
                    f"D) Disabilitazione della cifratura per ottimizzare il throughput di rete"
                ]
                answer = options[0]
            elif q_type != "multiple_choice":
                options = None

            q_obj = {
                "id": f"q_{i+1}",
                "question": f"[{i+1}] {tpl['question']}" if count > len(question_templates) else tpl["question"],
                "type": q_type,
                "difficulty": difficulty,
                "options": options,
                "answer": answer,
                "explanation": tpl["explanation"],
                "source_chunks": tpl["source_chunks"],
            }
            questions.append(q_obj)

        return json.dumps({"questions": questions}, ensure_ascii=False)

    def _generate_mock_concepts(self, prompt: str) -> str:
        concepts = [
            {
                "name": "HMAC",
                "description": "Meccanismo di autenticazione dei messaggi basato su funzioni hash crittografiche (RFC 2104).",
                "aliases": ["Hash MAC", "RFC 2104", "Keyed-Hash"],
                "relevance_score": 0.96,
            },
            {
                "name": "Raft Consensus",
                "description": "Protocollo di consenso per la gestione coerente di registri replicati in cluster distribuiti.",
                "aliases": ["Raft Protocol", "Raft State Machine"],
                "relevance_score": 0.94,
            },
            {
                "name": "Linearizability",
                "description": "Modello di consistenza forte in cui ogni operazione appare istantanea tra invocazione e completamento.",
                "aliases": ["Atomic Consistency", "Strong Consistency"],
                "relevance_score": 0.89,
            },
            {
                "name": "Vector Clocks",
                "description": "Meccanismo logico per ordinare causalmente eventi in un sistema distribuito asincrono.",
                "aliases": ["Orologi Vettoriali", "Vector Timestamps"],
                "relevance_score": 0.88,
            }
        ]
        return json.dumps({"concepts": concepts}, ensure_ascii=False)

    def _generate_mock_exam_matches(self, prompt: str) -> str:
        matches = [
            {
                "exam_question_id": "eq_past_01",
                "chunk_id": "chunk_cns_wep_01",
                "relevance_score": 0.94,
                "explanation": "Il chunk illustra in dettaglio la debolezza dell'IV a 24 bit e l'attacco FMS richiesto nel tema d'esame."
            },
            {
                "exam_question_id": "eq_past_02",
                "chunk_id": "chunk_sdcc_raft_01",
                "relevance_score": 0.91,
                "explanation": "Il chunk spiega formalmente le condizioni di elezione e la gestione dei term nell'algoritmo Raft."
            }
        ]
        return json.dumps({"matches": matches}, ensure_ascii=False)

    def _generate_mock_learning_path(self, prompt: str) -> str:
        steps = [
            {
                "step_number": 1,
                "concept_name": "Crittografia Simmetrica e Funzioni Hash",
                "description": "Studio di cifrari a blocchi, stream ciphers, proprietà di resistenza alle collisioni e HMAC.",
                "prerequisites": [],
                "recommended_chunk_ids": ["chunk_cns_crypto_01"]
            },
            {
                "step_number": 2,
                "concept_name": "Protocolli di Autenticazione e Sicurezza Wireless",
                "description": "Analisi dell'incapsulamento WEP, WPA2/WPA3, vulnerabilità dell'IV e 4-way handshake.",
                "prerequisites": ["Crittografia Simmetrica e Funzioni Hash"],
                "recommended_chunk_ids": ["chunk_cns_wep_01"]
            },
            {
                "step_number": 3,
                "concept_name": "Sistemi Distribuiti e Consenso Tollerante ai Guasti",
                "description": "Introduzione ai modelli di fallimento, teorema CAP, architetture a quorum e Raft.",
                "prerequisites": ["Crittografia Simmetrica e Funzioni Hash"],
                "recommended_chunk_ids": ["chunk_sdcc_raft_01"]
            }
        ]
        return json.dumps({
            "target_topic": "Sicurezza e Resilienza nei Sistemi Distribuiti",
            "summary": "Percorso didattico strutturato dai concetti crittografici fondamentali alla tolleranza ai guasti.",
            "steps": steps
        }, ensure_ascii=False)

    def _generate_mock_query_expansion(self, prompt: str) -> str:
        # Extract original query tokens
        q_match = re.search(r"['\"]([^'\"]+)['\"]", prompt)
        original = q_match.group(1).strip() if q_match else "crittografia di rete"

        terms = [
            "autenticazione HMAC",
            "analisi keystream",
            "protocolli crittografici",
            "vulnerabilità 802.11",
            "standard RFC"
        ]
        expanded_query = f"{original} " + " ".join(terms)
        return json.dumps({
            "expanded_terms": terms,
            "expanded_query": expanded_query
        }, ensure_ascii=False)

    def _generate_mock_thesis_outline(self, prompt: str) -> str:
        title_match = re.search(r"['\"]([^'\"]+)['\"]", prompt)
        title = title_match.group(1).strip() if title_match else "Analisi della Resilienza nei Sistemi Distribuiti Accademici"

        outline = {
            "title": title,
            "abstract": (
                "La presente dissertazione analizza le intersezioni tra protocolli di sicurezza crittografica "
                "e algoritmi di consenso distribuito nel contesto dei sistemi accademici ad alta affidabilità."
            ),
            "table_of_contents": [
                {
                    "section_number": 1,
                    "title": "Introduzione e Modelli Fondamentali",
                    "summary": "Definizione formale degli scenari di rete, assunzioni di sincronia e modelli di minaccia.",
                    "subsections": [
                        {
                            "sub_title": "1.1 Teorema CAP e Limiti Teorici",
                            "summary": "Analisi dei compromessi tra coerenza, disponibilità e partizionamento.",
                            "citations": [
                                {
                                    "chunk_id": "chunk_sdcc_cap_01",
                                    "source_title": "SDCC - Lezione 3: Consistenza nei Sistemi Distribuiti",
                                    "summary_point": "Formalizzazione del partizionamento di rete nel modello asincrono."
                                }
                            ]
                        }
                    ]
                },
                {
                    "section_number": 2,
                    "title": "Protocolli di Consenso Replicato",
                    "summary": "Studio comparativo tra Paxos, Raft e protocolli BFT.",
                    "subsections": [
                        {
                            "sub_title": "2.1 Elezione e Log Replication in Raft",
                            "summary": "Valutazione empirica della convergenza del cluster durante election timeout.",
                            "citations": [
                                {
                                    "chunk_id": "chunk_sdcc_raft_01",
                                    "source_title": "SDCC - Lezione 8: L'algoritmo Raft",
                                    "summary_point": "Proprietà di sicurezza del log matching e commit rule."
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        return json.dumps(outline, ensure_ascii=False)


def get_llm_client(settings: Optional[Settings] = None) -> LLMClient:
    """
    Factory function for obtaining the configured LLMClient.
    Gracefully falls back to MockProvider if API keys are missing or provider is set to 'mock'.
    Guarantees zero crashes on application or MCP server startup.
    """
    settings = settings or get_settings()
    provider = (settings.llm_provider or "mock").lower().strip()
    api_key = settings.effective_llm_api_key

    if provider == "mock":
        return MockProvider()

    elif provider == "gemini":
        if not api_key:
            logger.warning("LLM_PROVIDER='gemini' but no API key is configured. Falling back to MockProvider.")
            return MockProvider(fallback_reason="missing_gemini_api_key")
        model = settings.llm_model or "gemini-2.0-flash"
        if not model.startswith("gemini"):
            model = "gemini-2.0-flash"
        base_url = settings.llm_base_url
        if base_url and ("localhost" in base_url or "127.0.0.1" in base_url):
            base_url = None
        return GeminiProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
        )

    elif provider in ("openai", "deepseek"):
        if not api_key:
            logger.warning(f"LLM_PROVIDER='{provider}' but no API key is configured. Falling back to MockProvider.")
            return MockProvider(fallback_reason=f"missing_{provider}_api_key")

        base_url = settings.llm_base_url
        # If base_url was pointing to localhost from ollama config, reset to provider default
        if base_url and ("localhost" in base_url or "127.0.0.1" in base_url):
            base_url = None

        if provider == "deepseek" and not base_url:
            base_url = "https://api.deepseek.com"
        elif provider == "openai" and not base_url:
            base_url = "https://api.openai.com/v1"

        default_model = "deepseek-chat" if provider == "deepseek" else "gpt-4o"
        model = settings.llm_model or default_model
        if provider == "deepseek" and "deepseek" not in model.lower():
            model = "deepseek-chat"
        elif provider == "openai" and (model.startswith("gemini") or model.startswith("llama")):
            model = "gpt-4o"

        return OpenAIProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
        )

    elif provider == "ollama":
        base_url = (settings.llm_base_url or "http://localhost:11434").rstrip("/")
        model = settings.llm_model or "llama3.2"
        return OpenAIProvider(
            api_key=api_key or "ollama",
            model=model,
            base_url=f"{base_url}/v1",
        )

    else:
        logger.warning(f"Unknown LLM provider '{provider}'. Defaulting to MockProvider.")
        return MockProvider(fallback_reason=f"unknown_provider_{provider}")
