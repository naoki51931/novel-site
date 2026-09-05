from __future__ import annotations

import asyncio
import gc
import json
import os
import resource
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psutil
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    label: str
    repo_id: str
    base_model_id: str
    gguf_filename: str
    model_path_env: str
    chat_template: str
    license: str
    quantization: str = "Q4_K_M"
    context_window: int = 32768
    max_tokens: int = 1500
    temperature: float = 0.7
    top_p: float = 0.85
    top_k: int = 40
    repeat_penalty: float = 1.08
    file_size_gb: float | None = None
    ram_required_gb: float | None = None


LOCAL_MODELS: dict[str, ModelConfig] = {
    "local-doujinshi-14b": ModelConfig(
        model_id="local-doujinshi-14b",
        label="Doujinshi 14B",
        repo_id="puwaer/Doujinshi-14b-roleplay-gguf",
        base_model_id="puwaer/Doujinshi-14b-roleplay",
        gguf_filename="Doujinshi-14b-roleplay-Q4_K_M.gguf",
        model_path_env="LOCAL_LLM_DOUJINSHI_MODEL_PATH",
        chat_template="tokenizer",
        license="apache-2.0",
        context_window=32768,
        max_tokens=1500,
        temperature=0.7,
        top_p=0.8,
        top_k=20,
        file_size_gb=8.38,
        ram_required_gb=13.0,
    ),
    "local-llama3-jprp-8b": ModelConfig(
        model_id="local-llama3-jprp-8b",
        label="Llama 3 JPRP 8B",
        repo_id="mradermacher/Llama-3-JPRP-NSFW-8B-GGUF",
        base_model_id="melt-adzuki/Llama-3-JPRP-NSFW-8B",
        gguf_filename="Llama-3-JPRP-NSFW-8B.Q4_K_M.gguf",
        model_path_env="LOCAL_LLM_JPRP_MODEL_PATH",
        chat_template="llama-3",
        license="llama3",
        context_window=8192,
        max_tokens=1200,
        temperature=0.7,
        top_p=0.9,
        top_k=40,
        file_size_gb=4.58,
        ram_required_gb=8.0,
    ),
    "local-qwen3-8b-nsfw-jp": ModelConfig(
        model_id="local-qwen3-8b-nsfw-jp",
        label="Qwen3 8B JP",
        repo_id="mradermacher/Qwen3-8B-NSFW-JP-GGUF",
        base_model_id="Aratako/Qwen3-8B-NSFW-JP",
        gguf_filename="Qwen3-8B-NSFW-JP.Q4_K_M.gguf",
        model_path_env="LOCAL_LLM_QWEN_MODEL_PATH",
        chat_template="tokenizer",
        license="mit",
        context_window=32768,
        max_tokens=1200,
        temperature=0.7,
        top_p=0.8,
        top_k=20,
        file_size_gb=4.68,
        ram_required_gb=8.0,
    ),
}


class GenerateRequest(BaseModel):
    model: str
    messages: list[dict[str, str]]
    generation: dict[str, Any] | None = None
    strict_json: bool = False


class JobCreateResponse(BaseModel):
    job_id: str
    status: str
    queue_position: int


class LoadedModel:
    def __init__(self, config: ModelConfig, llm: Any, load_seconds: float):
        self.config = config
        self.llm = llm
        self.load_seconds = load_seconds


class LocalJob:
    def __init__(self, request: GenerateRequest):
        self.job_id = str(uuid.uuid4())
        self.request = request
        self.status = "queued"
        self.queue_position: int | None = None
        self.created_at = time.time()
        self.started_at: float | None = None
        self.completed_at: float | None = None
        self.result: dict[str, Any] | None = None
        self.error: str | None = None
        self.cancel_requested = False


app = FastAPI(title="Lexis Local CPU LLM")
_loaded: LoadedModel | None = None
_jobs: dict[str, LocalJob] = {}
_queue: asyncio.Queue[str] = asyncio.Queue()
_worker_task: asyncio.Task | None = None
_current_job_id: str | None = None


def _log(event: str, payload: dict[str, Any]) -> None:
    print(f"[INFO] {event} " + json.dumps(payload, ensure_ascii=False), flush=True)


