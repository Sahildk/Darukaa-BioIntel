"""Conversation evaluation cases: T-002, T-003, T-007, T-012, T-013 (Category Weight: 15%)."""
import time
import uuid

from app.evaluation.models import EvaluationCategory, TestCaseExecutionResult
from app.schemas.chat import ChatRequest, ClarificationResponse, StructuredInput
from app.schemas.recommendation import RecommendationResponse
from app.schemas.state import ProvenanceSource
from app.services.conversation_service import EnvironmentalChatService


def evaluate_t002_incomplete_clarification(service: EnvironmentalChatService) -> TestCaseExecutionResult:
    """
    T-002: Incomplete Data Clarification.
    Input lacking environmental variables must trigger targeted clarification rather than guessing.
    """
    start_t = time.perf_counter()
    conv_id = f"eval-t002-{uuid.uuid4().hex[:8]}"

    payload = ChatRequest(
        conversation_id=conv_id,
        message="Biodiversity is declining on my land.",
    )

    resp = service.process_chat(payload)
    elapsed_ms = (time.perf_counter() - start_t) * 1000

    passed = isinstance(resp, ClarificationResponse) and len(resp.missing_variables) >= 1
    score = 1.0 if passed else 0.0

    return TestCaseExecutionResult(
        test_id="T-002",
        title="Missing Data Clarification",
        category=EvaluationCategory.CONVERSATION,
        passed=passed,
        score=score,
        details="Targeted ClarificationResponse triggered with missing variable inquiries." if passed else "System failed to request clarification on incomplete input.",
        execution_time_ms=elapsed_ms,
        diagnostics={
            "response_type": type(resp).__name__,
            "missing_variables": resp.missing_variables if isinstance(resp, ClarificationResponse) else [],
        },
    )


def evaluate_t003_multiturn_persistence(service: EnvironmentalChatService) -> TestCaseExecutionResult:
    """
    T-003: Multi-Turn Context Persistence.
    Turn 1 provides region; Turn 2 provides soil and crop metrics.
    Verifies that state persists across turns and combines prior context without re-asking.
    """
    start_t = time.perf_counter()
    conv_id = f"eval-t003-{uuid.uuid4().hex[:8]}"

    # Turn 1
    t1_payload = ChatRequest(
        conversation_id=conv_id,
        message="We have a continuous monoculture wheat farm.",
    )
    t1_resp = service.process_chat(t1_payload)

    # Turn 2
    t2_payload = ChatRequest(
        conversation_id=conv_id,
        message="Here are our climate and soil readings.",
        structured_input=StructuredInput(
            region="semi-arid",
            soil_organic_carbon=0.3,
            rainfall="low",
        ),
    )
    t2_resp = service.process_chat(t2_payload)
    elapsed_ms = (time.perf_counter() - start_t) * 1000

    # In Turn 2, state should contain both Turn 1 (crop=wheat, monoculture) and Turn 2 (region, SOC)
    t1_clar = isinstance(t1_resp, ClarificationResponse)
    t2_rec = isinstance(t2_resp, RecommendationResponse)
    state = service.get_conversation_state(conv_id)

    has_crop = state.land_use.crop is not None and state.land_use.crop.value == "wheat"
    has_region = state.region is not None and state.region.value == "semi-arid"
    has_soc = state.soil.organic_carbon is not None and state.soil.organic_carbon.value == 0.3

    passed = t1_clar and t2_rec and has_crop and has_region and has_soc
    score = 1.0 if passed else 0.0

    return TestCaseExecutionResult(
        test_id="T-003",
        title="Multi-Turn Context Persistence",
        category=EvaluationCategory.CONVERSATION,
        passed=passed,
        score=score,
        details="Multi-turn state successfully accumulated observations across turns without re-asking established facts." if passed else "Multi-turn context failed to persist across turns.",
        execution_time_ms=elapsed_ms,
        diagnostics={
            "t1_type": type(t1_resp).__name__,
            "t2_type": type(t2_resp).__name__,
            "accumulated_vars": [has_crop, has_region, has_soc],
        },
    )


def evaluate_t007_structured_input_ingestion(service: EnvironmentalChatService) -> TestCaseExecutionResult:
    """
    T-007: Structured JSON Input Handling.
    Verifies that structured JSON environmental parameters are ingested into state
    with correct provenance (source='structured_input') and drive downstream reasoning.
    """
    start_t = time.perf_counter()
    conv_id = f"eval-t007-{uuid.uuid4().hex[:8]}"

    payload = ChatRequest(
        conversation_id=conv_id,
        message="Here is our verified laboratory soil testing payload.",
        structured_input=StructuredInput(
            region="semi-arid",
            soil_organic_carbon=0.3,
            soil_ph=6.8,
            rainfall="low",
            crop="wheat",
            land_use="monoculture",
        ),
    )

    resp = service.process_chat(payload)
    state = service.get_conversation_state(conv_id)
    elapsed_ms = (time.perf_counter() - start_t) * 1000

    soc = state.soil.organic_carbon
    ph = state.soil.ph

    soc_ok = soc is not None and soc.value == 0.3 and soc.source == ProvenanceSource.STRUCTURED_INPUT
    ph_ok = ph is not None and ph.value == 6.8 and ph.source == ProvenanceSource.STRUCTURED_INPUT
    rec_ok = isinstance(resp, RecommendationResponse)

    passed = soc_ok and ph_ok and rec_ok
    score = 1.0 if passed else 0.0

    return TestCaseExecutionResult(
        test_id="T-007",
        title="Structured JSON Input Handling",
        category=EvaluationCategory.CONVERSATION,
        passed=passed,
        score=score,
        details="Structured JSON inputs properly parsed, assigned provenance 'structured_input', and drove pipeline execution." if passed else "Structured input failed to map into state or pipeline.",
        execution_time_ms=elapsed_ms,
        diagnostics={
            "soc_source": str(soc.source) if soc else None,
            "ph_source": str(ph.source) if ph else None,
        },
    )


