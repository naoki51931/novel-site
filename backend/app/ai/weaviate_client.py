import os
import uuid
from typing import Any

import httpx


WEAVIATE_URL = (os.getenv("WEAVIATE_URL", "http://weaviate:8080") or "http://weaviate:8080").strip().rstrip("/")
WEAVIATE_TIMEOUT_SEC = float(os.getenv("WEAVIATE_TIMEOUT_SEC", "10") or 10)
WEAVIATE_CLASS = "AiMemory"
_UUID_NAMESPACE = uuid.UUID("7f090164-a0a7-4499-8177-5c33a81ba177")


def _memory_object_id(memory_id: int) -> str:
    return str(uuid.uuid5(_UUID_NAMESPACE, f"ai-memory:{int(memory_id)}"))


def ensure_schema() -> None:
    schema_body = {
        "class": WEAVIATE_CLASS,
        "vectorizer": "none",
        "properties": [
            {"name": "memory_id", "dataType": ["int"]},
            {"name": "user_id", "dataType": ["int"]},
            {"name": "scope", "dataType": ["text"]},
            {"name": "scope_id", "dataType": ["int"], "indexNullState": True},
            {"name": "category", "dataType": ["text"]},
            {"name": "importance", "dataType": ["number"]},
            {"name": "upsert_key", "dataType": ["text"]},
            {"name": "is_active", "dataType": ["boolean"]},
        ],
    }
    with httpx.Client(timeout=WEAVIATE_TIMEOUT_SEC) as client:
        res = client.get(f"{WEAVIATE_URL}/v1/schema")
        res.raise_for_status()
        classes = {c.get("class") for c in (res.json().get("classes") or []) if isinstance(c, dict)}
        if WEAVIATE_CLASS in classes:
            return
        create_res = client.post(f"{WEAVIATE_URL}/v1/schema", json=schema_body)
        create_res.raise_for_status()


def upsert_memory(memory_id: int, vector: list[float], payload: dict[str, Any]) -> None:
    object_id = _memory_object_id(memory_id)
    clean_payload = {k: v for k, v in (payload or {}).items() if v is not None}
    body = {
        "id": object_id,
        "class": WEAVIATE_CLASS,
        "properties": {
            "memory_id": int(memory_id),
            **clean_payload,
        },
        "vector": vector,
    }
    with httpx.Client(timeout=WEAVIATE_TIMEOUT_SEC) as client:
        del_res = client.delete(f"{WEAVIATE_URL}/v1/objects/{object_id}")
        if del_res.status_code not in (200, 204, 404):
            del_res.raise_for_status()
        res = client.post(f"{WEAVIATE_URL}/v1/objects", json=body)
        res.raise_for_status()


def deactivate_memory(memory_id: int) -> None:
    object_id = _memory_object_id(memory_id)
    body = {"class": WEAVIATE_CLASS, "properties": {"is_active": False}}
    with httpx.Client(timeout=WEAVIATE_TIMEOUT_SEC) as client:
        res = client.patch(f"{WEAVIATE_URL}/v1/objects/{object_id}", json=body)
        if res.status_code == 404:
            return
        res.raise_for_status()


def delete_memory(memory_id: int) -> None:
    object_id = _memory_object_id(memory_id)
    with httpx.Client(timeout=WEAVIATE_TIMEOUT_SEC) as client:
        res = client.delete(f"{WEAVIATE_URL}/v1/objects/{object_id}")
        if res.status_code == 404:
            return
        res.raise_for_status()


def search_memory_ids(
    vector: list[float],
    *,
    user_id: int,
    scope: str,
    scope_id: int | None,
    limit: int,
) -> list[int]:
    where_operands: list[dict[str, Any]] = [
        {"path": ["user_id"], "operator": "Equal", "valueInt": int(user_id)},
        {"path": ["scope"], "operator": "Equal", "valueText": str(scope)},
        {"path": ["is_active"], "operator": "Equal", "valueBoolean": True},
    ]
    if scope_id is None:
        where_operands.append({"path": ["scope_id"], "operator": "IsNull", "valueBoolean": True})
    else:
        where_operands.append({"path": ["scope_id"], "operator": "Equal", "valueInt": int(scope_id)})

    query = {
        "query": """
        query($vec:[Float!]!, $where:WhereFilter!, $limit:Int!){
          Get{
            AiMemory(nearVector:{vector:$vec}, where:$where, limit:$limit){
              memory_id
              _additional{distance}
            }
          }
        }
        """,
        "variables": {
            "vec": vector,
            "where": {"operator": "And", "operands": where_operands},
            "limit": int(limit),
        },
    }
    with httpx.Client(timeout=WEAVIATE_TIMEOUT_SEC) as client:
        res = client.post(f"{WEAVIATE_URL}/v1/graphql", json=query)
        res.raise_for_status()
        data = res.json()
    hits = (((data.get("data") or {}).get("Get") or {}).get(WEAVIATE_CLASS) or [])
    out: list[int] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        try:
            out.append(int(hit.get("memory_id")))
        except Exception:
            continue
    return out
