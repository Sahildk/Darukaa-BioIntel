# 02 — Architecture

## High-Level Pipeline

```text
User
  |
  v
Input / Query Parser
  |
  v
Environmental State Manager
  |
  +---- missing critical variables ----> Clarification
  |
  v
Query / Retrieval Planner
  |
  v
Knowledge Retrieval
  |------------------|
  v                  v
Structured Data    Scientific Documents
  |                  |
  +--------+---------+
           v
    Multi-Metric Reasoning
           |
           v
   Recommendation Generation
           |
           v
    Evidence / Claim Validator
           |
           v
     Structured Response
           |
           v
        Frontend
```

## Architectural Principles

### 1. Retrieval Before Recommendation
The recommendation stage should receive retrieved evidence rather than relying on the model's latent knowledge alone.

### 2. State Before Reasoning
Known environmental variables should be represented explicitly so the system can reason over them consistently.

### 3. Separate Evidence From Inference
Retrieved evidence and model-generated reasoning should be distinguishable.

### 4. Deterministic Where Possible
Use ordinary code for:
- schema validation
- state merging
- missing-field detection
- metadata filtering
- response validation

Use the LLM where it adds value:
- natural-language interpretation
- query planning
- synthesis
- explanation

## Suggested Technology Shape

Frontend:
- Next.js
- TypeScript

Backend:
- Python
- FastAPI

Knowledge:
- PostgreSQL + pgvector or an equivalent vector store
- structured environmental records
- document metadata

The final choice must be based on implementation speed and reliability. Do not introduce infrastructure that does not improve the demo.

## Core Components

### Query Understanding
Extract:
- user intent
- environmental variables
- values/qualifiers
- geography
- missing information

### Environmental State
Maintain the latest trusted values from the conversation.

### Retrieval Planner
Determine which knowledge topics and variables matter to the current question.

### Knowledge Retrieval
Perform semantic retrieval plus metadata filtering where useful.

### Reasoning Engine
Identify relationships among multiple variables and connect them to evidence.

### Recommendation Engine
Generate actionable interventions constrained by retrieved evidence.

### Evidence Validator
Check that claims/citations in the final response map to retrieved source records.

### Conversation Manager
Preserve state and determine whether to clarify or answer.

## Failure Modes

The system should degrade safely when:
- no evidence is retrieved
- user information is incomplete
- evidence is weak or conflicting
- an LLM response does not match the required schema
- an external model/API fails

In these cases, return a transparent limitation rather than a fabricated answer.
