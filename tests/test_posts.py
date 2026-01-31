"""Tests for posts feature: PostDAO, post_writer, and web routes."""
import pytest
from datetime import datetime
from unittest.mock import patch

from src.storage.dao import PostDAO, Post


# ── PostDAO tests ───────────────────────────────────────────────


class TestPostDAO:
    def test_insert_and_find(self, tmp_settings):
        dao = PostDAO()
        now = datetime.now().isoformat()

        post = Post(
            id="test-post-1",
            title="Test Post",
            content="# Hello\n\nThis is a test.",
            status="draft",
            created_at=now,
            updated_at=now,
            tags="test,hello",
            category="Other",
        )
        dao.insert(post)

        found = dao.find_by_id("test-post-1")
        assert found is not None
        assert found.title == "Test Post"
        assert found.status == "draft"
        assert found.tags == "test,hello"

    def test_update_immutable(self, tmp_settings):
        dao = PostDAO()
        now = datetime.now().isoformat()

        original = Post(
            id="test-post-2",
            title="Original Title",
            content="Original content",
            status="draft",
            created_at=now,
            updated_at=now,
        )
        dao.insert(original)

        updated = Post(
            id="test-post-2",
            title="Updated Title",
            content="Updated content",
            status="published",
            created_at=now,
            updated_at=datetime.now().isoformat(),
            published_at=datetime.now().isoformat(),
        )
        dao.update(updated)

        found = dao.find_by_id("test-post-2")
        assert found.title == "Updated Title"
        assert found.status == "published"
        assert found.published_at is not None

    def test_find_all_with_status_filter(self, tmp_settings):
        dao = PostDAO()
        now = datetime.now().isoformat()

        draft = Post(
            id="draft-1", title="Draft", content="draft",
            status="draft", created_at=now, updated_at=now,
        )
        published = Post(
            id="pub-1", title="Published", content="published",
            status="published", created_at=now, updated_at=now,
        )
        dao.insert(draft)
        dao.insert(published)

        drafts = dao.find_all(status="draft")
        assert len(drafts) == 1
        assert drafts[0].status == "draft"

        pubs = dao.find_all(status="published")
        assert len(pubs) == 1
        assert pubs[0].status == "published"

        all_posts = dao.find_all()
        assert len(all_posts) == 2

    def test_delete(self, tmp_settings):
        dao = PostDAO()
        now = datetime.now().isoformat()

        post = Post(
            id="del-1", title="To Delete", content="content",
            status="draft", created_at=now, updated_at=now,
        )
        dao.insert(post)
        assert dao.find_by_id("del-1") is not None

        dao.delete("del-1")
        assert dao.find_by_id("del-1") is None

    def test_find_nonexistent(self, tmp_settings):
        dao = PostDAO()
        assert dao.find_by_id("nonexistent") is None


# ── post_writer tests ───────────────────────────────────────────


class TestPostWriter:
    def test_write_to_obsidian(self, tmp_settings):
        from src.ingest.post_writer import write_post_to_obsidian

        post = Post(
            id="writer-1",
            title="My Test Post",
            content="# Hello\n\nParagraph here.",
            status="published",
            created_at="2025-01-15T10:00:00",
            updated_at="2025-01-15T12:00:00",
            published_at="2025-01-15T12:00:00",
            tags="test,writing",
            category="Personal/Philosophy",
        )

        path = write_post_to_obsidian(post)
        assert path.exists()
        content = path.read_text()
        assert "title: \"My Test Post\"" in content
        assert "# Hello" in content
        assert "test, writing" in content

    def test_export_to_html(self, tmp_settings):
        from src.ingest.post_writer import export_post_to_html

        post = Post(
            id="writer-2",
            title="HTML Export Test",
            content="# Title\n\n**Bold text** and *italic*.\n\n- item1\n- item2",
            status="published",
            created_at="2025-01-15T10:00:00",
            updated_at="2025-01-15T12:00:00",
            published_at="2025-01-15T12:00:00",
            category="Other",
        )

        path = export_post_to_html(post)
        assert path.exists()
        content = path.read_text()
        assert "<h1>HTML Export Test</h1>" in content
        assert "<strong>" in content
        assert "<em>" in content
        assert "<li>" in content
