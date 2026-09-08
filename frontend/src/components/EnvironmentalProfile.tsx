import React from "react";
import { EnvironmentalState, EnvironmentalVariable } from "../types";

interface EnvironmentalProfileProps {
  state: EnvironmentalState | null;
  conversationId: string | null;
  onResetSession: () => void;
}

export const EnvironmentalProfile: React.FC<EnvironmentalProfileProps> = ({
  state,
  conversationId,
  onResetSession,
}) => {
  const renderProvenanceBadge = (v: EnvironmentalVariable | null | undefined) => {
    if (!v || v.value === null || v.value === undefined) {
      return <span className="provenance-pill not-provided">Not Provided</span>;
    }

    const source = v.source;
    switch (source) {
      case "user":
        return <span className="provenance-pill user">User Provided</span>;
      case "structured_input":
        return <span className="provenance-pill structured_input">Structured Input</span>;
      case "retrieved":
        return <span className="provenance-pill retrieved">Retrieved</span>;
      case "inferred":
        return <span className="provenance-pill inferred">Inferred</span>;
      default:
        return <span className="provenance-pill not-provided">{source}</span>;
    }
  };

  const renderVariableRow = (label: string, v: EnvironmentalVariable | null | undefined) => {
    const isPresent = v && v.value !== null && v.value !== undefined;
    const displayValue = isPresent ? `${v.value}${v.unit ? ` ${v.unit}` : ""}` : "—";

    return (
      <div className="variable-row">
        <span className="variable-label">{label}</span>
        <div className="variable-value-wrap">
          <span className="variable-value">{displayValue}</span>
          {renderProvenanceBadge(v)}
        </div>
      </div>
    );
  };

  return (
    <aside className="profile-pane" aria-label="Live Environmental Profile">
      <div className="profile-header">
        <div>
          <h2 className="profile-title">Live Environmental Profile</h2>
          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
            Normalized State Inspector (Phase 5)
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {conversationId && (
            <span className="session-badge" title="Active Conversation ID">
              {conversationId.length > 18 ? `${conversationId.slice(0, 16)}...` : conversationId}
            </span>
          )}
          <button
            type="button"
            className="reset-session-btn"
            title="Start New Session"
            onClick={onResetSession}
          >
            ↺ New Session
          </button>
        </div>
      </div>

      <div className="profile-content">
        {/* Active Conflicts Alert */}
        {state?.active_conflicts && state.active_conflicts.length > 0 && (
          <div className="conflict-alert-box" role="alert">
            <strong>⚠️ Active Conflict Detected in State</strong>
            {state.active_conflicts.map((c) => (
              <div key={c.conflict_id} style={{ marginTop: "2px" }}>
                <span>Variable: <code>{c.variable_path}</code></span>
                <p style={{ fontStyle: "italic" }}>{c.explanation}</p>
              </div>
            ))}
          </div>
        )}

        {/* 1. Region */}
        <div className="category-card">
          <div className="category-card-header">
            <span className="category-name">Geography / Biome</span>
          </div>
          {renderVariableRow("Region", state?.region)}
        </div>

        {/* 2. Soil Health */}
        <div className="category-card">
          <div className="category-card-header">
            <span className="category-name">Soil Health</span>
          </div>
          {renderVariableRow("Soil Organic Carbon (SOC)", state?.soil?.organic_carbon)}
          {renderVariableRow("pH Level", state?.soil?.ph)}
          {renderVariableRow("Moisture Capacity", state?.soil?.moisture)}
        </div>

        {/* 3. Climate Factors */}
        <div className="category-card">
          <div className="category-card-header">
            <span className="category-name">Climate Factors</span>
          </div>
          {renderVariableRow("Rainfall / Precipitation", state?.climate?.rainfall)}
          {renderVariableRow("Temperature", state?.climate?.temperature)}
        </div>

        {/* 4. Land Use */}
        <div className="category-card">
          <div className="category-card-header">
            <span className="category-name">Land Use & Management</span>
          </div>
          {renderVariableRow("Land Cover", state?.land_use?.land_cover)}
          {renderVariableRow("Primary Crop", state?.land_use?.crop)}
          {renderVariableRow("Fragmentation", state?.land_use?.fragmentation)}
        </div>

        {/* 5. Biodiversity Indicators */}
        <div className="category-card">
          <div className="category-card-header">
            <span className="category-name">Biodiversity Indicators</span>
          </div>
          {renderVariableRow("Species Richness", state?.biodiversity?.species_richness)}
          {renderVariableRow("Habitat Diversity", state?.biodiversity?.habitat_diversity)}
          {renderVariableRow("Pollinator Abundance", state?.biodiversity?.pollinator_abundance)}
        </div>

        {/* 6. Human Impact */}
        <div className="category-card">
          <div className="category-card-header">
            <span className="category-name">Human Impact</span>
          </div>
          {renderVariableRow("Pollution", state?.human_impact?.pollution)}
          {renderVariableRow("Deforestation", state?.human_impact?.deforestation)}
        </div>
      </div>
    </aside>
  );
};
