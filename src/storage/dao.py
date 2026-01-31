"""Data Access Objects for all tables."""
import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

from src.storage.db import get_connection


@dataclass(frozen=True)
class Conversation:
    id: str
    platform: str
    title: str
    url: str
    created_at: Optional[str]
    collected_at: str
    category: str
    tags: str
    preview: Optional[str]
    obsidian_path: str
    content_hash: str
    status: str = "active"


@dataclass(frozen=True)
class SourceItem:
    id: str
    source: str
    title: str
    url: str
    published_at: Optional[str]
    fetched_at: str
    summary: Optional[str]
    tags: str
    importance: float = 0.0
    status: str = "new"


@dataclass(frozen=True)
class Bundle:
    id: str
    created_at: str
    query: str
    items_json: str
    markdown: str


class ConversationDAO:
    def upsert(self, conv: Conversation) -> None:
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO conversations
                   (id, platform, title, url, created_at, collected_at,
                    category, tags, preview, obsidian_path, content_hash, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     title=excluded.title,
                     category=excluded.category,
                     tags=excluded.tags,
                     collected_at=excluded.collected_at,
                     obsidian_path=excluded.obsidian_path,
                     preview=excluded.preview,
                     content_hash=excluded.content_hash
                """,
                (conv.id, conv.platform, conv.title, conv.url,
                 conv.created_at, conv.collected_at, conv.category,
                 conv.tags, conv.preview, conv.obsidian_path,
                 conv.content_hash, conv.status),
            )
            conn.commit()
        finally:
            conn.close()

    def find_by_id(self, cid: str) -> Optional[Conversation]:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (cid,)
            ).fetchone()
            if row is None:
                return None
            return Conversation(**dict(row))
        finally:
            conn.close()

    def find_by_ids(self, cids: list[str]) -> list[Conversation]:
        if not cids:
            return []
        conn = get_connection()
        try:
            placeholders = ",".join("?" for _ in cids)
            rows = conn.execute(
                f"SELECT * FROM conversations WHERE id IN ({placeholders})",
                cids,
            ).fetchall()
            return [Conversation(**dict(r)) for r in rows]
        finally:
            conn.close()

    def search(
        self,
        tags: Optional[str] = None,
        keyword: Optional[str] = None,
        days: Optional[int] = None,
        platform: Optional[str] = None,
        limit: int = 50,
    ) -> list[Conversation]:
        conn = get_connection()
        try:
            clauses = ["status = 'active'"]
            params: list = []

            if tags:
                clauses.append("tags LIKE ?")
                params.append(f"%{tags}%")
            if keyword:
                clauses.append("(title LIKE ? OR preview LIKE ?)")
                params.extend([f"%{keyword}%", f"%{keyword}%"])
            if days:
                cutoff = datetime.now().isoformat()[:10]
                clauses.append("collected_at >= date(?, ?)")
                params.extend([cutoff, f"-{days} days"])
            if platform:
                clauses.append("platform = ?")
                params.append(platform)

            where = " AND ".join(clauses)
            sql = f"""
                SELECT * FROM conversations
                WHERE {where}
                ORDER BY collected_at DESC
                LIMIT ?
            """
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [Conversation(**dict(r)) for r in rows]
        finally:
            conn.close()

    def count_all(self) -> int:
        conn = get_connection()
        try:
            row = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()
            return row[0]
        finally:
            conn.close()

    def find_all(self, limit: int = 100, offset: int = 0) -> list[Conversation]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM conversations ORDER BY collected_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [Conversation(**dict(r)) for r in rows]
        finally:
            conn.close()


class SourceItemDAO:
    def upsert(self, item: SourceItem) -> None:
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO source_items
                   (id, source, title, url, published_at, fetched_at,
                    summary, tags, importance, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     title=excluded.title,
                     summary=excluded.summary,
                     tags=excluded.tags,
                     importance=excluded.importance,
                     fetched_at=excluded.fetched_at
                """,
                (item.id, item.source, item.title, item.url,
                 item.published_at, item.fetched_at, item.summary,
                 item.tags, item.importance, item.status),
            )
            conn.commit()
        finally:
            conn.close()

    def get_top(self, limit: int = 3, status: Optional[str] = None) -> list[SourceItem]:
        conn = get_connection()
        try:
            clauses = []
            params: list = []
            if status:
                clauses.append("status = ?")
                params.append(status)

            where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = conn.execute(
                f"""SELECT * FROM source_items {where}
                    ORDER BY importance DESC, fetched_at DESC LIMIT ?""",
                (*params, limit),
            ).fetchall()
            return [SourceItem(**dict(r)) for r in rows]
        finally:
            conn.close()

    def find_all(self, limit: int = 50) -> list[SourceItem]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM source_items ORDER BY fetched_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [SourceItem(**dict(r)) for r in rows]
        finally:
            conn.close()


@dataclass(frozen=True)
class Post:
    id: str
    title: str
    content: str
    status: str
    created_at: str
    updated_at: str
    published_at: Optional[str] = None
    obsidian_path: Optional[str] = None
    published_url: Optional[str] = None
    tags: str = ""
    category: str = "Other"


class PostDAO:
    def insert(self, post: Post) -> None:
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO posts
                   (id, title, content, status, created_at, updated_at,
                    published_at, obsidian_path, published_url, tags, category)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (post.id, post.title, post.content, post.status,
                 post.created_at, post.updated_at, post.published_at,
                 post.obsidian_path, post.published_url, post.tags,
                 post.category),
            )
            conn.commit()
        finally:
            conn.close()

    def update(self, post: Post) -> None:
        """Update a post. Accepts new Post object (immutable pattern)."""
        conn = get_connection()
        try:
            conn.execute(
                """UPDATE posts SET
                     title=?, content=?, status=?, updated_at=?,
                     published_at=?, obsidian_path=?, published_url=?,
                     tags=?, category=?
                   WHERE id=?""",
                (post.title, post.content, post.status, post.updated_at,
                 post.published_at, post.obsidian_path, post.published_url,
                 post.tags, post.category, post.id),
            )
            conn.commit()
        finally:
            conn.close()

    def find_by_id(self, pid: str) -> Optional[Post]:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM posts WHERE id = ?", (pid,)
            ).fetchone()
            if row is None:
                return None
            return Post(**dict(row))
        finally:
            conn.close()

    def find_all(self, status: Optional[str] = None, limit: int = 50) -> list[Post]:
        conn = get_connection()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM posts WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM posts ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [Post(**dict(r)) for r in rows]
        finally:
            conn.close()

    def delete(self, pid: str) -> None:
        conn = get_connection()
        try:
            conn.execute("DELETE FROM posts WHERE id = ?", (pid,))
            conn.commit()
        finally:
            conn.close()


class BundleDAO:
    def insert(self, bundle: Bundle) -> None:
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO bundles (id, created_at, query, items_json, markdown)
                   VALUES (?, ?, ?, ?, ?)""",
                (bundle.id, bundle.created_at, bundle.query,
                 bundle.items_json, bundle.markdown),
            )
            conn.commit()
        finally:
            conn.close()

    def find_by_id(self, bid: str) -> Optional[Bundle]:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM bundles WHERE id = ?", (bid,)
            ).fetchone()
            if row is None:
                return None
            return Bundle(**dict(row))
        finally:
            conn.close()

    def find_all(self, limit: int = 20) -> list[Bundle]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM bundles ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [Bundle(**dict(r)) for r in rows]
        finally:
            conn.close()
