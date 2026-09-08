# 02 — Final System Architecture

## End-to-End System Architecture

Darukaa BioIntel is architected as an **Evidence-Constrained Scientific Decision-Support System** rather than an unconstrained generative chatbot. Every recommendation is bounded by retrieved scientific literature, evaluated across a structured multi-metric environmental state, and passed through deterministic claim-level validation firewalls before reaching the user.

```mermaid
flowchart TD
    User([User / Evaluator]) -->|Natural Language + Structured JSON| API[FastAPI HTTP Layer]
    API --> Service[EnvironmentalChatService]
    
    subgraph Conversation & State Management [Phases 5 & 6]
        Service --> Flow[ConversationFlow]
        Flow --> Parser[Query Parser]
        Parser --> Ingest[State Ingestion & Authority Separation]
        Ingest --> StateMgr[(EnvironmentalStateManager\nSQLite observation_history)]
        StateMgr --> State[(Consolidated EnvironmentalState)]
        State --> ConflictCheck{Active Conflicts or\n< 3 Variables?}
        ConflictCheck -->|Yes| Clarify[Targeted ClarificationResponse]
    end
    
    Clarify -->|Return Question & State| API
    
    subgraph Multi-Metric Reasoning [Phase 7]
        ConflictCheck -->|No: Sufficient| Reasoner[EcologicalReasoningEngine]
        Reasoner --> SuffCheck{Scientific Sufficiency\n& Connected Metrics?}
        SuffCheck -->|Disconnected| ClarifySci[Scientific Sufficiency Clarification]
        SuffCheck -->|Sufficient| Graph[Causal Graph Construction\n>= 3 Variables]
        Graph --> RetrievalPlanner[Retrieval Planner]
    end
    
    ClarifySci -->|Return Diagnostic Question| API
    
    subgraph Hybrid Retrieval [Phases 2-4]
        RetrievalPlanner --> Retriever[HybridRetriever]
        Retriever --> BM25[BM25 Inverted Index]
        Retriever --> Dense[Semantic Dense Reranker]
        BM25 & Dense --> RRF[Reciprocal Rank Fusion RRF]
        RRF --> KnStore[(KnowledgeStore SQLite\n10 Curated Sources & Chunks)]
        KnStore --> Chunks[Ranked ScoredChunks]
    end
    
    Chunks --> Reasoner
    Reasoner --> Pathways[Active Causal Pathways & Candidate Interventions]
    
    subgraph Evidence-Constrained Generation & Validation [Phase 8]
        Pathways --> RecGen[RecommendationGenerator]
        RecGen --> Val{4-Gate Claim Validator}
        Val --> Gate1[Gate 1: Evidence Presence]
        Gate1 --> Gate2[Gate 2: Mechanism-Specific Support]
        Gate2 --> Gate3[Gate 3: Context Compatibility Layer]
        Gate3 --> Gate4[Gate 4: Quantitative Audit & Contraindication Firewall]
        Gate4 --> VerifiedRecs[Verified Recommendations with Full Lineage]
    end
    
    subgraph Output Presentation [Phases 9 & 10]
        VerifiedRecs --> Response[RecommendationResponse\n+ DeveloperTrace]
        Response --> UI[React / TypeScript Frontend\nDecision-Support Interface]
    end
```

---

## Architectural Subsystems

### 1. State & Provenance Subsystem (`backend/app/state/`)
- **Authority Separation (`AuthorityLevel`)**:
  - `USER_DIRECT`: Assigned to user statements and structured inputs.
  - `EXTERNAL`: Assigned to retrieved database records.
  - `INFERRED`: Assigned to model estimations.
  - **Precedence Rule**:
    ```text
    AuthorityLevel.USER_DIRECT > AuthorityLevel.EXTERNAL > AuthorityLevel.INFERRED
    ```
    Inferred values can never overwrite direct user observations.
- **Immutable Observation History**: Every observation is assigned a deterministic ID (e.g., `OBS-conv-soil_organic_carbon-001`) and immutably appended to SQLite.
- **Active Conflict Tracking**: Equal-authority contradictions produce an explicit `ConflictRecord` (`unresolved`), preserving the incumbent value and requiring user confirmation rather than silently overwriting.

### 2. Knowledge & Hybrid Retrieval Subsystem (`backend/app/knowledge/`, `backend/app/retrieval/`)
- **Curated Scientific Corpus**: 10 peer-reviewed landmark studies across Soil Health, Land Use, Climate, and Biodiversity.
- **Hybrid Fusion**: Combines BM25 lexical search and dense semantic similarity using Reciprocal Rank Fusion (RRF, $k=60$).
- **Deterministic Out-of-Domain (OOD) Policy**:
  - Strict evidence acceptance threshold: `EVIDENCE_ACCEPTANCE_THRESHOLD = 0.50`.
  - Scores below $0.50$ are classified as background noise, preventing out-of-scope topics from generating accepted evidence.

### 3. Multi-Metric Ecological Reasoning Engine (`backend/app/reasoning/`)
- **Minimum Dimensionality**: Concurrently evaluates $\ge 3$ environmental variables.
- **Scientific Sufficiency Gate**: Blocks reasoning if submitted variables lack essential ecological context (e.g., climate + crop without soil condition or land management).
- **Causal Graph & Directional Verification**: Validates relationship templates against retrieved chunk keywords and directional indicators (`deplet`, `enhanc`, `loss`).
- **Exogenous Climate Boundary Condition**: Explicitly models `climate.rainfall` as an exogenous forcing; soil interventions modulate `soil.moisture` and water infiltration rather than atmospheric rainfall.

### 4. Evidence-Constrained Generation (ECG) & Claim Validator (`backend/app/recommendation/`)
Every candidate intervention must pass 4 consecutive deterministic gates before inclusion in final recommendations:
1. **Gate 1: Evidence Presence Gate**: Intercepts unbacked proposals. Every candidate must cite valid chunk IDs in the knowledge base.
2. **Gate 2: Mechanism-Specific Support Gate**: Cross-references action keywords and affected metrics against the verbatim text of cited chunks.
3. **Gate 3: Context Compatibility Gate**: Verifies regional, climatic, and soil prerequisites against active state using `ContextMatcher`.
4. **Gate 4: Quantitative Verbatim Audit & Contraindication Firewall**:
   - Audits all percentages and numbers; rejects claims not found verbatim in cited evidence.
   - Evaluates contraindications against state (e.g., modeled rule blocking cover crops below 300 mm/year rainfall).

### 5. Application & Evaluation Layer (`backend/app/services/`, `backend/app/evaluation/`)
- **Application-Scoped Lifecycle**: `EnvironmentalChatService` uses shared, reusable components without global singleton pollution.
- **Isolated Evaluation State**: `EvaluationRunner` executes test suites inside disposable SQLite databases (`data/eval_state_{id}.db`) that auto-delete after runs, guaranteeing zero contamination of production data.
