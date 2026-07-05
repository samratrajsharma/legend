from __future__ import annotations
import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


@dataclass
class Config:
    # --- LLM (optional; resolved from provider + model in providers.py) ---
    llm_provider: str = os.getenv("KNOWIT_LLM_PROVIDER", "")   # openai|anthropic|groq|ollama|openrouter|custom
    llm_model: str = os.getenv("KNOWIT_LLM_MODEL", "")         # full litellm model string once resolved
    llm_base_url: str = os.getenv("KNOWIT_LLM_BASE_URL", "")   # for ollama / custom endpoints
    llm_kwargs: dict = field(default_factory=dict)            # extra kwargs passed to litellm (e.g. api_base)
    # --- retrieval ---
    embed_backend: str = os.getenv("KNOWIT_EMBED_BACKEND", "auto")  # auto|hybrid|bm25|chroma
    data_dir: str = os.getenv("KNOWIT_DATA_DIR", ".knowit_cache")
    chunk_max_lines: int = int(os.getenv("KNOWIT_CHUNK_MAX_LINES", "160"))
    top_k: int = int(os.getenv("KNOWIT_TOP_K", "6"))
    graph_expand: int = int(os.getenv("KNOWIT_GRAPH_EXPAND", "1"))
    use_cache: bool = os.getenv("KNOWIT_USE_CACHE", "1") not in ("0", "false", "False")


CONFIG = Config()
