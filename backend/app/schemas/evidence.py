"""Evidence and candidate intervention schemas."""
from typing import List, Optional
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """An auditable piece of retrieved scientific evidence."""
    evidence_id: str
    source_id: str
    title: str
    publisher: str
    year: Optional[int] = None
    excerpt: str
    source_url: Optional[str] = None
    doi: Optional[str] = None
    relevance_score: Optional[float] = None


class CandidateIntervention(BaseModel):
    """An intermediate intervention evaluated during ecological reasoning."""
    action: str
    rationale: str
    affected_metrics: List[str]
    time_horizon: str  # "short" | "medium" | "long"
    required_conditions: List[str]
    evidence_ids: List[str]
    contraindications: List[str] = Field(default_factory=list)
