"""Phase 3 tests for document chunking, indexing, and ingestion pipeline."""
import json
from pathlib import Path
import pytest

from app.knowledge.chunker import CorpusChunk, DocumentChunker
from app.knowledge.indexer import IngestionPipeline, InvertedIndex, tokenize
from app.knowledge.manifest import CorpusSource, load_manifest
from app.knowledge.store import KnowledgeStore, REPO_ROOT

MANIFEST_PATH = REPO_ROOT / "data/corpus_manifest.json"
CORPUS_DIR = REPO_ROOT / "data/corpus"


def test_chunker_deterministic_ids_and_hashes():
    """Verify that chunk IDs and content hashes are strictly deterministic and reproducible."""
    source = CorpusSource(
        source_id="SRC-TEST-001",
        title="Test Scientific Document",
        publisher="Test Institute",
        year=2021,
        topic="soil_health",
        source_type="report",
        source_url="https://example.org/doc",
        variables=["soil_organic_carbon", "soil_moisture"],
        interventions=["cover_cropping"],
        geography=["semi-arid"],
        rel_path="soil/test.json",
        summary="A test summary of adequate length for validation constraints.",
    )

    doc_data = {
        "sections": [
            {
                "section_title": "First Findings",
                "text": "Cover crops increase soil organic carbon by 15% over 2 years.",
                "key_metrics": ["soil_organic_carbon"],
            },
            {
                "section_title": "Second Findings",
                "text": "Mulching reduces evaporative losses by 25%.",
                "key_metrics": ["soil_moisture"],
            },
        ]
    }

    chunks_run1 = DocumentChunker.chunk_document(source, doc_data)
    chunks_run2 = DocumentChunker.chunk_document(source, doc_data)

    assert len(chunks_run1) == 2
    assert chunks_run1[0].chunk_id == "CHK-SRC-TEST-001-001"
    assert chunks_run1[1].chunk_id == "CHK-SRC-TEST-001-002"

    # Verify run 1 and run 2 produce identical IDs, hashes, and text
    for c1, c2 in zip(chunks_run1, chunks_run2):
        assert c1.chunk_id == c2.chunk_id
        assert c1.content_hash == c2.content_hash
        assert c1.text == c2.text
        assert c1.source_id == "SRC-TEST-001"


def test_text_normalization_preserves_scientific_notations():
    """Verify normalization cleans whitespace and unicode without mutating numbers, %, or chemical terms."""
    raw = "  Legume cover   crops yield   a 15.5% increase in SOC; pH was 6.8 (±0.2)  \n\n\nunder CO2 fluxes.  "
    normalized = DocumentChunker.normalize_text(raw)
    assert normalized == "Legume cover crops yield a 15.5% increase in SOC; pH was 6.8 (±0.2)\n\nunder CO2 fluxes."
    assert "15.5%" in normalized
    assert "6.8" in normalized
    assert "CO2" in normalized


def test_chunker_handles_empty_or_malformed_sections():
    """Verify that empty or whitespace-only sections are skipped cleanly without crashing."""
    source = CorpusSource(
        source_id="SRC-TEST-002",
        title="Empty Sections Document",
        publisher="Test Publisher",
        year=2022,
        topic="climate",
        source_type="paper",
        source_url="https://example.org/test2",
        variables=["rainfall"],
        rel_path="climate/test2.json",
        summary="A fallback summary that contains sufficient words for testing.",
    )

    # Empty sections list should fall back to summary
    chunks_empty = DocumentChunker.chunk_document(source, {"sections": []})
    assert len(chunks_empty) == 1
    assert chunks_empty[0].section_title == "Summary"
    assert "fallback summary" in chunks_empty[0].text

    # Section with only whitespace should be discarded
    chunks_whitespace = DocumentChunker.chunk_document(source, {
        "sections": [
            {"section_title": "Blank", "text": "   \n\t  "},
            {"section_title": "Real Section", "text": "Real content here."},
        ]
    })
    assert len(chunks_whitespace) == 1
    assert chunks_whitespace[0].section_title == "Real Section"


