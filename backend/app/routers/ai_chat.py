from fastapi import APIRouter

from ..features.ai_chat_public_characters_routes import router as ai_chat_public_characters_router
from ..features.ai_chat_public_interactions_routes import router as ai_chat_public_interactions_router
from ..features.ai_memory_backfill_routes import router as ai_memory_backfill_router
from ..features.ai_memory_items_deactivate_routes import router as ai_memory_items_deactivate_router
from ..features.ai_memory_items_delete_routes import router as ai_memory_items_delete_router
from ..features.ai_memory_items_list_routes import router as ai_memory_items_list_router


router = APIRouter()
router.include_router(ai_chat_public_characters_router)
router.include_router(ai_chat_public_interactions_router)
router.include_router(ai_memory_items_list_router)
router.include_router(ai_memory_items_deactivate_router)
router.include_router(ai_memory_items_delete_router)
router.include_router(ai_memory_backfill_router)

# BEGIN AUTO-GENERATED ROUTER WRAPPERS: AI_CHAT
from fastapi import Body, Depends, Header, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..database import get_db


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
    from .. import main as legacy
    return legacy.get_ai_chat_access_status(request=request, response=response, db=db)

@router.post("/api/ai/chat/next_user_lines")
async def ai_chat_next_user_lines(
    req: dict,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    req_model = _parse_payload(legacy.AIChatNextLineSuggestRequest, req)
    return await legacy.ai_chat_next_user_lines(req=req_model, request=request, response=response, db=db)

@router.post("/api/ai/chat/generate_image")
async def ai_chat_generate_image(
    req: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    req_model = _parse_payload(legacy.AIChatImageGenerateRequest, req)
    return await legacy.ai_chat_generate_image(req=req_model, request=request, db=db)

@router.post("/api/ai/chat/auto_continue")
async def ai_chat_auto_continue(
    req: dict,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    req_model = _parse_payload(legacy.AIChatAutoContinueRequest, req)
    return await legacy.ai_chat_auto_continue(req=req_model, request=request, response=response, db=db)

@router.post("/api/ai/chat/character/augment")
async def augment_ai_chat_character(
    req: dict
):
    from .. import main as legacy
    req_model = _parse_payload(legacy.AIChatCharacterAugmentRequest, req)
    return await legacy.augment_ai_chat_character(req=req_model)

@router.get("/api/ai/chat/characters")
def list_ai_chat_characters(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.list_ai_chat_characters(request=request, db=db)

@router.post("/api/ai/chat/characters")
def create_ai_chat_character(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AIChatCharacterCreateRequest, payload)
    return legacy.create_ai_chat_character(payload=payload_model, request=request, db=db)

@router.put("/api/ai/chat/characters/{character_id}")
def update_ai_chat_character(
    character_id: int,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AIChatCharacterUpdateRequest, payload)
    return legacy.update_ai_chat_character(character_id=character_id, payload=payload_model, request=request, db=db)

@router.patch("/api/ai/chat/characters/{character_id}/publish")
def publish_ai_chat_character(
    character_id: int,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AIChatPublishRequest, payload)
    return legacy.publish_ai_chat_character(character_id=character_id, payload=payload_model, request=request, db=db)

@router.delete("/api/ai/chat/characters/{character_id}")
def delete_ai_chat_character(
    character_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.delete_ai_chat_character(character_id=character_id, request=request, db=db)

@router.get("/api/ai/chat/characters/{character_id}/messages")
def list_ai_chat_messages(
    character_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.list_ai_chat_messages(character_id=character_id, request=request, db=db)
# END AUTO-GENERATED ROUTER WRAPPERS: AI_CHAT
