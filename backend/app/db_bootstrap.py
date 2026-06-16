from sqlalchemy import text

from .database import Base, engine


def ensure_all_tables_exist() -> None:
    """
    SQLAlchemy models に定義されている不足テーブルを作成する。
    既存テーブルは変更しない（create_all の標準動作）。
    """
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print("[db] ensure_all_tables_exist failed:", repr(e))


def ensure_users_table_columns():
    """
    このリポジトリはマイグレーションツールを使っていないため、
    追加カラムは起動時に安全に補完する。
    """
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'users'
                    """
                )
            ).fetchall()
            existing = {r[0] for r in rows}

            alters: list[str] = []
            if "email_notifications_enabled" not in existing:
                alters.append("ADD COLUMN email_notifications_enabled TINYINT(1) NOT NULL DEFAULT 1")
            if "favorite_visibility" not in existing:
                alters.append("ADD COLUMN favorite_visibility VARCHAR(16) NOT NULL DEFAULT 'public'")
            if "profile_bio" not in existing:
                alters.append("ADD COLUMN profile_bio TEXT NULL")
            if "profile_icon_url" not in existing:
                alters.append("ADD COLUMN profile_icon_url VARCHAR(255) NULL")
            if "profile_header_url" not in existing:
                alters.append("ADD COLUMN profile_header_url VARCHAR(255) NULL")
            if "profile_website_url" not in existing:
                alters.append("ADD COLUMN profile_website_url VARCHAR(255) NULL")
            if "profile_x_url" not in existing:
                alters.append("ADD COLUMN profile_x_url VARCHAR(255) NULL")
            if "ai_summary_model" not in existing:
                alters.append("ADD COLUMN ai_summary_model VARCHAR(120) NULL")
            if "ai_title_model" not in existing:
                alters.append("ADD COLUMN ai_title_model VARCHAR(120) NULL")
            if "ai_tag_model" not in existing:
                alters.append("ADD COLUMN ai_tag_model VARCHAR(120) NULL")
            if "ai_chat_model" not in existing:
                alters.append("ADD COLUMN ai_chat_model VARCHAR(120) NULL")
            if "ai_translation_model" not in existing:
                alters.append("ADD COLUMN ai_translation_model VARCHAR(120) NULL")
            if "ai_story_agent_model" not in existing:
                alters.append("ADD COLUMN ai_story_agent_model VARCHAR(120) NULL")
            if "ai_comment_revision_model" not in existing:
                alters.append("ADD COLUMN ai_comment_revision_model VARCHAR(120) NULL")
            if "ai_story_agent_visible" not in existing:
                alters.append("ADD COLUMN ai_story_agent_visible TINYINT(1) NOT NULL DEFAULT 1")
            if "email_address_invalid" not in existing:
                alters.append("ADD COLUMN email_address_invalid TINYINT(1) NOT NULL DEFAULT 0")
            if "email_2fa_skip_until" not in existing:
                alters.append("ADD COLUMN email_2fa_skip_until DATETIME NULL")
            if "premium_checked_at" not in existing:
                alters.append("ADD COLUMN premium_checked_at DATETIME NULL")
            if "stripe_customer_id" not in existing:
                alters.append("ADD COLUMN stripe_customer_id VARCHAR(255) NULL")
            if "stripe_subscription_id" not in existing:
                alters.append("ADD COLUMN stripe_subscription_id VARCHAR(255) NULL")
            if "ai_novel_draft_json" not in existing:
                alters.append("ADD COLUMN ai_novel_draft_json LONGTEXT NULL")
            if "ai_novel_draft_updated_at" not in existing:
                alters.append("ADD COLUMN ai_novel_draft_updated_at DATETIME NULL")
            if "ai_novel_paid_generations" not in existing:
                alters.append("ADD COLUMN ai_novel_paid_generations INT NOT NULL DEFAULT 0")
            if "ai_chat_tokens_used" not in existing:
                alters.append("ADD COLUMN ai_chat_tokens_used INT NOT NULL DEFAULT 0")
            if "ai_chat_tokens_total_used" not in existing:
                alters.append("ADD COLUMN ai_chat_tokens_total_used INT NOT NULL DEFAULT 0")
            if "ai_chat_tokens_month_key" not in existing:
                alters.append("ADD COLUMN ai_chat_tokens_month_key INT NOT NULL DEFAULT 0")
            if "ai_chat_paid_blocks" not in existing:
                alters.append("ADD COLUMN ai_chat_paid_blocks INT NOT NULL DEFAULT 0")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE users {clause}"))
    except Exception as e:
        print("[db] ensure_users_table_columns failed:", repr(e))


def ensure_direct_messages_table_columns():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'direct_messages'
                    """
                )
            ).fetchall()
            existing = {r[0] for r in rows}

            alters: list[str] = []
            if "recipient_user_id" not in existing:
                alters.append("ADD COLUMN recipient_user_id INT NULL")
            if "is_read" not in existing:
                alters.append("ADD COLUMN is_read TINYINT(1) NOT NULL DEFAULT 0")
            if "read_at" not in existing:
                alters.append("ADD COLUMN read_at DATETIME NULL")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE direct_messages {clause}"))
    except Exception as e:
        print("[db] ensure_direct_messages_table_columns failed:", repr(e))


