"""Natural language query parser extracting structured environmental observations with provenance."""
import json
import re
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Set
from pydantic import BaseModel, Field, ValidationError

from app.schemas.state import EnvironmentalValueType, ProvenanceSource, VariableConfidence
from app.state.manager import VALID_VARIABLE_PATHS


class ExtractedObservation(BaseModel):
    """An observation extracted from natural language with strict provenance and evidence."""
    variable_path: str = Field(..., description="Dotted path e.g. soil.organic_carbon")
    value: EnvironmentalValueType
    unit: Optional[str] = None
    confidence: VariableConfidence = VariableConfidence.EXPLICIT
    evidence_text: str = Field(..., description="Verbatim substring from user text that supports this extraction")


class ParsedQueryResult(BaseModel):
    """Structured interpretation of user message."""
    raw_query: str
    intent: str
    extracted_observations: List[ExtractedObservation] = Field(default_factory=list)


class BaseQueryParser(ABC):
    """Abstract base class for query parsing implementations."""

    @abstractmethod
    def parse(self, text: str) -> ParsedQueryResult:
        pass


class DeterministicQueryParser(BaseQueryParser):
    """
    Deterministic rule-based and regex query parser.
    Extracts numerical observations, categorical states, and ecological conditions
    directly from user text with zero LLM dependency.
    """

    def parse(self, text: str) -> ParsedQueryResult:
        extracted: List[ExtractedObservation] = []
        lower = text.lower()

        # 1. Soil Organic Carbon (%)
        soc_match = re.search(r"(?:soil\s+organic\s+carbon|soc|organic\s+carbon)(?:[^0-9%]{1,30}?)(\d+(?:\.\d+)?)\s*%", lower)
        if not soc_match:
            soc_match = re.search(r"(\d+(?:\.\d+)?)\s*%(?:[^a-z0-9]{1,20}?)(?:soil\s+organic\s+carbon|soc|organic\s+carbon)", lower)
        if soc_match:
            val = float(soc_match.group(1))
            extracted.append(ExtractedObservation(
                variable_path="soil.organic_carbon",
                value=val,
                unit="%",
                confidence=VariableConfidence.EXPLICIT,
                evidence_text=soc_match.group(0).strip(),
            ))

        # 2. Soil pH
        ph_match = re.search(r"(?:soil\s+)?\bph\b(?:[^0-9]{1,25}?)(\d+(?:\.\d+)?)", lower)
        if ph_match:
            val = float(ph_match.group(1))
            if 3.0 <= val <= 10.0:  # Plausible pH range
                extracted.append(ExtractedObservation(
                    variable_path="soil.ph",
                    value=val,
                    unit=None,
                    confidence=VariableConfidence.EXPLICIT,
                    evidence_text=ph_match.group(0).strip(),
                ))

        # 3. Rainfall / Precipitation
        rain_num_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:mm|millimeters)(?:/year|/yr|\s+annual|\s+rainfall|\s+of\s+rain)?", lower)
        if not rain_num_match:
            rain_num_match = re.search(r"(?:rainfall|precipitation)(?:[^0-9]{1,25}?)(\d+(?:\.\d+)?)\s*(?:mm|millimeters)?", lower)
        if rain_num_match:
            val = float(rain_num_match.group(1))
            extracted.append(ExtractedObservation(
                variable_path="climate.rainfall",
                value=val,
                unit="mm/year",
                confidence=VariableConfidence.EXPLICIT,
                evidence_text=rain_num_match.group(0).strip(),
            ))
        else:
            rain_qual_match = re.search(r"\b(low|sparse|erratic|high|moderate|drought-prone)\s+rainfall\b|\brainfall\s+(?:is\s+)?(low|high|scarce|moderate)\b", lower)
            if rain_qual_match:
                qual = (rain_qual_match.group(1) or rain_qual_match.group(2)).strip()
                extracted.append(ExtractedObservation(
                    variable_path="climate.rainfall",
                    value="low" if qual in ["low", "sparse", "scarce", "drought-prone"] else qual,
                    unit=None,
                    confidence=VariableConfidence.EXPLICIT,
                    evidence_text=rain_qual_match.group(0).strip(),
                ))

        # 3b. Temperature
        temp_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:°c|degrees\s+(?:celsius|c)|deg\s+c|celsius)\b", lower)
        if not temp_match:
            temp_match = re.search(r"temperature\s+(?:is\s+)?(\d+(?:\.\d+)?)\b", lower)
        if temp_match:
            val = float(temp_match.group(1))
            extracted.append(ExtractedObservation(
                variable_path="climate.temperature",
                value=val,
                unit="C",
                confidence=VariableConfidence.EXPLICIT,
                evidence_text=temp_match.group(0).strip(),
            ))

        # 4. Crop Type
        crops = ["wheat", "rice", "corn", "maize", "barley", "sorghum", "soybean", "millet", "chickpea", "citrus", "cotton"]
        for c in crops:
            crop_match = re.search(rf"\b{c}\b", lower)
            if crop_match:
                extracted.append(ExtractedObservation(
                    variable_path="land_use.crop",
                    value=c,
                    unit=None,
                    confidence=VariableConfidence.EXPLICIT,
                    evidence_text=crop_match.group(0),
                ))
                break

        # 5. Land Cover / Land Use
        land_covers = [
            ("monoculture", "monoculture"),
            ("monocrop", "monoculture"),
            ("agroforestry", "agroforestry"),
            ("orchard", "orchard"),
            ("cropland", "cropland"),
            ("pasture", "pasture"),
            ("intercropping", "polyculture"),
        ]
        for term, canonical in land_covers:
            lc_match = re.search(rf"\b{term}\b", lower)
            if lc_match:
                extracted.append(ExtractedObservation(
                    variable_path="land_use.land_cover",
                    value=canonical,
                    unit=None,
                    confidence=VariableConfidence.EXPLICIT,
                    evidence_text=lc_match.group(0),
                ))
                break

        # 6. Region / Geography
        regions = ["semi-arid", "arid", "dryland", "drylands", "tropical", "temperate", "sub-humid", "mediterranean"]
        for r in regions:
            reg_match = re.search(rf"\b{r}\b", lower)
            if reg_match:
                extracted.append(ExtractedObservation(
                    variable_path="region",
                    value="semi-arid" if r in ["semi-arid", "dryland", "drylands"] else r,
                    unit=None,
                    confidence=VariableConfidence.EXPLICIT,
                    evidence_text=reg_match.group(0),
                ))
                break

        # 7. Biodiversity status
        bio_match = re.search(r"\bbiodiversity\s+(?:is\s+)?(declining|degraded|low|lost|depleted)\b|\bdecline\s+in\s+biodiversity\b", lower)
        if bio_match:
            extracted.append(ExtractedObservation(
                variable_path="biodiversity.habitat_diversity",
                value="declining",
                unit=None,
                confidence=VariableConfidence.EXPLICIT,
                evidence_text=bio_match.group(0),
            ))

        # 8. Human Impact / Fragmentation
        frag_match = re.search(r"\b(fragmented|fragmentation|deforestation|erosion|soil\s+degradation)\b", lower)
        if frag_match:
            term = frag_match.group(1).strip()
            if "deforestation" in term:
                extracted.append(ExtractedObservation(
                    variable_path="human_impact.deforestation",
                    value="high",
                    unit=None,
                    confidence=VariableConfidence.EXPLICIT,
                    evidence_text=frag_match.group(0),
                ))
            elif "fragment" in term:
                extracted.append(ExtractedObservation(
                    variable_path="land_use.fragmentation",
                    value="high",
                    unit=None,
                    confidence=VariableConfidence.EXPLICIT,
                    evidence_text=frag_match.group(0),
                ))

        intent = "assessment"
        if "help" in lower or "what should" in lower or "recommend" in lower or "how can" in lower:
            intent = "recommendation_request"
        elif "?" in text and len(extracted) == 0:
            intent = "inquiry"

        return ParsedQueryResult(
            raw_query=text,
            intent=intent,
            extracted_observations=extracted,
        )


