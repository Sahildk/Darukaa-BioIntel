# 05 — Conversation System

## Goal

Make the system conversationally useful without turning it into an uncontrolled free-form chatbot.

## Environmental State

Maintain a structured state such as:

```json
{
  "geography": {},
  "soil": {
    "ph": null,
    "organic_carbon": null,
    "moisture": null
  },
  "land_use": {
    "land_cover": null,
    "crop": null,
    "fragmentation": null
  },
  "biodiversity": {
    "species_richness": null,
    "habitat_diversity": null
  },
  "climate": {
    "temperature": null,
    "rainfall": null
  },
  "human_impact": {
    "pollution": null,
    "deforestation": null
  }
}
```

The actual schema can evolve, but the categories should remain aligned with the challenge.

## State Rules

1. Store values explicitly.
2. Track units when numeric.
3. Track source of the value:
   - user-provided
   - structured input
   - externally retrieved
4. Do not overwrite a user-provided value with an inferred value without explicit confirmation.
5. Preserve relevant state across turns.

## Clarification Strategy

Do not ask for every field.

Ask for the smallest set of high-value missing variables needed to provide a materially better answer.

Example:

User:
> Biodiversity is declining on my land.

Possible response:
> Can you provide your approximate soil organic carbon %, rainfall pattern, land-use type, and region?

If the user supplies some of these, ask only for the remaining information that materially affects the assessment.

## Conversation Flow

```text
User message
   |
   v
Extract environmental information
   |
   v
Merge with conversation state
   |
   v
Check completeness
   |
   +---- insufficient ----> clarification
   |
   +---- sufficient ------> retrieval + reasoning
```

## Memory Scope

Conversation memory should contain environmental context and prior recommendations relevant to the current assessment.

Do not store unnecessary personal information.

## Structured Input

Accept JSON or an equivalent structured payload.

Example:

```json
{
  "region": "semi-arid",
  "soil_organic_carbon": 0.3,
  "rainfall": "low",
  "crop": "wheat",
  "land_use": "monoculture"
}
```
