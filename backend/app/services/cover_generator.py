import base64
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from openai import OpenAI


@dataclass
class CoverImageConfig:
    api_key: str
    model: str
    size: str
    quality: str
    output_format: str
    upload_dir: str
    public_base_url: str
    timeout_seconds: float = 45.0


def _clean_text(value: str | None, max_len: int) -> str:
    raw = str(value or "").strip()
    if len(raw) > max_len:
        raw = raw[:max_len]
    return raw


def build_cover_prompt(
    *,
    title: str,
    catch_copy: str,
    genre: str | None,
    mood: str | None,
    color_theme: str | None,
    character_count: int | None,
    extra_prompt: str,
) -> str:
    genre_v = _clean_text(genre, 100) or "unspecified"
    mood_v = _clean_text(mood, 100) or "unspecified"
    color_v = _clean_text(color_theme, 100) or "unspecified"
    title_v = _clean_text(title, 300) or "untitled"
    catch_v = _clean_text(catch_copy, 500) or "none"
    extra_v = _clean_text(extra_prompt, 1000) or "none"
    count_v = character_count if character_count is not None else 0
    composition_hint = (
        "Keep composition simple with silhouettes and environmental storytelling."
        if count_v >= 3
        else "Allow one elegant focal point with generous negative space."
    )
    return (
        "You are creating a polished vertical novel cover background illustration.\n"
        "No text, no letters, no title, no logo, no watermark, no signature.\n"
        "Create a clean, high-quality, emotionally evocative cover art background for a Japanese web novel.\n"
        f"Genre: {genre_v}\n"
        f"Mood: {mood_v}\n"
        f"Color theme: {color_v}\n"
        f"Character count: {count_v}\n"
        f"Story title for inspiration only: {title_v}\n"
        f"Catch copy for inspiration only: {catch_v}\n"
        f"Additional direction: {extra_v}\n"
        "The composition should leave safe empty space for overlaying title and author text later.\n"
        "Vertical composition, elegant focal point, commercially usable, detailed but not cluttered.\n"
        f"{composition_hint}"
    )


def _image_extension(output_format: str) -> str:
    fmt = (output_format or "jpeg").strip().lower()
    if fmt in ("jpg", "jpeg"):
        return "jpeg"
    if fmt == "webp":
        return "webp"
    raise ValueError("output_format must be jpeg or webp")


def _extract_b64_image(response: Any) -> str:
    data = getattr(response, "data", None) or []
    if not data:
        raise ValueError("OpenAI image response is empty")
    item = data[0]
    b64 = getattr(item, "b64_json", None)
    if not b64 and isinstance(item, dict):
        b64 = item.get("b64_json")
    if not b64:
        raise ValueError("OpenAI image response did not include base64 image data")
    return str(b64)


def save_base64_image(
    *,
    image_b64: str,
    upload_dir: str,
    output_format: str,
    now: datetime | None = None,
) -> str:
    ext = _image_extension(output_format)
    moment = now or datetime.utcnow()
    year = f"{moment.year:04d}"
    month = f"{moment.month:02d}"
    target_dir = os.path.join(upload_dir, year, month)
    os.makedirs(target_dir, exist_ok=True)
    filename = f"{uuid.uuid4()}.{ext}"
    abs_path = os.path.join(target_dir, filename)
    binary = base64.b64decode(image_b64)
    with open(abs_path, "wb") as f:
        f.write(binary)
    return f"/uploads/covers/{year}/{month}/{filename}"


def build_public_image_url(public_base_url: str, image_path: str) -> str:
    base = (public_base_url or "").rstrip("/")
    if not base:
        return image_path
    return f"{base}{image_path}"


def generate_cover_image(
    *,
    prompt: str,
    config: CoverImageConfig,
) -> dict[str, str]:
    client = OpenAI(api_key=config.api_key, timeout=config.timeout_seconds)
    response = client.images.generate(
        model=config.model,
        prompt=prompt,
        size=config.size,
        quality=config.quality,
        output_format=config.output_format,
    )
    b64 = _extract_b64_image(response)
    image_path = save_base64_image(
        image_b64=b64,
        upload_dir=config.upload_dir,
        output_format=config.output_format,
    )
    image_url = build_public_image_url(config.public_base_url, image_path)
    return {"image_path": image_path, "image_url": image_url}
