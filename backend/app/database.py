import httpx
import chromadb
from supabase import Client, create_client

from app.config import settings

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

chroma_client = chromadb.PersistentClient(path=settings.resolved_chroma_path)


_SCHEMA_TABLES = ("papers", "notes")


def list_supabase_tables() -> list[str]:
    """Verify Supabase connectivity and list application tables in the public schema."""
    health = httpx.get(
        f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/health",
        headers={"apikey": settings.SUPABASE_KEY},
        timeout=10.0,
    )
    health.raise_for_status()

    found: list[str] = []
    postgrest_reachable = False
    for table in _SCHEMA_TABLES:
        try:
            supabase.table(table).select("id", count="exact").limit(0).execute()
            postgrest_reachable = True
            found.append(table)
        except Exception as exc:
            message = str(exc)
            if "Could not find the table" in message or "PGRST205" in message:
                postgrest_reachable = True
                continue
            raise

    if not postgrest_reachable:
        raise RuntimeError("Supabase PostgREST is not reachable")

    return found


def verify_supabase() -> tuple[bool, list[str]]:
    try:
        return True, list_supabase_tables()
    except Exception:
        return False, []


def verify_chroma() -> tuple[bool, str]:
    try:
        chroma_client.heartbeat()
        count = len(chroma_client.list_collections())
        return True, f"{count} collection(s)"
    except Exception as exc:
        return False, str(exc)