def ensure_episode_illusts_table_columns():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'episode_illusts'
                    """
                )
            ).fetchall()
            existing = {r[0] for r in rows}

            alters: list[str] = []
            if "illust_tag" not in existing:
                alters.append("ADD COLUMN illust_tag VARCHAR(32) NULL")
            if "meta_tags" not in existing:
                alters.append("ADD COLUMN meta_tags TEXT NULL")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE episode_illusts {clause}"))
    except Exception as e:
        print("[db] ensure_episode_illusts_table_columns failed:", repr(e))


def ensure_episodes_table_columns():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME, DATA_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'episodes'
                    """
                )
            ).fetchall()
            existing = {r[0]: (r[1] or "").lower() for r in rows}

            alters: list[str] = []
            if "status" not in existing:
                alters.append("ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'public'")
            if "is_public" not in existing:
                alters.append("ADD COLUMN is_public TINYINT(1) NOT NULL DEFAULT 1")
            if "is_free_public" not in existing:
                alters.append("ADD COLUMN is_free_public TINYINT(1) NOT NULL DEFAULT 0")
            if "language" not in existing:
                alters.append("ADD COLUMN language VARCHAR(8) NOT NULL DEFAULT 'ja'")
            if "site_key" not in existing:
                alters.append("ADD COLUMN site_key VARCHAR(32) NOT NULL DEFAULT 'main'")
            if "fanfic_source_title" not in existing:
                alters.append("ADD COLUMN fanfic_source_title VARCHAR(120) NULL")
            if "fanfic_characters" not in existing:
                alters.append("ADD COLUMN fanfic_characters TEXT NULL")
            if "fanfic_coupling" not in existing:
                alters.append("ADD COLUMN fanfic_coupling VARCHAR(120) NULL")
            if "fanfic_notes" not in existing:
                alters.append("ADD COLUMN fanfic_notes TEXT NULL")
            if "series_name" not in existing:
                alters.append("ADD COLUMN series_name VARCHAR(120) NULL")
            if "series_order" not in existing:
                alters.append("ADD COLUMN series_order INT NULL")
            if "scheduled_publish_at" not in existing:
                alters.append("ADD COLUMN scheduled_publish_at DATETIME NULL")
            if "published_at" not in existing:
                alters.append("ADD COLUMN published_at DATETIME NULL")
            if "estimated_read_minutes" not in existing:
                alters.append("ADD COLUMN estimated_read_minutes INT NOT NULL DEFAULT 0")
            if "body" in existing and existing["body"] != "longtext":
                alters.append("MODIFY COLUMN body LONGTEXT NULL")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE episodes {clause}"))
            conn.execute(
                text(
                    """
                    UPDATE episodes
                    SET estimated_read_minutes =
                        CASE
                            WHEN body IS NULL OR CHAR_LENGTH(TRIM(body)) = 0 THEN 0
                            ELSE GREATEST(1, CEIL(CHAR_LENGTH(REPLACE(REPLACE(REPLACE(body, '\r', ''), '\n', ''), ' ', '')) / 600))
                        END
                    WHERE estimated_read_minutes IS NULL OR estimated_read_minutes = 0
                    """
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE episodes e
                    JOIN novels n ON n.id = e.novel_id
                    SET e.site_key = n.site_key
                    WHERE (e.site_key IS NULL OR e.site_key = '')
                    """
                )
            )
    except Exception as e:
        print("[db] ensure_episodes_table_columns failed:", repr(e))


def ensure_novel_daily_metrics_table() -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS novel_daily_metrics (
                      id BIGINT AUTO_INCREMENT PRIMARY KEY,
                      novel_id BIGINT NOT NULL,
                      `date` DATE NOT NULL,
                      view_count INT NOT NULL DEFAULT 0,
                      like_count INT NOT NULL DEFAULT 0,
                      favorite_count INT NOT NULL DEFAULT 0,
                      created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                      UNIQUE KEY uq_novel_daily_metrics_novel_date (novel_id, `date`),
                      INDEX idx_novel_daily_metrics_date (`date`),
                      CONSTRAINT fk_novel_daily_metrics_novel
                        FOREIGN KEY (novel_id) REFERENCES novels(id)
                        ON DELETE CASCADE
                    )
                    """
                )
            )
    except Exception as e:
        print("[db] ensure_novel_daily_metrics_table failed:", repr(e))


