ALTER TABLE novels
  ADD COLUMN estimated_read_minutes INT NOT NULL DEFAULT 0;

ALTER TABLE episodes
  ADD COLUMN estimated_read_minutes INT NOT NULL DEFAULT 0;

UPDATE episodes
SET estimated_read_minutes =
  CASE
    WHEN body IS NULL OR CHAR_LENGTH(TRIM(body)) = 0 THEN 0
    ELSE GREATEST(1, CEIL(CHAR_LENGTH(REPLACE(REPLACE(REPLACE(body, '\r', ''), '\n', ''), ' ', '')) / 600))
  END;

UPDATE novels n
LEFT JOIN (
  SELECT novel_id, COALESCE(SUM(estimated_read_minutes), 0) AS total_minutes
  FROM episodes
  GROUP BY novel_id
) e ON e.novel_id = n.id
SET n.estimated_read_minutes = COALESCE(e.total_minutes, 0);
