"""Re-export production HF embed client for homework CLI."""

from homework.rag_markitdown.hf_embed import (
    DEFAULT_EMBED_MODEL,
    EXPECTED_DIMENSION,
    HuggingFaceEmbedError,
    _normalize_embedding,
    embed_texts,
    get_embed_model,
)

__all__ = [
    "DEFAULT_EMBED_MODEL",
    "EXPECTED_DIMENSION",
    "HuggingFaceEmbedError",
    "embed_texts",
    "get_embed_model",
]
