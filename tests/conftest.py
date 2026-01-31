"""Shared test fixtures for SJ Home Agent tests."""
import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from src.app.config import Settings, PROJECT_ROOT
from src.storage.db import init_db


@pytest.fixture()
def tmp_settings(tmp_path):
    """Create a Settings instance backed by a temporary directory.

    Patches get_settings globally so all modules use the temp paths.
    """
    settings = Settings(
        obsidian_vault=tmp_path / "vault",
        output_folder="test_output",
        db_path=tmp_path / "test.db",
        log_path=tmp_path / "logs" / "app.log",
        screenshot_dir=tmp_path / "logs" / "screens",
        html_dump_dir=tmp_path / "logs" / "html",
        vector_search_enabled=False,
        vector_model_name="intfloat/multilingual-e5-small",
    )

    # Ensure dirs exist
    for d in [
        settings.output_path,
        settings.bundles_path,
        settings.morning_path,
        settings.db_path.parent,
        settings.log_path.parent,
        settings.screenshot_dir,
        settings.html_dump_dir,
        settings.vector_path,
    ]:
        d.mkdir(parents=True, exist_ok=True)

    with patch("src.app.config.get_settings", return_value=settings):
        with patch("src.storage.db.get_settings", return_value=settings):
            init_db()
            yield settings


@pytest.fixture()
def sample_conversations(tmp_settings):
    """Insert sample conversations into the test database and return them."""
    from src.storage.dao import ConversationDAO, Conversation

    dao = ConversationDAO()
    convs = [
        Conversation(
            id="conv-1",
            platform="claude",
            title="Python investment strategies",
            url="https://example.com/conv/1",
            created_at="2025-01-15",
            collected_at="2025-01-15T10:00:00",
            category="Finance",
            tags="investment,python,strategy",
            preview="Discussing algorithmic trading and portfolio optimization using Python.",
            obsidian_path="/vault/test.md",
            content_hash="hash1",
        ),
        Conversation(
            id="conv-2",
            platform="chatgpt",
            title="React component patterns",
            url="https://example.com/conv/2",
            created_at="2025-01-16",
            collected_at="2025-01-16T10:00:00",
            category="Dev",
            tags="react,frontend,patterns",
            preview="Best practices for React hooks and component composition.",
            obsidian_path="/vault/test.md",
            content_hash="hash2",
        ),
        Conversation(
            id="conv-3",
            platform="gemini",
            title="Korean language learning tips",
            url="https://example.com/conv/3",
            created_at="2025-01-17",
            collected_at="2025-01-17T10:00:00",
            category="Learning",
            tags="korean,language,education",
            preview="Effective methods for learning Korean vocabulary and grammar.",
            obsidian_path="/vault/test.md",
            content_hash="hash3",
        ),
    ]

    for conv in convs:
        dao.upsert(conv)

    return convs
