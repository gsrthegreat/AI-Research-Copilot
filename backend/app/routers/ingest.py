# pip install pymupdf sentence-transformers trafilatura beautifulsoup4 requests gitpython

import asyncio
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

import fitz
import git
import requests
import trafilatura
from bs4 import BeautifulSoup
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from app.chunker import chunk_pages
from app.database import get_collection, sb

router = APIRouter(prefix="/ingest")

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

_embedding_model = SentenceTransformer(EMBEDDING_MODEL)


class IngestUrlRequest(BaseModel):
    url: str
    title: str | None = None


class IngestGithubRequest(BaseModel):
    repo_url: str
    title: str | None = None
    branch: str = "main"


GITHUB_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".rst",
}
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build", "venv"}
MAX_FILE_BYTES = 100 * 1024


def extract_pdf_pages(content: bytes) -> list[tuple[int, str]]:
    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        raise ValueError(f"Invalid PDF file: {exc}") from exc

    pages: list[tuple[int, str]] = []
    try:
        for page_idx in range(len(doc)):
            text = doc[page_idx].get_text().strip()
            if text:
                pages.append((page_idx + 1, text))
    finally:
        doc.close()

    return pages


def scrape_url(url: str) -> tuple[str, str | None]:
    """Fetch and extract page text; returns (text, html_title)."""
    downloaded = trafilatura.fetch_url(url)
    html_title: str | None = None
    text: str | None = None

    if downloaded:
        text = trafilatura.extract(
            downloaded, include_comments=False, include_tables=True
        )
        metadata = trafilatura.extract_metadata(downloaded)
        if metadata and metadata.title:
            html_title = metadata.title.strip()

    if text is None:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        if soup.title and soup.title.string:
            html_title = soup.title.string.strip()
        text = soup.get_text(separator="\n", strip=True)

    if not text or not text.strip():
        raise ValueError("No extractable text found at URL")

    return text.strip(), html_title


def _repo_title_from_url(repo_url: str) -> str:
    path = repo_url.rstrip("/").split("github.com/")[-1]
    return path.removesuffix(".git") or repo_url


def _collect_repo_files(repo_root: Path) -> list[tuple[str, str]]:
    collected: list[tuple[str, str]] = []
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.suffix.lower() not in GITHUB_EXTENSIONS:
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel_path = rel.as_posix()
        collected.append((rel_path, f"# File: {rel_path}\n\n{text}"))
    return collected


