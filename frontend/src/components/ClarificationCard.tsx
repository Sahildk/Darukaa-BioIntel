import React from "react";
import { ClarificationResponse } from "../types";

interface ClarificationCardProps {
  clarification: ClarificationResponse;
  onSelectVariable?: (variablePath: string) => void;
}

export const ClarificationCard: React.FC<ClarificationCardProps> = ({
  clarification,
}) => {
  return (
    <div className="clarification-card" role="region" aria-label="Clarification Request">
      <div className="clarification-header">
        <span aria-hidden="true">⚠️</span>
        <span>Additional Environmental Context Required</span>
      </div>

      <p className="clarification-question">{clarification.question}</p>

      {clarification.missing_variables && clarification.missing_variables.length > 0 && (
        <div className="missing-variables-wrap">
          <span className="missing-label">Critical Unspecified Parameters:</span>
          <div className="missing-pills">
            {clarification.missing_variables.map((varName) => (
              <span key={varName} className="missing-pill">
                {varName}
              </span>
            ))}
          </div>
        </div>
      )}

      <p style={{ fontSize: "12px", color: "var(--text-muted)", fontStyle: "italic" }}>
        * Darukaa BioIntel enforces evidence-constrained assessment. Recommendations cannot be
        safely synthesized without baseline ecological parameters.
      </p>
    </div>
  );
};
