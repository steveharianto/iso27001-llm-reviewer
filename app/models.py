from typing import List, Optional
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class IngestResponse(BaseModel):
    file_id: str
    filename: str
    n_chunks: int


class QueryRequest(BaseModel):
    file_id: str
    question: str


class ChunkUsed(BaseModel):
    page: Optional[int] = None
    snippet: str


class QueryResponse(BaseModel):
    answer: str
    chunks_used: List[ChunkUsed]