def ensure_episode_translations_table_columns():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME, DATA_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'episode_translations'
                    """
                )
            ).fetchall()
            existing = {r[0] for r in rows}
            data_types = {r[0]: str(r[1] or "").strip().lower() for r in rows}

            alters: list[str] = []
            if "body" not in existing:
                alters.append("ADD COLUMN body LONGTEXT NULL")
            elif data_types.get("body") != "longtext":
                alters.append("MODIFY COLUMN body LONGTEXT NULL")
            if "tag_names" not in existing:
                alters.append("ADD COLUMN tag_names TEXT NULL")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE episode_translations {clause}"))
    except Exception as e:
        print("[db] ensure_episode_translations_table_columns failed:", repr(e))


def ensure_novels_table_columns():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'novels'
                    """
                )
            ).fetchall()
            existing = {r[0] for r in rows}

            alters: list[str] = []
            if "creative_type" not in existing:
                alters.append("ADD COLUMN creative_type ENUM('original','fanfic') NOT NULL DEFAULT 'original'")
            if "language" not in existing:
                alters.append("ADD COLUMN language VARCHAR(8) NOT NULL DEFAULT 'ja'")
            if "site_key" not in existing:
                alters.append("ADD COLUMN site_key VARCHAR(32) NOT NULL DEFAULT 'main'")
            if "fanfic_source_title" not in existing:
                alters.append("ADD COLUMN fanfic_source_title VARCHAR(120) NULL")
            if "fanfic_characters" not in existing:
                alters.append("ADD COLUMN fanfic_characters TEXT NULL")
            if "fanfic_coupling" not in existing:
                alters.append("ADD COLUMN fanfic_coupling VARCHAR(120) NULL")
            if "fanfic_notes" not in existing:
                alters.append("ADD COLUMN fanfic_notes TEXT NULL")
            if "series_name" not in existing:
                alters.append("ADD COLUMN series_name VARCHAR(120) NULL")
            if "series_order" not in existing:
                alters.append("ADD COLUMN series_order INT NULL")
            if "cover_image_path" not in existing:
                alters.append("ADD COLUMN cover_image_path VARCHAR(500) NULL")
            if "estimated_read_minutes" not in existing:
                alters.append("ADD COLUMN estimated_read_minutes INT NOT NULL DEFAULT 0")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE novels {clause}"))
            conn.execute(
                text(
                    """
                    UPDATE novels n
                    LEFT JOIN (
                      SELECT novel_id, COALESCE(SUM(estimated_read_minutes), 0) AS total_minutes
                      FROM episodes
                      GROUP BY novel_id
                    ) e ON e.novel_id = n.id
                    SET n.estimated_read_minutes = COALESCE(e.total_minutes, 0)
                    WHERE n.estimated_read_minutes IS NULL OR n.estimated_read_minutes = 0
                    """
                )
            )
    except Exception as e:
        print("[db] ensure_novels_table_columns failed:", repr(e))


