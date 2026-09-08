import React, { useRef, useEffect } from "react";
import { ClarificationCard } from "./ClarificationCard";
import { RecommendationCard } from "./RecommendationCard";
import { DeveloperTraceView } from "./DeveloperTraceView";
import { StructuredInputDrawer } from "./StructuredInputDrawer";
import { ConversationTurn, StructuredInput } from "../types";

interface ConversationPaneProps {
  turns: ConversationTurn[];
  inputMessage: string;
  setInputMessage: (msg: string) => void;
  structuredInput: StructuredInput;
  setStructuredInput: (input: StructuredInput) => void;
  showStructuredDrawer: boolean;
  setShowStructuredDrawer: (show: boolean) => void;
  isLoading: boolean;
  errorBanner: string | null;
  onDismissError: () => void;
  onSendMessage: () => void;
  onResetSession: () => void;
}

export const ConversationPane: React.FC<ConversationPaneProps> = ({
  turns,
  inputMessage,
  setInputMessage,
  structuredInput,
  setStructuredInput,
  showStructuredDrawer,
  setShowStructuredDrawer,
  isLoading,
  errorBanner,
  onDismissError,
  onSendMessage,
  onResetSession,
}) => {
  const streamEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    streamEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, isLoading]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && inputMessage.trim()) {
        onSendMessage();
      }
    }
  };

  const hasStructuredValues = Object.values(structuredInput).some(
    (v) => v !== null && v !== undefined && v !== ""
  );

  return (
    <section className="conversation-pane" aria-label="Ecological Conversation and Decision Support">
      {/* Message Stream */}
      <div className="message-stream">
        {errorBanner && (
          <div className="alert-banner error" role="alert">
            <span>⚠️ {errorBanner}</span>
            <button
              type="button"
              onClick={onDismissError}
              style={{ background: "none", border: "none", color: "#fca5a5", cursor: "pointer", fontWeight: 700 }}
            >
              ✕
            </button>
          </div>
        )}

        {turns.length === 0 && (
          <div style={{ textAlign: "center", margin: "auto", maxWidth: "480px", color: "var(--text-muted)" }}>
            <div style={{ fontSize: "36px", marginBottom: "12px" }}>🌍</div>
            <h3 style={{ color: "#fff", marginBottom: "8px", fontSize: "18px" }}>
              Welcome to Darukaa BioIntel
            </h3>
            <p style={{ fontSize: "14px", lineHeight: "1.6" }}>
              An evidence-constrained decision-support platform designed to assess ecosystem vulnerability,
              evaluate multi-metric causal pathways, and generate scientifically validated restoration recommendations.
            </p>
            <p style={{ fontSize: "12px", marginTop: "12px", color: "#38bdf8" }}>
              💡 Select a scenario preset above or describe your ecosystem conditions below.
            </p>
          </div>
        )}

        {turns.map((turn) => (
          <React.Fragment key={turn.id}>
            {/* User Turn */}
            {turn.sender === "user" && (
              <div className="message-bubble user">
                <div className="user-message-text">{turn.request?.message}</div>
                {turn.request?.structured_input && (
                  <div className="user-structured-pills">
                    {Object.entries(turn.request.structured_input)
                      .filter(([, v]) => v !== null && v !== undefined && v !== "")
                      .map(([k, v]) => (
                        <span key={k} className="structured-tag">
                          {k}: {String(v)}
                        </span>
                      ))}
                  </div>
                )}
              </div>
            )}

            {/* Assistant Turn */}
            {turn.sender === "assistant" && turn.response && (
              <div className="message-bubble assistant">
                {/* 1. Clarification Response */}
                {turn.response.type === "clarification" && (
                  <ClarificationCard clarification={turn.response} />
                )}

                {/* 2. Recommendation Response */}
                {turn.response.type === "recommendation" && (
                  <div>
                    {/* Assessment Summary */}
                    <div className="assessment-summary-banner">
                      <p className="assessment-text">{turn.response.assessment}</p>
                      {turn.response.variables_considered &&
                        turn.response.variables_considered.length > 0 && (
                          <div className="variables-considered-row">
                            <span className="considered-label">Variables Analyzed:</span>
                            {turn.response.variables_considered.map((v) => (
                              <span key={v} className="considered-pill">
                                {v}
                              </span>
                            ))}
                          </div>
                        )}
                    </div>

                    {/* Validated Recommendations */}
                    {turn.response.recommendations && turn.response.recommendations.length > 0 ? (
                      turn.response.recommendations.map((rec, idx) => (
                        <RecommendationCard
                          key={rec.recommendation_id || idx}
                          recommendation={rec}
                          index={idx}
                        />
                      ))
                    ) : (
                      /* Empty recommendation state — strictly graceful without manufacturing fallbacks */
                      <div className="alert-banner warning">
                        <span>
                          ℹ️ No evidence-backed recommendation could be validated for this specific ecological context.
                        </span>
                      </div>
                    )}

                    {/* Scientific Limitations Banner */}
                    {turn.response.limitations && turn.response.limitations.length > 0 && (
                      <div className="limitations-banner">
                        <span className="limitations-title">
                          🛡️ Ecological Boundaries & Cautionary Conditions:
                        </span>
                        {turn.response.limitations.map((lim, lIdx) => (
                          <div key={lIdx} className="limitation-item">
                            • {lim}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Developer Trace View */}
                    {turn.response.developer_trace && (
                      <DeveloperTraceView trace={turn.response.developer_trace} />
                    )}
                  </div>
                )}
              </div>
            )}
          </React.Fragment>
        ))}

        {/* Loading Spinner */}
        {isLoading && (
          <div className="loading-indicator" role="status">
            <div className="spinner" />
            <span>Analyzing environmental state and validating evidence...</span>
          </div>
        )}

        <div ref={streamEndRef} />
      </div>

      {/* Input Console */}
      <div className="input-console">
        {showStructuredDrawer && (
          <StructuredInputDrawer
            structuredInput={structuredInput}
            onChange={setStructuredInput}
            disabled={isLoading}
          />
        )}

        <div className="input-row">
          <textarea
            className="chat-textarea"
            placeholder="Describe ecosystem conditions, land management, or observed changes (e.g., 'We have a wheat monoculture with 0.3% SOC and low rainfall')..."
            rows={2}
            value={inputMessage}
            disabled={isLoading}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button
            type="button"
            className="send-btn"
            disabled={isLoading || (!inputMessage.trim() && !hasStructuredValues)}
            onClick={onSendMessage}
          >
            {isLoading ? "..." : "Assess ↗"}
          </button>
        </div>

        <div className="console-actions-row">
          <button
            type="button"
            className="toggle-structured-btn"
            onClick={() => setShowStructuredDrawer(!showStructuredDrawer)}
          >
            {showStructuredDrawer ? "▲ Hide Parameters" : "⚙️ Structured Parameters (JSON)"}
            {hasStructuredValues && !showStructuredDrawer && " (Active)"}
          </button>

          <button
            type="button"
            className="reset-session-btn"
            onClick={onResetSession}
            disabled={isLoading}
          >
            Reset Session
          </button>
        </div>
      </div>
    </section>
  );
};
