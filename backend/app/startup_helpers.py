import os
from contextlib import asynccontextmanager


def on_startup(
    *,
    ensure_all_tables_exist,
    episode_image_dir: str,
    ai_chat_character_image_dir: str,
    ai_chat_message_image_dir: str,
    cover_upload_dir: str,
    get_redis_client,
    start_redis_metrics_flusher_if_enabled,
    start_daily_translation_bot_if_enabled,
    start_monthly_stripe_premium_sync_if_enabled,
    start_ui_i18n_watchdog_if_enabled,
    recover_ui_i18n_jobs_on_startup,
    ai_chat_memory_enabled: bool,
    ensure_weaviate_schema,
    ai_weaviate_features_enabled: bool,
    ensure_weaviate_feature_schema,
    logger,
) -> None:
    ensure_all_tables_exist()
    os.makedirs(episode_image_dir, exist_ok=True)
    os.makedirs(ai_chat_character_image_dir, exist_ok=True)
    os.makedirs(ai_chat_message_image_dir, exist_ok=True)
    os.makedirs(cover_upload_dir, exist_ok=True)
    get_redis_client()
    start_redis_metrics_flusher_if_enabled()
    start_daily_translation_bot_if_enabled()
    start_monthly_stripe_premium_sync_if_enabled()
    start_ui_i18n_watchdog_if_enabled()
    recover_ui_i18n_jobs_on_startup()
    if ai_chat_memory_enabled:
        try:
            ensure_weaviate_schema()
        except Exception as e:
            logger.warning("weaviate schema ensure failed: %r", e)
    if ai_weaviate_features_enabled:
        try:
            ensure_weaviate_feature_schema()
        except Exception as e:
            logger.warning("weaviate feature schema ensure failed: %r", e)


def build_lifespan(**kwargs):
    @asynccontextmanager
    async def lifespan(app):
        on_startup(**kwargs)
        yield

    return lifespan
