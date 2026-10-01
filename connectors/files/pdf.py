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

        return Document(
            id=f"pdf-{hashlib.md5(filepath.encode()).hexdigest()}",
            source_type="pdf",
            source_id=filepath,
            title=filename,
            uri=f"file://{os.path.abspath(filepath)}",
            mime_type="application/pdf",
            course=course,
            checksum=checksum,
            metadata={"raw_text": full_text, "pages": len(text_content)}
        )
