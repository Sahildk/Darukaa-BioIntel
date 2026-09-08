/**
 * Frontend TypeScript contracts mirroring backend API schemas exactly.
 * Reference: backend/app/schemas/ (chat.py, recommendation.py, state.py, evidence.py, demo.py)
 * RULE: Do not independently invent, rename, reinterpret, or derive fields.
 */

export type ProvenanceSource = "user" | "structured_input" | "retrieved" | "inferred";

export type VariableConfidence = "explicit" | "estimated" | "inferred";

export type EnvironmentalValueType = number | string | boolean;

export interface EnvironmentalVariable {
  value: EnvironmentalValueType;
  unit: string | null;
  source: ProvenanceSource;
  confidence: VariableConfidence;
  timestamp: string;
  observation_id: string | null;
}

export interface SoilState {
  ph: EnvironmentalVariable | null;
  organic_carbon: EnvironmentalVariable | null;
  moisture: EnvironmentalVariable | null;
}

export interface LandUseState {
  land_cover: EnvironmentalVariable | null;
  crop: EnvironmentalVariable | null;
  fragmentation: EnvironmentalVariable | null;
}

export interface BiodiversityState {
  species_richness: EnvironmentalVariable | null;
  habitat_diversity: EnvironmentalVariable | null;
  pollinator_abundance: EnvironmentalVariable | null;
}

export interface ClimateState {
  temperature: EnvironmentalVariable | null;
  rainfall: EnvironmentalVariable | null;
}

export interface HumanImpactState {
  pollution: EnvironmentalVariable | null;
  deforestation: EnvironmentalVariable | null;
}

export interface ConflictRecord {
  conflict_id: string;
  variable_path: string;
  existing_observation_id: string;
  incoming_observation_id: string;
  status: "unresolved" | "resolved";
  resolved_observation_id: string | null;
  detected_at: string;
  resolved_at: string | null;
  explanation: string;
}

export interface EnvironmentalState {
  region: EnvironmentalVariable | null;
  soil: SoilState;
  land_use: LandUseState;
  biodiversity: BiodiversityState;
  climate: ClimateState;
  human_impact: HumanImpactState;
  active_conflicts: ConflictRecord[];
  observation_history: Array<Record<string, unknown>>;
}

export interface StructuredInput {
  region?: string | null;
  soil_organic_carbon?: number | string | null;
  soil_ph?: number | string | null;
  rainfall?: number | string | null;
  crop?: string | null;
  land_use?: string | null;
}

export interface ChatRequest {
  conversation_id?: string | null;
  message: string;
  structured_input?: StructuredInput | null;
}

export interface ClarificationResponse {
  type: "clarification";
  conversation_id: string;
  question: string;
  missing_variables: string[];
  environmental_state: EnvironmentalState;
}

export type TimeHorizon = "short" | "medium" | "long";

export type EvidenceStrength = "Strong" | "Moderate" | "Limited";

export interface EvidenceItem {
  evidence_id: string;
  source_id: string;
  title: string;
  publisher: string;
  year?: number | null;
  excerpt: string;
  source_url?: string | null;
  doi?: string | null;
  relevance_score?: number | null;
}

export type ClaimValidationStatus =
  | "supported"
  | "unsupported_no_evidence"
  | "unsupported_claim"
  | "context_mismatch"
  | "quantitative_claim_unsupported"
  | "contraindication_blocked";

export interface ClaimValidationRecord {
  claim_id: string;
  claim_type: string;
  claim_text: string;
  status: ClaimValidationStatus;
  supporting_chunk_ids: string[];
  details: string;
}

export interface RecommendationItem {
  recommendation_id?: string | null;
  action: string;
  rationale?: string | null;
  why: string;
  impacted_metrics: string[];
  time_horizon: TimeHorizon;
  evidence_strength: EvidenceStrength;
  evidence: EvidenceItem[];
  evidence_ids?: string[];
  source_ids?: string[];
  supporting_relationship_ids?: string[];
  supporting_pathway_ids?: string[];
  contraindications?: string[];
  assumptions?: string[];
  limitations?: string[];
  claim_validations?: ClaimValidationRecord[];
}

export interface DeveloperTrace {
  query: string;
  extracted_variables: Record<string, unknown>;
  retrieval_query?: string | null;
  retrieved_source_ids: string[];
  reasoning_variables: string[];
  validation_status: string;
}

export interface RecommendationResponse {
  type: "recommendation";
  conversation_id: string;
  assessment: string;
  variables_considered: string[];
  recommendations: RecommendationItem[];
  environmental_state: EnvironmentalState;
  limitations: string[];
  developer_trace?: DeveloperTrace | null;
}

export type ChatResponse = ClarificationResponse | RecommendationResponse;

export interface HealthStatus {
  status: string;
  readiness: "ready" | "degraded";
  version: string;
  service: string;
  components: Record<string, string>;
  mode?: string;
}

export interface DemoScenario {
  scenario_id: string;
  title: string;
  description: string;
  sample_request: ChatRequest;
}

export interface ConversationTurn {
  id: string;
  sender: "user" | "assistant";
  timestamp: string;
  request?: ChatRequest;
  response?: ChatResponse;
  errorMessage?: string;
}