def ensure_cover_generations_table() -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS cover_generations (
                      id BIGINT AUTO_INCREMENT PRIMARY KEY,
                      user_id BIGINT NOT NULL,
                      novel_id BIGINT NULL,
                      prompt TEXT NOT NULL,
                      genre VARCHAR(100) NULL,
                      mood VARCHAR(100) NULL,
                      color_theme VARCHAR(100) NULL,
                      character_count INT NULL,
                      provider VARCHAR(50) NOT NULL DEFAULT 'openai',
                      model VARCHAR(100) NOT NULL,
                      status VARCHAR(30) NOT NULL,
                      image_path VARCHAR(500) NULL,
                      error_message TEXT NULL,
                      created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      INDEX idx_cover_generations_user_created (user_id, created_at),
                      INDEX idx_cover_generations_novel_created (novel_id, created_at),
                      CONSTRAINT fk_cover_generations_user
                        FOREIGN KEY (user_id) REFERENCES users(id)
                        ON DELETE CASCADE,
                      CONSTRAINT fk_cover_generations_novel
                        FOREIGN KEY (novel_id) REFERENCES novels(id)
                        ON DELETE SET NULL
                    )
                    """
                )
            )
    except Exception as e:
        print("[db] ensure_cover_generations_table failed:", repr(e))


def ensure_board_posts_table_columns():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME, IS_NULLABLE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'board_posts'
                    """
                )
            ).fetchall()
            existing = {r[0]: r[1] for r in rows}

            alters: list[str] = []
            if "site_key" not in existing:
                alters.append("ADD COLUMN site_key VARCHAR(32) NOT NULL DEFAULT 'main'")
            if "guest_name" not in existing:
                alters.append("ADD COLUMN guest_name VARCHAR(40) NULL")
            if "parent_post_id" not in existing:
                alters.append("ADD COLUMN parent_post_id INT NULL")
            if existing.get("user_id") == "NO":
                alters.append("MODIFY COLUMN user_id INT NULL")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE board_posts {clause}"))

            idx_rows = conn.execute(
                text(
                    """
                    SELECT INDEX_NAME
                    FROM INFORMATION_SCHEMA.STATISTICS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'board_posts'
                    """
                )
            ).fetchall()
            idx_names = {r[0] for r in idx_rows}
            if "idx_board_posts_parent_post_id" not in idx_names:
                conn.execute(text("CREATE INDEX idx_board_posts_parent_post_id ON board_posts(parent_post_id)"))
    except Exception as e:
        print("[db] ensure_board_posts_table_columns failed:", repr(e))


