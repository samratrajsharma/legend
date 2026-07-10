"""Embed symbols with the host's SentenceTransformers service and store them in Qdrant
(collection `kyc_<repo_id>`, one point per symbol). Reuses the host embedding + vector
primitives — does NOT bring its own model or client."""
from __future__ import annotations
import uuid

from core.embeddings.service import embed_texts        # host: List[str] -> List[List[float]]
from core.vector import qdrant_client                  # host: initialized QdrantClient

VECTOR_SIZE = 384   # all-MiniLM-L6-v2


def collection_name(repo_id: str) -> str:
    return f"kyc_{repo_id}"


def _embed_text(sym: dict) -> str:
    parts = [sym.get("path", ""), sym.get("name", ""), sym.get("kind", ""),
             sym.get("signature", ""), sym.get("docstring", "")]
    return "  ".join(p for p in parts if p)[:2000]


def ensure_collection(repo_id: str):
    from qdrant_client.models import Distance, VectorParams
    name = collection_name(repo_id)
    try:
        qdrant_client.get_collection(name)
    except Exception:
        qdrant_client.recreate_collection(
            collection_name=name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def index_symbols(repo_id: str, symbols: list[dict], batch: int = 256) -> int:
    """symbols: [{path, name, kind, signature, docstring, line_start, line_end}]."""
    from qdrant_client.models import PointStruct
    ensure_collection(repo_id)
    name = collection_name(repo_id)
    for i in range(0, len(symbols), batch):
        part = symbols[i:i + batch]
        vectors = embed_texts([_embed_text(s) for s in part])
        points = [PointStruct(id=str(uuid.uuid4()), vector=v, payload=s)
                  for s, v in zip(part, vectors)]
        qdrant_client.upsert(collection_name=name, points=points)
    return len(symbols)


def drop_collection(repo_id: str):
    try:
        qdrant_client.delete_collection(collection_name(repo_id))
    except Exception:
        pass
