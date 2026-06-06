# 🔬 AI Research Copilot

A full-stack RAG (Retrieval-Augmented Generation) system that lets you chat with your research documents — PDFs, websites, and GitHub repos — with grounded answers and inline source citations.

![Stack](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Stack](https://img.shields.io/badge/Next.js_14-000000?style=flat&logo=next.js&logoColor=white)
![Stack](https://img.shields.io/badge/Supabase-3ECF8E?style=flat&logo=supabase&logoColor=white)
![Stack](https://img.shields.io/badge/ChromaDB-FF6B35?style=flat)
![Stack](https://img.shields.io/badge/Gemini_2.0-4285F4?style=flat&logo=google&logoColor=white)

---

## ✨ Features

- **Multi-source ingestion** — upload PDFs, scrape URLs, or clone GitHub repos
- **Semantic search** — vector embeddings via `all-MiniLM-L6-v2` stored in ChromaDB
- **RAG pipeline** — retrieves relevant chunks, sends to Gemini, returns grounded answers
- **Inline citations** — every answer cites its sources with relevance scores and excerpts
- **Conversation memory** — multi-turn chat with full history stored in Supabase
- **Evaluation dashboard** — auto-runs a golden test set and tracks answer quality, citation hit rate, latency, and retrieval scores over time

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                              │
│   Next.js 14 · ChatThread · CitationCard · UploadPanel      │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP
┌───────────────────────▼─────────────────────────────────────┐
│                   FastAPI Backend                           │
│                                                             │
│  /ingest  →  chunker  →  SentenceTransformers  →  ChromaDB  │
│  /chat    →  retrieve  →  re-rank  →  Gemini  →  citations  │
│  /eval    →  golden test set  →  metrics  →  Supabase       │
└──────────┬────────────────────────────┬─────────────────────┘
           │                            │
    ┌──────▼──────┐              ┌──────▼──────┐
    │  ChromaDB   │              │  Supabase   │
    │  (local)    │              │ (PostgreSQL) │
    │  vectors    │              │ docs/chunks  │
    └─────────────┘              │ convos/msgs  │
                                 │ eval_runs    │
                                 └─────────────┘
```

---

## 📁 Project structure

```
ai-research-copilot/
├── backend/
│   ├── main.py                  # FastAPI app, CORS, router registration
│   ├── test_ingest.py           # Smoke tests for ingestion + search
│   └── app/
│       ├── config.py            # Pydantic settings (env vars)
│       ├── database.py          # Supabase client + ChromaDB client
│       ├── chunker.py           # Text chunking with overlap
│       ├── models.py            # SQLAlchemy / Pydantic models
│       └── routers/
│           ├── ingest.py        # POST /ingest/pdf, /url, /github + GET /search
│           ├── chat.py          # POST /chat + conversation endpoints
│           └── eval.py          # POST /eval/run + GET /eval/metrics
└── frontend/
    └── app/
        ├── page.tsx             # Main chat interface
        ├── layout.tsx           # Root layout + fonts
        ├── globals.css          # CSS variables + dark theme
        ├── eval/
        │   └── page.tsx         # Evaluation dashboard
        ├── lib/
        │   └── api.ts           # Typed fetch wrappers for all API calls
        └── components/
            ├── Sidebar.tsx      # Conversation list + document library
            ├── ChatThread.tsx   # Message bubbles + citation rendering
            ├── CitationCard.tsx # Expandable source citation card
            └── UploadPanel.tsx  # URL input + PDF drag-and-drop
```

---

## 🚀 Getting started

### Prerequisites

- Python 3.11+
- Node.js 20+
- A [Supabase](https://supabase.com) account (free tier)
- A [Google AI Studio](https://aistudio.google.com) API key (free tier)

### 1. Clone the repo

```bash
git clone https://github.com/your-username/ai-research-copilot
cd ai-research-copilot
```

### 2. Set up Supabase

Create a new Supabase project, then run this in the **SQL Editor**:

```sql
create extension if not exists vector;

create table documents (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  source_type text not null,
  source_url text,
  created_at timestamptz default now(),
  metadata jsonb default '{}'
);

create table chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid references documents(id) on delete cascade,
  chunk_index int not null,
  text text not null,
  chroma_id text unique not null,
  page_number int,
  source_type text,
  source_url text,
  metadata jsonb default '{}',
  created_at timestamptz default now()
);

create table conversations (
  id uuid primary key default gen_random_uuid(),
  title text,
  created_at timestamptz default now()
);

create table messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid references conversations(id) on delete cascade,
  role text not null,
  content text not null,
  citations jsonb default '[]',
  created_at timestamptz default now()
);

create table eval_runs (
  id uuid primary key default gen_random_uuid(),
  results jsonb not null default '[]',
  summary jsonb not null default '{}',
  created_at timestamptz default now()
);

-- Disable RLS for backend service access
alter table documents disable row level security;
alter table chunks disable row level security;
alter table conversations disable row level security;
alter table messages disable row level security;
alter table eval_runs disable row level security;

-- Indexes
create index idx_messages_conversation_id on messages(conversation_id);
create index idx_chunks_document_id on chunks(document_id);
create index idx_chunks_chroma_id on chunks(chroma_id);
```

### 3. Configure environment variables

Create `backend/.env`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
GEMINI_API_KEY=AIzaSy...
CHROMA_PATH=./chroma_db
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8888
```

### 4. Install backend dependencies

```bash
cd backend
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Mac/Linux

pip install fastapi "uvicorn[standard]" supabase chromadb \
  sentence-transformers google-genai pymupdf trafilatura \
  beautifulsoup4 requests gitpython python-multipart \
  aiofiles python-dotenv pydantic-settings lxml_html_clean
```

### 5. Install frontend dependencies

```bash
cd frontend
npm install
```

### 6. Run the app

**Terminal 1 — backend:**
```bash
cd backend
venv\Scripts\activate
uvicorn main:app --reload --port 8888
```

**Terminal 2 — frontend:**
```bash
cd frontend
npm run dev
```

Open **http://localhost:3000**

---

## 🧭 Usage

### Add a source

Click **＋ Add Source** in the top bar:
- Paste any URL and click **Add**
- Or drag and drop a PDF

### Chat

Type a question in the input box. The system will:
1. Embed your question and retrieve the top matching chunks
2. Send the chunks + question to Gemini
3. Return a grounded answer with `[1]` `[2]` citation markers
4. Show expandable citation cards below each answer

### Evaluation dashboard

Visit **http://localhost:3000/eval** to:
- See answer quality, citation hit rate, latency, and retrieval scores
- View ingested document stats
- Trigger a fresh eval run against the golden test set
- Track metric trends across runs

---

## 🔌 API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health check |
| `POST` | `/api/v1/ingest/pdf` | Upload and ingest a PDF |
| `POST` | `/api/v1/ingest/url` | Ingest a URL |
| `POST` | `/api/v1/ingest/github` | Ingest a GitHub repo |
| `GET` | `/api/v1/ingest/search` | Semantic search |
| `GET` | `/api/v1/ingest/documents` | List all ingested documents |
| `POST` | `/api/v1/chat` | Send a chat message |
| `GET` | `/api/v1/chat/conversations` | List conversations |
| `GET` | `/api/v1/chat/conversations/:id` | Get conversation with messages |
| `POST` | `/api/v1/eval/run` | Run evaluation against test set |
| `GET` | `/api/v1/eval/metrics` | Get aggregated metrics + doc stats |
| `GET` | `/api/v1/eval/runs` | List past eval runs |

Full interactive docs at **http://localhost:8888/docs**

---

## 🛠️ Tech stack

| Layer | Technology |
|-------|-----------|
| Backend framework | FastAPI + Uvicorn |
| LLM | Google Gemini 2.0 Flash Lite |
| Embeddings | `all-MiniLM-L6-v2` (SentenceTransformers) |
| Vector store | ChromaDB (local persistent) |
| Database | Supabase (PostgreSQL) |
| PDF parsing | PyMuPDF |
| Web scraping | trafilatura + BeautifulSoup4 |
| Frontend | Next.js 14 + TypeScript + Tailwind CSS |
| Evaluation | Keyword overlap scoring + retrieval metrics |

---

## 🗺️ Roadmap

- [ ] YouTube transcript ingestion
- [ ] Streaming chat responses (SSE)
- [ ] Ragas integration for faithfulness scoring
- [ ] Re-ranking with cross-encoder
- [ ] Multi-user support with Supabase Auth
- [ ] Vercel + Railway deployment guide
- [ ] Custom golden test set editor in the dashboard

---

## 📄 License

MIT
