from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
import base64
import os
import httpx
from sqlalchemy.orm import Session

from ..ai_novel import AINovelJobCreateResponse, AINovelRequest
from ..database import get_db
from ..features.ai_feature_service import create_ai_novel_job_service
from ..services.ai_novel_service import create_ai_episode_continue_job_service

router = APIRouter()


@router.post('/api/ai/novels/generate_job')
async def create_ai_novel_job(
    req: AINovelRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    return await create_ai_novel_job_service(
        req=req,
        request=request,
        response=response,
        db=db,
    )


@router.post("/api/ai/episodes/{episode_id}/continue_job", response_model=AINovelJobCreateResponse)
async def create_ai_episode_continue_job(
    episode_id: int,
    req: AINovelRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    return await create_ai_episode_continue_job_service(
        episode_id=episode_id,
        req=req,
        request=request,
        db=db,
    )

@router.post("/api/ai/novels/images/describe")
async def describe_ai_novel_images(files: list[UploadFile] = File(...)):
    """Describe up to 20 images for use as novel-generation reference material."""
    if not files or len(files) > 20:
        raise HTTPException(status_code=400, detail="画像は1〜20枚指定してください。")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="画像認識サービスが設定されていません。")
    descriptions = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        for index, file in enumerate(files):
            mime = (file.content_type or "").lower()
            if mime not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
                raise HTTPException(status_code=400, detail="jpg/png/webp/gifのみ対応しています。")
            data = await file.read(10 * 1024 * 1024 + 1)
            if not data or len(data) > 10 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="画像は1枚10MB以下にしてください。")
            image_url = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
            try:
                response = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": os.getenv("AI_CHAT_IMAGE_CAPTION_MODEL", "gpt-4.1-mini"),
                        "input": [{"role": "user", "content": [
                            {"type": "input_text", "text": "小説執筆の参考として、画像の人物、服装、背景、状況を日本語で具体的に説明してください。見えない事実は推測しないでください。"},
                            {"type": "input_image", "image_url": image_url},
                        ]}],
                        "max_output_tokens": 350,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                caption = "\n".join(
                    part.get("text", "")
                    for item in payload.get("output", [])
                    for part in item.get("content", [])
                    if part.get("type") == "output_text"
                ).strip()
                if not caption:
                    raise ValueError("画像の説明を取得できませんでした。")
                descriptions.append(caption)
            except (httpx.HTTPError, ValueError) as exc:
                raise HTTPException(status_code=502, detail=f"{index + 1}枚目の画像認識に失敗しました。") from exc
    return {"descriptions": descriptions}