def _memory_usage_mb() -> dict[str, int]:
    proc = psutil.Process(os.getpid())
    rss = int(proc.memory_info().rss / 1024 / 1024)
    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    return {"rss_mb": rss, "peak_rss_mb": peak}


def _default_model_path(config: ModelConfig) -> Path:
    base = Path(os.getenv("LOCAL_LLM_MODELS_DIR", "/models"))
    dirs = {
        "local-doujinshi-14b": "doujinshi-14b",
        "local-llama3-jprp-8b": "llama3-jprp-8b",
        "local-qwen3-8b-nsfw-jp": "qwen3-8b-nsfw-jp",
    }
    return base / dirs[config.model_id] / config.gguf_filename


def model_path(config: ModelConfig) -> Path:
    explicit = os.getenv(config.model_path_env)
    return Path(explicit).expanduser() if explicit else _default_model_path(config)


def model_public(config: ModelConfig) -> dict[str, Any]:
    path = model_path(config)
    data = asdict(config)
    data.update({"model_path_env": config.model_path_env, "path": str(path), "available": path.is_file()})
    return data


def _threads() -> int:
    cpu = os.cpu_count() or 4
    try:
        value = int(os.getenv("LOCAL_LLM_THREADS", str(max(1, cpu - 1))))
    except Exception:
        value = max(1, cpu - 1)
    return max(1, min(value, cpu * 2))


def _ctx_size(config: ModelConfig) -> int:
    try:
        value = int(os.getenv("LOCAL_LLM_CONTEXT_SIZE", str(config.context_window)))
    except Exception:
        value = config.context_window
    return max(1024, min(value, config.context_window))


def unload_model() -> None:
    global _loaded
    if _loaded is None:
        return
    _log("local_llm_unload", {"model": _loaded.config.model_id, **_memory_usage_mb()})
    del _loaded.llm
    _loaded = None
    gc.collect()


def load_model(model_id: str) -> LoadedModel:
    global _loaded
    if model_id not in LOCAL_MODELS:
        raise HTTPException(status_code=400, detail=f"unknown local model: {model_id}")
    if _loaded is not None and _loaded.config.model_id == model_id:
        return _loaded

    config = LOCAL_MODELS[model_id]
    path = model_path(config)
    if not path.is_file():
        raise HTTPException(status_code=503, detail=f"model file is not configured or missing: {config.model_path_env}={path}")

    unload_model()
    started = time.monotonic()
    _log("local_llm_load_start", {"model": model_id, "path": str(path), "threads": _threads(), "ctx": _ctx_size(config), **_memory_usage_mb()})
    try:
        from llama_cpp import Llama

        llm = Llama(
            model_path=str(path),
            n_ctx=_ctx_size(config),
            n_threads=_threads(),
            n_gpu_layers=0,
            verbose=bool(int(os.getenv("LOCAL_LLM_VERBOSE", "0") or "0")),
        )
    except Exception as exc:
        gc.collect()
        _log("local_llm_load_error", {"model": model_id, "error": f"{type(exc).__name__}: {exc}", **_memory_usage_mb()})
        raise HTTPException(status_code=500, detail=f"model load failed: {type(exc).__name__}: {exc}") from exc

    loaded = LoadedModel(config, llm, time.monotonic() - started)
    _loaded = loaded
    _log("local_llm_load_success", {"model": model_id, "load_seconds": round(loaded.load_seconds, 3), **_memory_usage_mb()})
    return loaded


def _safe_generation(config: ModelConfig, override: dict[str, Any] | None) -> dict[str, Any]:
    override = override or {}

    def number(name: str, default: float, lo: float, hi: float) -> float:
        try:
            value = float(override.get(name, default))
        except Exception:
            value = default
        return max(lo, min(hi, value))

    def integer(name: str, default: int, lo: int, hi: int) -> int:
        try:
            value = int(override.get(name, default))
        except Exception:
            value = default
        return max(lo, min(hi, value))

    seed_raw = override.get("seed", os.getenv("LOCAL_LLM_SEED", -1))
    try:
        seed = int(seed_raw)
    except Exception:
        seed = -1
    return {
        "max_tokens": integer("max_tokens", config.max_tokens, 64, 4096),
        "temperature": number("temperature", config.temperature, 0.0, 2.0),
        "top_p": number("top_p", config.top_p, 0.0, 1.0),
        "top_k": integer("top_k", config.top_k, 0, 200),
        "repeat_penalty": number("repeat_penalty", config.repeat_penalty, 0.8, 2.0),
        "seed": seed,
    }