def evaluate_t012_active_conflict_tracking(service: EnvironmentalChatService) -> TestCaseExecutionResult:
    """
    T-012: Active Conflict Tracking.
    Submitting two differing observations for the same variable with equal authority (USER_DIRECT)
    must create an explicit ConflictRecord and preserve incumbent value pending resolution.
    """
    start_t = time.perf_counter()
    conv_id = f"eval-t012-{uuid.uuid4().hex[:8]}"

    # Observation 1: User says wheat
    service.process_chat(ChatRequest(
        conversation_id=conv_id,
        message="We cultivate continuous wheat on our land.",
    ))

    # Observation 2: Conflicting user statement says barley
    service.process_chat(ChatRequest(
        conversation_id=conv_id,
        message="Our primary crop is barley.",
    ))

    state = service.get_conversation_state(conv_id)
    elapsed_ms = (time.perf_counter() - start_t) * 1000

    has_conflict = len(state.active_conflicts) > 0
    first_c = state.active_conflicts[0] if has_conflict else None
    if isinstance(first_c, dict):
        conflict_path = first_c.get("variable_path")
        conflict_status = first_c.get("status")
    elif first_c is not None:
        conflict_path = getattr(first_c, "variable_path", None)
        conflict_status = getattr(first_c, "status", None)
    else:
        conflict_path = None
        conflict_status = None

    passed = has_conflict and conflict_path == "land_use.crop" and conflict_status == "unresolved"
    score = 1.0 if passed else 0.0

    return TestCaseExecutionResult(
        test_id="T-012",
        title="Active Conflict Tracking & Authority Separation",
        category=EvaluationCategory.CONVERSATION,
        passed=passed,
        score=score,
        details="Equal-authority contradiction generated explicit ConflictRecord without silent data loss." if passed else "Contradictory observations failed to trigger explicit conflict tracking.",
        execution_time_ms=elapsed_ms,
        diagnostics={
            "active_conflicts_count": len(state.active_conflicts),
            "conflict_path": conflict_path,
        },
    )


def evaluate_t013_session_isolation(service: EnvironmentalChatService) -> TestCaseExecutionResult:
    """
    T-013: Session Isolation.
    Verifies that concurrent conversations (A and B) maintain separate memory namespaces
    and never leak or overwrite each other's environmental observations.
    """
    start_t = time.perf_counter()
    id_a = f"eval-t013-a-{uuid.uuid4().hex[:8]}"
    id_b = f"eval-t013-b-{uuid.uuid4().hex[:8]}"

    # Session A: Semi-arid wheat, 0.3% SOC
    service.process_chat(ChatRequest(
        conversation_id=id_a,
        message="Session A farm.",
        structured_input=StructuredInput(region="semi-arid", soil_organic_carbon=0.3, crop="wheat"),
    ))

    # Session B: Tropical citrus, 2.5% SOC
    service.process_chat(ChatRequest(
        conversation_id=id_b,
        message="Session B farm.",
        structured_input=StructuredInput(region="tropical", soil_organic_carbon=2.5, crop="citrus"),
    ))

    state_a = service.get_conversation_state(id_a)
    state_b = service.get_conversation_state(id_b)
    elapsed_ms = (time.perf_counter() - start_t) * 1000

    a_ok = (
        state_a.region is not None and state_a.region.value == "semi-arid" and
        state_a.soil.organic_carbon is not None and state_a.soil.organic_carbon.value == 0.3 and
        state_a.land_use.crop is not None and state_a.land_use.crop.value == "wheat"
    )
    b_ok = (
        state_b.region is not None and state_b.region.value == "tropical" and
        state_b.soil.organic_carbon is not None and state_b.soil.organic_carbon.value == 2.5 and
        state_b.land_use.crop is not None and state_b.land_use.crop.value == "citrus"
    )

    passed = a_ok and b_ok
    score = 1.0 if passed else 0.0

    return TestCaseExecutionResult(
        test_id="T-013",
        title="Session Isolation",
        category=EvaluationCategory.CONVERSATION,
        passed=passed,
        score=score,
        details="Independent sessions maintained strict state isolation with zero cross-contamination." if passed else "Session isolation failure: state leaked across conversation IDs.",
        execution_time_ms=elapsed_ms,
    )
