"""API routes connecting HTTP endpoints to application services and Phase 1-8 domain components."""
from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.chat import ChatRequest, ChatResponse, ClarificationResponse, StructuredInput
from app.schemas.demo import DemoScenario, EvaluationReport, EvaluationTestCaseResult
from app.schemas.recommendation import RecommendationResponse
from app.schemas.state import EnvironmentalState
from app.services.conversation_service import EnvironmentalChatService, get_chat_service

router = APIRouter()


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.get("/health", tags=["System"], summary="System health and readiness check")
def health_check(
    service: EnvironmentalChatService = Depends(get_chat_service),
) -> Dict[str, Any]:
    """
    Lightweight, deterministic readiness and liveness check.
    Inspects KnowledgeStore queryability, index presence, and engine readiness
    without running expensive re-indexing or ingestion per request.
    """
    health_data = service.get_health_status()
    # Preserve mode for backward compatibility with Phase 1 contracts
    health_data["mode"] = "contract_mock"
    return health_data


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    tags=["Chat"],
    summary="Process an environmental query or structured payload",
)
def chat_endpoint(
    request: ChatRequest,
    service: EnvironmentalChatService = Depends(get_chat_service),
) -> ChatResponse:
    """
    Primary chat endpoint orchestrating:
    1. Phase 6 Conversation flow & completeness/conflict check
    2. Phase 7 Multi-metric ecological reasoning & scientific sufficiency gate
    3. Phase 8 Recommendation generation & evidence validation firewall
    """
    try:
        return service.process_chat(request)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred while processing your environmental request.",
        )


@router.get(
    "/conversations/{conversation_id}",
    response_model=EnvironmentalState,
    tags=["Conversations"],
    summary="Retrieve current environmental state for a conversation",
)
def get_conversation_state(
    conversation_id: str,
    service: EnvironmentalChatService = Depends(get_chat_service),
) -> EnvironmentalState:
    """Returns the consolidated environmental state for a given conversation ID from state manager."""
    if not conversation_id or not conversation_id.strip():
        raise HTTPException(status_code=400, detail="conversation_id cannot be empty")
    return service.get_conversation_state(conversation_id.strip())


@router.get(
    "/demo/scenarios",
    response_model=List[DemoScenario],
    tags=["Demo"],
    summary="Retrieve pre-configured evaluator scenarios",
)
def get_demo_scenarios() -> List[DemoScenario]:
    """Returns 3 canonical demo scenarios for evaluator one-click testing."""
    return [
        DemoScenario(
            scenario_id="SCENARIO-001",
            title="Challenge Scenario: Semi-Arid Monoculture Wheat",
            description="Low rainfall, 0.3% SOC, wheat monoculture in semi-arid conditions.",
            sample_request=ChatRequest(
                message="We manage a wheat monoculture in a semi-arid zone with low rainfall and measured soil organic carbon of 0.3%. What interventions can restore soil carbon and biodiversity?",
                structured_input=StructuredInput(
                    region="semi-arid",
                    soil_organic_carbon=0.3,
                    rainfall="low",
                    crop="wheat",
                    land_use="monoculture",
                ),
            ),
        ),
        DemoScenario(
            scenario_id="SCENARIO-002",
            title="Incomplete Scenario: Vague Decline",
            description="User reports biodiversity decline with missing environmental parameters.",
            sample_request=ChatRequest(
                message="Biodiversity is declining on my land.",
            ),
        ),
        DemoScenario(
            scenario_id="SCENARIO-003",
            title="Alternative Ecosystem: Humid Tropical Soil Degradation",
            description="High temperature and precipitation with rapid nutrient leaching.",
            sample_request=ChatRequest(
                message="Tropical humid orchard experiencing intense runoff and soil degradation.",
                structured_input=StructuredInput(
                    region="humid tropical",
                    soil_organic_carbon=0.8,
                    rainfall="high",
                    crop="citrus",
                    land_use="orchard",
                ),
            ),
        ),
    ]


@router.post(
    "/evaluate/run",
    response_model=EvaluationReport,
    tags=["Evaluation"],
    summary="Execute comprehensive evaluation benchmark test suite",
)
def run_evaluation_suite(
    service: EnvironmentalChatService = Depends(get_chat_service),
) -> EvaluationReport:
    """
    Executes the comprehensive Phase 11 evaluation suite across all 15 benchmark cases
    (Reasoning, Grounding, Knowledge/Retrieval, Conversation, Safety) and returns the report.
    """
    from app.evaluation.runner import EvaluationRunner
    runner = EvaluationRunner(base_service=service)
    sys_report = runner.run_all()
    return runner.to_api_report(sys_report)