def ensure_ai_novel_jobs_table_columns():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME, DATA_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'ai_novel_jobs'
                    """
                )
            ).fetchall()
            existing = {r[0]: (r[1] or "").lower() for r in rows}

            alters: list[str] = []
            if "guest_id" not in existing:
                alters.append("ADD COLUMN guest_id VARCHAR(64) NULL")
            if "retry_attempts" not in existing:
                alters.append("ADD COLUMN retry_attempts INT NOT NULL DEFAULT 0")
            if "error_message" not in existing:
                alters.append("ADD COLUMN error_message TEXT NULL")
            if "started_at" not in existing:
                alters.append("ADD COLUMN started_at DATETIME NULL")
            if "finished_at" not in existing:
                alters.append("ADD COLUMN finished_at DATETIME NULL")
            if "request_json" in existing and existing["request_json"] != "longtext":
                alters.append("MODIFY COLUMN request_json LONGTEXT NOT NULL")
            if "response_json" in existing and existing["response_json"] != "longtext":
                alters.append("MODIFY COLUMN response_json LONGTEXT NULL")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE ai_novel_jobs {clause}"))
    except Exception as e:
        print("[db] ensure_ai_novel_jobs_table_columns failed:", repr(e))


def ensure_ai_chat_tables():
    try:
        with engine.begin() as conn:
            uq_rows = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM INFORMATION_SCHEMA.STATISTICS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'ai_chat_characters'
                      AND INDEX_NAME = 'uq_ai_chat_characters_user_name'
                    """
                )
            ).scalar() or 0
            if int(uq_rows) > 0:
                try:
                    conn.execute(text("ALTER TABLE ai_chat_characters DROP INDEX uq_ai_chat_characters_user_name"))
                except Exception:
                    pass

            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'ai_chat_characters'
                    """
                )
            ).fetchall()
            existing = {r[0] for r in rows}

            alters: list[str] = []
            if "is_public" not in existing:
                alters.append("ADD COLUMN is_public TINYINT(1) NOT NULL DEFAULT 0")
            if "published_at" not in existing:
                alters.append("ADD COLUMN published_at DATETIME NULL")
            if "speech_gender" not in existing:
                alters.append("ADD COLUMN speech_gender VARCHAR(16) NOT NULL DEFAULT 'auto'")
            if "image_url" not in existing:
                alters.append("ADD COLUMN image_url VARCHAR(512) NULL")
            if "is_r18" not in existing:
                alters.append("ADD COLUMN is_r18 TINYINT(1) NOT NULL DEFAULT 0")
            if "is_name_duplicate" not in existing:
                alters.append("ADD COLUMN is_name_duplicate TINYINT(1) NOT NULL DEFAULT 0")
            if "is_deleted" not in existing:
                alters.append("ADD COLUMN is_deleted TINYINT(1) NOT NULL DEFAULT 0")
            if "deleted_at" not in existing:
                alters.append("ADD COLUMN deleted_at DATETIME NULL")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE ai_chat_characters {clause}"))

            msg_rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'ai_chat_messages'
                    """
                )
            ).fetchall()
            msg_existing = {r[0] for r in msg_rows}
            msg_alters: list[str] = []
            if "is_auto_dialogue" not in msg_existing:
                msg_alters.append("ADD COLUMN is_auto_dialogue TINYINT(1) NOT NULL DEFAULT 0")
            if "is_deleted" not in msg_existing:
                msg_alters.append("ADD COLUMN is_deleted TINYINT(1) NOT NULL DEFAULT 0")
            if "deleted_at" not in msg_existing:
                msg_alters.append("ADD COLUMN deleted_at DATETIME NULL")
            if "character_name_snapshot" not in msg_existing:
                msg_alters.append("ADD COLUMN character_name_snapshot VARCHAR(80) NULL")
            if "personality_snapshot" not in msg_existing:
                msg_alters.append("ADD COLUMN personality_snapshot TEXT NULL")
            if "language_style_snapshot" not in msg_existing:
                msg_alters.append("ADD COLUMN language_style_snapshot VARCHAR(24) NULL")
            for clause in msg_alters:
                conn.execute(text(f"ALTER TABLE ai_chat_messages {clause}"))

            feedback_rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'ai_chat_turn_feedback'
                    """
                )
            ).fetchall()
            feedback_existing = {r[0] for r in feedback_rows}
            feedback_alters: list[str] = []
            if "character_profile_key" not in feedback_existing:
                feedback_alters.append("ADD COLUMN character_profile_key VARCHAR(64) NOT NULL DEFAULT ''")
            if "latency_score" not in feedback_existing:
                feedback_alters.append("ADD COLUMN latency_score FLOAT NOT NULL DEFAULT 0")
            if "intimacy_score" not in feedback_existing:
                feedback_alters.append("ADD COLUMN intimacy_score FLOAT NOT NULL DEFAULT 0")
            if "cuteness_score" not in feedback_existing:
                feedback_alters.append("ADD COLUMN cuteness_score FLOAT NOT NULL DEFAULT 0")
            if "proactiveness_score" not in feedback_existing:
                feedback_alters.append("ADD COLUMN proactiveness_score FLOAT NOT NULL DEFAULT 0")
            if "consistency_score" not in feedback_existing:
                feedback_alters.append("ADD COLUMN consistency_score FLOAT NOT NULL DEFAULT 0")
            if "empathy_score" not in feedback_existing:
                feedback_alters.append("ADD COLUMN empathy_score FLOAT NOT NULL DEFAULT 0")
            if "novelty_score" not in feedback_existing:
                feedback_alters.append("ADD COLUMN novelty_score FLOAT NOT NULL DEFAULT 0")
            if "clarity_score" not in feedback_existing:
                feedback_alters.append("ADD COLUMN clarity_score FLOAT NOT NULL DEFAULT 0")
            if "coolness_score" not in feedback_existing:
                feedback_alters.append("ADD COLUMN coolness_score FLOAT NOT NULL DEFAULT 0")
            if "seriousness_score" not in feedback_existing:
                feedback_alters.append("ADD COLUMN seriousness_score FLOAT NOT NULL DEFAULT 0")
            if "score_version" not in feedback_existing:
                feedback_alters.append("ADD COLUMN score_version VARCHAR(16) NOT NULL DEFAULT 'v1'")
            for clause in feedback_alters:
                conn.execute(text(f"ALTER TABLE ai_chat_turn_feedback {clause}"))
    except Exception as e:
        print("[db] ensure_ai_chat_tables failed:", repr(e))


def ensure_ai_memory_items_table_columns():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'ai_memory_items'
                    """
                )
            ).fetchall()
            existing = {r[0] for r in rows}

            alters: list[str] = []
            if "source_message_id" not in existing:
                alters.append("ADD COLUMN source_message_id INT NULL")
            if "upsert_key" not in existing:
                alters.append("ADD COLUMN upsert_key VARCHAR(128) NOT NULL DEFAULT ''")
            if "importance" not in existing:
                alters.append("ADD COLUMN importance FLOAT NOT NULL DEFAULT 0.5")
            if "expires_at" not in existing:
                alters.append("ADD COLUMN expires_at DATETIME NULL")
            if "is_active" not in existing:
                alters.append("ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE ai_memory_items {clause}"))
    except Exception as e:
        print("[db] ensure_ai_memory_items_table_columns failed:", repr(e))


