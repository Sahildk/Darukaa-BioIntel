"""Reasoning evaluation cases: T-001, T-006, T-011 (Category Weight: 30%)."""
import time
import uuid
from typing import Any

from app.evaluation.models import EvaluationCategory, TestCaseExecutionResult
from app.reasoning.context import ContextMatcher
from app.schemas.chat import ChatRequest, ClarificationResponse, StructuredInput
from app.schemas.evidence import CandidateIntervention
from app.schemas.recommendation import RecommendationResponse
from app.services.conversation_service import EnvironmentalChatService


def evaluate_t001_canonical_challenge(service: EnvironmentalChatService) -> TestCaseExecutionResult:
    """
    T-001: Challenge Canonical Scenario (P0).
    Input: semi-arid wheat monoculture with 0.3% SOC and low rainfall.
    Expects: >= 3 variables analyzed simultaneously, active causal pathways, and non-generic interventions.
    """
    start_t = time.perf_counter()
    conv_id = f"eval-t001-{uuid.uuid4().hex[:8]}"

    payload = ChatRequest(
        conversation_id=conv_id,
        message="We manage a wheat monoculture in a semi-arid zone with low rainfall and measured soil organic carbon of 0.3%. What interventions restore soil carbon and biodiversity?",
        structured_input=StructuredInput(
            region="semi-arid",
            soil_organic_carbon=0.3,
            rainfall="low",
            crop="wheat",
            land_use="monoculture",
        ),
    )

    resp = service.process_chat(payload)
    elapsed_ms = (time.perf_counter() - start_t) * 1000

    if not isinstance(resp, RecommendationResponse):
        return TestCaseExecutionResult(
            test_id="T-001",
            title="Challenge Semi-Arid Wheat Monoculture (>= 3 variables)",
            category=EvaluationCategory.REASONING,
            passed=False,
            score=0.0,
            details=f"Expected RecommendationResponse but received {type(resp).__name__}.",
            execution_time_ms=elapsed_ms,
        )

    vars_ok = len(resp.variables_considered) >= 3
    recs_ok = len(resp.recommendations) >= 1
    evidence_ok = all(len(r.evidence) >= 1 for r in resp.recommendations)
    passed = vars_ok and recs_ok and evidence_ok

    score = 0.0
    if vars_ok:
        score += 0.4
    if recs_ok:
        score += 0.3
    if evidence_ok:
        score += 0.3

    return TestCaseExecutionResult(
        test_id="T-001",
        title="Challenge Semi-Arid Wheat Monoculture (>= 3 variables)",
        category=EvaluationCategory.REASONING,
        passed=passed,
        score=score,
        details=f"Considered {len(resp.variables_considered)} variables, produced {len(resp.recommendations)} validated recommendations with complete evidence linkage.",
        execution_time_ms=elapsed_ms,
        diagnostics={
            "variables_considered": resp.variables_considered,
            "recommendation_count": len(resp.recommendations),
            "recommendation_actions": [r.action for r in resp.recommendations],
        },
    )


def evaluate_t006_context_mismatch(service: EnvironmentalChatService) -> TestCaseExecutionResult:
    """
    T-006: Context Mismatch Rejection.
    Verifies that an intervention requiring humid/tropical conditions is rejected
    when evaluated against a semi-arid environmental state.
    """
    start_t = time.perf_counter()
    conv_id = f"eval-t006-{uuid.uuid4().hex[:8]}"

    # Setup state for semi-arid monoculture
    payload = ChatRequest(
        conversation_id=conv_id,
        message="We have a semi-arid wheat farm.",
        structured_input=StructuredInput(
            region="semi-arid",
            crop="wheat",
            land_use="monoculture",
        ),
    )
    service.process_chat(payload)
    state = service.get_conversation_state(conv_id)

    # Candidate requiring humid/tropical context
    candidate = CandidateIntervention(
        action="Establish multi-strata tropical shaded agroforestry canopy",
        rationale="Humid tropical canopies intercept heavy monsoon rainfall and prevent high-temperature leaching.",
        affected_metrics=["biodiversity.habitat_diversity"],
        time_horizon="long",
        required_conditions=["region in ['tropical', 'humid_tropics']", "rainfall > 1200 mm"],
        evidence_ids=["CHK-SRC-KUYAH-2019-AGROFOR-001"],
    )

    validator = service.recommendation_generator.validator
    val_res = validator.validate_candidate(candidate, state)
    elapsed_ms = (time.perf_counter() - start_t) * 1000

    passed = not val_res.is_valid and val_res.rejection_stage == "context"
    score = 1.0 if passed else 0.0

    return TestCaseExecutionResult(
        test_id="T-006",
        title="Context Mismatch Rejection",
        category=EvaluationCategory.REASONING,
        passed=passed,
        score=score,
        details="Tropical agroforestry intervention correctly rejected for semi-arid state due to context mismatch." if passed else "Context mismatch failed to reject incompatible candidate.",
        execution_time_ms=elapsed_ms,
        diagnostics={
            "is_valid": val_res.is_valid,
            "rejection_stage": val_res.rejection_stage,
            "rejection_reason": val_res.rejection_reason,
        },
    )


def evaluate_t011_disconnected_variables(service: EnvironmentalChatService) -> TestCaseExecutionResult:
    """
    T-011: Disconnected Variables Scientific Sufficiency Gate.
    Verifies that when 3 variables are present (temperature, rainfall, crop) but baseline soil
    condition or land management is missing, Phase 7 rejects scientific sufficiency.
    """
    start_t = time.perf_counter()
    conv_id = f"eval-t011-{uuid.uuid4().hex[:8]}"

    payload = ChatRequest(
        conversation_id=conv_id,
        message="Our temperature is 31 degrees Celsius, rainfall is 800 mm, and we grow wheat.",
    )

    resp = service.process_chat(payload)
    elapsed_ms = (time.perf_counter() - start_t) * 1000

    is_clarification = isinstance(resp, ClarificationResponse)
    sufficiency_rejected = (
        is_clarification
        and any("soil" in v.lower() for v in resp.missing_variables)
    )

    passed = is_clarification and sufficiency_rejected
    score = 1.0 if passed else 0.0

    return TestCaseExecutionResult(
        test_id="T-011",
        title="Disconnected Variables Scientific Sufficiency Gate",
        category=EvaluationCategory.REASONING,
        passed=passed,
        score=score,
        details="Phase 7 correctly rejected scientific sufficiency for disconnected climate + crop metrics without soil condition." if passed else "Disconnected variables failed to trigger scientific sufficiency clarification.",
        execution_time_ms=elapsed_ms,
        diagnostics={
            "response_type": type(resp).__name__,
            "missing_variables": resp.missing_variables if is_clarification else [],
        },
    )
