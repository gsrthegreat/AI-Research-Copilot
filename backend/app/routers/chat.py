import asyncio
import re
from typing import Any
from uuid import UUID

from google import genai
from google.genai import types
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.database import get_collection, sb
from app.routers.ingest import embed_query

router = APIRouter(prefix="/chat")

MAX_CONTEXT_CHUNKS = 8
MAX_HISTORY_MESSAGES = 10


# ── Pydantic models ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    conversation_id: str | None = None
    source_type: str | None = None
    k: int = 6


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    source_type: str
    text: str
    score: float
    page_number: int | None = None
    source_url: str | None = None


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    citations: list[Citation]
    message_id: str


# ── Prompt builder (defined first so client can use it) ────────────────────────

def _build_system_prompt() -> str:
    return (
        "You are an AI research assistant. Answer the user's question using ONLY "
        "the provided context chunks below. Be precise, clear, and concise.\n\n"
        "CITATION RULES — you MUST follow these exactly:\n"
        "- After every claim drawn from a chunk, append a citation tag: [SOURCE:chunk_id]\n"
        "- Use the exact chunk_id strings provided in the context.\n"
        "- One tag per chunk used; you may cite multiple chunks per sentence.\n"
        "- If the context does not contain enough information, say so honestly.\n"
        "- Do NOT invent facts beyond the provided context."
    )


# ── Gemini client (initialized after _build_system_prompt is defined) ──────────

_gemini = genai.Client(api_key=settings.GEMINI_API_KEY)
GEMINI_MODEL = "gemini-3.1-flash-lite"


# ── Supabase helpers ───────────────────────────────────────────────────────────

def _create_conversation(question: str) -> str:
    title = question[:80]
    result = sb.table("conversations").insert({"title": title}).execute()
    if not result.data:
        raise RuntimeError("Failed to create conversation")
    return result.data[0]["id"]


def _load_history(conversation_id: str) -> list[dict[str, str]]:
    result = (
        sb.table("messages")
        .select("role, content")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .limit(MAX_HISTORY_MESSAGES)
        .execute()
    )
    return [{"role": r["role"], "content": r["content"]} for r in (result.data or [])]


def _save_message(
    conversation_id: str,
    role: str,
    content: str,
    citations: list[dict] | None = None,
) -> str:
    result = (
        sb.table("messages")
        .insert(
            {
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "citations": citations or [],
            }
        )
        .execute()
    )
    if not result.data:
        raise RuntimeError("Failed to save message")
    return result.data[0]["id"]


# ── Retrieval ──────────────────────────────────────────────────────────────────

def _retrieve_chunks(
    question: str, k: int, source_type: str | None
) -> list[dict[str, Any]]:
    collection = get_collection()
    query_vec = embed_query(question)

    kwargs: dict[str, Any] = {
        "query_embeddings": [query_vec],
        "n_results": min(k, MAX_CONTEXT_CHUNKS),
        "include": ["documents", "metadatas", "distances"],
    }
    if source_type:
        kwargs["where"] = {"source_type": source_type}

    res = collection.query(**kwargs)
    ids = res.get("ids", [[]])[0]
    distances = res.get("distances", [[]])[0]
    metadatas = res.get("metadatas", [[]])[0]

    if not ids:
        return []

    doc_ids = list({m.get("document_id", "") for m in metadatas if m.get("document_id")})
    chunk_rows = (
        sb.table("chunks")
        .select("id, document_id, text, chunk_index, page_number, source_type, source_url, chroma_id")
        .in_("document_id", doc_ids)
        .execute()
    ).data or []

    chunk_map = {r["chroma_id"]: r for r in chunk_rows if r.get("chroma_id")}

    title_rows = (
        sb.table("documents")
        .select("id, title")
        .in_("id", doc_ids)
        .execute()
    ).data or []
    title_map = {r["id"]: r["title"] for r in title_rows}

    chunks: list[dict[str, Any]] = []
    for chroma_id, distance, metadata in zip(ids, distances, metadatas):
        row = chunk_map.get(chroma_id)
        if not row:
            continue
        doc_id = str(row["document_id"])
        chunks.append(
            {
                "chroma_id": chroma_id,
                "chunk_id": row["id"],
                "document_id": doc_id,
                "document_title": title_map.get(doc_id, "Unknown"),
                "text": row["text"],
                "score": round(1 - distance, 4),
                "source_type": row.get("source_type", ""),
                "page_number": row.get("page_number"),
                "source_url": row.get("source_url"),
            }
        )

    chunks.sort(key=lambda c: c["score"], reverse=True)
    return chunks


