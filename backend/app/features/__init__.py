from fastapi import FastAPI

from .ai_episode_assist_routes import router as ai_episode_assist_router
from .ai_novel_generate_routes import router as ai_novel_generate_router
from .ai_novel_revision_target_routes import router as ai_novel_revision_target_router
from .public_novel_recommended_routes import router as public_novel_recommended_router
from .ai_chat_public_characters_routes import router as ai_chat_public_characters_router
from .ai_memory_items_list_routes import router as ai_memory_items_list_router
from .ai_memory_items_deactivate_routes import router as ai_memory_items_deactivate_router
from .ai_memory_items_delete_routes import router as ai_memory_items_delete_router
from .ai_memory_backfill_routes import router as ai_memory_backfill_router
from .ai_novel_job_routes import router as ai_novel_job_router
from .ai_chat_public_interactions_routes import router as ai_chat_public_interactions_router
from ..routers.auth import router as auth_router
from ..routers.episodes import router as episodes_router
from ..routers.me import router as me_router
from ..routers.novels import router as novels_router
from ..routers.other import router as other_router


def include_feature_routers(app: FastAPI) -> None:
    app.include_router(auth_router)
    app.include_router(ai_episode_assist_router)
    app.include_router(ai_novel_generate_router)
    app.include_router(ai_novel_revision_target_router)
    app.include_router(ai_novel_job_router)
    app.include_router(novels_router)
    app.include_router(episodes_router)
    app.include_router(ai_chat_public_characters_router)
    app.include_router(ai_chat_public_interactions_router)
    app.include_router(ai_memory_items_list_router)
    app.include_router(ai_memory_items_deactivate_router)
    app.include_router(ai_memory_items_delete_router)
    app.include_router(ai_memory_backfill_router)
    app.include_router(other_router)
    app.include_router(me_router)
