from __future__ import annotations
import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _alias_legacy_env() -> None:
    """Back-compat after the KNOWIT_* -> LEGEND_* rename: copy any old KNOWIT_* var to its
    LEGEND_* name when the new one isn't already set, so existing .env files and shell scripts
    keep working. Runs before Config reads the environment below."""
    for k, v in list(os.environ.items()):
        if k.startswith("KNOWIT_"):
            os.environ.setdefault("LEGEND_" + k[len("KNOWIT_"):], v)


_alias_legacy_env()


@dataclass
class Config:
    # --- LLM (optional; resolved from provider + model in providers.py) ---
    llm_provider: str = os.getenv("LEGEND_LLM_PROVIDER", "")   # openai|anthropic|groq|ollama|openrouter|custom
    llm_model: str = os.getenv("LEGEND_LLM_MODEL", "")         # full litellm model string once resolved
    llm_base_url: str = os.getenv("LEGEND_LLM_BASE_URL", "")   # for ollama / custom endpoints
    llm_kwargs: dict = field(default_factory=dict)            # extra kwargs passed to litellm (e.g. api_base)
    # --- retrieval ---
    embed_backend: str = os.getenv("LEGEND_EMBED_BACKEND", "auto")  # auto|hybrid|bm25|chroma
    data_dir: str = os.getenv("LEGEND_DATA_DIR", ".legend_cache")
    chunk_max_lines: int = int(os.getenv("LEGEND_CHUNK_MAX_LINES", "160"))
    top_k: int = int(os.getenv("LEGEND_TOP_K", "6"))
    graph_expand: int = int(os.getenv("LEGEND_GRAPH_EXPAND", "1"))
    use_cache: bool = os.getenv("LEGEND_USE_CACHE", "1") not in ("0", "false", "False")


CONFIG = Config()
