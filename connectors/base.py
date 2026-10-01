from abc import ABC, abstractmethod
from typing import List, Generator
from core.models import Document

class BaseConnector(ABC):
    @abstractmethod
    def extract(self) -> Generator[Document, None, None]:
        """
        Extract content from the source and yield normalized Document objects.
        """
        pass
