# Darukaa BioIntel — Local Setup & Reproducibility Guide

This guide provides instructions to set up, run, test, and evaluate the **Darukaa BioIntel** platform locally on Windows, macOS, or Linux.

---

## Prerequisites

- **Python**: `3.11` or higher
- **Node.js**: `18.x` or higher (`npm` included)
- **Git**: Installed and available on PATH
- **Hardware**: Standard developer machine (no GPU or specialized accelerators required)

---

## 1. Repository Setup

Clone the repository and enter the root directory:

```bash
git clone https://github.com/darukaa-earth/Darukaa-BioIntel.git
cd Darukaa-BioIntel
```

---

## 2. Backend Setup

### A. Python Environment
Create and activate a virtual environment:

**Windows (PowerShell)**:
```pwsh
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS**:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### B. Install Dependencies
Install the required backend packages:

```bash
pip install -r backend/requirements.txt
```

### C. Knowledge Base & Corpus Ingestion
The repository includes the curated 10-source corpus manifest (`data/corpus_manifest.json`) and raw document sections (`data/corpus/`).

To initialize the SQLite knowledge database (`data/knowledge.db`) and build the BM25 inverted index (`data/lexical_index.json`), run the deterministic ingestion pipeline:

```bash
python -c "import sys; sys.path.insert(0, 'backend'); from app.knowledge.indexer import IngestionPipeline; IngestionPipeline().run()"
```

*Verification*: This generates `data/knowledge.db` (10 sources, 38 chunks) and `data/lexical_index.json` in $< 500\text{ ms}$.

### D. Start Backend API Server
Start the FastAPI application on port `8000`:

```bash
uvicorn app.main:app --reload --port 8000 --app-dir backend
```

- **Interactive API Documentation (Swagger)**: `http://localhost:8000/docs`
- **Health / Readiness Endpoint**: `http://localhost:8000/api/health`

---

## 3. Frontend Setup

In a separate terminal, navigate to the `frontend/` directory:

```bash
cd frontend
npm install
```

### Start Development Server
Start Vite on port `5173`:

```bash
npm run dev
```

- **Web UI**: Open `http://localhost:5173` in any modern web browser.

### Production Build Verification
To verify TypeScript compilation and bundle generation:

```bash
npm run build
```

---

## 4. Running the Evaluation Benchmark

Darukaa BioIntel features a standalone evaluation benchmark executing 15 test cases across the 5 official hackathon criteria, plus an extended 20-query retrieval benchmark.

Run the evaluation runner:

```bash
python backend/scripts/run_evaluation.py
```

### Generated Artifacts
- **Markdown Report**: [`docs/EVALUATION_REPORT.md`](file:///G:/Github/Darukaa-BioIntel/docs/EVALUATION_REPORT.md)
- **JSON Report**: [`docs/evaluation_report.json`](file:///G:/Github/Darukaa-BioIntel/docs/evaluation_report.json)

You can also trigger evaluation via the live API:
```bash
curl -X POST http://localhost:8000/api/evaluate/run
```

---

## 5. Running the Full Test Suite

To run the automated regression test suite:

```bash
pytest backend/tests -v
```

All test suites execute 100% offline with zero external network dependencies.