def test_ingestion_pipeline_execution(tmp_path):
    """Verify IngestionPipeline loads all manifest sources, produces chunks, and builds index."""
    test_db = tmp_path / "test_knowledge.db"
    test_index = tmp_path / "test_index.json"

    pipeline = IngestionPipeline(
        manifest_path=MANIFEST_PATH,
        corpus_dir=CORPUS_DIR,
        db_path=test_db,
        index_path=test_index,
    )

    report = pipeline.run()

    # 1. All manifest sources ingested
    assert report.total_sources == 10
    assert report.total_chunks >= 20, "10 sources each with 2 sections should produce >= 20 chunks"
    assert report.vocabulary_size > 50

    # 2. Verify SQLite database contains sources and chunks
    store = KnowledgeStore(db_path=test_db)
    assert store.get_chunk_count() == report.total_chunks

    all_chunks = store.list_all_chunks()
    assert len(all_chunks) == report.total_chunks

    # 3. Check every chunk retains source_id and full metadata
    for c in all_chunks:
        assert c["chunk_id"].startswith("CHK-SRC-")
        assert c["source_id"].startswith("SRC-")
        assert c["title"]
        assert c["publisher"]
        assert c["topic"] in ["soil_health", "land_use", "biodiversity", "climate", "human_impact"]
        assert c["source_url"].startswith("http")
        assert len(c["variables"]) >= 1
        assert len(c["text"]) > 20

    # 4. Check no orphaned chunks (foreign key integrity)
    all_source_ids = set(report.source_ids)
    for c in all_chunks:
        assert c["source_id"] in all_source_ids

    # 5. Verify InvertedIndex structure was saved and can be reloaded
    assert test_index.exists()
    loaded_index = InvertedIndex.load_from_file(test_index)
    assert loaded_index.num_docs == report.total_chunks
    assert "soil_organic_carbon" in loaded_index.variable_index
    assert "rainfall" in loaded_index.variable_index
    assert len(loaded_index.doc_lengths) == report.total_chunks


def test_ingestion_idempotence(tmp_path):
    """Verify that executing ingestion twice on the same corpus produces identical results."""
    test_db = tmp_path / "idempotent.db"
    test_index = tmp_path / "idempotent.json"

    pipeline = IngestionPipeline(
        manifest_path=MANIFEST_PATH,
        corpus_dir=CORPUS_DIR,
        db_path=test_db,
        index_path=test_index,
    )

    report1 = pipeline.run()
    report2 = pipeline.run()

    # Exact equality across runs
    assert report1.total_sources == report2.total_sources
    assert report1.total_chunks == report2.total_chunks
    assert report1.total_tokens == report2.total_tokens
    assert report1.vocabulary_size == report2.vocabulary_size
    assert report1.chunk_ids == report2.chunk_ids
    assert report1.source_ids == report2.source_ids


def test_provenance_traceability_chain(tmp_path):
    """Verify the mapping: chunk_id -> source_id -> document -> source metadata."""
    test_db = tmp_path / "traceability.db"
    test_index = tmp_path / "traceability.json"

    pipeline = IngestionPipeline(
        manifest_path=MANIFEST_PATH,
        corpus_dir=CORPUS_DIR,
        db_path=test_db,
        index_path=test_index,
    )
    pipeline.run()

    store = KnowledgeStore(db_path=test_db)
    chunk = store.get_chunk("CHK-SRC-FAO-2020-RECARB-001")
    assert chunk is not None
    assert chunk["source_id"] == "SRC-FAO-2020-RECARB"

    source = store.get_source(chunk["source_id"])
    assert source is not None
    assert source["title"] == "Recarbonizing Global Soils: A Technical Manual of Recommended Management Practices"
    assert source["publisher"] == "Food and Agriculture Organization of the United Nations (FAO)"
    assert source["doi"] == "10.4060/ca9668en"
    assert "https://www.fao.org" in source["source_url"]


def test_index_can_be_rebuilt_from_corpus(tmp_path):
    """Verify that if the index file is deleted, it can be cleanly rebuilt from corpus."""
    test_db = tmp_path / "rebuild.db"
    test_index = tmp_path / "rebuild.json"

    pipeline = IngestionPipeline(
        manifest_path=MANIFEST_PATH,
        corpus_dir=CORPUS_DIR,
        db_path=test_db,
        index_path=test_index,
    )
    pipeline.run()
    assert test_index.exists()

    # Delete index file
    test_index.unlink()
    assert not test_index.exists()

    # Rebuild
    pipeline.run()
    assert test_index.exists()
    rebuilt_index = InvertedIndex.load_from_file(test_index)
    assert rebuilt_index.num_docs >= 20
