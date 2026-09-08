"""Grounding evaluation cases: T-004, T-005, T-009 (Category Weight: 25%)."""
import time
import uuid

from app.evaluation.models import EvaluationCategory, TestCaseExecutionResult
from app.recommendation.models import ClaimValidationStatus
from app.schemas.chat import ChatRequest, StructuredInput
from app.schemas.evidence import CandidateIntervention
from app.schemas.recommendation import RecommendationResponse
from app.services.conversation_service import EnvironmentalChatService


def evaluate_t004_quantitative_claim_firewall(service: EnvironmentalChatService) -> TestCaseExecutionResult:
    """
    T-004: Quantitative Claim Firewall.
    Directly tests EvidenceTraceabilityValidator against an intervention asserting an unbacked
    quantitative claim ('boosts soil carbon by 45%').
    Asserts candidate is rejected or the claim is marked QUANTITATIVE_CLAIM_UNSUPPORTED.
    """
    start_t = time.perf_counter()
    conv_id = f"eval-t004-{uuid.uuid4().hex[:8]}"

    # Setup valid state
    payload = ChatRequest(
        conversation_id=conv_id,
        message="We have 0.3% SOC wheat monoculture in semi-arid land.",
        structured_input=StructuredInput(
            region="semi-arid",
            soil_organic_carbon=0.3,
            rainfall="low",
            crop="wheat",
            land_use="monoculture",
        ),
    )
    service.process_chat(payload)
    state = service.get_conversation_state(conv_id)

    # Candidate with unbacked quantitative claim '45%' (not present in any FAO/Lal chunk)
    candidate = CandidateIntervention(
        action="Apply synthetic mineral catalyst to surface soil",
        rationale="Synthetic mineral catalyst boosts soil carbon by 45% within three months.",
        affected_metrics=["soil.organic_carbon"],
        time_horizon="short",
        required_conditions=[],
        evidence_ids=["CHK-SRC-LAL-2004-SCIENCE-001"],
    )

    validator = service.recommendation_generator.validator
    val_res = validator.validate_candidate(candidate, state)
    elapsed_ms = (time.perf_counter() - start_t) * 1000

    has_unsupported_quant = any(
        r.claim_type == "quantitative_claim" and r.status != ClaimValidationStatus.SUPPORTED
        for r in val_res.claim_records
    )
    passed = not val_res.is_valid or has_unsupported_quant
    score = 1.0 if passed else 0.0

    return TestCaseExecutionResult(
        test_id="T-004",
        title="Quantitative Claim Firewall",
        category=EvaluationCategory.GROUNDING,
        passed=passed,
        score=score,
        details="Deterministic quantitative firewall detected unbacked numeric claim '45%' and rejected claim validity." if passed else "Firewall failed to intercept unsupported quantitative claim.",
        execution_time_ms=elapsed_ms,
        diagnostics={
            "is_valid": val_res.is_valid,
            "claim_records": [
                {"type": r.claim_type, "status": r.status, "text": r.claim_text}
                for r in val_res.claim_records
            ],
        },
    )


def evaluate_t005_evidence_traceability_chain(service: EnvironmentalChatService) -> TestCaseExecutionResult:
    """
    T-005: Evidence Traceability Chain.
    Asserts every recommendation returned by the pipeline traces:
    Action -> Impacted Metrics -> Evidence IDs -> Source Records -> Publisher & DOI/URL.
    """
    start_t = time.perf_counter()
    conv_id = f"eval-t005-{uuid.uuid4().hex[:8]}"

    payload = ChatRequest(
        conversation_id=conv_id,
        message="Assess semi-arid wheat monoculture with 0.3% SOC and low rainfall.",
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

    if not isinstance(resp, RecommendationResponse) or not resp.recommendations:
        return TestCaseExecutionResult(
            test_id="T-005",
            title="Evidence Traceability Chain",
            category=EvaluationCategory.GROUNDING,
            passed=False,
            score=0.0,
            details="No recommendations returned to evaluate evidence traceability.",
            execution_time_ms=elapsed_ms,
        )

    all_traceable = True
    verified_items = 0
    for rec in resp.recommendations:
        if not rec.evidence:
            all_traceable = False
            break
        for ev in rec.evidence:
            if not (ev.evidence_id and ev.source_id and ev.title and ev.publisher and (ev.source_url or ev.doi)):
                all_traceable = False
                break
            verified_items += 1

    passed = all_traceable and verified_items > 0
    score = 1.0 if passed else 0.0

    return TestCaseExecutionResult(
        test_id="T-005",
        title="Evidence Traceability Chain",
        category=EvaluationCategory.GROUNDING,
        passed=passed,
        score=score,
        details=f"Verified {verified_items} evidence items across {len(resp.recommendations)} recommendations with complete metadata chains." if passed else "Evidence chain incomplete or missing critical provenance attributes.",
        execution_time_ms=elapsed_ms,
        diagnostics={"verified_evidence_count": verified_items},
    )


def evaluate_t009_anti_hallucination_firewall(service: EnvironmentalChatService) -> TestCaseExecutionResult:
    """
    T-009: Anti-Hallucination Gate (No Evidence -> No Claim).
    Verifies that a candidate lacking authentic evidence IDs or referencing non-existent chunk IDs
    is hard-blocked from entering final recommendations.
    """
    start_t = time.perf_counter()
    conv_id = f"eval-t009-{uuid.uuid4().hex[:8]}"

    payload = ChatRequest(
        conversation_id=conv_id,
        message="We have 0.3% SOC wheat monoculture in semi-arid land.",
        structured_input=StructuredInput(
            region="semi-arid",
            soil_organic_carbon=0.3,
            rainfall="low",
            crop="wheat",
            land_use="monoculture",
        ),
    )
    service.process_chat(payload)
    state = service.get_conversation_state(conv_id)

    # Candidate with unresolvable/fabricated chunk ID
    hallucinated_candidate = CandidateIntervention(
        action="Broadcast synthetic nanobiochar particles across field",
        rationale="Nanoparticles claim to fix 100% of atmospheric carbon instantly.",
        affected_metrics=["soil.organic_carbon"],
        time_horizon="short",
        required_conditions=[],
        evidence_ids=["CHK-SRC-FABRICATED-NANO-999"],
    )

    validator = service.recommendation_generator.validator
    val_res = validator.validate_candidate(hallucinated_candidate, state)
    elapsed_ms = (time.perf_counter() - start_t) * 1000

    passed = not val_res.is_valid and val_res.rejection_stage == "evidence"
    score = 1.0 if passed else 0.0

    return TestCaseExecutionResult(
        test_id="T-009",
        title="Anti-Hallucination Gate (No Evidence -> No Claim)",
        category=EvaluationCategory.GROUNDING,
        passed=passed,
        score=score,
        details="Anti-hallucination firewall intercepted candidate with fabricated chunk ID and rejected it." if passed else "Firewall failed to block candidate with unresolvable evidence ID.",
        execution_time_ms=elapsed_ms,
        diagnostics={
            "is_valid": val_res.is_valid,
            "rejection_stage": val_res.rejection_stage,
            "rejection_reason": val_res.rejection_reason,
        },
    )
