import React, { useEffect, useState } from "react";
import { fetchDemoScenarios, fetchHealthStatus } from "../api";
import { ChatRequest, DemoScenario, HealthStatus } from "../types";

interface HeaderProps {
  onSelectScenario: (request: ChatRequest) => void;
  isLoading: boolean;
}

export const Header: React.FC<HeaderProps> = ({ onSelectScenario, isLoading }) => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);

  useEffect(() => {
    // Initial health check
    fetchHealthStatus()
      .then(setHealth)
      .catch(() =>
        setHealth({
          status: "offline",
          readiness: "degraded",
          version: "0.1.0",
          service: "Darukaa BioIntel",
          components: {},
        })
      );

    // Load demo scenarios dynamically from API
    fetchDemoScenarios()
      .then(setScenarios)
      .catch(() => setScenarios([]));
  }, []);

  const getShortTitle = (title: string, index: number) => {
    if (title.toLowerCase().includes("semi-arid")) return "Canonical P0 (Wheat)";
    if (title.toLowerCase().includes("vague") || title.toLowerCase().includes("incomplete"))
      return "Clarification Demo";
    if (title.toLowerCase().includes("tropical")) return "Tropical Runoff";
    return `Scenario ${index + 1}`;
  };

  return (
    <header className="app-header">
      <div className="brand-section">
        <div className="brand-logo" aria-hidden="true">
          🌱
        </div>
        <div>
          <h1 className="brand-title">Darukaa BioIntel</h1>
          <p className="brand-subtitle">
            Evidence-Constrained Ecological Intelligence & Decision Support
          </p>
        </div>
      </div>

      <div className="header-controls">
        {/* Live System Health */}
        <div
          className={`health-pill ${health?.readiness === "ready" ? "ready" : "offline"}`}
          title={
            health
              ? `Status: ${health.status} (${health.readiness})\nDatabase: ${health.components?.database || "unknown"}\nIndex: ${health.components?.retrieval_index || "unknown"}\nReasoning: ${health.components?.reasoning_engine || "unknown"}\nRecommendation: ${health.components?.recommendation_generator || "unknown"}`
              : "Connecting to API..."
          }
        >
          <span className="status-dot" />
          <span>
            {health?.readiness === "ready" ? "System Ready" : "System Offline"}
          </span>
        </div>

        {/* Demo Scenarios from GET /api/demo/scenarios */}
        {scenarios.length > 0 && (
          <div className="scenario-selector-group" role="group" aria-label="Demo Scenarios">
            <span style={{ fontSize: "11px", color: "var(--text-muted)", marginRight: "4px" }}>
              Presets:
            </span>
            {scenarios.map((s, idx) => (
              <button
                key={s.scenario_id}
                type="button"
                className={`scenario-btn ${idx === 0 ? "primary" : ""}`}
                disabled={isLoading}
                title={s.description}
                onClick={() => onSelectScenario(s.sample_request)}
              >
                {getShortTitle(s.title, idx)}
              </button>
            ))}
          </div>
        )}
      </div>
    </header>
  );
};
