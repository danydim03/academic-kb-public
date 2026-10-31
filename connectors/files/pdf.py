import os
import hashlib
from datetime import datetime
from typing import Generator
import pypdf
from connectors.base import BaseConnector
from core.models import Document

class PDFConnector(BaseConnector):
    def __init__(self, directory: str, course_name: str = None):
        self.directory = directory
        self.course_name = course_name

    def extract(self) -> Generator[Document, None, None]:
        for root, _, files in os.walk(self.directory):
            for file in files:
                if file.lower().endswith('.pdf'):
                    filepath = os.path.join(root, file)
                    yield self._parse_pdf(filepath)

    def _parse_pdf(self, filepath: str) -> Document:
        text_content = []
        try:
            with open(filepath, 'rb') as f:
                reader = pypdf.PdfReader(f)
                for page_num, page in enumerate(reader.pages):
                    try:
                        text = page.extract_text()
                        if text:
                            text_content.append(f"--- PAGE {page_num + 1} ---\n{text}")
                    except Exception as pe:
                        continue
        except Exception as e:
            text_content.append(f"Error reading PDF: {e}")

        full_text = "\n".join(text_content)
        checksum = hashlib.sha256(full_text.encode('utf-8')).hexdigest()
        filename = os.path.basename(filepath)

        # Inferred course name
        course = self.course_name
        if not course or course.lower() == "auto":
            rel_path = os.path.relpath(filepath, self.directory)
            parts = rel_path.split(os.sep)
            if len(parts) > 1 and parts[0] != ".":
                course = parts[0]
            else:
                course = "Generale"

        # Source tier — sistema a 3 livelli di priorità:
        #   "primary"  = slide, appunti, notion  (⭐⭐⭐ priorità massima)
        #   "resource" = libri di testo in resources/  (⭐⭐ priorità media)
        #   "article"  = articoli scientifici / paper in articles/ dentro resources/  (⭐ priorità bassa)
        abs_path = os.path.abspath(filepath)
        path_segments = abs_path.lower().split(os.sep)
        filename_lower = os.path.basename(filepath).lower()

        # 1) Articoli: dentro una cartella "articles" o "papers", oppure file che NON iniziano
        #    con "book" dentro resources/ (euristica: i libri hanno prefisso "book -")
        is_in_articles_dir = any(seg in ("articles", "papers", "articoli") for seg in path_segments)
        is_in_resources = any(seg.endswith(" resources") or seg == "resources" for seg in path_segments)
        is_book_file = filename_lower.startswith("book -") or filename_lower.startswith("book-")

        if is_in_articles_dir:
            source_tier = "article"
        elif is_in_resources and not is_book_file:
            # File in resources/ che NON è un libro → articolo/paper
            source_tier = "article"
        elif is_in_resources and is_book_file:
            # File in resources/ con prefisso "book" → libro
            source_tier = "resource"
        else:
            source_tier = "primary"

        return Document(
            id=f"pdf-{hashlib.md5(filepath.encode()).hexdigest()}",
            source_type="pdf",
            source_id=filepath,
            title=filename,
            uri=f"file://{abs_path}",
            mime_type="application/pdf",
            course=course,
            source_tier=source_tier,
            checksum=checksum,
            metadata={"raw_text": full_text, "pages": len(text_content)}
        )
