"""SQLite knowledge storage layer for curated corpus sources and structured records."""
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from .manifest import CorpusManifest, CorpusSource, load_manifest


REPO_ROOT = Path(__file__).resolve().parents[3]


class KnowledgeStore:
    """Manages persistent SQLite storage of scientific sources and structured environmental records."""

    def __init__(self, db_path: str | Path = "data/knowledge.db"):
        path = Path(db_path)
        if not path.is_absolute():
            self.db_path = REPO_ROOT / path
        else:
            self.db_path = path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self) -> None:
        """Creates the relational tables for sources, documents, and environmental records."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    source_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    publisher TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    topic TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    doi TEXT,
                    geography TEXT NOT NULL,       -- JSON array of strings
                    variables TEXT NOT NULL,       -- JSON array of strings
                    interventions TEXT NOT NULL,   -- JSON array of strings
                    rel_path TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    key_findings TEXT NOT NULL     -- JSON array of strings
                );

                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    sections_json TEXT NOT NULL,   -- JSON serialized sections
                    char_count INTEGER NOT NULL,
                    FOREIGN KEY (source_id) REFERENCES sources (source_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS environmental_records (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    ecosystem TEXT,
                    condition_text TEXT,
                    FOREIGN KEY (source_id) REFERENCES sources (source_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    publisher TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    topic TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    doi TEXT,
                    geography TEXT NOT NULL,       -- JSON array
                    variables TEXT NOT NULL,       -- JSON array
                    interventions TEXT NOT NULL,   -- JSON array
                    section_title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    key_metrics TEXT NOT NULL,     -- JSON array
                    token_count INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    FOREIGN KEY (source_id) REFERENCES sources (source_id) ON DELETE CASCADE
                );
                """
            )

    def load_manifest_and_documents(
        self,
        manifest_path: str | Path = "data/corpus_manifest.json",
        corpus_dir: str | Path = "data/corpus",
    ) -> int:
        """Loads and persists all sources from manifest into SQLite."""
        self.init_db()
        m_path = Path(manifest_path)
        if not m_path.is_absolute():
            m_path = REPO_ROOT / m_path

        c_base = Path(corpus_dir)
        if not c_base.is_absolute():
            c_base = REPO_ROOT / c_base

        manifest: CorpusManifest = load_manifest(m_path)

        with self._get_connection() as conn:
            for source in manifest.sources:
                # Insert or replace source
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sources (
                        source_id, title, publisher, year, topic, source_type,
                        source_url, doi, geography, variables, interventions,
                        rel_path, summary, key_findings
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source.source_id,
                        source.title,
                        source.publisher,
                        source.year,
                        source.topic,
                        source.source_type,
                        source.source_url,
                        source.doi,
                        json.dumps(source.geography),
                        json.dumps(source.variables),
                        json.dumps(source.interventions),
                        source.rel_path,
                        source.summary,
                        json.dumps(source.key_findings),
                    ),
                )

                # Load associated document content if available
                doc_path = c_base / source.rel_path
                if doc_path.exists():
                    with open(doc_path, "r", encoding="utf-8") as f:
                        doc_data = json.load(f)
                    sections = doc_data.get("sections", [])
                    total_chars = sum(len(s.get("text", "")) for s in sections)
                    
                    doc_id = f"DOC-{source.source_id}"
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO documents (
                            doc_id, source_id, file_path, sections_json, char_count
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            doc_id,
                            source.source_id,
                            str(doc_path),
                            json.dumps(sections),
                            total_chars,
                        ),
                    )

            conn.commit()

        return len(manifest.sources)

    def get_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a source record by its unique source_id."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sources WHERE source_id = ?", (source_id,)
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["geography"] = json.loads(result["geography"])
            result["variables"] = json.loads(result["variables"])
            result["interventions"] = json.loads(result["interventions"])
            result["key_findings"] = json.loads(result["key_findings"])
            return result

    def list_sources(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists sources, optionally filtered by environmental topic."""
        with self._get_connection() as conn:
            if topic:
                rows = conn.execute(
                    "SELECT * FROM sources WHERE topic = ? ORDER BY year DESC", (topic,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sources ORDER BY year DESC"
                ).fetchall()

            sources = []
            for row in rows:
                item = dict(row)
                item["geography"] = json.loads(item["geography"])
                item["variables"] = json.loads(item["variables"])
                item["interventions"] = json.loads(item["interventions"])
                item["key_findings"] = json.loads(item["key_findings"])
                sources.append(item)
            return sources

    def get_sources_for_variables(self, variables: List[str]) -> List[Dict[str, Any]]:
        """Finds sources whose indexed variables intersect with the requested list."""
        all_sources = self.list_sources()
        target_set = {v.lower() for v in variables}
        matched = []
        for s in all_sources:
            s_vars = {v.lower() for v in s["variables"]}
            if target_set.intersection(s_vars):
                matched.append(s)
        return matched

    def save_chunks(self, chunks: List[Any]) -> int:
        """Persists a list of CorpusChunk objects into the SQLite chunks table."""
        self.init_db()
        with self._get_connection() as conn:
            for c in chunks:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO chunks (
                        chunk_id, source_id, title, publisher, year, topic,
                        source_type, source_url, doi, geography, variables,
                        interventions, section_title, text, key_metrics,
                        token_count, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        c.chunk_id,
                        c.source_id,
                        c.title,
                        c.publisher,
                        c.year,
                        c.topic,
                        c.source_type,
                        c.source_url,
                        c.doi,
                        json.dumps(c.geography),
                        json.dumps(c.variables),
                        json.dumps(c.interventions),
                        c.section_title,
                        c.text,
                        json.dumps(c.key_metrics),
                        c.token_count,
                        c.content_hash,
                    ),
                )
            conn.commit()
        return len(chunks)

    def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single chunk by chunk_id."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,)
            ).fetchone()
            if not row:
                return None
            item = dict(row)
            item["geography"] = json.loads(item["geography"])
            item["variables"] = json.loads(item["variables"])
            item["interventions"] = json.loads(item["interventions"])
            item["key_metrics"] = json.loads(item["key_metrics"])
            return item

    def get_chunks_for_source(self, source_id: str) -> List[Dict[str, Any]]:
        """Retrieves all chunks belonging to a given source_id."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM chunks WHERE source_id = ? ORDER BY chunk_id ASC", (source_id,)
            ).fetchall()
            chunks = []
            for row in rows:
                item = dict(row)
                item["geography"] = json.loads(item["geography"])
                item["variables"] = json.loads(item["variables"])
                item["interventions"] = json.loads(item["interventions"])
                item["key_metrics"] = json.loads(item["key_metrics"])
                chunks.append(item)
            return chunks

    def list_all_chunks(self) -> List[Dict[str, Any]]:
        """Lists all chunks currently indexed in SQLite."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM chunks ORDER BY chunk_id ASC"
            ).fetchall()
            chunks = []
            for row in rows:
                item = dict(row)
                item["geography"] = json.loads(item["geography"])
                item["variables"] = json.loads(item["variables"])
                item["interventions"] = json.loads(item["interventions"])
                item["key_metrics"] = json.loads(item["key_metrics"])
                chunks.append(item)
            return chunks

    def get_chunk_count(self) -> int:
        """Returns the total number of chunks in the database."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM chunks").fetchone()
            return row["cnt"] if row else 0

