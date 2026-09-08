# 03 — Knowledge System

## Goal

Build a curated, retrievable environmental knowledge layer. The knowledge layer is a critical part of the challenge and must be visibly used by the system.

## Knowledge Domains

### Soil Health
- pH
- soil organic carbon
- soil moisture

### Land Use / Land Cover
- crop/vegetation type
- monoculture
- land-cover characteristics
- habitat fragmentation where supported by sources

### Biodiversity
- species richness
- habitat diversity
- other biodiversity indicators supported by the corpus

### Climate
- temperature
- rainfall
- drought/water availability where supported

### Human Impact
- pollution
- deforestation
- habitat degradation where supported

## Source Strategy

Prefer a small, high-quality, curated corpus over a large unverified corpus.

Candidate source classes:
- FAO reports/resources
- IPCC reports where relevant
- peer-reviewed research papers
- credible environmental datasets
- other authoritative scientific/environmental institutions

Do not claim that a source supports a specific number or relationship until the actual source has been indexed and inspected.

## Document Pipeline

```text
Source
  |
  v
Document Acquisition
  |
  v
Text Extraction
  |
  v
Cleaning
  |
  v
Chunking
  |
  v
Metadata Assignment
  |
  v
Embedding
  |
  v
Vector / Structured Storage
```

## Chunk Metadata

Recommended fields:

```json
{
  "source_id": "string",
  "title": "string",
  "publisher": "string",
  "year": "number|null",
  "topic": "soil_health|land_use|biodiversity|climate|human_impact",
  "variables": ["string"],
  "interventions": ["string"],
  "geography": ["string"],
  "source_type": "paper|report|dataset|other",
  "text": "string"
}
```

## Retrieval Strategy

Use:
1. semantic similarity
2. metadata filtering where available
3. query expansion based on environmental variables
4. optional reranking if it improves quality

Do not retrieve blindly from the entire corpus if the query clearly identifies a domain.

## Structured Environmental Data

Where structured data is used, keep a separate representation for metrics rather than forcing numeric observations into document chunks.

Example:

```json
{
  "region": "string",
  "soil_organic_carbon": 0.3,
  "soil_organic_carbon_unit": "%",
  "rainfall": 600,
  "rainfall_unit": "mm/year",
  "land_use": "wheat monoculture"
}
```

## Retrieval Output

Every retrieved item should retain:
- source identity
- relevant excerpt/chunk
- metadata
- retrieval score if available

The downstream reasoning layer must be able to identify exactly which sources informed an answer.

## Corpus Quality Checks

Before using a document:
- confirm source identity
- preserve source metadata
- avoid duplicate/near-duplicate documents
- avoid unsupported summaries
- record extraction failures

## Scientific Integrity

Never manufacture:
- citations
- DOI values
- quantitative effects
- study conclusions
- causal relationships

If evidence is insufficient, the system should say so.
