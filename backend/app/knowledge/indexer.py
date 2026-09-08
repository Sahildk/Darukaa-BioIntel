"""Indexing engine and ingestion pipeline for hybrid scientific retrieval."""
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from .chunker import CorpusChunk, DocumentChunker
from .manifest import CorpusManifest, load_manifest
from .store import KnowledgeStore, REPO_ROOT

# Standard English + scientific stop words to filter out of the lexical index
STOP_WORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its",
    "itself", "let's", "me", "more", "most", "my", "myself", "no", "nor", "not",
    "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours",
    "ourselves", "out", "over", "own", "same", "she", "should", "so", "some",
    "such", "than", "that", "the", "their", "theirs", "them", "themselves", "then",
    "there", "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "with", "would", "you", "your", "yours", "yourself",
}


def tokenize(text: str) -> List[str]:
    """Extracts lowercase tokens, preserving alphanumeric symbols, percentages, and hyphenated terms."""
    tokens = re.findall(r"\b[a-z0-9]+(?:-[a-z0-9]+)*\b|(?:\d+(?:\.\d+)?%)", text.lower())
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


class InvertedIndex(BaseModel):
    """Pre-computed BM25 and metadata inverted index structures for hybrid retrieval."""
    num_docs: int = 0
    avg_doc_len: float = 0.0
    doc_lengths: Dict[str, int] = Field(default_factory=dict)
    doc_freqs: Dict[str, int] = Field(default_factory=dict)
    term_freqs: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    
    # Metadata inverted indexes
    variable_index: Dict[str, List[str]] = Field(default_factory=dict)
    intervention_index: Dict[str, List[str]] = Field(default_factory=dict)
    topic_index: Dict[str, List[str]] = Field(default_factory=dict)
    source_index: Dict[str, List[str]] = Field(default_factory=dict)

    def save_to_file(self, file_path: str | Path) -> None:
        """Serializes index to a JSON file."""
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2)

    @classmethod
    def load_from_file(cls, file_path: str | Path) -> "InvertedIndex":
        """Loads serialized index from JSON file."""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Index file not found: {p}")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)


class IngestionReport(BaseModel):
    """Summary metrics of an ingestion and indexing execution."""
    total_sources: int
    total_chunks: int
    total_tokens: int
    vocabulary_size: int
    source_ids: List[str]
    chunk_ids: List[str]


class IngestionPipeline:
    """Orchestrates deterministic ingestion: reading, chunking, persisting, and indexing."""

    def __init__(
        self,
        manifest_path: str | Path = "data/corpus_manifest.json",
        corpus_dir: str | Path = "data/corpus",
        db_path: str | Path = "data/knowledge.db",
        index_path: str | Path = "data/lexical_index.json",
    ):
        self.manifest_path = Path(manifest_path) if Path(manifest_path).is_absolute() else REPO_ROOT / manifest_path
        self.corpus_dir = Path(corpus_dir) if Path(corpus_dir).is_absolute() else REPO_ROOT / corpus_dir
        self.db_path = Path(db_path) if Path(db_path).is_absolute() else REPO_ROOT / db_path
        self.index_path = Path(index_path) if Path(index_path).is_absolute() else REPO_ROOT / index_path
        self.store = KnowledgeStore(db_path=self.db_path)

    def run(self) -> IngestionReport:
        """
        Executes the complete deterministic ingestion and indexing pipeline:
        1. Validates and loads corpus manifest.
        2. Ingests all sources into SQLite storage.
        3. Parses document sections into normalized CorpusChunks with deterministic IDs.
        4. Persists chunks into SQLite `chunks` table.
        5. Computes BM25 frequencies and metadata inverted lists.
        6. Serializes InvertedIndex to disk.
        """
        manifest: CorpusManifest = load_manifest(self.manifest_path)
        
        # Load sources & document records into SQLite
        self.store.load_manifest_and_documents(
            manifest_path=self.manifest_path,
            corpus_dir=self.corpus_dir,
        )

        all_chunks: List[CorpusChunk] = []
        for source in manifest.sources:
            doc_path = self.corpus_dir / source.rel_path
            if not doc_path.exists():
                raise FileNotFoundError(f"Document file missing for source {source.source_id}: {doc_path}")

            with open(doc_path, "r", encoding="utf-8") as f:
                doc_data = json.load(f)

            source_chunks = DocumentChunker.chunk_document(source, doc_data)
            all_chunks.extend(source_chunks)

        # Persist chunks to SQLite
        self.store.save_chunks(all_chunks)

        # Build InvertedIndex
        index = self._build_inverted_index(all_chunks)
        index.save_to_file(self.index_path)

        source_ids = [s.source_id for s in manifest.sources]
        chunk_ids = [c.chunk_id for c in all_chunks]
        total_tokens = sum(c.token_count for c in all_chunks)

        return IngestionReport(
            total_sources=len(source_ids),
            total_chunks=len(chunk_ids),
            total_tokens=total_tokens,
            vocabulary_size=len(index.doc_freqs),
            source_ids=source_ids,
            chunk_ids=chunk_ids,
        )

    def _build_inverted_index(self, chunks: List[CorpusChunk]) -> InvertedIndex:
        """Builds term frequency, document frequency, and metadata inverted index structures."""
        doc_lengths: Dict[str, int] = {}
        doc_freqs: Dict[str, int] = Counter()
        term_freqs: Dict[str, Dict[str, int]] = {}

        variable_index: Dict[str, List[str]] = {}
        intervention_index: Dict[str, List[str]] = {}
        topic_index: Dict[str, List[str]] = {}
        source_index: Dict[str, List[str]] = {}

        total_length = 0

        for chunk in chunks:
            cid = chunk.chunk_id
            tokens = tokenize(chunk.text + " " + chunk.section_title)
            length = len(tokens)
            doc_lengths[cid] = length
            total_length += length

            tf = Counter(tokens)
            term_freqs[cid] = dict(tf)

            for term in tf.keys():
                doc_freqs[term] += 1

            # Metadata inverted mapping
            for var in chunk.variables:
                var_key = var.lower().strip()
                variable_index.setdefault(var_key, []).append(cid)

            for interv in chunk.interventions:
                interv_key = interv.lower().strip()
                intervention_index.setdefault(interv_key, []).append(cid)

            topic_key = chunk.topic.lower().strip()
            topic_index.setdefault(topic_key, []).append(cid)

            source_index.setdefault(chunk.source_id, []).append(cid)

        num_docs = len(chunks)
        avg_doc_len = (total_length / num_docs) if num_docs > 0 else 0.0

        return InvertedIndex(
            num_docs=num_docs,
            avg_doc_len=avg_doc_len,
            doc_lengths=doc_lengths,
            doc_freqs=dict(doc_freqs),
            term_freqs=term_freqs,
            variable_index=variable_index,
            intervention_index=intervention_index,
            topic_index=topic_index,
            source_index=source_index,
        )