# ── Context block ──────────────────────────────────────────────────────────────

def _build_context_block(chunks: list[dict[str, Any]]) -> str:
    lines = ["CONTEXT CHUNKS:"]
    for i, c in enumerate(chunks, 1):
        lines.append(
            f"\n[{i}] chunk_id={c['chunk_id']} | "
            f"source={c['source_type']} | "
            f"title={c['document_title']} | "
            f"score={c['score']}\n{c['text']}"
        )
    return "\n".join(lines)


# ── Citation parser ────────────────────────────────────────────────────────────

_CITATION_RE = re.compile(r"\[SOURCE:([a-f0-9\-]+)\]")


def _parse_citations(
    answer: str, chunks: list[dict[str, Any]]
) -> tuple[str, list[Citation]]:
    chunk_map = {c["chunk_id"]: c for c in chunks}
    seen: dict[str, Citation] = {}
    citation_list: list[Citation] = []

    for match in _CITATION_RE.finditer(answer):
        chunk_id = match.group(1)
        if chunk_id in seen or chunk_id not in chunk_map:
            continue
        c = chunk_map[chunk_id]
        citation = Citation(
            chunk_id=chunk_id,
            document_id=c["document_id"],
            document_title=c["document_title"],
            source_type=c["source_type"],
            text=c["text"][:300],
            score=c["score"],
            page_number=c.get("page_number"),
            source_url=c.get("source_url"),
        )
        seen[chunk_id] = citation
        citation_list.append(citation)

    counter: dict[str, int] = {}
    idx = [1]

    def replacer(m: re.Match) -> str:
        cid = m.group(1)
        if cid not in counter:
            counter[cid] = idx[0]
            idx[0] += 1
        return f"[{counter[cid]}]"

    clean_answer = _CITATION_RE.sub(replacer, answer)
    return clean_answer, citation_list


# ── LLM call ──────────────────────────────────────────────────────────────────

def _call_gemini(
    history: list[dict[str, str]],
    question: str,
    context_block: str,
) -> str:
    user_message = f"{context_block}\n\nQUESTION: {question}"

    # Build conversation history in Gemini format
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

    # Add current question
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    response = _gemini.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=_build_system_prompt(),
            max_output_tokens=1024,
        ),
    )
    return response.text


# ── Main endpoint ──────────────────────────────────────────────────────────────

@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    conversation_id = body.conversation_id
    if conversation_id:
        row = sb.table("conversations").select("id").eq("id", conversation_id).limit(1).execute()
        if not row.data:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation_id = await asyncio.to_thread(_create_conversation, question)

    history_task = asyncio.to_thread(_load_history, conversation_id)
    chunks_task = asyncio.to_thread(_retrieve_chunks, question, body.k, body.source_type)
    history, chunks = await asyncio.gather(history_task, chunks_task)

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="No relevant documents found. Please ingest some documents first.",
        )

    context_block = _build_context_block(chunks)
    raw_answer = await asyncio.to_thread(_call_gemini, history, question, context_block)

    clean_answer, citations = _parse_citations(raw_answer, chunks)

    citations_json = [c.model_dump() for c in citations]
    await asyncio.to_thread(_save_message, conversation_id, "user", question)
    message_id = await asyncio.to_thread(
        _save_message, conversation_id, "assistant", clean_answer, citations_json
    )

    return ChatResponse(
        answer=clean_answer,
        conversation_id=conversation_id,
        citations=citations,
        message_id=message_id,
    )


# ── Conversation endpoints ─────────────────────────────────────────────────────

@router.get("/conversations")
async def list_conversations() -> list[dict[str, Any]]:
    try:
        result = (
            sb.table("conversations")
            .select("id, title, created_at")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: UUID) -> dict[str, Any]:
    conv = (
        sb.table("conversations")
        .select("id, title, created_at")
        .eq("id", str(conversation_id))
        .limit(1)
        .execute()
    )
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        sb.table("messages")
        .select("id, role, content, citations, created_at")
        .eq("conversation_id", str(conversation_id))
        .order("created_at")
        .execute()
    )
    return {**conv.data[0], "messages": messages.data or []}