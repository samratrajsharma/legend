"""KnowIT — Phase 0: ingest → parse → code graph → retrieval → eval.

Dependency-light core (stdlib only). Optional accelerators activate when installed:
  - chromadb  → semantic embeddings (else built-in BM25)
  - litellm   → LLM answer synthesis (else returns retrieved context only)
"""
__version__ = "0.0.1-phase0"
