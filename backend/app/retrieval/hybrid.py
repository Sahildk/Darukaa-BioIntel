"""Hybrid retrieval orchestrator combining BM25, semantic search, and metadata filtering via RRF."""
from typing import Any, Dict, List, Literal, Optional, Set
from pydantic import BaseModel, Field

from app.knowledge.indexer import InvertedIndex
from app.knowledge.store import KnowledgeStore
from .bm25 import BM25Retriever
from .semantic import BaseSemanticEmbedder, SemanticRetriever


class MetadataFilter(BaseModel):
    """Metadata constraints for filtering candidate chunks before or during scoring."""
    topics: Optional[List[str]] = None
    variables: Optional[List[str]] = None
    interventions: Optional[List[str]] = None
    source_ids: Optional[List[str]] = None
    geographies: Optional[List[str]] = None

    def apply(self, index: InvertedIndex, store: KnowledgeStore) -> Set[str]:
        """Returns the set of chunk IDs that satisfy all active filter criteria."""
        all_chunks = store.list_all_chunks()
        candidate_ids = {c["chunk_id"] for c in all_chunks}

        if self.source_ids:
            target_sources = {s.strip() for s in self.source_ids}
            candidate_ids = {c["chunk_id"] for c in all_chunks if c["source_id"] in target_sources}

        if self.topics:
            target_topics = {t.lower().strip() for t in self.topics}
            candidate_ids = {
                cid for cid in candidate_ids
                if any(cid in index.topic_index.get(t, []) for t in target_topics)
            }

        if self.variables:
            target_vars = {v.lower().strip() for v in self.variables}
            candidate_ids = {
                cid for cid in candidate_ids
                if any(cid in index.variable_index.get(v, []) for v in target_vars)
            }

        if self.interventions:
            target_intervs = {i.lower().strip() for i in self.interventions}
            candidate_ids = {
                cid for cid in candidate_ids
                if any(cid in index.intervention_index.get(i, []) for i in target_intervs)
            }

        if self.geographies:
            target_geos = {g.lower().strip() for g in self.geographies}
            geo_chunk_ids: Set[str] = set()
            for c in all_chunks:
                c_geos = {g.lower().strip() for g in c.get("geography", [])}
                if target_geos.intersection(c_geos):
                    geo_chunk_ids.add(c["chunk_id"])
            candidate_ids = candidate_ids.intersection(geo_chunk_ids)

        return candidate_ids


class ScoredChunk(BaseModel):
    """A retrieved chunk enriched with scoring, ranking, and scientific provenance."""
    chunk_id: str
    source_id: str
    title: str
    publisher: str
    year: int
    topic: str
    source_url: str
    doi: Optional[str] = None
    section_title: str
    text: str
    variables: List[str]
    interventions: List[str]
    score: float
    rank: int
    retrieval_method: Literal["hybrid", "bm25", "semantic"]
    bm25_rank: Optional[int] = None
    semantic_rank: Optional[int] = None
    bm25_score: Optional[float] = None
    semantic_score: Optional[float] = None


class HybridRetriever:
    """Combines BM25 lexical and dense semantic rankings using Reciprocal Rank Fusion (RRF)."""

    def __init__(
        self,
        store: KnowledgeStore,
        index: InvertedIndex,
        embedder: Optional[BaseSemanticEmbedder] = None,
        rrf_k: int = 60,
    ):
        self.store = store
        self.index = index
        self.rrf_k = rrf_k
        self.bm25 = BM25Retriever(index)
        self.semantic = SemanticRetriever(store, index, embedder=embedder)

    def retrieve(
        self,
        query: str,
        filters: Optional[MetadataFilter] = None,
        top_k: int = 5,
        mode: Literal["hybrid", "bm25", "semantic"] = "hybrid",
    ) -> List[ScoredChunk]:
        """
        Executes hybrid retrieval:
        1. Identifies candidate chunk IDs if metadata filters are specified.
        2. Scores candidates via BM25 and/or Semantic embeddings.
        3. Fuses rankings via Reciprocal Rank Fusion (RRF) when mode='hybrid'.
        4. Fetches full provenance records from KnowledgeStore and returns top_k ScoredChunks.
        """
        candidate_ids: Optional[Set[str]] = None
        if filters:
            candidate_ids = filters.apply(self.index, self.store)
            if not candidate_ids:
                return []

        # 1. Lexical BM25 ranking
        bm25_ranked = self.bm25.score(query, candidate_chunk_ids=candidate_ids)
        bm25_rank_map = {cid: rank for rank, (cid, _) in enumerate(bm25_ranked, start=1)}
        bm25_score_map = {cid: score for cid, score in bm25_ranked}

        # 2. Dense Semantic ranking
        semantic_ranked = self.semantic.score(query, candidate_chunk_ids=candidate_ids)
        semantic_rank_map = {cid: rank for rank, (cid, _) in enumerate(semantic_ranked, start=1)}
        semantic_score_map = {cid: score for cid, score in semantic_ranked}

        final_ranked: List[tuple[str, float]] = []

        if mode == "bm25":
            final_ranked = bm25_ranked[:top_k]
        elif mode == "semantic":
            final_ranked = semantic_ranked[:top_k]
        else:
            # Hybrid mode: Reciprocal Rank Fusion (RRF)
            rrf_scores: Dict[str, float] = {}
            all_cids = set(bm25_rank_map.keys()).union(set(semantic_rank_map.keys()))

            for cid in all_cids:
                score = 0.0
                if cid in bm25_rank_map:
                    score += 1.0 / (self.rrf_k + bm25_rank_map[cid])
                if cid in semantic_rank_map:
                    score += 1.0 / (self.rrf_k + semantic_rank_map[cid])
                rrf_scores[cid] = score

            sorted_rrf = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
            final_ranked = sorted_rrf[:top_k]

        # Populate ScoredChunk models with full provenance
        results: List[ScoredChunk] = []
        for rank, (cid, score) in enumerate(final_ranked, start=1):
            raw_chunk = self.store.get_chunk(cid)
            if not raw_chunk:
                continue

            scored_item = ScoredChunk(
                chunk_id=cid,
                source_id=raw_chunk["source_id"],
                title=raw_chunk["title"],
                publisher=raw_chunk["publisher"],
                year=raw_chunk["year"],
                topic=raw_chunk["topic"],
                source_url=raw_chunk["source_url"],
                doi=raw_chunk.get("doi"),
                section_title=raw_chunk["section_title"],
                text=raw_chunk["text"],
                variables=raw_chunk.get("variables", []),
                interventions=raw_chunk.get("interventions", []),
                score=round(score, 6),
                rank=rank,
                retrieval_method=mode,
                bm25_rank=bm25_rank_map.get(cid),
                semantic_rank=semantic_rank_map.get(cid),
                bm25_score=round(bm25_score_map[cid], 4) if cid in bm25_score_map else None,
                semantic_score=round(semantic_score_map[cid], 4) if cid in semantic_score_map else None,
            )
            results.append(scored_item)

        return results
