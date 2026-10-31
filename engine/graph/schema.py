"""
Graph Schema Manager & Study Engine Neo4j Extensions.

Defines schemas, constraints, indexes, and relationship contracts for:
- Core KB: Document, Chunk, Source
- Study Engine: Flashcard, Concept, ExamQuestion
- Relationships: HAS_CHUNK, SIMILAR_TO, RELATED_TO, MENTIONS, CROSS_COURSE, ANSWERS, PREREQUISITE_OF
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import logging
from pydantic import BaseModel, Field

from core.database import Neo4jManager

logger = logging.getLogger(__name__)

# Node Labels
LABEL_DOCUMENT = "Document"
LABEL_CHUNK = "Chunk"
LABEL_SOURCE = "Source"
LABEL_FLASHCARD = "Flashcard"
LABEL_CONCEPT = "Concept"
LABEL_EXAM_QUESTION = "ExamQuestion"

# Relationship Types
REL_HAS_CHUNK = "HAS_CHUNK"            # (Document)-[:HAS_CHUNK]->(Chunk)
REL_SIMILAR_TO = "SIMILAR_TO"          # (Chunk)-[:SIMILAR_TO {score: float}]->(Chunk)
REL_RELATED_TO = "RELATED_TO"          # (Document)-[:RELATED_TO]->(Document)
REL_MENTIONS = "MENTIONS"              # (Chunk)-[:MENTIONS]->(Concept)
REL_CROSS_COURSE = "CROSS_COURSE"      # (Concept)-[:CROSS_COURSE {courses: [...]}]->(Concept)
REL_ANSWERS = "ANSWERS"                # (Chunk)-[:ANSWERS {relevance_score: float}]->(ExamQuestion)
REL_PREREQUISITE_OF = "PREREQUISITE_OF"  # (Concept)-[:PREREQUISITE_OF]->(Concept)


# ---------------------------------------------------------------------------
# Schema Domain Models
# ---------------------------------------------------------------------------

class FlashcardNode(BaseModel):
    """
    Flashcard node representation for Spaced Repetition (SM-2).
    """
    id: str = Field(description="Unique UUID or slug for the flashcard")
    question: str = Field(description="Question or prompt on front of card")
    answer: str = Field(description="Answer or explanation on back of card")
    source_chunk_id: Optional[str] = Field(default=None, description="Originating KB Chunk ID")
    course: str = Field(description="Associated academic course code (e.g. CNS, SDCC)")
    easiness_factor: float = Field(default=2.5, description="SM-2 Easiness Factor (EF >= 1.3)")
    interval: int = Field(default=0, description="Current interval in days")
    repetitions: int = Field(default=0, description="Consecutive successful review count")
    next_review: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 timestamp string for next scheduled review"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConceptNode(BaseModel):
    """
    Concept node representation for Knowledge Graph & Learning Paths.
    """
    id: str = Field(description="Unique slugified ID (e.g. 'concept-hmac')")
    name: str = Field(description="Canonical concept title")
    description: Optional[str] = Field(default=None, description="Concise academic definition")
    aliases: List[str] = Field(default_factory=list, description="Synonyms, acronyms, or variants")
    courses: List[str] = Field(default_factory=list, description="Courses covering this concept")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExamQuestionNode(BaseModel):
    """
    Exam Question node extracted from past exams.
    """
    id: str = Field(description="Unique identifier for the exam question")
    text: str = Field(description="Full text of the exam question")
    exam_year: Optional[str] = Field(default=None, description="Year or session of exam (e.g. '2020')")
    course: str = Field(description="Academic course (e.g. 'CNS')")
    difficulty_estimate: str = Field(default="media", description="Estimated difficulty (facile, media, difficile)")
    source_doc_id: Optional[str] = Field(default=None, description="Document ID of source exam PDF")
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Cypher Constraint & Index Definitions
# ---------------------------------------------------------------------------

STUDY_CONSTRAINTS: List[str] = [
    "CREATE CONSTRAINT flashcard_id IF NOT EXISTS FOR (f:Flashcard) REQUIRE f.id IS UNIQUE",
    "CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT exam_question_id IF NOT EXISTS FOR (eq:ExamQuestion) REQUIRE eq.id IS UNIQUE",
]

STUDY_INDEXES: List[str] = [
    "CREATE INDEX flashcard_course IF NOT EXISTS FOR (f:Flashcard) ON (f.course)",
    "CREATE INDEX flashcard_next_review IF NOT EXISTS FOR (f:Flashcard) ON (f.next_review)",
    "CREATE INDEX exam_question_course IF NOT EXISTS FOR (eq:ExamQuestion) ON (eq.course)",
]


# ---------------------------------------------------------------------------
# Schema Manager
# ---------------------------------------------------------------------------

class GraphSchemaManager:
    """
    Manages Neo4j constraints, vector indexes, and fulltext indexes
    for both base KB entities and study engine extensions.
    """

    def __init__(self, db: Neo4jManager):
        self.db = db

    def ensure_study_constraints(self) -> None:
        """
        Applies uniqueness constraints and indexes for study nodes:
        - Flashcard(id) unique, indexes on course and next_review
        - Concept(id) unique
        - ExamQuestion(id) unique, index on course
        """
        for query in STUDY_CONSTRAINTS:
            try:
                self.db.execute_query(query)
                logger.info(f"Verified constraint: {query}")
            except Exception as e:
                logger.error(f"Failed to apply constraint '{query}': {e}")
                raise

        for query in STUDY_INDEXES:
            try:
                self.db.execute_query(query)
                logger.info(f"Verified index: {query}")
            except Exception as e:
                logger.error(f"Failed to apply index '{query}': {e}")
                raise

    def setup_schema(self, vector_dimension: int = 768) -> None:
        """
        Set up the complete Neo4j schema:
        1. Base constraints (Chunk, Document, Concept, Source)
        2. Study engine constraints & indexes (Flashcard, ExamQuestion)
        3. Vector index for chunk embeddings
        4. Fulltext index for chunks
        5. Fulltext index for concepts
        """
        # Base constraints
        self.db.ensure_constraints()

        # Extended study constraints & indexes
        self.ensure_study_constraints()

        # Vector index
        self.db.create_vector_index(
            index_name="chunk_embeddings",
            label="Chunk",
            property_name="embedding",
            dimensions=vector_dimension
        )

        # Full-text indexes
        self.db.create_fulltext_index(
            index_name="chunk_text",
            labels=["Chunk"],
            properties=["text"]
        )
        self.db.create_fulltext_index(
            index_name="concept_text",
            labels=["Concept"],
            properties=["name", "aliases"]
        )
        logger.info("Complete schema setup verified successfully.")


def apply_schema_constraints(db: Neo4jManager, vector_dimension: int = 768) -> GraphSchemaManager:
    """
    Convenience helper function to safely verify and apply all schema
    definitions, constraints, and indexes using Neo4jManager.
    """
    manager = GraphSchemaManager(db)
    manager.setup_schema(vector_dimension=vector_dimension)
    return manager
