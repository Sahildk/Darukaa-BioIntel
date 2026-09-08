# 04 — Reasoning Engine

## Purpose

Turn environmental observations + retrieved evidence into explicit multi-metric reasoning.

The challenge's core differentiator is connecting multiple environmental variables rather than producing single-variable advice.

## Reasoning Pipeline

```text
Environmental State
       |
       v
Relevant Variables
       |
       v
Variable Relationships
       |
       v
Retrieved Evidence
       |
       v
Candidate Interventions
       |
       v
Multi-Metric Impact Analysis
       |
       v
Evidence-Constrained Recommendation
```

## Minimum Reasoning Rule

When the user provides enough information, the system should reason over at least 3 environmental variables.

Example challenge scenario:
- soil organic carbon
- rainfall
- land use/crop
- region

A response should explain relationships among these variables rather than giving four unrelated facts.

## Relationship Representation

Represent relationships conceptually, for example:

```text
low rainfall
    +
low soil moisture
    +
low habitat diversity
    |
    v
potential biodiversity stress
```

The exact causal relationship must be supported by retrieved evidence where it is presented as scientific fact.

## Candidate Intervention Model

A candidate intervention should contain:

```json
{
  "action": "string",
  "rationale": "string",
  "affected_metrics": ["string"],
  "time_horizon": "short|medium|long",
  "required_conditions": ["string"],
  "evidence_ids": ["string"]
}
```

## Non-Obvious Recommendation Principle

Prefer recommendations that address several identified constraints at once, provided the evidence supports them.

Do not force complexity for its own sake. A simple intervention can still be strong if the reasoning is specific and evidence-backed.

## Quantitative Claims

Only provide measurable improvement estimates when a retrieved source directly supports the estimate and its context is sufficiently comparable.

The system should preserve the source context rather than generalize a study result to every region or ecosystem.

## Uncertainty

Consider:
- completeness of user inputs
- number and quality of supporting sources
- relevance of the source context
- agreement/conflict among sources

Do not treat raw LLM confidence as scientific confidence.

## Reasoning Output

Internally retain:

```json
{
  "variables_considered": ["string"],
  "relationships": [
    {
      "from": "string",
      "to": "string",
      "relationship": "string",
      "evidence_ids": ["string"]
    }
  ],
  "candidate_actions": [],
  "selected_actions": []
}
```

This trace can later be summarized for the user without exposing hidden chain-of-thought.
