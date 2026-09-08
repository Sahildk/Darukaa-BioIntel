# 01 — Requirements

## Requirement IDs

### R-001 — Natural-Language Input
The system MUST accept a user's environmental question or description as text.

### R-002 — Structured Input
The system MUST support structured environmental input, preferably JSON.

### R-003 — Environmental State
The system SHOULD normalize known environmental variables into a structured state.

Suggested state categories:
- soil
- climate
- land_use
- biodiversity
- human_impact
- geography

### R-004 — Missing Information
When information required for a useful assessment is missing, the system MUST ask targeted clarification questions rather than inventing values.

### R-005 — Multi-Turn Context
The system MUST retain relevant environmental information across turns within a conversation.

### R-006 — Retrievable Knowledge
The system MUST use an external/structured knowledge layer during recommendation generation.

### R-007 — Evidence Retrieval
The system MUST retrieve relevant evidence from indexed sources.

### R-008 — Multi-Metric Reasoning
When enough information exists, the system MUST consider at least 3 environmental variables together.

### R-009 — Recommendation Structure
Each recommendation MUST expose:
- action
- scientific rationale
- impacted metrics
- time horizon
- evidence/reference

### R-010 — No Unsupported Claims
The system MUST NOT fabricate citations, study results, numerical estimates, or confidence values.

### R-011 — Evidence Trace
The system SHOULD retain an internal trace of:
- variables considered
- retrieved evidence
- relationships used
- recommendation generated

### R-012 — Confidence
The system MAY provide confidence, but it should be tied to evidence quality and completeness rather than arbitrary model certainty.

### R-013 — Graceful Uncertainty
If the knowledge layer does not contain sufficient evidence, the system SHOULD explicitly say that evidence is insufficient and request additional context where appropriate.

### R-014 — Testability
Core retrieval, state extraction, clarification, reasoning, and response validation MUST be testable independently.

## Acceptance Principles

A feature is not complete merely because it returns a response. It must satisfy the relevant requirement and have a test or demonstrable evaluation case.
