# Architecture Decisions

This file records decisions that should not be silently changed by coding agents.

## ADR-001 — System Shape
Status: Accepted

Decision:
Use a pipeline separating state extraction, retrieval, reasoning, recommendation generation, and evidence validation.

Reason:
The challenge evaluates knowledge grounding and reasoning, not a generic LLM-only chatbot.

## ADR-002 — Evidence Traceability
Status: Accepted

Decision:
Every recommendation should retain evidence IDs that map to retrieved source records.

Reason:
Scientific grounding is worth 25% of the evaluation and citations must be auditable.

## ADR-003 — Multi-Metric Reasoning
Status: Accepted

Decision:
Represent environmental variables explicitly and reason across at least 3 variables when sufficient input exists.

Reason:
The challenge identifies multi-metric reasoning as its core differentiator.

## ADR-004 — UI Scope
Status: Accepted

Decision:
Prioritize clarity and evidence visibility over visual complexity.

Reason:
The challenge explicitly says it is not looking for a UI-heavy application.

## ADR-005 — Scientific Integrity
Status: Accepted

Decision:
Never fabricate citations or quantitative claims.

Reason:
Unsupported scientific claims directly undermine the scientific-grounding requirement.

## Future Decisions

Add new decisions here before changing major architecture.
