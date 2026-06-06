from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ROOT_DIR = _BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_BACKEND_DIR / ".env", _ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    SUPABASE_URL: str
    SUPABASE_KEY: str
    GEMINI_API_KEY: str = "AIzaSyBj_fZjIrbZPcWooWs0lidQsIfRHTBfVwA"
    CHROMA_PATH: str = "./chroma_db"

    @property
    def resolved_chroma_path(self) -> str:
        path = Path(self.CHROMA_PATH)
        if path.is_absolute():
            return str(path)
        normalized = self.CHROMA_PATH.removeprefix("./")
        if normalized.startswith("backend/"):
            return str((_ROOT_DIR / normalized).resolve())
        return str((_BACKEND_DIR / path).resolve())


settings = Settings()
