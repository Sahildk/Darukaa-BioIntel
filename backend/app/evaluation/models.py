"""Evaluation domain models, schemas, and metric data structures."""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EvaluationCategory(str, Enum):
    """Official scoring categories matching hackathon criteria."""
    REASONING = "reasoning"          # 30%
    GROUNDING = "grounding"          # 25%
    RETRIEVAL = "retrieval"          # 20%
    CONVERSATION = "conversation"    # 15%
    SAFETY = "safety"                # 10%


CATEGORY_WEIGHTS: Dict[EvaluationCategory, float] = {
    EvaluationCategory.REASONING: 0.30,
    EvaluationCategory.GROUNDING: 0.25,
    EvaluationCategory.RETRIEVAL: 0.20,
    EvaluationCategory.CONVERSATION: 0.15,
    EvaluationCategory.SAFETY: 0.10,
}


class TestCaseExecutionResult(BaseModel):
    """Result of an individual evaluation test case execution."""
    test_id: str
    title: str
    category: EvaluationCategory
    passed: bool
    score: float = Field(..., ge=0.0, le=1.0, description="Score between 0.0 and 1.0")
    details: str
    execution_time_ms: float = 0.0
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class CategoryScoreSummary(BaseModel):
    """Aggregated score summary for an evaluation category."""
    category: EvaluationCategory
    weight: float
    total_tests: int
    passed_tests: int
    pass_rate: float
    weighted_score: float


class ExtendedRetrievalMetrics(BaseModel):
    """Extended retrieval benchmark metrics over fixed 20-query evaluation set."""
    total_queries: int
    in_domain_queries: int
    ood_queries: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr: float
    precision_at_5: float
    ood_accepted_matches: int = Field(
        ..., description="Must be 0: count of out-of-domain queries that crossed the acceptance threshold"
    )
    acceptance_threshold: float = Field(
        0.5, description="Minimum hybrid retrieval score or domain topic match required for evidence acceptance"
    )


class SystemEvaluationReport(BaseModel):
    """Comprehensive evaluation report for Darukaa BioIntel."""
    timestamp: str
    git_commit: Optional[str] = None
    corpus_version: str = "1.0.0"
    corpus_source_count: int = 10
    total_tests: int
    passed_tests: int
    internal_hackathon_score: float = Field(
        ..., description="Internal hackathon-aligned score out of 100 based on official criteria weights"
    )
    categories: Dict[str, CategoryScoreSummary]
    retrieval_benchmark: ExtendedRetrievalMetrics
    results: List[TestCaseExecutionResult]
    metadata: Dict[str, Any] = Field(default_factory=dict)
