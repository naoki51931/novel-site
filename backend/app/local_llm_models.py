from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GenerationConfig:
    temperature: float = 0.7
    top_p: float = 0.85
    top_k: int = 40
    repeat_penalty: float = 1.08
    max_tokens: int = 1500
    context_window: int = 32768


@dataclass(frozen=True)
class LocalModelDefinition:
    model_id: str
    label_ja: str
    label_en: str
    repo_id: str
    gguf_filename: str
    chat_template: str
    generation: GenerationConfig
    model_path_env: str
    quantization: str = "Q4_K_M"
    file_size_gb: float | None = None
    ram_required_gb: float | None = None
    base_model_id: str | None = None
    notes: str = ""
    license: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)


LOCAL_MODELS: dict[str, LocalModelDefinition] = {
    "local-doujinshi-14b": LocalModelDefinition(
        model_id="local-doujinshi-14b",
        label_ja="Doujinshi 14B（ローカルCPU）",
        label_en="Doujinshi 14B (Local CPU)",
        repo_id="puwaer/Doujinshi-14b-roleplay-gguf",
        base_model_id="puwaer/Doujinshi-14b-roleplay",
        gguf_filename="Doujinshi-14b-roleplay-Q4_K_M.gguf",
        chat_template="tokenizer",
        generation=GenerationConfig(temperature=0.7, top_p=0.8, top_k=20, repeat_penalty=1.08, max_tokens=1500, context_window=32768),
        model_path_env="LOCAL_LLM_DOUJINSHI_MODEL_PATH",
        file_size_gb=8.38,
        ram_required_gb=13.0,
        notes="Qwen3-14B based Japanese roleplay/novel model. Apache-2.0 model card; sensitive/R18 training data requires operational policy review.",
        license="apache-2.0",
        tags=("local", "cpu", "gguf", "japanese", "roleplay", "novel"),
    ),
    "local-llama3-jprp-8b": LocalModelDefinition(
        model_id="local-llama3-jprp-8b",
        label_ja="Llama 3 JPRP 8B（ローカルCPU）",
        label_en="Llama 3 JPRP 8B (Local CPU)",
        repo_id="mradermacher/Llama-3-JPRP-NSFW-8B-GGUF",
        base_model_id="melt-adzuki/Llama-3-JPRP-NSFW-8B",
        gguf_filename="Llama-3-JPRP-NSFW-8B.Q4_K_M.gguf",
        chat_template="llama-3",
        generation=GenerationConfig(temperature=0.7, top_p=0.9, top_k=40, repeat_penalty=1.08, max_tokens=1200, context_window=8192),
        model_path_env="LOCAL_LLM_JPRP_MODEL_PATH",
        file_size_gb=4.58,
        ram_required_gb=8.0,
        notes="Llama 3 based Japanese RP model. Commercial service use must follow the Meta Llama 3 license terms.",
        license="llama3",
        tags=("local", "cpu", "gguf", "japanese", "roleplay", "lightweight"),
    ),
    "local-qwen3-8b-nsfw-jp": LocalModelDefinition(
        model_id="local-qwen3-8b-nsfw-jp",
        label_ja="Qwen3 8B JP（ローカルCPU）",
        label_en="Qwen3 8B JP (Local CPU)",
        repo_id="mradermacher/Qwen3-8B-NSFW-JP-GGUF",
        base_model_id="Aratako/Qwen3-8B-NSFW-JP",
        gguf_filename="Qwen3-8B-NSFW-JP.Q4_K_M.gguf",
        chat_template="tokenizer",
        generation=GenerationConfig(temperature=0.7, top_p=0.8, top_k=20, repeat_penalty=1.08, max_tokens=1200, context_window=32768),
        model_path_env="LOCAL_LLM_QWEN_MODEL_PATH",
        file_size_gb=4.68,
        ram_required_gb=8.0,
        notes="Qwen3-8B Japanese NSFW model, used as comparison model. MIT model card.",
        license="mit",
        tags=("local", "cpu", "gguf", "japanese", "qwen", "comparison"),
    ),
}


LOCAL_MODEL_IDS = frozenset(LOCAL_MODELS.keys())


def is_local_model(model_id: str | None) -> bool:
    return str(model_id or "").strip() in LOCAL_MODEL_IDS


def get_local_model(model_id: str | None) -> LocalModelDefinition:
    normalized = str(model_id or "").strip()
    try:
        return LOCAL_MODELS[normalized]
    except KeyError as exc:
        raise ValueError(f"unknown local model: {normalized}") from exc


def public_local_models() -> list[dict]:
    return [
        {
            "id": model.model_id,
            "label_ja": model.label_ja,
            "label_en": model.label_en,
            "provider": "local",
            "loader": "llama-cpp-python",
            "repo_id": model.repo_id,
            "base_model_id": model.base_model_id,
            "gguf_filename": model.gguf_filename,
            "quantization": model.quantization,
            "file_size_gb": model.file_size_gb,
            "ram_required_gb": model.ram_required_gb,
            "license": model.license,
            "tags": list(model.tags),
        }
        for model in LOCAL_MODELS.values()
    ]
