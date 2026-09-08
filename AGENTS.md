# Darukaa BioIntel — Agent Instructions

## Mission

Build an AI-powered biodiversity intelligence system for the Darukaa.Earth hackathon.

The system must behave like an AI environmental scientist, not a generic chatbot.

The official challenge emphasizes:
- a retrievable knowledge layer
- conversational context and clarification
- evidence-backed recommendations
- multi-metric environmental reasoning
- text and structured input
- clear recommendations, impacted metrics, and time horizons

## Source of Truth

Before implementation, read:
1. `docs/00-project-brief.md`
2. `docs/01-requirements.md`
3. `docs/02-architecture.md`

Before modifying a subsystem, also read its relevant specification:
- Knowledge/RAG: `03-knowledge-system.md`
- Reasoning: `04-reasoning-engine.md`
- Conversation: `05-conversation-system.md`
- Evidence: `06-evidence-system.md`
- API: `07-api-contracts.md`
- Frontend: `08-frontend.md`
- Evaluation: `09-evaluation.md`
- Execution: `10-execution-plan.md`

## Non-Negotiable Principles

1. No LLM-only solution.
2. Recommendations must be grounded in retrieved evidence.
3. The system must reason across at least 3 environmental variables when the input provides enough information.
4. If critical information is missing, ask a useful clarification question rather than inventing values.
5. Never fabricate scientific citations, numerical estimates, or study findings.
6. Keep retrieval, reasoning, recommendation generation, and evidence validation as distinguishable stages.
7. Prefer simple, testable components over unnecessary multi-agent complexity.
8. Do not add technologies merely to make the architecture look sophisticated.
9. Keep secrets in environment variables.
10. Do not silently change architectural decisions. Propose changes and update the relevant specification first.

## Coding-Agent Workflow

For every task:
1. Read the relevant specification.
2. Identify dependencies and interfaces.
3. Implement only the requested phase/scope.
4. Run relevant tests.
5. Inspect failures and fix them.
6. Update documentation if the implementation changes an agreed interface or architecture.
7. Report what changed, what was tested, and any remaining limitations.

Do not implement future phases unless explicitly instructed.

## Quality Bar

A successful response should be:
- actionable
- evidence-grounded
- transparent about uncertainty
- structured
- traceable to retrieved knowledge
- based on multiple environmental relationships where appropriate

## Anti-Patterns

Do not:
- create a chatbot that answers from a system prompt alone
- hard-code fake scientific claims
- display citations that were not retrieved
- generate confident recommendations when evidence is absent
- spend disproportionate effort on animations or UI polish
- create multiple agents when a deterministic pipeline is sufficient