class PluggableLLMQueryParser(BaseQueryParser):
    """
    Pluggable LLM query parser that delegates to a callable LLM provider if configured,
    while strictly enforcing validation against VALID_VARIABLE_PATHS and falling back
    to the deterministic parser if offline or if malformed output occurs.
    """

    def __init__(
        self,
        llm_fn: Optional[Callable[[str], str]] = None,
        fallback_parser: Optional[BaseQueryParser] = None,
    ):
        self.llm_fn = llm_fn
        self.fallback = fallback_parser or DeterministicQueryParser()

    def parse(self, text: str) -> ParsedQueryResult:
        if not self.llm_fn:
            return self.fallback.parse(text)

        try:
            prompt = (
                "You are an environmental query parser. Return JSON with 'intent' and 'extracted_observations'. "
                f"Valid variable_path must be in: {sorted(list(VALID_VARIABLE_PATHS))}. Query: {text}"
            )
            raw_json = self.llm_fn(prompt)
            data = json.loads(raw_json)
            
            # Validate extracted variables against strict whitelist
            valid_extracted: List[ExtractedObservation] = []
            for item in data.get("extracted_observations", []):
                path = item.get("variable_path")
                if path in VALID_VARIABLE_PATHS:
                    valid_extracted.append(ExtractedObservation.model_validate(item))

            return ParsedQueryResult(
                raw_query=text,
                intent=data.get("intent", "assessment"),
                extracted_observations=valid_extracted,
            )
        except Exception:
            # Fallback cleanly on LLM error or invalid formatting
            return self.fallback.parse(text)
