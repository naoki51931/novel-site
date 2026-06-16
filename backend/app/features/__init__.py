from fastapi import FastAPI

from .ai_episode_assist_routes import router as ai_episode_assist_router
from .ai_novel_generate_routes import router as ai_novel_generate_router
from .ai_novel_revision_target_routes import router as ai_novel_revision_target_router
from .ai_chat_public_character_detail_routes import router as ai_chat_public_character_detail_router
from .public_novel_recommended_routes import router as public_novel_recommended_router
from .ai_chat_public_characters_routes import router as ai_chat_public_characters_router
from .ai_memory_items_list_routes import router as ai_memory_items_list_router
from .ai_memory_items_deactivate_routes import router as ai_memory_items_deactivate_router
from .ai_memory_items_delete_routes import router as ai_memory_items_delete_router
from .ai_memory_backfill_routes import router as ai_memory_backfill_router
from .ai_novel_job_routes import router as ai_novel_job_router
from .ai_chat_public_interactions_routes import router as ai_chat_public_interactions_router
from ..routers.ai_chat import router as ai_chat_router
from ..routers.ai_jobs import router as ai_jobs_router
from ..routers.ai_misc import router as ai_misc_router
from ..routers.ai_novel_drafts import router as ai_novel_drafts_router
from ..routers.ai_novel_misc import router as ai_novel_misc_router
from ..routers.ai_story_agent import router as ai_story_agent_router
from ..routers.admin import router as admin_router
from ..routers.auth import router as auth_router
from ..routers.board import router as board_router
from ..routers.dms import router as dms_router
from ..routers.episodes import router as episodes_router
from ..routers.feed import router as feed_router
from ..routers.i18n import router as i18n_router
from ..routers.me import router as me_router
from ..routers.novels import router as novels_router
from ..routers.other import router as other_router
from ..routers.payments import router as payments_router
from ..routers.public import router as public_router
from ..routers.search import router as search_router
from ..routers.series import router as series_router
from ..routers.tags import router as tags_router


def include_feature_routers(app: FastAPI) -> None:
    app.include_router(admin_router)
    app.include_router(auth_router)
    app.include_router(board_router)
    app.include_router(dms_router)
    app.include_router(ai_chat_router)
    app.include_router(ai_episode_assist_router)
    app.include_router(ai_novel_generate_router)
    app.include_router(ai_novel_revision_target_router)
    app.include_router(ai_novel_job_router)
    app.include_router(ai_jobs_router)
    app.include_router(ai_misc_router)
    app.include_router(ai_novel_drafts_router)
    app.include_router(ai_novel_misc_router)
    app.include_router(ai_story_agent_router)
    app.include_router(novels_router)
    app.include_router(episodes_router)
    app.include_router(feed_router)
    app.include_router(i18n_router)
    app.include_router(ai_chat_public_characters_router)
    app.include_router(ai_chat_public_character_detail_router)
    app.include_router(ai_chat_public_interactions_router)
    app.include_router(ai_memory_items_list_router)
    app.include_router(ai_memory_items_deactivate_router)
    app.include_router(ai_memory_items_delete_router)
    app.include_router(ai_memory_backfill_router)
    app.include_router(other_router)
    app.include_router(me_router)
    app.include_router(payments_router)
    app.include_router(public_router)
    app.include_router(search_router)
    app.include_router(series_router)
    app.include_router(tags_router)
