CREATE TABLE IF NOT EXISTS notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department TEXT NOT NULL,
    post_number TEXT NOT NULL,
    title TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT '',
    date TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    attachments TEXT NOT NULL DEFAULT '[]',
    collected_at TEXT NOT NULL,
    UNIQUE(department, post_number)
);
CREATE INDEX IF NOT EXISTS idx_notices_date ON notices(date);
CREATE INDEX IF NOT EXISTS idx_notices_title ON notices(title);
