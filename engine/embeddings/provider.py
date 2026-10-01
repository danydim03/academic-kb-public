from typing import List
import numpy as np
import httpx

class EmbeddingProvider:
    def __init__(self, provider: str, model: str, dimension: int, api_key: str = None, base_url: str = None):
        self.provider = provider.lower() if provider else "mock"
        self.model = model
        self.dimension = dimension
        self.api_key = api_key
        self.base_url = base_url

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if self.provider == "mock":
            return self._mock_embeddings(texts)
        elif self.provider == "openai":
            return self._openai_embeddings(texts)
        elif self.provider == "gemini":
            return self._gemini_embeddings(texts)
        elif self.provider == "ollama":
            return self._ollama_embeddings(texts)
        else:
            raise NotImplementedError(f"Provider '{self.provider}' non supportato. Usa 'openai', 'gemini', 'ollama' o 'mock'.")

    def _openai_embeddings(self, texts: List[str]) -> List[List[float]]:
        url = (self.base_url or "https://api.openai.com/v1").rstrip("/") + "/embeddings"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        # Batch in chunks of 50 to avoid payload limits
        results = []
        batch_size = 50
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            payload = {"input": batch, "model": self.model}
            if "text-embedding-3" in self.model and self.dimension:
                payload["dimensions"] = self.dimension
            resp = httpx.post(url, headers=headers, json=payload, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()["data"]
            # Sort by index
            data.sort(key=lambda x: x["index"])
            results.extend([item["embedding"] for item in data])
        return results

    def _gemini_embeddings(self, texts: List[str]) -> List[List[float]]:
        # Google Generative Language REST API batchEmbedContents
        model_name = self.model if self.model.startswith("models/") else f"models/{self.model}"
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:batchEmbedContents?key={self.api_key}"
        results = []
        batch_size = 50
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            requests = [{"model": model_name, "content": {"parts": [{"text": t}]}} for t in batch]
            resp = httpx.post(url, json={"requests": requests}, timeout=30.0)
            resp.raise_for_status()
            embeddings = resp.json().get("embeddings", [])
            results.extend([e["values"] for e in embeddings])
        return results

    def _ollama_embeddings(self, texts: List[str]) -> List[List[float]]:
        url = (self.base_url or "http://localhost:11434").rstrip("/") + "/api/embed"
        results = []
        batch_size = 30
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            resp = httpx.post(url, json={"model": self.model, "input": batch}, timeout=60.0)
            resp.raise_for_status()
            results.extend(resp.json()["embeddings"])
        return results

    def _mock_embeddings(self, texts: List[str]) -> List[List[float]]:
        # Deterministic mock embedding based on string length (offline testing)
        embeddings = []
        for text in texts:
            np.random.seed(len(text) % 10000)
            emb = np.random.rand(self.dimension).tolist()
            embeddings.append(emb)
        return embeddings
