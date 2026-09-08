"""Curated relationship templates and candidate interventions for ecological reasoning."""
from typing import Any, Dict, List, Optional
from app.schemas.evidence import CandidateIntervention
from .models import RelationshipTemplate


RELATIONSHIP_TEMPLATES: List[RelationshipTemplate] = [
    RelationshipTemplate(
        template_id="TPL-MONOCULTURE-SOC-DEPLETION",
        source_variable="land_use.land_cover",
        target_variable="soil.organic_carbon",
        mechanism_pattern="Continuous intensive monoculture depletes soil organic matter pools and accelerates carbon loss.",
        required_topics=["climate", "land_use", "soil_health"],
        required_terms=["monoculture", "depletion", "organic"],
        directional_indicators=["deplet", "exacerbat", "loss", "diminish", "degrad"],
        applicable_conditions={
            "land_use.land_cover": ["monoculture", "continuous_cropping", "simplified_rotation"],
        },
        candidate_intervention_actions=["legume_cover_crops", "conservation_tillage"],
    ),
    RelationshipTemplate(
        template_id="TPL-SOC-WATER-RETENTION",
        source_variable="soil.organic_carbon",
        target_variable="soil.moisture",
        mechanism_pattern="Soil organic carbon critically governs available soil water holding capacity and moisture retention under low-rainfall dryland regimes.",
        required_topics=["soil_health", "climate"],
        required_terms=["water", "capacity", "rainfall"],
        directional_indicators=["water capacity", "efficiency", "availab", "retention", "moisture"],
        applicable_conditions={
            "soil.organic_carbon": {"lte": 1.1},
            "region": ["semi-arid", "drylands", "arid"],
        },
        candidate_intervention_actions=["crop_residue_retention", "organic_amendments"],
    ),
    RelationshipTemplate(
        template_id="TPL-DIVERSIFICATION-BIODIVERSITY",
        source_variable="land_use.land_cover",
        target_variable="biodiversity.species_richness",
        mechanism_pattern="Agricultural diversification enhances biological diversity and strengthens natural pest regulation without yield penalty.",
        required_topics=["land_use", "biodiversity"],
        required_terms=["diversification", "biodiversity", "yield"],
        directional_indicators=["enhanc", "promot", "increas", "benefit", "stabiliz"],
        applicable_conditions={
            "land_use.land_cover": ["monoculture", "cropland", "simplified_rotation"],
        },
        candidate_intervention_actions=["intercropping", "crop_rotation", "agroforestry"],
    ),
    RelationshipTemplate(
        template_id="TPL-HABITAT-BORDERS-POLLINATORS",
        source_variable="land_use.land_cover",
        target_variable="biodiversity.pollinator_abundance",
        mechanism_pattern="Non-crop semi-natural flowering borders and hedgerows enhance wild pollinator density and stabilize crop yields.",
        required_topics=["biodiversity"],
        required_terms=["pollinator", "density", "hedgerows"],
        directional_indicators=["enhanc", "support", "pollinator density", "clos"],
        applicable_conditions={
            "land_use.land_cover": ["monoculture", "cropland"],
        },
        candidate_intervention_actions=["hedgerows", "flower_strips", "habitat_corridors"],
    ),
    RelationshipTemplate(
        template_id="TPL-AGROFORESTRY-MICROCLIMATE",
        source_variable="land_use.land_cover",
        target_variable="climate.temperature",
        mechanism_pattern="Integrating perennial windbreaks and agroforestry buffers microclimatic extremes and curbs surface wind speeds.",
        required_topics=["climate", "land_use"],
        required_terms=["windbreaks", "microclimate", "temperature"],
        directional_indicators=["buffer", "lower", "reduc", "preserv", "curtail"],
        applicable_conditions={
            "region": ["semi-arid", "drylands", "arid"],
        },
        candidate_intervention_actions=["shelterbelts", "agroforestry", "perennial_windbreaks"],
    ),
    RelationshipTemplate(
        template_id="TPL-CONNECTIVITY-FRAGMENTATION",
        source_variable="land_use.fragmentation",
        target_variable="biodiversity.habitat_diversity",
        mechanism_pattern="Landscape fragmentation without ecological corridors drives steep declines in terrestrial biodiversity and habitat connectivity.",
        required_topics=["human_impact", "biodiversity"],
        required_terms=["fragmentation", "corridors", "biodiversity"],
        directional_indicators=["declin", "driv", "loss", "sever"],
        applicable_conditions={
            "land_use.fragmentation": ["high", "fragmented"],
        },
        candidate_intervention_actions=["ecological_corridors", "landscape_restoration"],
    ),
]


