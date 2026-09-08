"""Phase 4 tests for hybrid retrieval, BM25, semantic search, and golden benchmark."""
import pytest
from pathlib import Path

from app.knowledge.indexer import InvertedIndex
from app.knowledge.store import KnowledgeStore, REPO_ROOT
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.golden_benchmark import evaluate_retriever_on_golden_set
from app.retrieval.hybrid import HybridRetriever, MetadataFilter
from app.retrieval.semantic import LocalDenseEmbedder, SemanticRetriever

INDEX_PATH = REPO_ROOT / "data/lexical_index.json"
DB_PATH = REPO_ROOT / "data/knowledge.db"


@pytest.fixture(scope="module")
def knowledge_components():
    """Provides pre-loaded KnowledgeStore, InvertedIndex, and HybridRetriever."""
    assert INDEX_PATH.exists(), "Production index data/lexical_index.json must exist"
    assert DB_PATH.exists(), "Production database data/knowledge.db must exist"

    store = KnowledgeStore(db_path=DB_PATH)
    index = InvertedIndex.load_from_file(INDEX_PATH)
    retriever = HybridRetriever(store, index)
    return store, index, retriever


def test_bm25_retrieval(knowledge_components):
    """Verify BM25 produces relevant lexical matches with positive scores."""
    store, index, retriever = knowledge_components
    bm25 = BM25Retriever(index)

    # Query for soil organic carbon and drylands
    results = bm25.score("soil organic carbon drylands legumes")
    assert len(results) > 0

    top_chunk_id, top_score = results[0]
    assert top_score > 0.0
    assert "CHK-SRC-FAO-2020-RECARB" in top_chunk_id or "CHK-SRC-LAL" in top_chunk_id


def test_semantic_retrieval(knowledge_components):
    """Verify SemanticRetriever returns dense similarity scores between 0 and 1."""
    store, index, retriever = knowledge_components
    semantic = SemanticRetriever(store, index)

    results = semantic.score("biodiversity stability and drought resistance")
    assert len(results) > 0

    top_chunk_id, top_score = results[0]
    assert 0.0 < top_score <= 1.0
    assert "CHK-SRC-ISBELL" in top_chunk_id or "CHK-SRC-TAMBURINI" in top_chunk_id


def test_metadata_filtering(knowledge_components):
    """Verify MetadataFilter restricts candidate chunks to specified topics or variables."""
    store, index, retriever = knowledge_components

    # 1. Filter by topic
    soil_filter = MetadataFilter(topics=["soil_health"])
    results = retriever.retrieve("carbon", filters=soil_filter, top_k=5)
    assert len(results) > 0
    for r in results:
        assert r.topic == "soil_health"

    # 2. Filter by environmental variable
    var_filter = MetadataFilter(variables=["pollinator_abundance"])
    results_var = retriever.retrieve("diversity crops", filters=var_filter, top_k=5)
    assert len(results_var) > 0
    for r in results_var:
        assert "pollinator_abundance" in r.variables

    # 3. Filter by source_id
    src_filter = MetadataFilter(source_ids=["SRC-IPCC-2019-SRCCL"])
    results_src = retriever.retrieve("climate land", filters=src_filter, top_k=5)
    assert len(results_src) > 0
    for r in results_src:
        assert r.source_id == "SRC-IPCC-2019-SRCCL"


def test_rrf_hybrid_fusion(knowledge_components):
    """Verify RRF fusion successfully combines BM25 and Semantic rank information."""
    store, index, retriever = knowledge_components
    query = "semi-arid wheat monoculture rainfall deficit"

    hybrid_results = retriever.retrieve(query, top_k=5, mode="hybrid")
    assert len(hybrid_results) > 0

    # Verify every returned ScoredChunk has rank, score, and provenance
    for rank, chunk in enumerate(hybrid_results, start=1):
        assert chunk.rank == rank
        assert chunk.retrieval_method == "hybrid"
        assert chunk.score > 0.0
        assert chunk.chunk_id.startswith("CHK-SRC-")
        assert chunk.source_id.startswith("SRC-")
        assert chunk.source_url.startswith("http")


def test_retrieval_determinism(knowledge_components):
    """Verify identical queries yield strictly identical scores, chunk IDs, and ranks."""
    store, index, retriever = knowledge_components
    query = "agricultural diversification without compromising yield"

    run1 = retriever.retrieve(query, top_k=5)
    run2 = retriever.retrieve(query, top_k=5)

    assert len(run1) == len(run2)
    for c1, c2 in zip(run1, run2):
        assert c1.chunk_id == c2.chunk_id
        assert c1.score == c2.score
        assert c1.rank == c2.rank


def test_provenance_preservation(knowledge_components):
    """Verify chunk_id -> source_id -> document metadata traceability."""
    store, index, retriever = knowledge_components
    query = "recarbonizing dryland soils"

    results = retriever.retrieve(query, top_k=1)
    assert len(results) == 1
    top = results[0]

    # Verify source_id maps to valid record in KnowledgeStore
    source_record = store.get_source(top.source_id)
    assert source_record is not None
    assert source_record["title"] == top.title
    assert source_record["publisher"] == top.publisher
    assert source_record["source_url"] == top.source_url


def test_empty_or_nomatch_queries(knowledge_components):
    """Verify empty or non-matching queries degrade safely to empty lists."""
    store, index, retriever = knowledge_components

    # Empty query
    assert retriever.retrieve("", top_k=5) == []
    assert retriever.retrieve("    ", top_k=5) == []

    # Non-existent vocabulary gibberish
    results = retriever.retrieve("xyznonexistentterm987654321", top_k=5)
    assert len(results) == 0


def test_golden_retrieval_benchmark(knowledge_components):
    """Verify hybrid retrieval achieves high Recall@5 and MRR over the 10 golden benchmark queries."""
    store, index, retriever = knowledge_components

    report = evaluate_retriever_on_golden_set(retriever, top_k=5, mode="hybrid")
    assert report.total_queries == 10

    # Recall@5 and MRR should exceed 0.80 across the 10 canonical queries
    assert report.mean_recall_at_k >= 0.80, f"Expected Recall@5 >= 0.80, got {report.mean_recall_at_k}"
    assert report.mean_reciprocal_rank >= 0.80, f"Expected MRR >= 0.80, got {report.mean_reciprocal_rank}"

    # Verify every query had at least one relevant hit
    for q in report.query_results:
        assert q.hit is True, f"Query {q.query_id} ('{q.query_text}') had zero relevant hits"
        assert q.reciprocal_rank > 0.0
