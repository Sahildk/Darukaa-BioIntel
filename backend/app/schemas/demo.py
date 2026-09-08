"""Demo scenario and evaluation test schemas."""
from typing import List
from pydantic import BaseModel
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


class EvaluationReport(BaseModel):
    """Comprehensive report across evaluation benchmark cases."""
    timestamp: str
    total_tests: int
    passed_tests: int
    results: List[EvaluationTestCaseResult]
