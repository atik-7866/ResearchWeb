# ResearchGraph

ResearchGraph combines OpenAlex paper metadata, Neo4j citation relationships, Qdrant vector search, local sentence-transformer embeddings, and Groq reasoning.

## Requirements

- Python 3.12+
- Node.js 20+
- Neo4j Desktop running on `localhost:7687`
- Qdrant running on `localhost:6333`
- A Groq API key

## Backend

From the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

## Ingest papers

With the backend terminal active, open another terminal:

```powershell
cd C:\Users\HP\Documents\researchgraph\backend
..\.venv\Scripts\python.exe -m scripts.ingest --topic "retrieval augmented generation" --limit 50
```

## Frontend

Open a third terminal:

```powershell
cd C:\Users\HP\Documents\researchgraph\frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Configuration

Copy `.env.example` to `.env` and set `GROQ_API_KEY`. Keep Neo4j and Qdrant running locally before starting the backend.
