import React, { useState } from "react";
import { DeveloperTrace } from "../types";

interface DeveloperTraceViewProps {
  trace: DeveloperTrace;
}

export const DeveloperTraceView: React.FC<DeveloperTraceViewProps> = ({ trace }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="dev-trace-card">
      <div
        className="dev-trace-header"
        onClick={() => setIsOpen(!isOpen)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") setIsOpen(!isOpen);
        }}
      >
        <span>🔍 Developer & Auditor Observability Trace</span>
        <span>{isOpen ? "Collapse ▲" : "Expand Audit Trace ▼"}</span>
      </div>

      {isOpen && (
        <div className="dev-trace-body">
          <div>
            <strong>Audit Status:</strong>{" "}
            <span style={{ color: "#34d399" }}>{trace.validation_status}</span>
          </div>
          <div>
            <strong>User Query:</strong> {trace.query}
          </div>
          <div>
            <strong>Variables Considered:</strong>{" "}
            {trace.reasoning_variables && trace.reasoning_variables.length > 0
              ? trace.reasoning_variables.join(", ")
              : "None"}
          </div>
          <div>
            <strong>Retrieved Sources ({trace.retrieved_source_ids?.length || 0}):</strong>{" "}
            {trace.retrieved_source_ids?.join(", ") || "None"}
          </div>
          {trace.extracted_variables && Object.keys(trace.extracted_variables).length > 0 && (
            <div>
              <strong>Extracted Parameters:</strong>
              <pre style={{ marginTop: "4px", backgroundColor: "rgba(0,0,0,0.3)", padding: "6px 8px", borderRadius: "4px" }}>
                {JSON.stringify(trace.extracted_variables, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
