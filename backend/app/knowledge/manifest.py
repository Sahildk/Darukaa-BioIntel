"""Corpus manifest and metadata schema models."""
import json
from pathlib import Path
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator

TopicType = Literal["soil_health", "land_use", "biodiversity", "climate", "human_impact"]
SourceCategoryType = Literal["report", "paper", "dataset", "other"]


class CorpusSource(BaseModel):
    """Metadata contract for an indexed scientific source."""
    source_id: str = Field(..., min_length=3, description="Stable unique identifier e.g. SRC-FAO-2020-RECARB")
    title: str = Field(..., min_length=5)
    publisher: str = Field(..., min_length=2)
    year: int = Field(..., ge=1900, le=2030)
    topic: TopicType
    source_type: SourceCategoryType
    source_url: str
    doi: Optional[str] = None
    geography: List[str] = Field(default_factory=list)
    variables: List[str] = Field(..., min_length=1, description="Environmental metrics addressed by this source")
    interventions: List[str] = Field(default_factory=list, description="Ecological actions evaluated")
    rel_path: str = Field(..., description="Relative path to source document JSON under data/corpus/")
    summary: str = Field(..., min_length=20)
    key_findings: List[str] = Field(default_factory=list)

    @field_validator("source_id")
    @classmethod
    def validate_source_id_format(cls, v: str) -> str:
        if not v.startswith("SRC-"):
            raise ValueError("source_id must start with prefix 'SRC-'")
        return v


class CorpusManifest(BaseModel):
    """Manifest describing all curated scientific sources."""
    manifest_version: str = "1.0.0"
    last_updated: str
    description: str
    sources: List[CorpusSource]

    @field_validator("sources")
    @classmethod
    def validate_unique_source_ids(cls, sources: List[CorpusSource]) -> List[CorpusSource]:
        ids = [s.source_id for s in sources]
        if len(ids) != len(set(ids)):
            duplicates = [x for x in ids if ids.count(x) > 1]
            raise ValueError(f"Duplicate source_ids found in manifest: {set(duplicates)}")
        return sources


def load_manifest(manifest_path: str | Path) -> CorpusManifest:
    """Loads and validates the corpus manifest from disk."""
    path = Path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(f"Manifest file not found at: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return CorpusManifest.model_validate(data)
