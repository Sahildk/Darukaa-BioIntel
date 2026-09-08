# 07 — API Contracts

## Principle

Frontend and backend should communicate through explicit, validated contracts.

## POST `/api/chat`

### Request

```json
{
  "conversation_id": "string|null",
  "message": "string",
  "structured_input": {
    "region": "string|null",
    "soil_organic_carbon": "number|null",
    "rainfall": "number|string|null",
    "crop": "string|null",
    "land_use": "string|null"
  }
}
```

`structured_input` is optional.

### Clarification Response

```json
{
  "type": "clarification",
  "conversation_id": "string",
  "question": "string",
  "missing_variables": ["string"],
  "environmental_state": {}
}
```

### Recommendation Response

```json
{
  "type": "recommendation",
  "conversation_id": "string",
  "assessment": "string",
  "variables_considered": ["string"],
  "recommendations": [
    {
      "action": "string",
      "why": "string",
      "impacted_metrics": ["string"],
      "time_horizon": "short|medium|long",
      "confidence": "number|null",
      "evidence": [
        {
          "source_id": "string",
          "title": "string",
          "publisher": "string"
        }
      ]
    }
  ],
  "environmental_state": {},
  "limitations": ["string"]
}
```

## POST `/api/ingest`

For development/admin ingestion of documents or structured records.

The endpoint should not be exposed publicly without appropriate protection.

## GET `/api/conversations/{conversation_id}`

Returns the relevant conversation/environmental state.

## Validation

Use schema validation at the API boundary.

Invalid requests should return useful errors rather than reaching the LLM layer.

## Backward Compatibility

If an API contract changes:
1. update this document
2. update backend schemas
3. update frontend consumers
4. run API tests
