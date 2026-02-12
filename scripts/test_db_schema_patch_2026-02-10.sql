-- Patch date: 2026-02-10
-- Purpose: fill missing schema parts in test DB based on backend/app/models.py and ensure_* in backend/app/main.py
-- Target: MySQL 8.0+

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ---------------------------------------------------------------------
-- 1) Missing tables (create only when absent)
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `push_subscriptions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `endpoint` varchar(512) NOT NULL,
  `p256dh` varchar(512) NOT NULL,
  `auth` varchar(512) NOT NULL,
  `user_agent` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_push_subscription_endpoint` (`endpoint`),
  KEY `ix_push_subscriptions_id` (`id`),
  KEY `ix_push_subscriptions_user_id` (`user_id`),
  CONSTRAINT `push_subscriptions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `ai_novel_drafts` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `title` varchar(255) NOT NULL,
  `draft_json` longtext NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_ai_novel_drafts_id` (`id`),
  KEY `ix_ai_novel_drafts_user_id` (`user_id`),
  KEY `ix_ai_novel_drafts_created_at` (`created_at`),
  KEY `ix_ai_novel_drafts_updated_at` (`updated_at`),
  CONSTRAINT `ai_novel_drafts_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `ai_chat_characters` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `name` varchar(80) NOT NULL,
  `personality` text,
  `speech_gender` varchar(16) NOT NULL DEFAULT 'auto',
  `is_public` tinyint(1) NOT NULL DEFAULT '0',
  `published_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_ai_chat_characters_user_name` (`user_id`, `name`),
  KEY `ix_ai_chat_characters_id` (`id`),
  KEY `ix_ai_chat_characters_user_id` (`user_id`),
  KEY `ix_ai_chat_characters_is_public` (`is_public`),
  KEY `ix_ai_chat_characters_published_at` (`published_at`),
  KEY `ix_ai_chat_characters_created_at` (`created_at`),
  KEY `ix_ai_chat_characters_updated_at` (`updated_at`),
  CONSTRAINT `ai_chat_characters_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `ai_chat_messages` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `character_id` int NOT NULL,
  `role` varchar(16) NOT NULL,
  `mode` varchar(16) NOT NULL DEFAULT 'say',
  `is_auto_dialogue` tinyint(1) NOT NULL DEFAULT '0',
  `character_name_snapshot` varchar(80) DEFAULT NULL,
  `personality_snapshot` text,
  `language_style_snapshot` varchar(24) DEFAULT NULL,
  `content` text NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_ai_chat_messages_id` (`id`),
  KEY `ix_ai_chat_messages_user_id` (`user_id`),
  KEY `ix_ai_chat_messages_character_id` (`character_id`),
  KEY `ix_ai_chat_messages_is_auto_dialogue` (`is_auto_dialogue`),
  KEY `ix_ai_chat_messages_created_at` (`created_at`),
  CONSTRAINT `ai_chat_messages_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `ai_chat_messages_ibfk_2` FOREIGN KEY (`character_id`) REFERENCES `ai_chat_characters` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `ai_chat_addon_purchases` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `stripe_checkout_session_id` varchar(255) NOT NULL,
  `amount_yen` int NOT NULL,
  `token_blocks` int NOT NULL,
  `status` varchar(16) NOT NULL DEFAULT 'pending',
  `paid_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_ai_chat_addon_purchases_checkout` (`stripe_checkout_session_id`),
  KEY `ix_ai_chat_addon_purchases_id` (`id`),
  KEY `ix_ai_chat_addon_purchases_user_id` (`user_id`),
  KEY `ix_ai_chat_addon_purchases_created_at` (`created_at`),
  CONSTRAINT `ai_chat_addon_purchases_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------
-- 2) Missing columns (safe: IF NOT EXISTS)
-- ---------------------------------------------------------------------

ALTER TABLE `users`
  ADD COLUMN IF NOT EXISTS `stripe_customer_id` varchar(255) DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS `stripe_subscription_id` varchar(255) DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS `ai_novel_draft_json` longtext,
  ADD COLUMN IF NOT EXISTS `ai_novel_draft_updated_at` datetime DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS `ai_chat_tokens_used` int NOT NULL DEFAULT '0',
  ADD COLUMN IF NOT EXISTS `ai_chat_paid_blocks` int NOT NULL DEFAULT '0';

ALTER TABLE `password_reset_tokens`
  ADD COLUMN IF NOT EXISTS `user_id` int DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS `email` varchar(255) DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN IF NOT EXISTS `consumed` tinyint(1) NOT NULL DEFAULT '0';

ALTER TABLE `oauth_accounts`
  ADD COLUMN IF NOT EXISTS `provider_username` varchar(255) DEFAULT NULL;

ALTER TABLE `novels`
  ADD COLUMN IF NOT EXISTS `language` varchar(8) NOT NULL DEFAULT 'ja',
  ADD COLUMN IF NOT EXISTS `view_count` int NOT NULL DEFAULT '0',
  ADD COLUMN IF NOT EXISTS `like_count` int NOT NULL DEFAULT '0';

ALTER TABLE `novel_daily_metrics`
  ADD COLUMN IF NOT EXISTS `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