def clone_and_collect_repo(repo_url: str, branch: str) -> tuple[str, int, str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            git.Repo.clone_from(repo_url, tmpdir, depth=1, branch=branch)
        except git.GitCommandError as exc:
            raise ValueError(f"Failed to clone repository: {exc}") from exc

        files = _collect_repo_files(Path(tmpdir))
        if not files:
            raise ValueError("No matching text files found in repository")

        combined = "\n\n---\n\n".join(content for _, content in files)
        return combined, len(files), _repo_title_from_url(repo_url)


def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors = _embedding_model.encode(texts, show_progress_bar=False)
    return vectors.tolist()


def embed_query(query: str) -> list[float]:
    vector = _embedding_model.encode([query], show_progress_bar=False)
    return vector[0].tolist()


def _parse_chroma_id(chroma_id: str) -> tuple[str, int]:
    document_id, chunk_index_str = chroma_id.rsplit("_", 1)
    return document_id, int(chunk_index_str)


def _fetch_chunks_by_chroma_ids(chroma_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not chroma_ids:
        return {}

    pairs: set[tuple[str, int]] = set()
    for chroma_id in chroma_ids:
        document_id, chunk_index = _parse_chroma_id(chroma_id)
        pairs.add((document_id, chunk_index))

    document_ids = list({document_id for document_id, _ in pairs})
    result = (
        sb.table("chunks")
        .select(
            "id, document_id, text, source_type, chunk_index, page_number, source_url"
        )
        .in_("document_id", document_ids)
        .execute()
    )

    lookup: dict[str, dict[str, Any]] = {}
    for row in result.data or []:
        key = f"{row['document_id']}_{row['chunk_index']}"
        if (row["document_id"], row["chunk_index"]) in pairs:
            lookup[key] = row
    return lookup


def _fetch_document_titles(document_ids: list[str]) -> dict[str, str]:
    if not document_ids:
        return {}
    result = (
        sb.table("documents")
        .select("id, title")
        .in_("id", document_ids)
        .execute()
    )
    return {row["id"]: row["title"] for row in result.data or []}


def search_research_chunks(
    query: str, k: int, source_type: str | None
) -> list[dict[str, Any]]:
    collection = get_collection()
    query_kwargs: dict[str, Any] = {
        "query_embeddings": [embed_query(query)],
        "n_results": k,
    }
    if source_type is not None:
        query_kwargs["where"] = {"source_type": source_type}

    chroma_results = collection.query(**query_kwargs)
    chroma_ids: list[str] = chroma_results.get("ids", [[]])[0]
    distances: list[float] = chroma_results.get("distances", [[]])[0]
    metadatas: list[dict[str, Any]] = chroma_results.get("metadatas", [[]])[0]

    if not chroma_ids:
        return []

    chunk_lookup = _fetch_chunks_by_chroma_ids(chroma_ids)
    document_ids = list(
        {
            meta.get("document_id") or _parse_chroma_id(chroma_id)[0]
            for chroma_id, meta in zip(chroma_ids, metadatas)
        }
    )
    title_lookup = _fetch_document_titles(document_ids)

    results: list[dict[str, Any]] = []
    for chroma_id, distance, metadata in zip(chroma_ids, distances, metadatas):
        chunk_row = chunk_lookup.get(chroma_id)
        if not chunk_row:
            continue
        document_id = str(chunk_row["document_id"])
        score = 1 - distance
        results.append(
            {
                "chunk_id": chunk_row["id"],
                "document_id": document_id,
                "text": chunk_row["text"],
                "score": score,
                "source_type": chunk_row["source_type"],
                "metadata": metadata or {},
                "document_title": title_lookup.get(document_id, ""),
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results


def list_documents() -> list[dict[str, Any]]:
    result = (
        sb.table("documents")
        .select("id, title, source_type, source_url, created_at, chunks(count)")
        .order("created_at", desc=True)
        .execute()
    )
    documents: list[dict[str, Any]] = []
    for row in result.data or []:
        chunks_info = row.pop("chunks", [])
        chunk_count = chunks_info[0]["count"] if chunks_info else 0
        documents.append({**row, "chunk_count": chunk_count})
    return documents


def get_document_chunks(document_id: str) -> list[dict[str, Any]]:
    doc_result = (
        sb.table("documents")
        .select("id")
        .eq("id", document_id)
        .limit(1)
        .execute()
    )
    if not doc_result.data:
        raise HTTPException(status_code=404, detail="Document not found")

    result = (
        sb.table("chunks")
        .select(
            "id, document_id, text, chunk_index, page_number, source_type, source_url, created_at"
        )
        .eq("document_id", document_id)
        .order("chunk_index")
        .execute()
    )
    return result.data or []


def _insert_document(
    title: str, source_type: str, source_url: str | None = None
) -> UUID:
    row: dict[str, Any] = {"title": title, "source_type": source_type}
    if source_url is not None:
        row["source_url"] = source_url
    result = sb.table("documents").insert(row).execute()
    if not result.data:
        raise RuntimeError("Failed to insert document into Supabase")
    return UUID(result.data[0]["id"])


def _insert_chunks(
    document_id: UUID,
    chunks: list[dict[str, Any]],
    source_url: str | None = None,
) -> None:
    rows: list[dict[str, Any]] = []
    for chunk in chunks:
        chroma_id = f"{document_id}_{chunk['chunk_index']}"   # ← generate here
        row: dict[str, Any] = {
            "document_id": str(document_id),
            "text": chunk["text"],
            "chunk_index": chunk["chunk_index"],
            "chroma_id": chroma_id,                           # ← include in row
            "page_number": chunk.get("page_number"),
            "source_type": chunk["source_type"],
            "source_url": source_url,                         # ← always include (null ok)
        }
        rows.append(row)
    result = sb.table("chunks").insert(rows).execute()
    if not result.data:
        raise RuntimeError("Failed to insert chunks into Supabase")


def _chroma_metadata(
    document_id: UUID,
    chunk: dict[str, Any],
    source_url: str | None = None,
    chroma_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "document_id": str(document_id),
        "chunk_index": chunk["chunk_index"],
        "source_type": chunk["source_type"],
    }
    source_type = chunk["source_type"]
    if source_type == "url" and source_url is not None:
        metadata["url"] = source_url
    elif source_type == "github" and source_url is not None:
        metadata["repo_url"] = source_url
        if chroma_extra and "file_count" in chroma_extra:
            metadata["file_count"] = chroma_extra["file_count"]
    else:
        metadata["page_number"] = chunk["page_number"]
    return metadata


def _upsert_chroma_embeddings(
    document_id: UUID,
    chunks: list[dict[str, Any]],
    embeddings: list[list[float]],
    source_url: str | None = None,
    chroma_extra: dict[str, Any] | None = None,
) -> None:
    collection = get_collection()
    ids = [f"{document_id}_{chunk['chunk_index']}" for chunk in chunks]
    metadatas = [
        _chroma_metadata(document_id, chunk, source_url, chroma_extra)
        for chunk in chunks
    ]
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=[chunk["text"] for chunk in chunks],
        metadatas=metadatas,
    )


async def _persist_ingestion(
    doc_title: str,
    source_type: str,
    chunks: list[dict[str, Any]],
    source_url: str | None = None,
    chroma_extra: dict[str, Any] | None = None,
) -> UUID:
    document_id = await asyncio.to_thread(
        _insert_document, doc_title, source_type, source_url
    )
    await asyncio.to_thread(_insert_chunks, document_id, chunks, source_url)
    texts = [chunk["text"] for chunk in chunks]
    embeddings = await asyncio.to_thread(embed_texts, texts)
    await asyncio.to_thread(
        _upsert_chroma_embeddings,
        document_id,
        chunks,
        embeddings,
        source_url,
        chroma_extra,
    )
    return document_id


@router.post("/pdf")
async def ingest_pdf(
    file: UploadFile = File(...),
    title: str | None = Form(None),
) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF (.pdf)")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if not content.startswith(b"%PDF"):
        raise HTTPException(
            status_code=400, detail="File does not appear to be a valid PDF"
        )

    doc_title = title or file.filename.removesuffix(".pdf") or "Untitled"

    try:
        pages = await asyncio.to_thread(extract_pdf_pages, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not pages:
        raise HTTPException(status_code=400, detail="No extractable text found in PDF")

    chunks = await asyncio.to_thread(chunk_pages, pages, "pdf")
    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks produced from PDF text")

    try:
        document_id = await _persist_ingestion(doc_title, "pdf", chunks)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc

    return {
        "document_id": str(document_id),
        "title": doc_title,
        "chunk_count": len(chunks),
        "status": "success",
    }


@router.post("/url")
async def ingest_url(body: IngestUrlRequest) -> dict[str, Any]:
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    try:
        text, html_title = await asyncio.to_thread(scrape_url, url)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed to fetch URL: {exc}"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    doc_title = body.title or html_title or url

    chunks = await asyncio.to_thread(
        chunk_pages, [(1, text)], "url"
    )
    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks produced from URL text")

    try:
        document_id = await _persist_ingestion(
            doc_title, "url", chunks, source_url=url
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc

    return {
        "document_id": str(document_id),
        "title": doc_title,
        "chunk_count": len(chunks),
        "url": url,
        "status": "success",
    }


@router.post("/github")
async def ingest_github(body: IngestGithubRequest) -> dict[str, Any]:
    repo_url = body.repo_url.strip()
    if not repo_url:
        raise HTTPException(status_code=400, detail="repo_url is required")

    try:
        combined, file_count, default_title = await asyncio.to_thread(
            clone_and_collect_repo, repo_url, body.branch
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    doc_title = body.title or default_title

    chunks = await asyncio.to_thread(
        chunk_pages, [(1, combined)], "github"
    )
    if not chunks:
        raise HTTPException(
            status_code=400, detail="No chunks produced from repository text"
        )

    try:
        document_id = await _persist_ingestion(
            doc_title,
            "github",
            chunks,
            source_url=repo_url,
            chroma_extra={"file_count": file_count},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc

    return {
        "document_id": str(document_id),
        "title": doc_title,
        "chunk_count": len(chunks),
        "file_count": file_count,
        "status": "success",
    }


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    k: int = Query(10, ge=1, le=100),
    source_type: str | None = Query(None),
) -> list[dict[str, Any]]:
    try:
        return await asyncio.to_thread(search_research_chunks, q.strip(), k, source_type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc


@router.get("/documents")
async def documents() -> list[dict[str, Any]]:
    try:
        return await asyncio.to_thread(list_documents)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to list documents: {exc}"
        ) from exc


@router.get("/documents/{document_id}/chunks")
async def document_chunks(document_id: UUID) -> list[dict[str, Any]]:
    try:
        return await asyncio.to_thread(get_document_chunks, str(document_id))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch chunks: {exc}"
        ) from exc
