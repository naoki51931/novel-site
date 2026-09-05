import pytest
from fastapi import HTTPException

from app.ai_novel import AINovelRequest, _assert_r18_adult_characters, _clean_local_llm_text, _merge_generation_config, list_ai_novel_models
from app.local_llm_models import LOCAL_MODELS, get_local_model, is_local_model


def test_local_model_list_contains_requested_models():
    data = list_ai_novel_models()
    ids = {item["id"] for item in data["local_models"]}
    assert {"local-doujinshi-14b", "local-llama3-jprp-8b", "local-qwen3-8b-nsfw-jp"}.issubset(ids)
    assert data["default_model"] == "local-qwen3-8b-nsfw-jp"


def test_local_model_metadata_uses_gguf_cpu_loader():
    for model in LOCAL_MODELS.values():
        assert model.gguf_filename.endswith(".gguf")
        assert model.quantization == "Q4_K_M"
        assert model.model_path_env.startswith("LOCAL_LLM_")
    public = list_ai_novel_models()["local_models"]
    assert all(item["loader"] == "llama-cpp-python" for item in public)


def test_unknown_local_model_is_rejected():
    assert not is_local_model("local-missing")
    with pytest.raises(ValueError):
        get_local_model("local-missing")


def test_generation_config_clamps_values():
    req = AINovelRequest(
        model="local-qwen3-8b-nsfw-jp",
        max_new_tokens=999999,
        temperature=9,
        top_p=2,
        top_k=999,
        repetition_penalty=9,
    )
    cfg = _merge_generation_config(req)
    assert cfg["max_tokens"] == 4096
    assert cfg["temperature"] == 2.0
    assert cfg["top_p"] == 1.0
    assert cfg["top_k"] == 200
    assert cfg["repeat_penalty"] == 2.0


def test_generation_config_expands_for_numeric_local_length():
    cfg = _merge_generation_config(AINovelRequest(model="local-qwen3-8b-nsfw-jp", length="2000"))
    assert cfg["max_tokens"] >= 2750


def test_clean_local_llm_text_removes_empty_think_tag():
    assert _clean_local_llm_text("<think>\n\n</think>\n\n本文") == "本文"


def test_r18_requires_adult_characters():
    with pytest.raises(HTTPException):
        _assert_r18_adult_characters(AINovelRequest(model="local-doujinshi-14b", r18=True, characters="高校生"))
    _assert_r18_adult_characters(AINovelRequest(model="local-doujinshi-14b", r18=True, characters="25歳の社会人"))
