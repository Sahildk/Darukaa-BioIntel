# 09 — Evaluation

## Purpose

Turn the challenge's scoring criteria into concrete tests.

## Scoring Alignment

### 30% — Depth of Reasoning
Test whether the system:
- combines multiple variables
- identifies interactions
- produces specific interventions
- avoids generic sustainability advice

### 25% — Scientific Grounding
Test whether:
- recommendations have evidence
- claims map to sources
- quantitative estimates are source-supported
- unsupported claims are rejected

### 20% — Knowledge System
Test:
- retrieval works
- metadata is preserved
- relevant evidence is returned
- the final answer actually uses retrieved knowledge

### 15% — Conversational Intelligence
Test:
- clarification
- multi-turn state
- contextual follow-up

### 10% — Output Clarity
Test:
- recommendation
- rationale
- metrics
- time horizon
- evidence
are easy to identify.

## Core Test Cases

### T-001 — Challenge Example
Input:
- SOC = 0.3%
- rainfall = low
- crop = wheat
- land use = monoculture
- region = semi-arid

Expected:
- at least 3 variables considered
- evidence retrieved
- specific recommendation
- impacted metrics
- time horizon
- no unsupported numeric estimate

### T-002 — Missing Data
Input:
> Biodiversity is declining on my land.

Expected:
- clarification question
- no unsupported intervention

### T-003 — Multi-Turn
Turn 1:
> My farm is in a semi-arid region.

Turn 2:
> Rainfall is low and I grow wheat.

Expected:
- system retains region and rainfall
- next response uses prior context

### T-004 — Unsupported Quantitative Claim
Ask for an exact percentage improvement when the corpus contains no matching evidence.

Expected:
- system declines to provide an unsupported number
- optionally explains what evidence would be needed

### T-005 — Evidence Trace
Generate a recommendation.

Expected:
- every displayed evidence reference maps to a retrieved source

### T-006 — Conflicting/Weak Evidence
Provide or retrieve sources that do not strongly agree.

Expected:
- response acknowledges uncertainty
- does not manufacture consensus

### T-007 — Structured Input
Submit JSON environmental metrics.

Expected:
- state populated
- normal recommendation pipeline executed

### T-008 — Out-of-Scope / Low-Evidence Query
Ask a question unrelated to the indexed knowledge.

Expected:
- graceful limitation rather than hallucinated scientific advice

## Manual Demo Checklist

Before submission:
- run all core tests
- inspect 5–10 realistic environmental scenarios
- inspect citations manually
- verify no fabricated quantitative claims
- verify clarification behavior
- verify multi-turn context
- verify deployed version matches local behavior
