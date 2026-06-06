from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PaperBase(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: Optional[str] = None
    url: Optional[str] = None


class PaperCreate(PaperBase):
    pass


class Paper(PaperBase):
    id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class NoteBase(BaseModel):
    content: str
    paper_id: Optional[UUID] = None


class NoteCreate(NoteBase):
    pass


class Note(NoteBase):
    id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
