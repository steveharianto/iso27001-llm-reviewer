from typing import Any, Dict, List, Tuple

from openai import OpenAI

from .ingest import collection
from .controls import get_control
from .config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL


client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL,
)


def detect_control(question: str) -> str | None:
    possible = ["A.5", "A.6", "A.7", "A.8"]
    for cid in possible:
        if cid in question:
            return cid
    return None


def retrieve_relevant_chunks(question: str, file_id: str, k: int = 5) -> List[Tuple[str, dict]]:
    # --- FIX C: composite semantic query ---
    control_id = detect_control(question)
    composite_query = question

    if control_id:
        c = get_control(control_id)
        if c:
            composite_query += " " + c["description"]
            if "key_requirements" in c:
                composite_query += " " + " ".join(c["key_requirements"])

    results = collection.query(
        query_texts=[composite_query],
        n_results=k,
        where={"file_id": file_id},
    )

    chunks: List[Tuple[str, dict]] = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]

    for i in range(len(docs)):
        chunk_text = docs[i]
        metadata = metas[i]
        chunks.append((chunk_text, metadata))

    return chunks


def build_prompt(question: str, chunks: List[Tuple[str, dict]], control_id: str | None = None) -> str:
    context_texts = "\n\n---\n\n".join([c[0] for c in chunks])

    control_text = ""
    if control_id:
        c = get_control(control_id)
        if c:
            control_text = f"""
ISO Control: {c['id']} - {c['title']}
Description: {c['description']}
"""

    prompt = f"""
You are an ISO27001 assistant.

You MUST:
- Answer ONLY using the Context below.
- If the answer is not clearly supported by the Context, say exactly:
  "Not mentioned clearly in this policy."
- Quote exact sentences from the Context for "Relevant text fragments".
- Do NOT invent or hallucinate policy text.

Question:
{question}

{control_text}

Context:
{context_texts}

---
Answer in this exact structure:

Summary:
[1–3 sentences summarizing what the policy says or that it's not mentioned.]

Relevant text fragments:
- "quote 1 from context"
- "quote 2 from context"
(if nothing is relevant, say "None.")

Potential missing items:
- item 1 (only if clearly not addressed in the context)
- item 2
(or say "Not enough information to determine missing items.")
"""
    return prompt


def call_llm(prompt: str) -> str:
    response = client.chat.completions.create(
        model="anthropic/claude-3-haiku",
        messages=[
            {"role": "system", "content": "You are an ISO27001 assistant."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


def _make_snippet(text: str, max_len: int = 220) -> str:
    cleaned = text.replace("\n", " ").strip()
    first_sentence = cleaned.split(".")[0]
    if len(first_sentence) > max_len:
        first_sentence = first_sentence[:max_len]
    return first_sentence + "..."


def answer_question(file_id: str, question: str) -> Dict[str, Any]:
    chunks = retrieve_relevant_chunks(question, file_id=file_id, k=5)
    control_id = detect_control(question)
    prompt = build_prompt(question, chunks, control_id)
    answer = call_llm(prompt)

    chunks_used = []
    for text, meta in chunks:
        snippet = _make_snippet(text)
        chunks_used.append({"page": meta.get("page"), "snippet": snippet})

    return {"answer": answer, "chunks_used": chunks_used}
