# 10 — Two-Day Execution Plan

## Rule

Build the smallest complete scientifically grounded system first. Add polish only after the core pipeline works.

## Phase 1 — Repository and Contracts
- scaffold frontend/backend
- create environment configuration
- add API schemas
- establish lint/test commands

## Phase 2 — Knowledge Storage
- create database/vector schema
- create source/document metadata schema
- load a small curated corpus

## Phase 3 — Ingestion
- implement extraction
- cleaning
- chunking
- metadata
- embeddings
- indexing

## Phase 4 — Retrieval
- implement semantic retrieval
- metadata filters
- return source IDs and excerpts
- test retrieval independently

## Phase 5 — Environmental State
- parse user inputs
- normalize known variables
- merge multi-turn state
- detect missing critical fields

## Phase 6 — Clarification
- implement targeted clarification
- test incomplete scenarios

## Phase 7 — Reasoning
- implement multi-variable relationship analysis
- generate candidate interventions
- require evidence IDs

## Phase 8 — Recommendation + Evidence Validation
- structured response generation
- validate evidence mappings
- reject unsupported claims
- add limitations/confidence handling

## Phase 9 — API Integration
- connect end-to-end chat flow
- add structured input
- test API contracts

## Phase 10 — Frontend
- conversation
- environmental profile
- recommendation cards
- evidence section
- loading/error states

## Phase 11 — Evaluation
- run `docs/09-evaluation.md`
- fix failure cases
- manually inspect scientific claims

## Phase 12 — Submission
- deployment
- README
- architecture diagram
- sample scenarios
- short demo video if useful
- document limitations and future improvements

## Agent Execution Rule

Implement one phase at a time.

After each phase:
1. test
2. verify
3. commit
4. report
5. proceed

Do not build all phases in one unreviewed pass.
