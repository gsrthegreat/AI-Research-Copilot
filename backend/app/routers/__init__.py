from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/")
async def api_root():
    return {"message": "AI Research Copilot API"}
