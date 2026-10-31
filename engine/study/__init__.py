"""
Academic KB Study Engine Package.

Provides intelligent study features including spaced repetition (SM-2),
concept extraction, past exam linking, prerequisite learning paths,
infinite question generation, knowledge gap detection, query expansion,
and thesis assistance.
"""

from engine.study.llm_client import (
    LLMClient,
    GeminiProvider,
    OpenAIProvider,
    MockProvider,
    get_llm_client,
    extract_json_payload,
)
from engine.study.question_generator import QuestionGenerator
from engine.study.flashcard_engine import FlashcardEngine
from engine.study.gap_detector import GapDetector
from engine.study.concept_extractor import ConceptExtractor
from engine.study.exam_linker import ExamLinker
from engine.study.learning_path import LearningPathEngine, LearningPathGenerator
from engine.study.query_expander import QueryExpander
from engine.study.thesis_assistant import ThesisAssistant

__all__ = [
    "LLMClient",
    "GeminiProvider",
    "OpenAIProvider",
    "MockProvider",
    "get_llm_client",
    "extract_json_payload",
    "QuestionGenerator",
    "FlashcardEngine",
    "GapDetector",
    "ConceptExtractor",
    "ExamLinker",
    "LearningPathEngine",
    "LearningPathGenerator",
    "QueryExpander",
    "ThesisAssistant",
]
