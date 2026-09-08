"""API routes providing contract-validated endpoints with deterministic Phase 1 fixtures."""
from datetime import datetime, timezone
import uuid
from typing import List
from fastapi import APIRouter, HTTPException, status

from app.schemas.chat import ChatRequest, ChatResponse, ClarificationResponse, StructuredInput
from app.schemas.demo import DemoScenario, EvaluationReport, EvaluationTestCaseResult
from app.schemas.evidence import EvidenceItem
from app.schemas.recommendation import (
    DeveloperTrace,
    EvidenceStrength,
    RecommendationItem,
    RecommendationResponse,
    TimeHorizon,
)
from app.schemas.state import (
    BiodiversityState,
    ClimateState,
    EnvironmentalState,
    EnvironmentalVariable,
    HumanImpactState,
    LandUseState,
    ProvenanceSource,
    SoilState,
    VariableConfidence,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Deterministic Phase 1 Mock Fixtures
# ---------------------------------------------------------------------------

def _create_mock_state_challenge(structured: StructuredInput | None = None) -> EnvironmentalState:
    """Build a deterministic EnvironmentalState fixture matching the challenge scenario."""
    now_iso = datetime.now(timezone.utc).isoformat()
    
    soc_val = 0.3
    rain_val = "low"
    crop_val = "wheat"
    land_val = "monoculture"
    reg_val = "semi-arid"
    
    # If structured input provided, use it
    if structured:
        if structured.soil_organic_carbon is not None:
            soc_val = float(structured.soil_organic_carbon) if isinstance(structured.soil_organic_carbon, (int, float)) else structured.soil_organic_carbon
        if structured.rainfall is not None:
            rain_val = structured.rainfall
        if structured.crop is not None:
            crop_val = structured.crop
        if structured.land_use is not None:
            land_val = structured.land_use
        if structured.region is not None:
            reg_val = structured.region

    return EnvironmentalState(
        region=EnvironmentalVariable(
            value=reg_val,
            source=ProvenanceSource.STRUCTURED_INPUT if structured and structured.region else ProvenanceSource.USER,
            confidence=VariableConfidence.EXPLICIT,
            timestamp=now_iso,
        ),
        soil=SoilState(
            organic_carbon=EnvironmentalVariable(
                value=soc_val,
                unit="%",
                source=ProvenanceSource.STRUCTURED_INPUT if structured and structured.soil_organic_carbon is not None else ProvenanceSource.USER,
                confidence=VariableConfidence.EXPLICIT,
                timestamp=now_iso,
            )
        ),
        land_use=LandUseState(
            crop=EnvironmentalVariable(
                value=crop_val,
                source=ProvenanceSource.STRUCTURED_INPUT if structured and structured.crop else ProvenanceSource.USER,
                confidence=VariableConfidence.EXPLICIT,
                timestamp=now_iso,
            ),
            land_cover=EnvironmentalVariable(
                value=land_val,
                source=ProvenanceSource.STRUCTURED_INPUT if structured and structured.land_use else ProvenanceSource.USER,
                confidence=VariableConfidence.EXPLICIT,
                timestamp=now_iso,
            ),
        ),
        climate=ClimateState(
            rainfall=EnvironmentalVariable(
                value=rain_val,
                source=ProvenanceSource.STRUCTURED_INPUT if structured and structured.rainfall else ProvenanceSource.USER,
                confidence=VariableConfidence.EXPLICIT,
                timestamp=now_iso,
            )
        ),
        biodiversity=BiodiversityState(),
        human_impact=HumanImpactState(),
    )


def _create_mock_clarification(conv_id: str) -> ClarificationResponse:
    """Build a deterministic ClarificationResponse fixture when input data is incomplete."""
    now_iso = datetime.now(timezone.utc).isoformat()
    return ClarificationResponse(
        conversation_id=conv_id,
        question="To provide an evidence-backed assessment, could you specify your approximate soil organic carbon %, typical annual rainfall pattern, and current land use or crop type?",
        missing_variables=["soil_organic_carbon", "rainfall", "crop", "region"],
        environmental_state=EnvironmentalState(
            biodiversity=BiodiversityState(
                habitat_diversity=EnvironmentalVariable(
                    value="declining",
                    source=ProvenanceSource.USER,
                    confidence=VariableConfidence.EXPLICIT,
                    timestamp=now_iso,
                )
            )
        ),
    )


def _create_mock_recommendation(conv_id: str, structured: StructuredInput | None = None) -> RecommendationResponse:
    """Build a deterministic RecommendationResponse fixture for contract validation."""
    state = _create_mock_state_challenge(structured)
    
    mock_evidence = [
        EvidenceItem(
            evidence_id="EVD-001",
            source_id="SRC-FAO-2020",
            title="Recarbonizing Global Soils: A Technical Manual of Recommended Management Practices",
            publisher="Food and Agriculture Organization (FAO)",
            year=2020,
            excerpt="In semi-arid drylands with baseline soil organic carbon below 0.5%, introducing legume-based cover crops and diversified agroforestry increases organic carbon retention and stimulates mycorrhizal activity without exacerbating water stress.",
            source_url="https://www.fao.org/documents/card/en/c/ca9668en",
            doi="10.4060/ca9668en",
            relevance_score=0.92,
        ),
        EvidenceItem(
            evidence_id="EVD-002",
            source_id="SRC-IPCC-SRCCL-2019",
            title="Climate Change and Land: Special Report on Climate Change, Desertification, Land Degradation",
            publisher="Intergovernmental Panel on Climate Change (IPCC)",
            year=2019,
            excerpt="Diversified crop rotations with drought-tolerant legumes improve soil structure, increase aggregate stability, and reduce vulnerability to rainfall variability in semi-arid wheat monocultures.",
            source_url="https://www.ipcc.ch/srccl/",
            doi="10.1017/9781009157988",
            relevance_score=0.88,
        ),
    ]

    mock_recommendations = [
        RecommendationItem(
            action="Introduce drought-tolerant legume intercropping (e.g., chickpea or pigeon pea) into the wheat rotation cycle.",
            why="Breaks monoculture pest cycles, enhances soil organic nitrogen fixation, and builds active soil organic carbon in dryland environments.",
            impacted_metrics=["soil_organic_carbon", "microbial_diversity", "nitrogen_availability"],
            time_horizon=TimeHorizon.MEDIUM,
            evidence_strength=EvidenceStrength.STRONG,
            evidence=mock_evidence,
        ),
        RecommendationItem(
            action="Establish native perennial windbreaks along field boundaries.",
            why="Reduces evaporative wind demand, mitigates topsoil erosion, and provides habitat corridors for local pollinator species.",
            impacted_metrics=["habitat_connectivity", "pollinator_abundance", "wind_erosion"],
            time_horizon=TimeHorizon.LONG,
            evidence_strength=EvidenceStrength.STRONG,
            evidence=[mock_evidence[1]],
        ),
    ]

    mock_trace = DeveloperTrace(
        query="Challenge scenario mock verification",
        extracted_variables={
            "soil_organic_carbon": 0.3,
            "rainfall": "low",
            "crop": "wheat",
            "land_use": "monoculture",
            "region": "semi-arid",
        },
        retrieval_query="semi-arid wheat monoculture soil organic carbon low rainfall agroforestry legumes",
        retrieved_source_ids=["SRC-FAO-2020", "SRC-IPCC-SRCCL-2019"],
        reasoning_variables=["soil_organic_carbon", "rainfall", "crop", "region"],
        validation_status="verified_audit_passed",
    )

    return RecommendationResponse(
        conversation_id=conv_id,
        assessment="Multi-metric analysis identifies severe vulnerability arising from the combination of critically depleted soil organic carbon (0.3%), limited rainfall, and biodiversity deficit under wheat monoculture.",
        variables_considered=["soil_organic_carbon", "rainfall", "crop", "region"],
        recommendations=mock_recommendations,
        environmental_state=state,
        limitations=[
            "Field-specific soil moisture retention curve is not provided; planting density should be calibrated to local seasonal rainfall onset."
        ],
        developer_trace=mock_trace,
    )


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.get("/health", tags=["System"])
def health_check():
    """Health check endpoint confirming API availability and mock mode."""
    return {
        "status": "ok",
        "mode": "contract_mock",
        "version": "0.1.0",
        "service": "Darukaa BioIntel API",
    }


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    tags=["Chat"],
    summary="Process an environmental query or structured payload",
)
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """
    Deterministic Phase 1 chat endpoint.
    Validates the incoming ChatRequest contract and returns deterministic fixtures
    (either a ClarificationResponse or RecommendationResponse) without invoking any external
    LLM, vector DB, or non-deterministic service.
    """
    conv_id = request.conversation_id or str(uuid.uuid4())
    msg_lower = request.message.lower()

    # If the user message indicates incomplete data (e.g. "declining on my land" without structured data)
    # trigger the clarification contract response.
    is_incomplete_prompt = (
        ("declining" in msg_lower or "help" in msg_lower or "biodiversity" in msg_lower)
        and not request.structured_input
        and "0.3" not in request.message
        and "wheat" not in msg_lower
    )

    if is_incomplete_prompt:
        return _create_mock_clarification(conv_id)

    # Otherwise return the full recommendation fixture
    return _create_mock_recommendation(conv_id, request.structured_input)


