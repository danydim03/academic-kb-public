from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class Source(BaseModel):
    id: str
    source_type: str # 'notion', 'pdf', 'web', 'code'
    canonical_uri: str
    title: str
    authority: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Chunk(BaseModel):
    id: str
    document_id: str
    index: int
    text: str
    embedding: Optional[List[float]] = None
    page: Optional[int] = None
    section: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Document(BaseModel):
    id: str
    source_type: str
    source_id: str
    title: str
    uri: str
    mime_type: str
    course: Optional[str] = None
    topic: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    checksum: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Concept(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    course: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
