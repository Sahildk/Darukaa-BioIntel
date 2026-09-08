"""Evidence resolution layer connecting evidence IDs back to the knowledge store."""
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.knowledge.store import KnowledgeStore, REPO_ROOT
from app.schemas.evidence import EvidenceItem


class EvidenceResolver:
    """
    Resolves evidence IDs (chunk IDs) back to the curated knowledge store,
    preserving the complete scientific traceability chain:
    Recommendation -> Evidence ID -> Chunk -> Source Metadata -> URL / DOI.
    """

    def __init__(self, store: Optional[KnowledgeStore] = None):
        if store:
            self.store = store
        else:
            db_path = REPO_ROOT / "data/knowledge.db"
            self.store = KnowledgeStore(db_path=db_path)

    def resolve_evidence_items(self, evidence_ids: List[str]) -> List[EvidenceItem]:
        """
        Resolves a list of chunk IDs into contract-compliant EvidenceItem models.
        Preserves source identity, publication metadata, URL, and DOI.
        """
        items: List[EvidenceItem] = []
        seen: set = set()

        for eid in evidence_ids:
            if eid in seen:
                continue
            seen.add(eid)

            chunk = self.store.get_chunk(eid)
            if not chunk:
                continue

            item = EvidenceItem(
                evidence_id=chunk["chunk_id"],
                source_id=chunk["source_id"],
                title=chunk["title"],
                publisher=chunk["publisher"],
                year=chunk.get("year"),
                excerpt=chunk["text"],
                source_url=chunk.get("source_url"),
                doi=chunk.get("doi"),
                relevance_score=None,
            )
            items.append(item)

        return items

    def get_chunk_records(self, evidence_ids: List[str]) -> List[Dict[str, Any]]:
        """Retrieves raw chunk records with structured variables, topics, and key metrics."""
        records: List[Dict[str, Any]] = []
        for eid in evidence_ids:
            chunk = self.store.get_chunk(eid)
            if chunk:
                records.append(chunk)
        return records

    def verify_evidence_exists(self, evidence_id: str) -> bool:
        """Returns True if the evidence ID exists as a verified chunk in the knowledge store."""
        return self.store.get_chunk(evidence_id) is not None
