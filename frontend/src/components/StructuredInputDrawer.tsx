import React from "react";
import { StructuredInput } from "../types";

interface StructuredInputDrawerProps {
  structuredInput: StructuredInput;
  onChange: (input: StructuredInput) => void;
  disabled?: boolean;
}

export const StructuredInputDrawer: React.FC<StructuredInputDrawerProps> = ({
  structuredInput,
  onChange,
  disabled = false,
}) => {
  const updateField = (field: keyof StructuredInput, val: string) => {
    let parsedVal: string | number | null = val;
    if (val === "") {
      parsedVal = null;
    } else if (field === "soil_organic_carbon" || field === "soil_ph") {
      const num = parseFloat(val);
      parsedVal = isNaN(num) ? val : num;
    } else if (field === "rainfall") {
      const num = parseFloat(val);
      parsedVal = isNaN(num) ? val : num;
    }

    onChange({
      ...structuredInput,
      [field]: parsedVal,
    });
  };

  return (
    <div className="structured-drawer" role="group" aria-label="Structured Environmental Parameters">
      <div className="field-group">
        <label htmlFor="input-region">Region / Biome</label>
        <input
          id="input-region"
          type="text"
          className="field-input"
          placeholder="e.g. semi-arid, temperate"
          value={structuredInput.region || ""}
          disabled={disabled}
          onChange={(e) => updateField("region", e.target.value)}
        />
      </div>

      <div className="field-group">
        <label htmlFor="input-soc">Soil Organic Carbon (SOC %)</label>
        <input
          id="input-soc"
          type="text"
          className="field-input"
          placeholder="e.g. 0.3"
          value={structuredInput.soil_organic_carbon ?? ""}
          disabled={disabled}
          onChange={(e) => updateField("soil_organic_carbon", e.target.value)}
        />
      </div>

      <div className="field-group">
        <label htmlFor="input-rainfall">Rainfall (mm/year or low/high)</label>
        <input
          id="input-rainfall"
          type="text"
          className="field-input"
          placeholder="e.g. 220, low, 650"
          value={structuredInput.rainfall ?? ""}
          disabled={disabled}
          onChange={(e) => updateField("rainfall", e.target.value)}
        />
      </div>

      <div className="field-group">
        <label htmlFor="input-crop">Primary Crop</label>
        <input
          id="input-crop"
          type="text"
          className="field-input"
          placeholder="e.g. wheat, citrus"
          value={structuredInput.crop || ""}
          disabled={disabled}
          onChange={(e) => updateField("crop", e.target.value)}
        />
      </div>

      <div className="field-group">
        <label htmlFor="input-landuse">Land Use / Cover</label>
        <input
          id="input-landuse"
          type="text"
          className="field-input"
          placeholder="e.g. monoculture, cropland"
          value={structuredInput.land_use || ""}
          disabled={disabled}
          onChange={(e) => updateField("land_use", e.target.value)}
        />
      </div>
    </div>
  );
};
