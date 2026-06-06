import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import check_chroma_health, check_supabase_health, verify_chroma, verify_supabase
from app.routers import router
from app.routers.chat import router as chat_router
from app.routers.ingest import router as ingest_router


def _print_startup_banner(
    supabase_ok: bool, tables: list[str], chroma_ok: bool, chroma_info: str
) -> None:
    ok, fail = "OK", "FAILED"
    width = 52
    print()
    print("=" * width)
    print("  AI Research Copilot - Backend")
    print("=" * width)
    print(f"  Supabase:  {ok if supabase_ok else fail}")
    if supabase_ok:
        table_list = ", ".join(tables) if tables else "(no tables)"
        print(f"             tables: {table_list}")
    print(f"  ChromaDB:  {ok if chroma_ok else fail}  ({chroma_info})")
    print(f"  Health:    GET /health")
    print(f"  Docs:      GET /docs")
    print("=" * width)
    print()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    supabase_ok, tables = verify_supabase()
    chroma_ok, chroma_info = verify_chroma()
    _print_startup_banner(supabase_ok, tables, chroma_ok, chroma_info)
    yield


app = FastAPI(
    title="AI Research Copilot",
    description="Backend API for AI-powered research assistance",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(ingest_router, prefix="/api/v1", tags=["ingest"])
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])


@app.get("/health")
async def health():
    chroma_status, supabase_status = await asyncio.gather(
        asyncio.to_thread(check_chroma_health),
        asyncio.to_thread(check_supabase_health),
    )
    services = {"chroma": chroma_status, "supabase": supabase_status}
    all_ok = all(status == "ok" for status in services.values())
    return {
        "status": "ok" if all_ok else "error",
        "version": "0.1.0",
        "services": services,
    }