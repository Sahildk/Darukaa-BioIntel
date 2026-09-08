"""Deterministic chunking and text normalization for scientific corpus documents."""
import hashlib
import re
import unicodedata
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .manifest import CorpusSource


class CorpusChunk(BaseModel):
    """A retrieval-ready chunk retaining complete source provenance."""
    chunk_id: str = Field(..., description="Deterministic ID formatted as CHK-{source_id}-{idx:03d}")
    source_id: str
    title: str
    publisher: str
    year: int
    topic: str
    source_type: str
    source_url: str
    doi: Optional[str] = None
    geography: List[str]
    variables: List[str]
    interventions: List[str]
    section_title: str
    text: str
    key_metrics: List[str] = Field(default_factory=list)
    token_count: int
    content_hash: str


class DocumentChunker:
    """Normalizes document sections into deterministic retrieval chunks without altering scientific content."""

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalizes unicode and whitespace while preserving scientific numbers,
        symbols, percentages, and chemical nomenclature verbatim.
        """
        if not text:
            return ""
        # Normalize unicode to NFKC (compatible decomposition and canonical composition)
        normalized = unicodedata.normalize("NFKC", text)
        # Normalize line endings
        normalized = re.sub(r"\r\n|\r", "\n", normalized)
        # Collapse intra-line whitespace and strip per line
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in normalized.split("\n")]
        # Recombine and collapse multiple empty lines into at most double newlines
        recombined = "\n".join(lines)
        recombined = re.sub(r"\n{3,}", "\n\n", recombined)
        return recombined.strip()

    @classmethod
    def compute_content_hash(cls, text: str) -> str:
        """Computes a SHA-256 hash of normalized text for tamper detection and idempotency."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @classmethod
    def chunk_document(cls, source: CorpusSource, doc_data: Dict[str, Any]) -> List[CorpusChunk]:
        """
        Chunks a parsed document dictionary into deterministic CorpusChunk items.
        
        Preserves complete provenance:
        chunk_id -> source_id -> document -> source metadata
        """
        sections = doc_data.get("sections", [])
        if not sections:
            # Fallback to summary if no explicit sections exist
            summary = source.summary
            if summary:
                sections = [{"section_title": "Summary", "text": summary, "key_metrics": source.variables}]
            else:
                return []

        chunks: List[CorpusChunk] = []
        for idx, sec in enumerate(sections, start=1):
            raw_text = sec.get("text", "")
            norm_text = cls.normalize_text(raw_text)
            if not norm_text:
                continue

            sec_title = cls.normalize_text(sec.get("section_title", f"Section {idx}"))
            key_metrics = sec.get("key_metrics", source.variables)

            # Combine source variables with any section-specific metrics
            combined_variables = list(dict.fromkeys(source.variables + [m for m in key_metrics if m in source.variables]))

            # Deterministic chunk ID
            chunk_id = f"CHK-{source.source_id}-{idx:03d}"
            content_hash = cls.compute_content_hash(norm_text)
            approx_token_count = len(norm_text.split())

            chunk = CorpusChunk(
                chunk_id=chunk_id,
                source_id=source.source_id,
                title=source.title,
                publisher=source.publisher,
                year=source.year,
                topic=source.topic,
                source_type=source.source_type,
                source_url=source.source_url,
                doi=source.doi,
                geography=list(source.geography),
                variables=combined_variables,
                interventions=list(source.interventions),
                section_title=sec_title,
                text=norm_text,
                key_metrics=list(key_metrics),
                token_count=approx_token_count,
                content_hash=content_hash,
            )
            chunks.append(chunk)

        return chunks
