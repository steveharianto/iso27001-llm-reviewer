from pathlib import Path
from typing import Tuple, List

from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import numpy as np
import chromadb
from chromadb.config import Settings

from .config import VECTORSTORE_DIR

# ----- VECTOR STORE INITIALIZATION -----
chroma_client = chromadb.PersistentClient(
    path=str(VECTORSTORE_DIR)
)
collection = chroma_client.get_or_create_collection("policies")

# ----- EMBEDDING MODEL -----
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def extract_text_from_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages_text = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except:
            text = ""
        pages_text.append(text)
    return "\n".join(pages_text)


def chunk_text(text: str, max_words: int = 250) -> List[tuple[str, dict]]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # split double newline as "paragraph"
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # --- FIX A: fallback if only 1 paragraph ---
    if len(paragraphs) <= 1:
        words = text.split()
        chunks = []
        for i in range(0, len(words), max_words):
            chunk_words = words[i:i+max_words]
            chunk_text = " ".join(chunk_words)
            meta = {
                "chunk_index": len(chunks),
                "page": None
            }
            chunks.append((chunk_text, meta))
        return chunks

    # --- paragraph accumulation ---
    chunks = []
    current_words = []
    current_para_indices = []

    def flush_chunk():
        if not current_words:
            return
        chunk_t = " ".join(current_words)
        meta = {
            "chunk_index": len(chunks),
            "paragraph_indices": current_para_indices.copy(),
            "page": None,
        }
        chunks.append((chunk_t, meta))

    for idx, para in enumerate(paragraphs):
        words = para.split()
        if len(current_words) + len(words) > max_words:
            flush_chunk()
            current_words = []
            current_para_indices = []
        current_words.extend(words)
        current_para_indices.append(idx)

    flush_chunk()
    return chunks


def embed_chunks(chunks: List[tuple[str, dict]]) -> tuple[np.ndarray, list[dict]]:
    texts = [c[0] for c in chunks]
    metas = [c[1] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False)
    embeddings = np.array(embeddings)
    return embeddings, metas


def _clean_metadata(meta: dict) -> dict:
    cleaned = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, list):
            cleaned[k] = ",".join(str(x) for x in v)
        elif isinstance(v, (str, int, float, bool)):
            cleaned[k] = v
        else:
            cleaned[k] = str(v)
    return cleaned


def store_embeddings(file_id: str, chunks: List[tuple[str, dict]], embeddings: np.ndarray):
    texts = [c[0] for c in chunks]
    metas = []

    for meta in [c[1] for c in chunks]:
        m = meta.copy()
        m["file_id"] = file_id
        m = _clean_metadata(m)
        metas.append(m)

    ids = [f"{file_id}_{i}" for i in range(len(chunks))]
    collection.add(
        ids=ids,
        embeddings=embeddings.tolist(),
        metadatas=metas,
        documents=texts,
    )


def ingest_pdf(file_path: Path) -> Tuple[str, int]:
    text = extract_text_from_pdf(file_path)
    chunks = chunk_text(text, max_words=250)
    embeddings, metas = embed_chunks(chunks)

    file_id = file_path.stem

    # --- FIX B: remove old embeddings for same file ---
    collection.delete(where={"file_id": file_id})

    store_embeddings(file_id, chunks, embeddings)
    return file_id, len(chunks)
