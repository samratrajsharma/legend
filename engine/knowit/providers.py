"""LLM provider registry. Everything routes through litellm, so adding a provider is
just a model-string prefix (+ optional api_base). Keys are read from the environment."""
from __future__ import annotations
import os

PROVIDERS = {
    "openai":     {"label": "OpenAI",                 "key_env": "OPENAI_API_KEY",
                   "prefix": "",            "base_url": False,
                   "models": ["gpt-4o-mini", "gpt-4o"]},
    "anthropic":  {"label": "Anthropic",              "key_env": "ANTHROPIC_API_KEY",
                   "prefix": "anthropic/",  "base_url": False,
                   "models": ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest"]},
    "gemini":     {"label": "Google Gemini",          "key_env": "GEMINI_API_KEY",
                   "prefix": "gemini/",     "base_url": False,
                   "models": ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]},
    "groq":       {"label": "Groq",                   "key_env": "GROQ_API_KEY",
                   "prefix": "groq/",       "base_url": False,
                   "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]},
    "ollama":     {"label": "Ollama (local)",         "key_env": "",
                   "prefix": "ollama/",     "base_url": True,
                   "default_base": "http://localhost:11434",
                   "models": ["llama3.1", "qwen2.5-coder:7b", "mistral"]},
    "openrouter": {"label": "OpenRouter",             "key_env": "OPENROUTER_API_KEY",
                   "prefix": "openrouter/", "base_url": False,
                   "models": ["meta-llama/llama-3.1-70b-instruct", "google/gemini-flash-1.5"]},
    "custom":     {"label": "Custom (OpenAI-compatible)", "key_env": "OPENAI_API_KEY",
                   "prefix": "openai/",     "base_url": True,
                   "default_base": "http://localhost:8000/v1", "models": []},
}
ORDER = ["", "openai", "anthropic", "gemini", "groq", "ollama", "openrouter", "custom"]


def resolve(provider, model, base_url=""):
    """Return (litellm_model_string, extra_kwargs) for a provider + model."""
    if not model:
        return ("", {})
    if not provider:
        return (model, {})                     # treat model as a raw litellm string
    p = PROVIDERS.get(provider)
    if not p:
        return (model, {})
    full = p["prefix"] + model
    extra = {}
    if p.get("base_url"):
        bu = base_url or p.get("default_base", "")
        if bu:
            extra["api_base"] = bu
    return (full, extra)


def key_present(provider):
    p = PROVIDERS.get(provider)
    if not p:
        return True
    env = p.get("key_env")
    return (not env) or bool(os.getenv(env))


def test_connection(full_model, extra=None):
    """Tiny round-trip to verify the provider/model/key work. Graceful if litellm absent."""
    if not full_model:
        return (False, "no model configured")
    try:
        import litellm
        r = litellm.completion(
            model=full_model,
            messages=[{"role": "user", "content": "Reply with exactly: ok"}],
            max_tokens=5, timeout=30, **(extra or {}))
        return (True, r["choices"][0]["message"]["content"].strip()[:60])
    except Exception as e:
        return (False, f"{type(e).__name__}: {e}")
