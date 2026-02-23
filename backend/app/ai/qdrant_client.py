import os
from typing import Any

import httpx

from .embeddings import EMBED_MODEL, embedding_dimensions


QDRANT_URL = (os.getenv("QDRANT_URL", "http://qdrant:6333") or "http://qdrant:6333").strip().rstrip("/")
QDRANT_COLLECTION = (os.getenv("QDRANT_COLLECTION", "ai_memory") or "ai_memory").strip()
QDRANT_TIMEOUT_SEC = float(os.getenv("QDRANT_TIMEOUT_SEC", "10") or 10)


def ensure_collection() -> None:
    url = f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}"
    body = {
        "vectors": {
            "size": embedding_dimensions(EMBED_MODEL),
            "distance": "Cosine",
        }
    }
    with httpx.Client(timeout=QDRANT_TIMEOUT_SEC) as client:
        res = client.put(url, json=body)
        if res.status_code in (200, 201, 409):
            return
        res.raise_for_status()


def qdrant_upsert(point_id: int, vector: list[float], payload: dict[str, Any]) -> None:
    url = f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points"
    body = {"points": [{"id": int(point_id), "vector": vector, "payload": payload}]}
    with httpx.Client(timeout=QDRANT_TIMEOUT_SEC) as client:
        res = client.put(url, json=body)
        res.raise_for_status()


def qdrant_search(query_vector: list[float], limit: int, qdrant_filter: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    url = f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/search"
    body: dict[str, Any] = {"vector": query_vector, "limit": int(limit)}
    if qdrant_filter:
        body["filter"] = qdrant_filter
    with httpx.Client(timeout=QDRANT_TIMEOUT_SEC) as client:
        res = client.post(url, json=body)
        res.raise_for_status()
        data = res.json()
    result = data.get("result")
    return result if isinstance(result, list) else []


def qdrant_delete(point_ids: list[int]) -> None:
    ids = [int(v) for v in point_ids if v is not None]
    if not ids:
        return
    url = f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/delete"
    body = {"points": ids}
    with httpx.Client(timeout=QDRANT_TIMEOUT_SEC) as client:
        res = client.post(url, json=body)
        res.raise_for_status()
