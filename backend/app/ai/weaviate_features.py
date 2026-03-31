import os
import uuid
from typing import Any

import httpx

from .embeddings import embed_text


WEAVIATE_URL = (os.getenv("WEAVIATE_URL", "http://weaviate:8080") or "http://weaviate:8080").strip().rstrip("/")
WEAVIATE_TIMEOUT_SEC = float(os.getenv("WEAVIATE_TIMEOUT_SEC", "10") or 10)
WEAVIATE_FEATURE_CLASS = "AiFeatureDoc"
_UUID_NAMESPACE = uuid.UUID("e7f4d3f0-cfa8-4d8e-82ff-c35e06f8822f")


def _feature_object_id(doc_id: str) -> str:
    return str(uuid.uuid5(_UUID_NAMESPACE, f"feature-doc:{str(doc_id or '').strip()}"))


def ensure_feature_schema() -> None:
    schema_body = {
        "class": WEAVIATE_FEATURE_CLASS,
        "vectorizer": "none",
        "properties": [
            {"name": "doc_id", "dataType": ["text"]},
            {"name": "feature", "dataType": ["text"]},
            {"name": "site_key", "dataType": ["text"]},
            {"name": "target_id", "dataType": ["int"]},
            {"name": "target_type", "dataType": ["text"]},
            {"name": "title", "dataType": ["text"]},
            {"name": "content", "dataType": ["text"]},
            {"name": "is_public", "dataType": ["boolean"]},
            {"name": "is_r18", "dataType": ["boolean"]},
        ],
    }
    with httpx.Client(timeout=WEAVIATE_TIMEOUT_SEC) as client:
        res = client.get(f"{WEAVIATE_URL}/v1/schema")
        res.raise_for_status()
        classes = {c.get("class") for c in (res.json().get("classes") or []) if isinstance(c, dict)}
        if WEAVIATE_FEATURE_CLASS in classes:
            return
        create_res = client.post(f"{WEAVIATE_URL}/v1/schema", json=schema_body)
        create_res.raise_for_status()


def upsert_feature_docs(docs: list[dict[str, Any]]) -> None:
    if not docs:
        return
    with httpx.Client(timeout=WEAVIATE_TIMEOUT_SEC) as client:
        for doc in docs:
            doc_id = str(doc.get("doc_id") or "").strip()
            if not doc_id:
                continue
            content = str(doc.get("content") or "").strip()
            if not content:
                continue
            vector = embed_text(content)
            object_id = _feature_object_id(doc_id)
            payload = {
                "doc_id": doc_id,
                "feature": str(doc.get("feature") or "").strip(),
                "site_key": str(doc.get("site_key") or "main").strip() or "main",
                "target_id": int(doc.get("target_id") or 0),
                "target_type": str(doc.get("target_type") or "unknown").strip() or "unknown",
                "title": str(doc.get("title") or "").strip(),
                "content": content[:4000],
                "is_public": bool(doc.get("is_public", True)),
                "is_r18": bool(doc.get("is_r18", False)),
            }
            body = {
                "id": object_id,
                "class": WEAVIATE_FEATURE_CLASS,
                "properties": payload,
                "vector": vector,
            }
            del_res = client.delete(f"{WEAVIATE_URL}/v1/objects/{object_id}")
            if del_res.status_code not in (200, 204, 404):
                del_res.raise_for_status()
            res = client.post(f"{WEAVIATE_URL}/v1/objects", json=body)
            res.raise_for_status()


def semantic_search_feature_docs(
    query_text: str,
    *,
    feature: str | None,
    site_key: str | None,
    limit: int,
    target_ids: list[int] | None = None,
    include_r18: bool = False,
    public_only: bool = True,
) -> list[dict[str, Any]]:
    text_value = str(query_text or "").strip()
    if not text_value:
        return []
    vector = embed_text(text_value)

    where_operands: list[dict[str, Any]] = []
    feature_value = str(feature or "").strip()
    if feature_value:
        where_operands.append({"path": ["feature"], "operator": "Equal", "valueText": feature_value})
    site_value = str(site_key or "").strip()
    if site_value:
        where_operands.append({"path": ["site_key"], "operator": "Equal", "valueText": site_value})
    if public_only:
        where_operands.append({"path": ["is_public"], "operator": "Equal", "valueBoolean": True})
    if not include_r18:
        where_operands.append({"path": ["is_r18"], "operator": "Equal", "valueBoolean": False})
    id_list = [int(v) for v in (target_ids or []) if int(v) > 0]
    if id_list:
        where_operands.append(
            {
                "operator": "Or",
                "operands": [
                    {"path": ["target_id"], "operator": "Equal", "valueInt": int(v)}
                    for v in id_list[:200]
                ],
            }
        )

    query = {
        "query": """
        query($vec:[Float!]!, $where:WhereFilter!, $limit:Int!){
          Get{
            AiFeatureDoc(nearVector:{vector:$vec}, where:$where, limit:$limit){
              doc_id
              target_id
              target_type
              title
              content
              _additional{distance}
            }
          }
        }
        """,
        "variables": {
            "vec": vector,
            "where": {"operator": "And", "operands": where_operands}
            if where_operands
            else {"path": ["target_id"], "operator": "GreaterThanEqual", "valueInt": 0},
            "limit": max(1, int(limit)),
        },
    }

    with httpx.Client(timeout=WEAVIATE_TIMEOUT_SEC) as client:
        res = client.post(f"{WEAVIATE_URL}/v1/graphql", json=query)
        res.raise_for_status()
        data = res.json()
    hits = (((data.get("data") or {}).get("Get") or {}).get(WEAVIATE_FEATURE_CLASS) or [])

    out: list[dict[str, Any]] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        try:
            target_id = int(hit.get("target_id"))
        except Exception:
            continue
        additional = hit.get("_additional") if isinstance(hit.get("_additional"), dict) else {}
        try:
            distance = float(additional.get("distance", 1.0))
        except Exception:
            distance = 1.0
        out.append(
            {
                "doc_id": str(hit.get("doc_id") or ""),
                "target_id": target_id,
                "target_type": str(hit.get("target_type") or ""),
                "title": str(hit.get("title") or ""),
                "content": str(hit.get("content") or ""),
                "distance": distance,
            }
        )
    return out


