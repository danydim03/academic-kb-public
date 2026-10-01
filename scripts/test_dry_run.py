import os
import json
from connectors.files.pdf import PDFConnector
from engine.ingestion.chunking import TextChunker
from engine.embeddings.provider import EmbeddingProvider

def test_pipeline():
    pdf_dir = "test_pdfs"
    print(f"Testing PDF ingestion from {pdf_dir}...")
    
    connector = PDFConnector(directory=pdf_dir, course_name="Sistemi Operativi")
    chunker = TextChunker(chunk_size=150, chunk_overlap=20) # Small chunk size for testing
    embedder = EmbeddingProvider(provider="mock", model="mock-model", dimension=16) # Small dimension
    
    docs = list(connector.extract())
    print(f"Extracted {len(docs)} documents.")
    
    for doc in docs:
        print(f"\nDocument: {doc.title}")
        print(f"ID: {doc.id}")
        print(f"Course: {doc.course}")
        print(f"Checksum: {doc.checksum}")
        print("-" * 40)
        
        chunks = chunker.chunk_document(doc)
        print(f"Generated {len(chunks)} chunks.")
        
        if chunks:
            texts = [c.text for c in chunks]
            embeddings = embedder.get_embeddings(texts)
            
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                print(f"\nChunk {i+1} (ID: {chunk.id})")
                print(f"Text: {chunk.text.strip()}")
                print(f"Embedding length: {len(emb)}")
                print(f"Embedding sample: {emb[:3]}...")
                
if __name__ == "__main__":
    test_pipeline()