def _count_tokens(llm: Any, messages: list[dict[str, str]]) -> int | None:
    try:
        prompt = "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)
        return len(llm.tokenize(prompt.encode("utf-8"), add_bos=False))
    except Exception:
        return None


def _trim_messages(messages: list[dict[str, str]], approx_budget_chars: int) -> list[dict[str, str]]:
    total = sum(len(str(m.get("content") or "")) for m in messages)
    if total <= approx_budget_chars:
        return messages
    trimmed = [dict(m) for m in messages]
    for msg in reversed(trimmed):
        if msg.get("role") != "user":
            continue
        content = str(msg.get("content") or "")
        keep = max(2000, approx_budget_chars - (total - len(content)))
        previous_marker = "PREVIOUS TEXT"
        instruction_marker = "USER INSTRUCTION"
        if previous_marker in content and instruction_marker in content:
            head, rest = content.split(previous_marker, 1)
            previous, instruction = rest.split(instruction_marker, 1)
            msg["content"] = f"{head}{previous_marker}\n{previous[-keep:].strip()}\n\n{instruction_marker}{instruction}"
        else:
            msg["content"] = content[-keep:]
        return trimmed
    return trimmed


def generate_sync(req: GenerateRequest) -> dict[str, Any]:
    loaded = load_model(req.model)
    config = loaded.config
    gen = _safe_generation(config, req.generation)
    approx_chars = max(2000, (_ctx_size(config) - gen["max_tokens"] - 256) * 2)
    messages = _trim_messages(req.messages, approx_chars)
    if req.strict_json:
        messages = [*messages, {"role": "user", "content": '出力は必ずJSON 1個のみ。形式: {"title":"タイトル","body":"本文"}'}]

    input_tokens = _count_tokens(loaded.llm, messages)
    started = time.monotonic()
    _log("local_llm_inference_start", {"model": req.model, "input_tokens": input_tokens, "max_tokens": gen["max_tokens"], **_memory_usage_mb()})
    try:
        response = loaded.llm.create_chat_completion(
            messages=messages,
            max_tokens=gen["max_tokens"],
            temperature=gen["temperature"],
            top_p=gen["top_p"],
            top_k=gen["top_k"],
            repeat_penalty=gen["repeat_penalty"],
            seed=gen["seed"],
        )
    except TypeError:
        response = loaded.llm.create_chat_completion(
            messages=messages,
            max_tokens=gen["max_tokens"],
            temperature=gen["temperature"],
            top_p=gen["top_p"],
            repeat_penalty=gen["repeat_penalty"],
            seed=gen["seed"],
        )
    elapsed = time.monotonic() - started
    choice = (response.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    text = str(message.get("content") or choice.get("text") or "").strip()
    usage = response.get("usage") or {}
    output_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    if output_tokens is None:
        try:
            output_tokens = len(loaded.llm.tokenize(text.encode("utf-8"), add_bos=False))
        except Exception:
            output_tokens = None
    tokens_per_sec = (float(output_tokens) / elapsed) if output_tokens and elapsed > 0 else None
    _log(
        "local_llm_inference_end",
        {
            "model": req.model,
            "input_tokens": input_tokens or usage.get("prompt_tokens"),
            "output_tokens": output_tokens,
            "generation_time": round(elapsed, 3),
            "tokens_per_sec": round(tokens_per_sec, 3) if tokens_per_sec else None,
            **_memory_usage_mb(),
        },
    )
    return {
        "text": text,
        "input_tokens": input_tokens or usage.get("prompt_tokens"),
        "output_tokens": output_tokens,
        "total_tokens": total_tokens or ((input_tokens or 0) + (output_tokens or 0) if output_tokens is not None else None),
        "generation_time": elapsed,
        "tokens_per_sec": tokens_per_sec,
        "load_seconds": loaded.load_seconds,
        "memory": _memory_usage_mb(),
    }


def _queue_position(job_id: str) -> int | None:
    queued = list(_queue._queue)  # status API only; approximate but stable enough for display.
    try:
        return queued.index(job_id)
    except ValueError:
        return None


async def worker() -> None:
    global _current_job_id
    while True:
        job_id = await _queue.get()
        job = _jobs.get(job_id)
        if job is None:
            _queue.task_done()
            continue
        if job.cancel_requested:
            job.status = "cancelled"
            job.completed_at = time.time()
            _queue.task_done()
            continue
        _current_job_id = job_id
        job.status = "running"
        job.started_at = time.time()
        try:
            job.result = await asyncio.to_thread(generate_sync, job.request)
            job.status = "completed"
        except Exception as exc:
            job.error = str(getattr(exc, "detail", None) or exc)
            job.status = "failed"
            _log("local_llm_job_error", {"job_id": job_id, "model": job.request.model, "error": job.error, **_memory_usage_mb()})
        finally:
            job.completed_at = time.time()
            _current_job_id = None
            _queue.task_done()


@app.on_event("startup")
async def startup() -> None:
    global _worker_task
    _worker_task = asyncio.create_task(worker())
    preload = (os.getenv("LOCAL_LLM_PRELOAD_MODEL") or "").strip()
    _log("local_llm_startup", {"threads": _threads(), "preload": preload or None, **_memory_usage_mb()})
    if preload:
        try:
            await asyncio.to_thread(load_model, preload)
        except Exception as exc:
            _log("local_llm_preload_error", {"model": preload, "error": str(exc)})


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "loaded_model": _loaded.config.model_id if _loaded else None, **_memory_usage_mb()}