def ensure_tag_indexes():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT TABLE_NAME, INDEX_NAME
                    FROM INFORMATION_SCHEMA.STATISTICS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME IN ('novel_tags', 'episode_tags')
                    """
                )
            ).fetchall()
            existing = {(r[0], r[1]) for r in rows}

            desired = [
                ("novel_tags", "idx_novel_tags_tag_id", "tag_id"),
                ("episode_tags", "idx_episode_tags_tag_id", "tag_id"),
            ]

            for table, index_name, column in desired:
                if (table, index_name) in existing:
                    continue
                conn.execute(text(f"CREATE INDEX {index_name} ON {table} ({column})"))
    except Exception as e:
        print("[db] ensure_tag_indexes failed:", repr(e))


def ensure_seo_pages_table() -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS seo_pages (
                      id BIGINT AUTO_INCREMENT PRIMARY KEY,
                      slug VARCHAR(190) NOT NULL,
                      title VARCHAR(255) NOT NULL,
                      description VARCHAR(500) NULL,
                      h1 VARCHAR(255) NOT NULL,
                      body TEXT NOT NULL,
                      related_tags TEXT NULL,
                      is_published TINYINT(1) NOT NULL DEFAULT 0,
                      created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                      UNIQUE KEY uq_seo_pages_slug (slug),
                      KEY idx_seo_pages_published (is_published),
                      KEY idx_seo_pages_updated_at (updated_at)
                    )
                    """
                )
            )
    except Exception as e:
        print("[db] ensure_seo_pages_table failed:", repr(e))


def run_db_bootstrap() -> None:
    ensure_all_tables_exist()
    ensure_users_table_columns()
    ensure_direct_messages_table_columns()
    ensure_episode_illusts_table_columns()
    ensure_episodes_table_columns()
    ensure_novel_daily_metrics_table()
    ensure_episode_translations_table_columns()
    ensure_novels_table_columns()
    ensure_cover_generations_table()
    ensure_board_posts_table_columns()
    ensure_ai_novel_jobs_table_columns()
    ensure_ai_chat_tables()
    ensure_ai_memory_items_table_columns()
    ensure_tag_indexes()
    ensure_seo_pages_table()