def bm25_search_feature_docs(
    query_text: str,
    *,
    feature: str | None,
    site_key: str | None,
    limit: int,
    target_ids: list[int] | None = None,
    include_r18: bool = False,
    public_only: bool = True,
) -> list[dict[str, Any]]:
    text_value = str(query_text or "").strip()
    if not text_value:
        return []

    where_operands: list[dict[str, Any]] = []
    feature_value = str(feature or "").strip()
    if feature_value:
        where_operands.append({"path": ["feature"], "operator": "Equal", "valueText": feature_value})
    site_value = str(site_key or "").strip()
    if site_value:
        where_operands.append({"path": ["site_key"], "operator": "Equal", "valueText": site_value})
    if public_only:
        where_operands.append({"path": ["is_public"], "operator": "Equal", "valueBoolean": True})
    if not include_r18:
        where_operands.append({"path": ["is_r18"], "operator": "Equal", "valueBoolean": False})
    id_list = [int(v) for v in (target_ids or []) if int(v) > 0]
    if id_list:
        where_operands.append(
            {
                "operator": "Or",
                "operands": [
                    {"path": ["target_id"], "operator": "Equal", "valueInt": int(v)}
                    for v in id_list[:200]
                ],
            }
        )

    query = {
        "query": """
        query($q:String!, $where:WhereFilter!, $limit:Int!){
          Get{
            AiFeatureDoc(
              bm25:{query:$q, properties:["title","content"]},
              where:$where,
              limit:$limit
            ){
              doc_id
              target_id
              target_type
              title
              content
              _additional{score}
            }
          }
        }
        """,
        "variables": {
            "q": text_value,
            "where": {"operator": "And", "operands": where_operands}
            if where_operands
            else {"path": ["target_id"], "operator": "GreaterThanEqual", "valueInt": 0},
            "limit": max(1, int(limit)),
        },
    }

    with httpx.Client(timeout=WEAVIATE_TIMEOUT_SEC) as client:
        res = client.post(f"{WEAVIATE_URL}/v1/graphql", json=query)
        res.raise_for_status()
        data = res.json()
    hits = (((data.get("data") or {}).get("Get") or {}).get(WEAVIATE_FEATURE_CLASS) or [])

    out: list[dict[str, Any]] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        try:
            target_id = int(hit.get("target_id"))
        except Exception:
            continue
        additional = hit.get("_additional") if isinstance(hit.get("_additional"), dict) else {}
        try:
            score = float(additional.get("score", 0.0))
        except Exception:
            score = 0.0
        out.append(
            {
                "doc_id": str(hit.get("doc_id") or ""),
                "target_id": target_id,
                "target_type": str(hit.get("target_type") or ""),
                "title": str(hit.get("title") or ""),
                "content": str(hit.get("content") or ""),
                "score": score,
            }
        )
    return out


def scan_feature_docs(
    *,
    feature: str | None,
    site_key: str | None,
    limit: int = 400,
    target_ids: list[int] | None = None,
    include_r18: bool = False,
    public_only: bool = False,
) -> list[dict[str, Any]]:
    with httpx.Client(timeout=WEAVIATE_TIMEOUT_SEC) as client:
        res = client.get(
            f"{WEAVIATE_URL}/v1/objects",
            params={"class": WEAVIATE_FEATURE_CLASS, "limit": max(1, int(limit))},
        )
        res.raise_for_status()
        data = res.json()
    objs = data.get("objects") or []
    id_set = {int(v) for v in (target_ids or []) if int(v) > 0}
    feature_value = str(feature or "").strip()
    site_value = str(site_key or "").strip()
    out: list[dict[str, Any]] = []
    for obj in objs:
        if not isinstance(obj, dict):
            continue
        props = obj.get("properties") if isinstance(obj.get("properties"), dict) else {}
        if feature_value and str(props.get("feature") or "").strip() != feature_value:
            continue
        if site_value and str(props.get("site_key") or "").strip() != site_value:
            continue
        if public_only and not bool(props.get("is_public", False)):
            continue
        if not include_r18 and bool(props.get("is_r18", False)):
            continue
        try:
            tid = int(props.get("target_id"))
        except Exception:
            continue
        if id_set and tid not in id_set:
            continue
        out.append(
            {
                "doc_id": str(props.get("doc_id") or ""),
                "target_id": tid,
                "target_type": str(props.get("target_type") or ""),
                "title": str(props.get("title") or ""),
                "content": str(props.get("content") or ""),
            }
        )
    return out
