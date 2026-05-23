from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.ai_chat_service import (
    ai_chat_generate_image_service,
    ai_chat_service,
    ai_chat_auto_continue_service,
    ai_chat_character_anime_title_candidates_service,
    ai_chat_next_user_lines_service,
    augment_ai_chat_character_service,
    create_ai_chat_character_service,
    delete_ai_chat_message_image_service,
    delete_ai_chat_messages_from_point_service,
    delete_ai_chat_character_service,
    get_ai_chat_access_status_service,
    get_ai_chat_engagement_summary_service,
    get_ai_chat_latest_prompt_preview_service,
    import_ai_chat_messages_service,
    list_ai_chat_characters_service,
    list_ai_chat_messages_service,
    publish_ai_chat_character_service,
    update_ai_chat_character_service,
    upload_ai_chat_character_image_service,
    upload_ai_chat_message_images_service,
)


router = APIRouter()


def _parse_payload(model_cls, payload: dict):
    try:
        return model_cls(**payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

@router.get("/api/ai/chat/access")
def get_ai_chat_access_status(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    return get_ai_chat_access_status_service(request=request, response=response, db=db)

@router.post("/api/ai/chat/next_user_lines")
async def ai_chat_next_user_lines(
    req: dict,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    req_model = _parse_payload(legacy.AIChatNextLineSuggestRequest, req)
    return await ai_chat_next_user_lines_service(req=req_model, request=request, response=response, db=db)

@router.post("/api/ai/chat/generate_image")
async def ai_chat_generate_image(
    req: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    req_model = _parse_payload(legacy.AIChatImageGenerateRequest, req)
    return await ai_chat_generate_image_service(req=req_model, request=request, db=db)

@router.post("/api/ai/chat")
async def ai_chat(
    req: dict,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    req_model = _parse_payload(legacy.AIChatRequest, req)
    return await ai_chat_service(req=req_model, request=request, response=response, db=db)

@router.post("/api/ai/chat/auto_continue")
async def ai_chat_auto_continue(
    req: dict,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    req_model = _parse_payload(legacy.AIChatAutoContinueRequest, req)
    return await ai_chat_auto_continue_service(req=req_model, request=request, response=response, db=db)

@router.post("/api/ai/chat/character/augment")
async def augment_ai_chat_character(
    req: dict
):
    from .. import main as legacy
    req_model = _parse_payload(legacy.AIChatCharacterAugmentRequest, req)
    return await augment_ai_chat_character_service(req=req_model)

@router.post("/api/ai/chat/character/anime_title_candidates")
async def ai_chat_character_anime_title_candidates(
    req: dict
):
    from .. import main as legacy
    req_model = _parse_payload(legacy.AIChatAnimeTitleCandidatesRequest, req)
    return await ai_chat_character_anime_title_candidates_service(req=req_model)

@router.get("/api/ai/chat/characters")
def list_ai_chat_characters(
    request: Request,
    db: Session = Depends(get_db)
):
    return list_ai_chat_characters_service(request=request, db=db)

@router.post("/api/ai/chat/characters")
def create_ai_chat_character(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AIChatCharacterCreateRequest, payload)
    return create_ai_chat_character_service(payload=payload_model, request=request, db=db)

@router.put("/api/ai/chat/characters/{character_id}")
def update_ai_chat_character(
    character_id: int,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AIChatCharacterUpdateRequest, payload)
    return update_ai_chat_character_service(character_id=character_id, payload=payload_model, request=request, db=db)

@router.post("/api/ai/chat/characters/{character_id}/image")
async def upload_ai_chat_character_image(
    character_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    return await upload_ai_chat_character_image_service(
        character_id=character_id,
        request=request,
        file=file,
        db=db,
    )

@router.patch("/api/ai/chat/characters/{character_id}/publish")
def publish_ai_chat_character(
    character_id: int,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AIChatPublishRequest, payload)
    return publish_ai_chat_character_service(character_id=character_id, payload=payload_model, request=request, db=db)

@router.delete("/api/ai/chat/characters/{character_id}")
def delete_ai_chat_character(
    character_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    return delete_ai_chat_character_service(character_id=character_id, request=request, db=db)

@router.get("/api/ai/chat/characters/{character_id}/messages")
def list_ai_chat_messages(
    character_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    return list_ai_chat_messages_service(character_id=character_id, request=request, db=db)

@router.get("/api/ai/chat/characters/{character_id}/engagement_summary")
def get_ai_chat_engagement_summary(
    character_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    return get_ai_chat_engagement_summary_service(character_id=character_id, request=request, db=db)

@router.post("/api/ai/chat/characters/{character_id}/messages/import")
def import_ai_chat_messages(
    character_id: int,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AIChatMessageImportRequest, payload)
    return import_ai_chat_messages_service(
        character_id=character_id,
        payload=payload_model,
        request=request,
        db=db,
    )

@router.delete("/api/ai/chat/characters/{character_id}/messages/{message_id}")
def delete_ai_chat_messages_from_point(
    character_id: int,
    message_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    return delete_ai_chat_messages_from_point_service(
        character_id=character_id,
        message_id=message_id,
        request=request,
        db=db,
    )

@router.delete("/api/ai/chat/characters/{character_id}/messages/{message_id}/images/{image_index}")
def delete_ai_chat_message_image(
    character_id: int,
    message_id: int,
    image_index: int,
    request: Request,
    db: Session = Depends(get_db)
):
    return delete_ai_chat_message_image_service(
        character_id=character_id,
        message_id=message_id,
        image_index=image_index,
        request=request,
        db=db,
    )

@router.post("/api/ai/chat/characters/{character_id}/messages/images")
async def upload_ai_chat_message_images(
    character_id: int,
    request: Request,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    return await upload_ai_chat_message_images_service(
        character_id=character_id,
        request=request,
        files=files,
        db=db,
    )

@router.get("/api/ai/chat/characters/{character_id}/latest_prompt_preview")
def get_ai_chat_latest_prompt_preview(
    character_id: int,
    request: Request,
    db: Session = Depends(get_db),
    r18: bool = Query(default=False)
):
    return get_ai_chat_latest_prompt_preview_service(
        character_id=character_id,
        request=request,
        db=db,
        r18=r18,
    )
