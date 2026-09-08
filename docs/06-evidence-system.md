# 06 — Evidence System

## Goal

Make every recommendation traceable to the knowledge retrieved by the system.

## Evidence Chain

```text
Environmental Variables
        |
        v
Retrieved Sources
        |
        v
Scientific Relationships
        |
        v
Recommendation
        |
        v
Impacted Metrics + Time Horizon
```

## Evidence Record

```json
{
  "evidence_id": "string",
  "source_id": "string",
  "source_title": "string",
  "publisher": "string",
  "excerpt": "string",
  "relevance": "string",
  "supports": ["string"]
}
```

## Recommendation Record

```json
{
  "action": "string",
  "why": "string",
  "impacted_metrics": ["string"],
  "time_horizon": "short|medium|long",
  "evidence_ids": ["string"],
  "confidence": null
}
```

## Evidence Validation

Before displaying a recommendation:
1. Verify that every cited evidence ID exists.
2. Verify that the cited source was actually retrieved.
3. Verify that the recommendation claim is supported by the retrieved excerpt/source context.
4. Reject or revise unsupported quantitative claims.
5. If support is insufficient, state the limitation.

## User-Facing Evidence

The UI should show concise evidence information such as:
- source title
- publisher
- relevant excerpt or summary
- why the source matters

Do not overwhelm the user with raw retrieval internals.

## Evidence Trace

The system should retain enough information to answer:

- Which environmental variables led to this recommendation?
- Which sources were retrieved?
- Which source supports the intervention?
- Which source supports a quantitative claim?
- Which metrics are expected to be affected?

## Citation Integrity

Never generate a citation solely because a source name sounds plausible. Citations must map to real indexed source records.
