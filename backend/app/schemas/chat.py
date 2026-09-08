"""Chat request and clarification response schemas."""
from typing import List, Literal, Optional, Union
from pydantic import BaseModel, Field

from .recommendation import RecommendationResponse
from .state import EnvironmentalState


class StructuredInput(BaseModel):
    """Optional structured input providing verified metrics directly."""
    region: Optional[str] = None
    soil_organic_carbon: Optional[Union[float, str]] = None
    soil_ph: Optional[Union[float, str]] = None
    rainfall: Optional[Union[float, str]] = None
    crop: Optional[str] = None
    land_use: Optional[str] = None


class ChatRequest(BaseModel):
    """Incoming user chat request supporting natural text and/or structured data."""
    conversation_id: Optional[str] = None
    message: str = Field(..., min_length=1, description="Natural language environmental query or context")
    structured_input: Optional[StructuredInput] = None


class ClarificationResponse(BaseModel):
    """Returned when critical information is missing rather than guessing values."""
    type: Literal["clarification"] = "clarification"
    conversation_id: str
    question: str
    missing_variables: List[str]
    environmental_state: EnvironmentalState


# Combined chat response type
ChatResponse = Union[ClarificationResponse, RecommendationResponse]
