import os
from openai import OpenAI


EMBED_MODEL = (os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small") or "text-embedding-3-small").strip()


def embedding_dimensions(model: str | None = None) -> int:
    target = (model or EMBED_MODEL or "").strip()
    if target == "text-embedding-3-large":
        return 1536
    return 768


def _get_client() -> OpenAI:
    return OpenAI()


def embed_text(text: str, *, model: str | None = None) -> list[float]:
    value = str(text or "").strip()
    if not value:
        raise ValueError("text is empty")
    effective_model = (model or EMBED_MODEL).strip()
    client = _get_client()
    res = client.embeddings.create(
        model=effective_model,
        input=value,
        encoding_format="float",
    )
    return list(res.data[0].embedding)

