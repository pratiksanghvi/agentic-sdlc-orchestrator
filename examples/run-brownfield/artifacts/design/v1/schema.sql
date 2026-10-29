CREATE TABLE IF NOT EXISTS short_links (
  short_code TEXT PRIMARY KEY,
  long_url TEXT NOT NULL,
  created_at TEXT NOT NULL,
  click_count INTEGER NOT NULL DEFAULT 0,
  last_clicked_at TEXT,
  expires_at TEXT
);
-- expires_at: nullable; NULL = never expires. Same fixed-width UTC microsecond text format as created_at so lexicographic comparison is chronological.
-- Existing databases: persistence.SchemaMigrator adds expires_at idempotently (PRAGMA table_info check, then ALTER TABLE ... ADD COLUMN expires_at TEXT only if missing); existing rows get NULL.
