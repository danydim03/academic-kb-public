import uuid
from typing import List
from core.models import Document, Chunk

class TextChunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(self, document: Document) -> List[Chunk]:
        raw_text = document.metadata.get("raw_text", "")
        if not raw_text:
            return []

        # Very basic sliding window chunker
        chunks = []
        start = 0
        text_length = len(raw_text)
        index = 0

        while start < text_length:
            end = start + self.chunk_size
            chunk_text = raw_text[start:end]
            
            # Simple page heuristic extraction for PDF
            page = None
            if "--- PAGE" in chunk_text:
                import re
                match = re.search(r"--- PAGE (\d+) ---", chunk_text)
                if match:
                    page = int(match.group(1))

            chunk = Chunk(
                id=str(uuid.uuid4()),
                document_id=document.id,
                index=index,
                text=chunk_text,
                page=page,
                metadata={
                    "source_title": document.title,
                    "course": document.course
                }
            )
            chunks.append(chunk)
            index += 1
            start += (self.chunk_size - self.chunk_overlap)

        return chunks
