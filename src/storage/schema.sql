CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    created_at TEXT,
    collected_at TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Other',
    tags TEXT NOT NULL DEFAULT '',
    preview TEXT,
    obsidian_path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS source_items (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    published_at TEXT,
    fetched_at TEXT NOT NULL,
    summary TEXT,
    tags TEXT NOT NULL DEFAULT '',
    importance REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'new'
);

CREATE TABLE IF NOT EXISTS bundles (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    query TEXT NOT NULL,
    items_json TEXT NOT NULL,
    markdown TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversations_platform ON conversations(platform);
CREATE INDEX IF NOT EXISTS idx_conversations_category ON conversations(category);
CREATE INDEX IF NOT EXISTS idx_conversations_collected_at ON conversations(collected_at);
CREATE INDEX IF NOT EXISTS idx_source_items_published_at ON source_items(published_at);
CREATE INDEX IF NOT EXISTS idx_source_items_importance ON source_items(importance);