@app.get("/models")
async def models() -> dict[str, Any]:
    return {"models": [model_public(model) for model in LOCAL_MODELS.values()]}


@app.get("/status")
async def status() -> dict[str, Any]:
    return {
        "loaded_model": _loaded.config.model_id if _loaded else None,
        "available_models": [model_public(model) for model in LOCAL_MODELS.values()],
        "running_jobs": 1 if _current_job_id else 0,
        "queued_jobs": _queue.qsize(),
        "current_job_id": _current_job_id,
        "memory_usage_mb": _memory_usage_mb()["rss_mb"],
        **_memory_usage_mb(),
    }


@app.post("/unload")
async def unload() -> dict[str, Any]:
    unload_model()
    return {"ok": True, **_memory_usage_mb()}


@app.post("/generate")
async def generate(req: GenerateRequest) -> dict[str, Any]:
    return await asyncio.to_thread(generate_sync, req)


@app.post("/jobs", response_model=JobCreateResponse)
async def create_job(req: GenerateRequest) -> JobCreateResponse:
    if req.model not in LOCAL_MODELS:
        raise HTTPException(status_code=400, detail=f"unknown local model: {req.model}")
    path = model_path(LOCAL_MODELS[req.model])
    if not path.is_file():
        raise HTTPException(status_code=503, detail=f"model file is not configured or missing: {LOCAL_MODELS[req.model].model_path_env}={path}")
    job = LocalJob(req)
    _jobs[job.job_id] = job
    await _queue.put(job.job_id)
    position = _queue_position(job.job_id)
    job.queue_position = position
    return JobCreateResponse(job_id=job.job_id, status=job.status, queue_position=position if position is not None else 0)


@app.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    pos = _queue_position(job_id)
    status_value = "cancelled" if job.cancel_requested and job.status == "queued" else job.status
    return {
        "job_id": job.job_id,
        "status": status_value,
        "queue_position": pos if pos is not None else (0 if job.status == "running" else None),
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "result": job.result,
        "error": job.error,
    }


@app.delete("/jobs/{job_id}")
async def cancel_job(job_id: str) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job.status == "queued":
        job.cancel_requested = True
        return {"ok": True, "status": "cancel_requested"}
    if job.status == "running":
        job.cancel_requested = True
        return {"ok": True, "status": "cancel_requested", "detail": "running llama.cpp generation cannot be interrupted immediately"}
    return {"ok": True, "status": job.status}
