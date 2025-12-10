from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
SAMPLE_POLICIES_DIR = DATA_DIR / "sample_policies"
VECTORSTORE_DIR = BASE_DIR / "vectorstore"

# embedding / model names (can change later)
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# service info
SERVICE_NAME = "iso27001-llm-reviewer"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
