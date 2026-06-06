# AI Research Copilot

A monorepo for an AI-powered research assistant with a FastAPI backend and Next.js frontend.

## Structure

```
ai-research-copilot/
├── backend/          # FastAPI API server
├── frontend/         # Next.js 14 web app
├── .env.example      # Environment variable template
└── README.md
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- Supabase project
- Anthropic API key

## Setup

### 1. Clone and configure environment

```bash
cp .env.example .env
cp backend/.env.example backend/.env
```

Fill in your Supabase URL, Supabase key, and Anthropic API key.

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:3000

## API

| Endpoint   | Description        |
|------------|--------------------|
| `GET /health` | Health check    |
| `GET /api/`   | API root        |

## License

MIT
