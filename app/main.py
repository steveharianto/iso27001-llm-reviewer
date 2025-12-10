# app/main.py
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from .config import DATA_DIR
from .models import (
    HealthResponse,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    ChunkUsed,
)
from .ingest import ingest_pdf
from .rag import answer_question


app = FastAPI(title="ISO27001 LLM Reviewer (Prototype)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- HEALTH ----------
@app.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok")


# ---------- INGEST ----------
@app.post("/ingest", response_model=IngestResponse)
async def ingest_endpoint(file: UploadFile = File(...)):
    # basic validation
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # ensure upload dir exists
    upload_dir = DATA_DIR / "uploaded"
    os.makedirs(upload_dir, exist_ok=True)

    # define where to save
    file_path = upload_dir / file.filename

    # save uploaded PDF
    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    finally:
        await file.close()

    # run ingestion pipeline (extract → chunk → embed → store)
    try:
        file_id, n_chunks = ingest_pdf(file_path)
    except Exception as e:
        # if ingestion fails, surface error
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    return IngestResponse(
        file_id=file_id,
        filename=file.filename,
        n_chunks=n_chunks,
    )


# ---------- QUERY ----------
@app.post("/query", response_model=QueryResponse)
async def query_endpoint(payload: QueryRequest):
    """
    JSON body:
    {
      "file_id": "example_policy",
      "question": "What does this say about ISO27001 A.7?"
    }
    """
    file_id = payload.file_id
    question = payload.question.strip()

    if not file_id or not question:
        raise HTTPException(status_code=400, detail="file_id and question are required.")

    try:
        result = answer_question(file_id=file_id, question=question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")

    # map to Pydantic models
    chunks = [
        ChunkUsed(page=chunk.get("page"), snippet=chunk.get("snippet", ""))
        for chunk in result.get("chunks_used", [])
    ]

    return QueryResponse(
        answer=result.get("answer", ""),
        chunks_used=chunks,
    )