ALTER TABLE `episodes`
  ADD COLUMN IF NOT EXISTS `status` varchar(16) NOT NULL DEFAULT 'public',
  ADD COLUMN IF NOT EXISTS `is_public` tinyint(1) NOT NULL DEFAULT '1',
  ADD COLUMN IF NOT EXISTS `language` varchar(8) NOT NULL DEFAULT 'ja';

ALTER TABLE `episodes` MODIFY COLUMN `body` longtext;

ALTER TABLE `novel_translations`
  ADD COLUMN IF NOT EXISTS `title` varchar(200) DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

ALTER TABLE `episode_translations`
  ADD COLUMN IF NOT EXISTS `language` varchar(8) DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS `body` text,
  ADD COLUMN IF NOT EXISTS `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

ALTER TABLE `episode_illusts`
  ADD COLUMN IF NOT EXISTS `episode_id` int DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS `created_at` datetime DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE `episode_likes`
  ADD COLUMN IF NOT EXISTS `created_at` datetime DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE `novel_likes`
  ADD COLUMN IF NOT EXISTS `created_at` datetime DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE `novel_comments`
  ADD COLUMN IF NOT EXISTS `novel_id` int DEFAULT NULL;

ALTER TABLE `episode_comments`
  ADD COLUMN IF NOT EXISTS `created_at` datetime DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE `ai_generate_logs`
  ADD COLUMN IF NOT EXISTS `user_id` int DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS `prompt_summary` varchar(255) DEFAULT NULL;

ALTER TABLE `ai_novel_jobs`
  ADD COLUMN IF NOT EXISTS `finished_at` datetime DEFAULT NULL,
  MODIFY COLUMN `request_json` longtext NOT NULL,
  MODIFY COLUMN `response_json` longtext;

ALTER TABLE `authors_payout_profiles`
  ADD COLUMN IF NOT EXISTS `bank_account_type` varchar(20) DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS `created_at` datetime DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE `support_plans`
  ADD COLUMN IF NOT EXISTS `name` varchar(100) NOT NULL DEFAULT 'Standard Plan',
  ADD COLUMN IF NOT EXISTS `created_at` datetime DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE `memberships`
  ADD COLUMN IF NOT EXISTS `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

ALTER TABLE `membership_invoices`
  ADD COLUMN IF NOT EXISTS `author_share_yen` int NOT NULL DEFAULT '0',
  ADD COLUMN IF NOT EXISTS `created_at` datetime DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE `payouts`
  ADD COLUMN IF NOT EXISTS `period_end` date,
  ADD COLUMN IF NOT EXISTS `amount_yen` int,
  ADD COLUMN IF NOT EXISTS `created_at` datetime DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE `payout_items`
  ADD COLUMN IF NOT EXISTS `payout_id` int,
  ADD COLUMN IF NOT EXISTS `source_id` int,
  ADD COLUMN IF NOT EXISTS `created_at` datetime DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE `direct_messages`
  ADD COLUMN IF NOT EXISTS `created_at` datetime DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE `notifications`
  ADD COLUMN IF NOT EXISTS `is_read` tinyint(1) NOT NULL DEFAULT '0';

ALTER TABLE `admin_contact_messages`
  ADD COLUMN IF NOT EXISTS `subject` varchar(255) NOT NULL DEFAULT '';

-- ---------------------------------------------------------------------
-- 3) Missing indexes / unique keys (safe)
-- ---------------------------------------------------------------------

CREATE UNIQUE INDEX IF NOT EXISTS `uq_oauth_provider_user_id` ON `oauth_accounts` (`provider`, `provider_user_id`);
CREATE UNIQUE INDEX IF NOT EXISTS `uq_dm_thread_users` ON `direct_message_threads` (`user1_id`, `user2_id`);
CREATE INDEX IF NOT EXISTS `idx_ai_generate_logs_user_id_created_at` ON `ai_generate_logs` (`user_id`, `created_at`);
CREATE INDEX IF NOT EXISTS `ix_direct_messages_recipient_user_id` ON `direct_messages` (`recipient_user_id`);
CREATE INDEX IF NOT EXISTS `idx_episode_illusts_illust_tag` ON `episode_illusts` (`illust_tag`);
CREATE INDEX IF NOT EXISTS `idx_novel_likes_novel_id` ON `novel_likes` (`novel_id`);
CREATE INDEX IF NOT EXISTS `idx_novel_likes_user_id` ON `novel_likes` (`user_id`);
CREATE INDEX IF NOT EXISTS `idx_novel_tags_tag_id` ON `novel_tags` (`tag_id`);
CREATE INDEX IF NOT EXISTS `idx_episode_tags_tag_id` ON `episode_tags` (`tag_id`);

-- NOTE:
-- Some dumps in your message look truncated (for example missing PRIMARY KEY definitions or missing CREATE TABLE lines).
-- If those tables were actually created without PK, fix manually after checking:
--   SHOW CREATE TABLE novel_comments;
--   SHOW CREATE TABLE episode_comments;
--   SHOW CREATE TABLE novel_favorites;
-- Then add PK/AI only when needed:
--   ALTER TABLE novel_comments ADD COLUMN id INT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST;
--   ALTER TABLE episode_comments ADD COLUMN id INT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST;
--   ALTER TABLE novel_favorites ADD COLUMN id INT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST;

SET FOREIGN_KEY_CHECKS = 1;
