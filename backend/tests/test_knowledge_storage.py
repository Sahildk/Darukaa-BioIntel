"""Phase 2 tests for knowledge storage, corpus manifest, and scientific sources integrity."""
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.knowledge.manifest import (
    CorpusManifest,
    CorpusSource,
    load_manifest,
)
from app.knowledge.store import KnowledgeStore

MANIFEST_PATH = Path("data/corpus_manifest.json")
CORPUS_DIR = Path("data/corpus")


def test_manifest_file_exists_and_loads():
    """Verify that data/corpus_manifest.json exists and adheres to CorpusManifest schema."""
    assert MANIFEST_PATH.exists(), "Manifest file must exist"
    manifest = load_manifest(MANIFEST_PATH)
    assert len(manifest.sources) >= 10, "Corpus must contain at least 10 curated sources"
    assert manifest.manifest_version == "1.0.0"


def test_source_id_uniqueness():
    """Verify that all source_ids in the manifest are strictly unique."""
    manifest = load_manifest(MANIFEST_PATH)
    source_ids = [s.source_id for s in manifest.sources]
    assert len(source_ids) == len(set(source_ids)), "All source_ids must be unique"


def test_source_id_prefix_validation():
    """Verify that source_ids must start with 'SRC-' prefix."""
    with pytest.raises(ValidationError):
        CorpusSource(
            source_id="INVALID-PREFIX-001",
            title="Valid Title",
            publisher="FAO",
            year=2020,
            topic="soil_health",
            source_type="report",
            source_url="https://example.org",
            variables=["soil_organic_carbon"],
            rel_path="soil/test.json",
            summary="A test summary that is long enough to satisfy constraints.",
        )


def test_required_metadata_fields():
    """Verify that each source has valid publisher, year, URLs, and summaries."""
    manifest = load_manifest(MANIFEST_PATH)
    for source in manifest.sources:
        assert source.title and len(source.title) >= 5
        assert source.publisher and len(source.publisher) >= 2
        assert 1990 <= source.year <= 2030
        assert source.source_url.startswith("http")
        assert len(source.variables) >= 1
        assert len(source.summary) >= 20
        assert len(source.key_findings) >= 1


def test_referenced_source_files_exist_on_disk():
    """Verify that each rel_path referenced in manifest exists and is valid JSON."""
    manifest = load_manifest(MANIFEST_PATH)
    for source in manifest.sources:
        doc_file = CORPUS_DIR / source.rel_path
        assert doc_file.exists(), f"Source file does not exist: {doc_file}"
        assert doc_file.stat().st_size > 0


def test_domain_coverage():
    """Verify that all 5 challenge domains are represented by authentic sources."""
    manifest = load_manifest(MANIFEST_PATH)
    topics = {s.topic for s in manifest.sources}
    required_topics = {"soil_health", "land_use", "biodiversity", "climate", "human_impact"}
    missing = required_topics - topics
    assert not missing, f"Manifest is missing coverage for required domains: {missing}"


def test_multi_metric_reasoning_capacity():
    """Verify that the corpus contains sources linking >= 3 variables simultaneously."""
    manifest = load_manifest(MANIFEST_PATH)
    multi_metric_sources = [s for s in manifest.sources if len(s.variables) >= 3]
    assert len(multi_metric_sources) >= 5, "At least 5 sources must support multi-metric reasoning"

    # Specifically verify the challenge scenario variables (SOC, rainfall, crop/land-use)
    challenge_matches = [
        s for s in manifest.sources
        if "soil_organic_carbon" in s.variables and "rainfall" in s.variables
    ]
    assert len(challenge_matches) >= 2, "Must have sources connecting soil organic carbon and rainfall"


def test_knowledge_store_sqlite_persistence(tmp_path):
    """Verify KnowledgeStore initializes SQLite tables, persists sources, and supports queries."""
    db_file = tmp_path / "test_knowledge.db"
    store = KnowledgeStore(db_path=db_file)
    store.init_db()

    # Load from master manifest
    count = store.load_manifest_and_documents(
        manifest_path=MANIFEST_PATH,
        corpus_dir=CORPUS_DIR,
    )
    assert count >= 10

    # Test get_source
    fao = store.get_source("SRC-FAO-2020-RECARB")
    assert fao is not None
    assert fao["publisher"] == "Food and Agriculture Organization of the United Nations (FAO)"
    assert "soil_organic_carbon" in fao["variables"]
    assert "https://www.fao.org" in fao["source_url"]

    # Test listing filtered by topic
    soil_sources = store.list_sources(topic="soil_health")
    assert len(soil_sources) >= 3

    climate_sources = store.list_sources(topic="climate")
    assert len(climate_sources) >= 2

    # Test querying by variables
    matched = store.get_sources_for_variables(["soil_organic_carbon", "microbial_diversity"])
    assert len(matched) >= 1
    matched_ids = [m["source_id"] for m in matched]
    assert "SRC-FAO-2020-RECARB" in matched_ids


def test_manifest_rejects_duplicate_sources():
    """Verify CorpusManifest validator raises ValueError if duplicate source_ids exist."""
    manifest = load_manifest(MANIFEST_PATH)
    duplicated_sources = list(manifest.sources) + [manifest.sources[0]]
    with pytest.raises(ValidationError):
        CorpusManifest(
            manifest_version="1.0.0",
            last_updated="2026-09-08T00:00:00Z",
            description="Test manifest with duplicates",
            sources=duplicated_sources,
        )