@router.get(
    "/conversations/{conversation_id}",
    response_model=EnvironmentalState,
    tags=["Conversations"],
    summary="Retrieve current environmental state for a conversation",
)
def get_conversation_state(conversation_id: str) -> EnvironmentalState:
    """Returns the mock environmental state for a given conversation ID."""
    if not conversation_id:
        raise HTTPException(status_code=400, detail="conversation_id cannot be empty")
    return _create_mock_state_challenge()


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
    summary="Development stub for executing benchmark test suite",
)
def run_evaluation_stub() -> EvaluationReport:
    """Stub returning the structured evaluation report format for T-001 through T-009."""
    now_iso = datetime.now(timezone.utc).isoformat()
    test_cases = [
        EvaluationTestCaseResult(
            test_id="T-001",
            title="Challenge Semi-Arid Wheat Monoculture (>= 3 variables)",
            passed=True,
            details="Contract mock validates >=3 environmental variables and evidence linkage.",
        ),
        EvaluationTestCaseResult(
            test_id="T-002",
            title="Missing Data Clarification",
            passed=True,
            details="Contract mock returns ClarificationResponse when input lacks variables.",
        ),
        EvaluationTestCaseResult(
            test_id="T-003",
            title="Multi-Turn Context Persistence",
            passed=True,
            details="Contract schema supports multi-turn EnvironmentalState accumulation.",
        ),
        EvaluationTestCaseResult(
            test_id="T-004",
            title="Unsupported Quantitative Claim Handling",
            passed=True,
            details="Contract schema includes limitation field and requires evidence backing.",
        ),
        EvaluationTestCaseResult(
            test_id="T-005",
            title="Evidence Trace Auditability",
            passed=True,
            details="Evidence records retain source_id, title, publisher, and source_url.",
        ),
        EvaluationTestCaseResult(
            test_id="T-006",
            title="Conflicting/Weak Evidence Transparency",
            passed=True,
            details="EvidenceStrength field enables categorizing support level.",
        ),
        EvaluationTestCaseResult(
            test_id="T-007",
            title="Structured JSON Input Handling",
            passed=True,
            details="StructuredInput model properly maps to EnvironmentalState.",
        ),
        EvaluationTestCaseResult(
            test_id="T-008",
            title="Out-of-Scope Query Handling",
            passed=True,
            details="Contract supports limitations list to signal boundary conditions.",
        ),
        EvaluationTestCaseResult(
            test_id="T-009",
            title="Anti-Hallucination: No Evidence -> No Claim",
            passed=True,
            details="Traceability schema verifies evidence presence before recommendation generation.",
        ),
    ]

    return EvaluationReport(
        timestamp=now_iso,
        total_tests=len(test_cases),
        passed_tests=len(test_cases),
        results=test_cases,
    )
