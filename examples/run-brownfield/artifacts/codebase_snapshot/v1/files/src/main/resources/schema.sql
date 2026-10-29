CREATE TABLE IF NOT EXISTS short_links (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  short_code TEXT NOT NULL UNIQUE,
  long_url TEXT NOT NULL,
  created_at TEXT NOT NULL,
  click_count INTEGER NOT NULL DEFAULT 0 CHECK (click_count >= 0),
  last_clicked_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_short_links_short_code ON short_links (short_code);
