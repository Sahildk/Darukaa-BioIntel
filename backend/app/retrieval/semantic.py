"""Semantic retrieval engine with pluggable embedding architecture."""
import math
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Set, Tuple
import numpy as np

from app.knowledge.indexer import InvertedIndex, tokenize
from app.knowledge.store import KnowledgeStore


class BaseSemanticEmbedder(ABC):
    """Abstract base class for pluggable semantic embedding providers."""

    @abstractmethod
    def embed_text(self, text: str) -> np.ndarray:
        """Returns a 1D normalized float vector for the input text."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Returns a 2D matrix of shape (n_texts, dim) with normalized rows."""
        pass


class LocalDenseEmbedder(BaseSemanticEmbedder):
    """
    Lightweight, deterministic local semantic vector space embedder.
    Computes sublinear TF-IDF weighted semantic embeddings over the corpus vocabulary
    with L2-normalization, enabling cosine similarity without external dependencies.
    """

    def __init__(self, index: InvertedIndex):
        self.vocab = sorted(list(index.doc_freqs.keys()))
        self.term_to_idx = {t: i for i, t in enumerate(self.vocab)}
        self.dim = len(self.vocab)
        self.n_docs = max(index.num_docs, 1)

        # Precompute smooth IDF weights
        self.idf = np.zeros(self.dim, dtype=np.float32)
        for term, idx in self.term_to_idx.items():
            df = index.doc_freqs.get(term, 1)
            self.idf[idx] = math.log((self.n_docs + 1.0) / (df + 1.0)) + 1.0

    def embed_text(self, text: str) -> np.ndarray:
        tokens = tokenize(text)
        vec = np.zeros(self.dim, dtype=np.float32)
        if not tokens:
            return vec

        for t in tokens:
            if t in self.term_to_idx:
                idx = self.term_to_idx[t]
                # Sublinear term frequency scaling: 1 + log(tf)
                vec[idx] += 1.0

        nonzero = vec > 0
        vec[nonzero] = (1.0 + np.log(vec[nonzero])) * self.idf[nonzero]

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        return np.vstack([self.embed_text(t) for t in texts])


class SemanticRetriever:
    """Manages dense semantic search over indexed corpus chunks."""

    def __init__(self, store: KnowledgeStore, index: InvertedIndex, embedder: Optional[BaseSemanticEmbedder] = None):
        self.store = store
        self.embedder = embedder or LocalDenseEmbedder(index)
        self._build_chunk_matrix()

    def _build_chunk_matrix(self) -> None:
        """Embeds and caches all chunks currently in the KnowledgeStore."""
        chunks = self.store.list_all_chunks()
        self.chunk_ids: List[str] = [c["chunk_id"] for c in chunks]
        texts = [f"{c['section_title']}. {c['text']}" for c in chunks]

        if texts:
            self.matrix = self.embedder.embed_batch(texts)  # Shape (n_chunks, dim)
        else:
            self.matrix = np.empty((0, getattr(self.embedder, "dim", 0)), dtype=np.float32)

    def score(
        self,
        query: str,
        candidate_chunk_ids: Optional[Set[str]] = None,
    ) -> List[Tuple[str, float]]:
        """
        Computes cosine similarity between query and all candidate chunks.
        Returns (chunk_id, similarity_score) sorted descending.
        """
        if not self.chunk_ids:
            return []

        q_vec = self.embedder.embed_text(query)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []

        # Cosine similarity is dot product because rows and q_vec are L2-normalized
        sims = np.dot(self.matrix, q_vec)

        results: List[Tuple[str, float]] = []
        for cid, sim in zip(self.chunk_ids, sims):
            if candidate_chunk_ids is not None and cid not in candidate_chunk_ids:
                continue
            if sim > 0.0001:
                results.append((cid, float(sim)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results
