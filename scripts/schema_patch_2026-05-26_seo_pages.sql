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
);
