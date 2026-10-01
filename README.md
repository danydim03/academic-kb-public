# Academic KB

This is a 3D visualization and retrieval system for academic courses (Machine Learning, Distributed Systems, Cybersecurity, etc.).

## 🚀 Quick Start (Mock Mode)

To quickly view the 3D graph without setting up the entire database pipeline, a functional mock dataset is provided (`graph_3d_data.json`).

1. Start a local HTTP server:
   ```bash
   python3 -m http.server 8090
   ```
2. Open your browser and navigate to: [http://localhost:8090/graph_3d.html](http://localhost:8090/graph_3d.html)

The UI will load the mock dataset and you can explore the relationships, use the Ego-Network search, and interact with the 3D physics engine.

## 🛠 Full Database Setup (Neo4j & Embeddings)

If you want to ingest your own documents and generate your own semantic links, follow these steps:

1. Copy `.env.example` to `.env` and fill in your API keys (e.g., Notion, OpenAI/Gemini, and Neo4j password).
2. Start the Neo4j database using Docker:
   ```bash
   docker-compose up -d
   ```
3. Run the ingestion pipeline (ensure you have installed dependencies from `pyproject.toml`):
   ```bash
   python scripts/index.py
   python scripts/build_semantic_links.py
   ```
