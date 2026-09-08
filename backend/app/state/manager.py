"""Environmental state manager maintaining multi-turn memory, provenance, and conflict records."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel

from app.knowledge.store import REPO_ROOT
from app.schemas.chat import StructuredInput
from app.schemas.state import (
    BiodiversityState,
    ClimateState,
    EnvironmentalState,
    EnvironmentalValueType,
    EnvironmentalVariable,
    HumanImpactState,
    LandUseState,
    ProvenanceSource,
    SoilState,
    VariableConfidence,
)
from .models import (
    AuthorityLevel,
    ConflictRecord,
    EnvironmentalObservation,
    UpdateResult,
    get_authority_level,
)


def _get_nested_attr(obj: Any, path: str) -> Optional[EnvironmentalVariable]:
    """Navigates dot-separated path (e.g. 'soil.organic_carbon') to retrieve an EnvironmentalVariable."""
    parts = path.split(".")
    curr = obj
    for part in parts:
        if curr is None:
            return None
        curr = getattr(curr, part, None)
    return curr


def _set_nested_attr(obj: Any, path: str, val: Optional[EnvironmentalVariable]) -> None:
    """Navigates dot-separated path and sets the target field."""
    parts = path.split(".")
    curr = obj
    for part in parts[:-1]:
        next_obj = getattr(curr, part, None)
        if next_obj is None:
            raise AttributeError(f"Intermediate path '{part}' is None in '{path}'")
        curr = next_obj
    setattr(curr, parts[-1], val)


VALID_VARIABLE_PATHS: Set[str] = {
    "region",
    "soil.ph",
    "soil.organic_carbon",
    "soil.moisture",
    "land_use.land_cover",
    "land_use.crop",
    "land_use.fragmentation",
    "biodiversity.species_richness",
    "biodiversity.habitat_diversity",
    "biodiversity.pollinator_abundance",
    "climate.temperature",
    "climate.rainfall",
    "human_impact.pollution",
    "human_impact.deforestation",
}


class EnvironmentalStateManager:
    """
    Manages conversation-scoped environmental states with strict provenance,
    deterministic precedence rules, immutable observation history, and explicit conflict tracking.
    """

    def __init__(self, db_path: Optional[str | Path] = None):
        if db_path is None:
            self.db_path = REPO_ROOT / "data/knowledge.db"
        else:
            p = Path(db_path)
            self.db_path = p if p.is_absolute() else REPO_ROOT / p
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        """Initializes conversation state tables."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversation_states (
                    conversation_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS observation_history (
                    observation_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    variable_path TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    unit TEXT,
                    source TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversation_states (conversation_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS state_conflicts (
                    conflict_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    variable_path TEXT NOT NULL,
                    existing_obs_id TEXT NOT NULL,
                    incoming_obs_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    resolved_obs_id TEXT,
                    detected_at TEXT NOT NULL,
                    resolved_at TEXT,
                    explanation TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversation_states (conversation_id) ON DELETE CASCADE
                );
                """
            )

    def get_state(self, conversation_id: str) -> EnvironmentalState:
        """Retrieves current environmental state for a conversation, or initializes a clean one."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT state_json FROM conversation_states WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()

            if row:
                data = json.loads(row["state_json"])
                state = EnvironmentalState.model_validate(data)
            else:
                state = EnvironmentalState()
                self._save_state(conn, conversation_id, state)

        # Hydrate active conflicts and observation history from database tables
        state.active_conflicts = [c.model_dump() for c in self.list_active_conflicts(conversation_id)]
        state.observation_history = [o.model_dump() for o in self.get_observation_history(conversation_id)]
        return state

    def _save_state(self, conn: sqlite3.Connection, conversation_id: str, state: EnvironmentalState) -> None:
        """Serializes and persists state to SQLite without triggering cascade deletes."""
        now_iso = datetime.now(timezone.utc).isoformat()
        # Exclude hydrated lists from primary state JSON to maintain clean normalization
        state_dict = state.model_dump(exclude={"active_conflicts", "observation_history"})
        conn.execute(
            """
            INSERT INTO conversation_states (conversation_id, state_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
            """,
            (conversation_id, json.dumps(state_dict), now_iso),
        )

    def record_observation(
        self,
        conversation_id: str,
        variable_path: str,
        value: EnvironmentalValueType,
        unit: Optional[str] = None,
        source: ProvenanceSource = ProvenanceSource.USER,
        confidence: VariableConfidence = VariableConfidence.EXPLICIT,
        observation_id: Optional[str] = None,
    ) -> UpdateResult:
        """
        Records an environmental observation into the conversation's immutable history
        and updates the active state governed by deterministic provenance precedence.
        """
        if variable_path not in VALID_VARIABLE_PATHS:
            raise ValueError(f"Invalid variable path '{variable_path}'. Must be one of: {sorted(list(VALID_VARIABLE_PATHS))}")

        with self._get_connection() as conn:
            # Ensure conversation state exists
            state_row = conn.execute(
                "SELECT state_json FROM conversation_states WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()

            if state_row:
                state = EnvironmentalState.model_validate(json.loads(state_row["state_json"]))
            else:
                state = EnvironmentalState()
                self._save_state(conn, conversation_id, state)

            # Generate stable deterministic observation ID if not supplied
            if not observation_id:
                obs_count_row = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM observation_history WHERE conversation_id = ? AND variable_path = ?",
                    (conversation_id, variable_path),
                ).fetchone()
                count = (obs_count_row["cnt"] if obs_count_row else 0) + 1
                observation_id = f"OBS-{conversation_id[:6]}-{variable_path.replace('.', '_')}-{count:03d}"

            now_iso = datetime.now(timezone.utc).isoformat()

            # Create immutable observation record
            obs = EnvironmentalObservation(
                observation_id=observation_id,
                variable_path=variable_path,
                value=value,
                unit=unit,
                source=source,
                confidence=confidence,
                timestamp=now_iso,
            )

            # Insert into immutable observation history
            conn.execute(
                """
                INSERT OR REPLACE INTO observation_history (
                    observation_id, conversation_id, variable_path, value_json,
                    unit, source, confidence, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    obs.observation_id,
                    conversation_id,
                    obs.variable_path,
                    json.dumps(obs.value),
                    obs.unit,
                    obs.source.value,
                    obs.confidence.value,
                    obs.timestamp,
                ),
            )

            # Check existing active variable at this path
            current_var = _get_nested_attr(state, variable_path)

            # Case 1: No prior observation exists -> Apply immediately
            if current_var is None:
                _set_nested_attr(state, variable_path, obs.to_variable())
                self._save_state(conn, conversation_id, state)
                conn.commit()
                return UpdateResult(
                    variable_path=variable_path,
                    observation_id=observation_id,
                    status="applied",
                    message="Observation applied to empty state field.",
                )

            # Case 2: Prior observation exists with identical value -> Refresh active reference
            if current_var.value == obs.value:
                # If units match or incoming specifies unit, keep unit
                resolved_unit = obs.unit if obs.unit else current_var.unit
                updated_var = obs.to_variable()
                updated_var.unit = resolved_unit
                _set_nested_attr(state, variable_path, updated_var)
                self._save_state(conn, conversation_id, state)
                conn.commit()
                return UpdateResult(
                    variable_path=variable_path,
                    observation_id=observation_id,
                    status="applied",
                    message="Observation confirmed identical value.",
                )

            # Case 3: Prior observation exists with differing value -> Check authority tiers
            curr_authority = get_authority_level(current_var.source)
            inc_authority = get_authority_level(obs.source)

            # 3a. Higher authority overrides lower authority
            if inc_authority > curr_authority:
                _set_nested_attr(state, variable_path, obs.to_variable())
                self._save_state(conn, conversation_id, state)
                conn.commit()
                return UpdateResult(
                    variable_path=variable_path,
                    observation_id=observation_id,
                    status="applied",
                    message=f"Higher authority '{obs.source.value}' ({inc_authority.name}) overrode '{current_var.source.value}' ({curr_authority.name}).",
                )

            # 3b. Lower authority CANNOT override higher authority
            if inc_authority < curr_authority:
                conn.commit()
                return UpdateResult(
                    variable_path=variable_path,
                    observation_id=observation_id,
                    status="rejected_precedence",
                    message=f"Lower authority '{obs.source.value}' ({inc_authority.name}) cannot overwrite existing '{current_var.source.value}' ({curr_authority.name}). Current fact preserved.",
                )

            # 3c. Equal authority with conflicting values -> Create explicit ConflictRecord
            conf_count_row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM state_conflicts WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            conf_count = (conf_count_row["cnt"] if conf_count_row else 0) + 1
            conflict_id = f"CONF-{conversation_id[:6]}-{variable_path.replace('.', '_')}-{conf_count:03d}"

            existing_obs_id = current_var.observation_id or f"OBS-{conversation_id[:6]}-{variable_path.replace('.', '_')}-prior"

            conflict = ConflictRecord(
                conflict_id=conflict_id,
                variable_path=variable_path,
                existing_observation_id=existing_obs_id,
                incoming_observation_id=observation_id,
                status="unresolved",
                detected_at=now_iso,
                explanation=f"Conflicting equal-authority observations for '{variable_path}': active value '{current_var.value}' ({current_var.source.value}) vs incoming value '{obs.value}' ({obs.source.value}).",
            )

            conn.execute(
                """
                INSERT OR REPLACE INTO state_conflicts (
                    conflict_id, conversation_id, variable_path, existing_obs_id,
                    incoming_obs_id, status, resolved_obs_id, detected_at,
                    resolved_at, explanation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conflict.conflict_id,
                    conversation_id,
                    conflict.variable_path,
                    conflict.existing_observation_id,
                    conflict.incoming_observation_id,
                    conflict.status,
                    conflict.resolved_observation_id,
                    conflict.detected_at,
                    conflict.resolved_at,
                    conflict.explanation,
                ),
            )

            # Preserve existing active value until explicitly resolved by user
            conn.commit()
            return UpdateResult(
                variable_path=variable_path,
                observation_id=observation_id,
                status="conflict_detected",
                message="Conflicting observations of equal authority detected. Preserving current value pending resolution.",
                conflict=conflict,
            )

    def add_observation(
        self,
        conversation_id: str,
        variable_path: str,
        value: EnvironmentalValueType,
        unit: Optional[str] = None,
        source: ProvenanceSource = ProvenanceSource.USER,
        confidence: VariableConfidence = VariableConfidence.EXPLICIT,
        observation_id: Optional[str] = None,
    ) -> UpdateResult:
        """Alias for record_observation to support explicit observation additions."""
        return self.record_observation(
            conversation_id=conversation_id,
            variable_path=variable_path,
            value=value,
            unit=unit,
            source=source,
            confidence=confidence,
            observation_id=observation_id,
        )

    def resolve_conflict(
        self,
        conversation_id: str,
        conflict_id: str,
        selected_observation_id: str,
    ) -> EnvironmentalState:
        """
        Resolves an active conflict by selecting an existing historical observation ID.
        Rejects arbitrary or non-existent observation IDs.
        """
        with self._get_connection() as conn:
            conf_row = conn.execute(
                "SELECT * FROM state_conflicts WHERE conflict_id = ? AND conversation_id = ?",
                (conflict_id, conversation_id),
            ).fetchone()

            if not conf_row:
                raise ValueError(f"Conflict '{conflict_id}' not found in conversation '{conversation_id}'")

            conflict = ConflictRecord(
                conflict_id=conf_row["conflict_id"],
                variable_path=conf_row["variable_path"],
                existing_observation_id=conf_row["existing_obs_id"],
                incoming_observation_id=conf_row["incoming_obs_id"],
                status=conf_row["status"],
                resolved_observation_id=conf_row["resolved_obs_id"],
                detected_at=conf_row["detected_at"],
                resolved_at=conf_row["resolved_at"],
                explanation=conf_row["explanation"],
            )

            # Verify selected_observation_id belongs to the conflict candidates
            valid_ids = {conflict.existing_observation_id, conflict.incoming_observation_id}
            if selected_observation_id not in valid_ids:
                # Also allow any observation recorded in history for this path
                hist_rows = conn.execute(
                    "SELECT observation_id FROM observation_history WHERE conversation_id = ? AND variable_path = ?",
                    (conversation_id, conflict.variable_path),
                ).fetchall()
                all_path_ids = {r["observation_id"] for r in hist_rows}
                if selected_observation_id not in all_path_ids:
                    raise ValueError(
                        f"Invalid selected_observation_id '{selected_observation_id}'. Must be an existing historical observation ID for path '{conflict.variable_path}'"
                    )

            # Retrieve the selected observation from history
            obs_row = conn.execute(
                "SELECT * FROM observation_history WHERE observation_id = ?",
                (selected_observation_id,),
            ).fetchone()

            if not obs_row:
                raise ValueError(f"Observation '{selected_observation_id}' not found in history")

            selected_obs = EnvironmentalObservation(
                observation_id=obs_row["observation_id"],
                variable_path=obs_row["variable_path"],
                value=json.loads(obs_row["value_json"]),
                unit=obs_row["unit"],
                source=ProvenanceSource(obs_row["source"]),
                confidence=VariableConfidence(obs_row["confidence"]),
                timestamp=obs_row["timestamp"],
            )

            # Load current state and set the selected observation
            state_row = conn.execute(
                "SELECT state_json FROM conversation_states WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            state = EnvironmentalState.model_validate(json.loads(state_row["state_json"]))

            _set_nested_attr(state, conflict.variable_path, selected_obs.to_variable())
            self._save_state(conn, conversation_id, state)

            # Mark conflict as resolved
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                UPDATE state_conflicts
                SET status = 'resolved', resolved_obs_id = ?, resolved_at = ?
                WHERE conflict_id = ?
                """,
                (selected_observation_id, now_iso, conflict_id),
            )
            conn.commit()

        return self.get_state(conversation_id)

    def update_from_structured_input(
        self,
        conversation_id: str,
        structured_input: StructuredInput,
    ) -> List[UpdateResult]:
        """
        Ingests structured environmental parameters from a StructuredInput payload,
        treating each as an explicit USER_DIRECT observation with structured provenance.
        """
        results: List[UpdateResult] = []

        mappings = [
            ("region", structured_input.region, None),
            ("soil.organic_carbon", structured_input.soil_organic_carbon, "%" if isinstance(structured_input.soil_organic_carbon, (int, float)) else None),
            ("soil.ph", structured_input.soil_ph, None),
            ("climate.rainfall", structured_input.rainfall, None),
            ("land_use.crop", structured_input.crop, None),
            ("land_use.land_cover", structured_input.land_use, None),
        ]

        for path, val, unit in mappings:
            if val is not None and val != "":
                # Convert numeric string to float if applicable
                parsed_val: EnvironmentalValueType = val
                if isinstance(val, str):
                    try:
                        parsed_val = float(val)
                    except ValueError:
                        parsed_val = val

                res = self.record_observation(
                    conversation_id=conversation_id,
                    variable_path=path,
                    value=parsed_val,
                    unit=unit,
                    source=ProvenanceSource.STRUCTURED_INPUT,
                    confidence=VariableConfidence.EXPLICIT,
                )
                results.append(res)

        return results

    def list_active_conflicts(self, conversation_id: str) -> List[ConflictRecord]:
        """Lists all unresolved conflicts for a conversation."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM state_conflicts WHERE conversation_id = ? AND status = 'unresolved'",
                (conversation_id,),
            ).fetchall()
            return [
                ConflictRecord(
                    conflict_id=r["conflict_id"],
                    variable_path=r["variable_path"],
                    existing_observation_id=r["existing_obs_id"],
                    incoming_observation_id=r["incoming_obs_id"],
                    status=r["status"],
                    resolved_observation_id=r["resolved_obs_id"],
                    detected_at=r["detected_at"],
                    resolved_at=r["resolved_at"],
                    explanation=r["explanation"],
                )
                for r in rows
            ]

    def get_observation_history(
        self,
        conversation_id: str,
        variable_path: Optional[str] = None,
    ) -> List[EnvironmentalObservation]:
        """Returns the chronological observation history for a conversation."""
        with self._get_connection() as conn:
            if variable_path:
                rows = conn.execute(
                    "SELECT * FROM observation_history WHERE conversation_id = ? AND variable_path = ? ORDER BY timestamp ASC",
                    (conversation_id, variable_path),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM observation_history WHERE conversation_id = ? ORDER BY timestamp ASC",
                    (conversation_id,),
                ).fetchall()

            return [
                EnvironmentalObservation(
                    observation_id=r["observation_id"],
                    variable_path=r["variable_path"],
                    value=json.loads(r["value_json"]),
                    unit=r["unit"],
                    source=ProvenanceSource(r["source"]),
                    confidence=VariableConfidence(r["confidence"]),
                    timestamp=r["timestamp"],
                )
                for r in rows
            ]

    def reset_conversation(self, conversation_id: str) -> bool:
        """Completely resets all state, observations, and conflicts for a conversation."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM conversation_states WHERE conversation_id = ?", (conversation_id,))
            conn.commit()
            return True
