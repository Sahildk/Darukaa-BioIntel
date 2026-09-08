"""Demo scenario and evaluation test schemas."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from .chat import ChatRequest


class DemoScenario(BaseModel):
    """Pre-built test scenario for evaluators and demonstrators."""
    scenario_id: str
    title: str
    description: str
    sample_request: ChatRequest


class EvaluationTestCaseResult(BaseModel):
    """Result of an evaluation test case."""
    test_id: str
    title: str
    passed: bool
    details: str
    category: Optional[str] = None
    score: Optional[float] = None
    execution_time_ms: Optional[float] = None
    diagnostics: Optional[Dict[str, Any]] = None


class EvaluationReport(BaseModel):
    """Comprehensive report across evaluation benchmark cases."""
    timestamp: str
    total_tests: int
    passed_tests: int
    results: List[EvaluationTestCaseResult]
    overall_score: Optional[float] = Field(None, description="Internal hackathon-aligned evaluation score out of 100")
    categories: Optional[Dict[str, Any]] = None
    retrieval_benchmark: Optional[Dict[str, Any]] = None
