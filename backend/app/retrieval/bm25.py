"""BM25 lexical retrieval engine consuming Phase 3 InvertedIndex."""
import math
from typing import Dict, List, Optional, Set, Tuple

from app.knowledge.indexer import InvertedIndex, tokenize


class BM25Retriever:
    """Computes Okapi BM25 scores directly from pre-computed InvertedIndex statistics."""

    def __init__(self, index: InvertedIndex, k1: float = 1.5, b: float = 0.75):
        self.index = index
        self.k1 = k1
        self.b = b
        self._precompute_idf()

    def _precompute_idf(self) -> None:
        """Precomputes Robertson-Spärck Jones IDF for all vocabulary terms."""
        self.idf: Dict[str, float] = {}
        n_docs = self.index.num_docs
        for term, df in self.index.doc_freqs.items():
            # Standard BM25 IDF formulation
            self.idf[term] = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)

    def score(
        self,
        query: str,
        candidate_chunk_ids: Optional[Set[str]] = None,
    ) -> List[Tuple[str, float]]:
        """
        Calculates BM25 score for all matching chunks.
        
        If candidate_chunk_ids is provided, scores are restricted to that subset
        (used for metadata filtering).
        """
        query_tokens = tokenize(query)
        if not query_tokens or self.index.num_docs == 0:
            return []

        scores: Dict[str, float] = {}
        avg_dl = self.index.avg_doc_len

        for token in query_tokens:
            if token not in self.idf:
                continue

            term_idf = self.idf[token]

            for cid, term_counts in self.index.term_freqs.items():
                if candidate_chunk_ids is not None and cid not in candidate_chunk_ids:
                    continue

                if token in term_counts:
                    tf = term_counts[token]
                    doc_len = self.index.doc_lengths.get(cid, int(avg_dl))
                    denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / avg_dl))
                    term_score = term_idf * (tf * (self.k1 + 1.0)) / denominator
                    scores[cid] = scores.get(cid, 0.0) + term_score

        # Sort descending by score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked
