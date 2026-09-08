# 04 — Multi-Metric Ecological Reasoning Engine

## Core Purpose

The primary differentiator of Darukaa BioIntel is **multi-metric ecological reasoning**. Rather than dispensing single-variable agricultural tips, the engine concurrently evaluates at least three environmental variables, models active causal pathways across them, and anchors every inference in retrieved scientific evidence.

---

## Reasoning Subsystem Architecture

```text
Consolidated Environmental State (>= 3 populated variables)
                       │
                       ▼
         Scientific Sufficiency Gate
         (Validates connected ecological context;
          rejects disconnected climate+crop sets without soil/management)
                       │
                       ▼
       Context Compatibility Matching (ContextMatcher)
       (Filters relationship templates by region, soil condition, crop)
                       │
                       ▼
       Dynamic Retrieval Query Formulation
       (Targeted queries combining active variables & context)
                       │
                       ▼
            Hybrid Evidence Retrieval
            (BM25 + Dense Semantic Fusion via RRF)
                       │
                       ▼
       Directional Relationship Verification
       (Validates causal indicators: deplet, enhanc, loss, mitigat)
                       │
                       ▼
         Active Causal Pathways Constructed
         (Chain of validated multi-variable relationships)
                       │
                       ▼
         Candidate Interventions Instantiated
         (Passed to Phase 8 Evidence Validation Pipeline)
```

---

## Scientific Modeling & Boundary Conditions

### 1. Exogenous Climatic Forcing vs. Endogenous Soil State
A critical ecological distinction implemented in the reasoning engine:
- **`climate.rainfall` is an Exogenous Climatic Boundary Condition**: Precipitation regimes (e.g., annual rainfall, seasonal distribution) are macroclimatic drivers imposed on the parcel. The system does not model agricultural or soil practices as creating rainfall.
- **Interventions Modulate `soil.moisture` and Infiltration**: Interventions such as crop residue retention and organic matter additions increase **soil moisture retention capacity (`soil.moisture`)**, reduce direct evaporation, and improve **water infiltration rates** from available rainfall.
- **Contraindication Thresholds**: When rainfall is severely deficit (e.g., modeled below 300 mm/year in semi-arid zones), competitive interventions like cover crops pose a high risk of soil moisture depletion for the primary cash crop.

### 2. Multi-Variable Relationship Templates (`RELATIONSHIP_TEMPLATES`)
The engine maintains declarative, evidence-grounded templates across key ecological domains:

1. **Monoculture $\rightarrow$ Soil Organic Carbon Depletion (`TPL-MONOCULTURE-SOC-DEPLETION`)**:
   - *Source*: `land_use.land_cover` (monoculture) $\rightarrow$ *Target*: `soil.organic_carbon`
   - *Mechanism*: Continuous intensive monoculture depletes soil organic matter pools and accelerates carbon loss.
   - *Directional Indicators*: `deplet`, `exacerbat`, `loss`, `diminish`, `degrad`.

2. **Soil Organic Carbon $\rightarrow$ Moisture Retention (`TPL-SOC-WATER-RETENTION`)**:
   - *Source*: `soil.organic_carbon` $\rightarrow$ *Target*: `soil.moisture`
   - *Mechanism*: Soil organic carbon critically governs available soil water holding capacity and moisture retention under low-rainfall dryland regimes.
   - *Directional Indicators*: `water capacity`, `efficiency`, `availab`, `retention`, `moisture`.

3. **Diversification $\rightarrow$ Species Richness (`TPL-DIVERSIFICATION-BIODIVERSITY`)**:
   - *Source*: `land_use.land_cover` (diversified) $\rightarrow$ *Target*: `biodiversity.species_richness`
   - *Mechanism*: Agricultural diversification enhances biological diversity and strengthens natural pest regulation without yield penalty.
   - *Directional Indicators*: `enhanc`, `promot`, `increas`, `benefit`, `stabiliz`.

4. **Field Borders $\rightarrow$ Pollinator Abundance (`TPL-HABITAT-BORDERS-POLLINATORS`)**:
   - *Source*: `land_use.land_cover` (borders/hedgerows) $\rightarrow$ *Target*: `biodiversity.pollinator_abundance`
   - *Mechanism*: Non-crop semi-natural flowering borders and hedgerows enhance wild pollinator density and stabilize crop yields.
   - *Directional Indicators*: `enhanc`, `support`, `pollinator density`.

---

## Scientific Sufficiency Gate (`backend/app/reasoning/sufficiency.py`)

The engine enforces a strict prerequisite before initiating multi-metric reasoning:
- **Minimum Count**: Must contain $\ge 3$ distinct environmental variables.
- **Connected Context Requirement**: Observations must span at least two complementary domains (e.g., Soil + Climate, Soil + Land Use, or Land Use + Biodiversity).
- **Disconnected Variable Interception**: A set containing only `climate.temperature`, `climate.rainfall`, and `land_use.crop` lacks baseline soil condition (SOC or pH) and land management practice. The sufficiency gate intercepts this configuration and routes to a targeted scientific clarification question rather than producing ungrounded advice.

---

## Directional Evidence Verification

A relationship template is activated if and only if:
1. Context rules match the active state (via `ContextMatcher`).
2. Hybrid retrieval returns relevant chunks matching the required topics.
3. The retrieved chunks contain both required mechanism terms and at least one directional indicator.

This guarantees that an intervention is never recommended merely because a paper mentions the variable name; it must explicitly demonstrate evidence-supported causal alignment.