# Concrete CandidateIntervention specifications mapped to action names
INTERVENTION_SPECS: Dict[str, Dict[str, Any]] = {
    "legume_cover_crops": {
        "action": "Introduce legume-based cover crops into rotation",
        "rationale": "Builds soil organic carbon pools, stimulates mycorrhizal activity, and biological nitrogen fixation without exacerbating water stress.",
        "affected_metrics": ["soil.organic_carbon", "climate.rainfall", "biodiversity.habitat_diversity"],
        "time_horizon": "medium",
        "required_conditions": ["semi-arid drylands or degraded croplands", "baseline SOC < 1.0%"],
        "contraindications": [
            "In regions with severe annual rainfall deficits (< 300 mm/year), unmanaged cover crop biomass may cause seasonal soil moisture competition; terminate cover crops early before crop sowing."
        ],
    },
    "crop_residue_retention": {
        "action": "Retain at least 30% crop residue on soil surface",
        "rationale": "Reduces direct solar evaporation, moderates soil temperature by 2-5 degrees Celsius, and improves rainfall infiltration.",
        "affected_metrics": ["soil.organic_carbon", "climate.rainfall", "climate.temperature"],
        "time_horizon": "short",
        "required_conditions": ["annual cropland", "mechanized or no-till system"],
        "contraindications": [
            "Excessive residue in high-humidity or waterlogged soils can foster fungal pathogens; calibrate residue levels to local moisture dynamics."
        ],
    },
    "hedgerows": {
        "action": "Establish native flowering hedgerows and border strips",
        "rationale": "Enhances wild pollinator density, creates nesting refugia for predatory beneficial insects, and stabilizes yield without expanding crop acreage.",
        "affected_metrics": ["biodiversity.pollinator_abundance", "biodiversity.species_richness"],
        "time_horizon": "medium",
        "required_conditions": ["field boundaries available", "semi-natural vegetative seed stock"],
        "contraindications": [
            "Avoid introducing invasive or water-greedy plant species that compete with crops for shallow root moisture."
        ],
    },
    "agroforestry": {
        "action": "Integrate nitrogen-fixing trees and boundary windbreaks",
        "rationale": "Reduces ground wind speeds by 30-50%, buffers microclimatic heat stress, and generates deep soil carbon sequestration.",
        "affected_metrics": ["soil.organic_carbon", "climate.temperature", "biodiversity.species_richness"],
        "time_horizon": "long",
        "required_conditions": ["semi-arid or sub-humid drylands", "perennial tenure stability"],
        "contraindications": [
            "Requires careful tree-crop species pairing to prevent excessive root competition for subsurface water during prolonged drought spells."
        ],
    },
    "ecological_corridors": {
        "action": "Establish landscape-level ecological connectivity corridors",
        "rationale": "Connects fragmented habitats, restores dispersal pathways for native wildlife, and mitigates isolation bottlenecks.",
        "affected_metrics": ["biodiversity.habitat_diversity", "land_use.fragmentation"],
        "time_horizon": "long",
        "required_conditions": ["fragmented agricultural landscapes", "community or watershed coordination"],
        "contraindications": [
            "Narrow corridors with high edge-effects may inadvertently facilitate invasive species dispersal if unmonitored."
        ],
    },
}
