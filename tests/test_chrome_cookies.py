"""Tests for Chrome cookie extraction and decryption."""
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.collectors.chrome_cookies import (
    _decrypt_value,
    _get_db_version,
    _get_encryption_key,
    get_cookies_for_domain,
    get_cookies_for_domains,
)


# ── _get_encryption_key ─────────────────────────────────────────


class TestGetEncryptionKey:
    """Test Keychain password retrieval and key derivation."""

    @patch("src.collectors.chrome_cookies.subprocess.run")
    def test_derives_key_from_keychain_password(self, mock_run):
        mock_run.return_value = MagicMock(stdout="fake-password\n")

        key = _get_encryption_key()

        assert isinstance(key, bytes)
        assert len(key) == 16  # AES-128

        mock_run.assert_called_once_with(
            ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage"],
            capture_output=True,
            text=True,
            check=True,
        )

    @patch("src.collectors.chrome_cookies.subprocess.run")
    def test_raises_on_empty_password(self, mock_run):
        mock_run.return_value = MagicMock(stdout="\n")

        with pytest.raises(RuntimeError, match="Empty password"):
            _get_encryption_key()

    @patch("src.collectors.chrome_cookies.subprocess.run")
    def test_same_password_gives_same_key(self, mock_run):
        mock_run.return_value = MagicMock(stdout="test-password\n")

        key1 = _get_encryption_key()
        key2 = _get_encryption_key()
        assert key1 == key2


# ── _decrypt_value ───────────────────────────────────────────────


class TestDecryptValue:
    """Test cookie value decryption."""

    def test_empty_value_returns_empty(self):
        assert _decrypt_value(b"", b"x" * 16, "example.com", 20) == ""

    def test_short_value_returns_empty(self):
        assert _decrypt_value(b"v1", b"x" * 16, "example.com", 20) == ""

    def test_non_v10_prefix_returns_empty(self):
        assert _decrypt_value(b"v20abcdef", b"x" * 16, "example.com", 20) == ""

    def test_v10_decryption_roundtrip(self):
        """Encrypt a value with v10 scheme and verify decryption works."""
        from Cryptodome.Cipher import AES
        from Cryptodome.Protocol.KDF import PBKDF2

        password = "test-password"
        salt = b"saltysalt"
        iv = b" " * 16
        key = PBKDF2(password.encode("utf-8"), salt, dkLen=16, count=1003)

        plaintext = b"my-cookie-value!"  # 16 bytes (aligned)
        cipher = AES.new(key, AES.MODE_CBC, iv=iv)

        # PKCS7 pad to 16 bytes
        pad_len = 16 - (len(plaintext) % 16)
        padded = plaintext + bytes([pad_len] * pad_len)
        encrypted = b"v10" + cipher.encrypt(padded)

        result = _decrypt_value(encrypted, key, "example.com", db_version=20)
        assert result == "my-cookie-value!"

    def test_v10_decryption_with_domain_hash_strip(self):
        """Chrome 130+ (db_version >= 24) prepends 32-byte hash."""
        from Cryptodome.Cipher import AES
        from Cryptodome.Protocol.KDF import PBKDF2

        password = "test-password"
        key = PBKDF2(password.encode("utf-8"), b"saltysalt", dkLen=16, count=1003)
        iv = b" " * 16

        # 32 bytes hash + actual value
        domain_hash = b"\x00" * 32
        value = b"actual-value-pad"  # 16 bytes
        plaintext = domain_hash + value

        pad_len = 16 - (len(plaintext) % 16)
        padded = plaintext + bytes([pad_len] * pad_len)
        cipher = AES.new(key, AES.MODE_CBC, iv=iv)
        encrypted = b"v10" + cipher.encrypt(padded)

        result = _decrypt_value(encrypted, key, "example.com", db_version=24)
        assert result == "actual-value-pad"


# ── _get_db_version ──────────────────────────────────────────────


class TestGetDbVersion:
    """Test SQLite meta version reading."""

    def test_reads_version_from_meta(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE meta (key TEXT, value TEXT)")
        conn.execute("INSERT INTO meta VALUES ('version', '24')")
        conn.commit()

        version = _get_db_version(conn)
        conn.close()
        assert version == 24

    def test_returns_zero_when_no_meta(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE other (key TEXT)")
        conn.commit()

        version = _get_db_version(conn)
        conn.close()
        assert version == 0


# ── get_cookies_for_domain ───────────────────────────────────────


class TestGetCookiesForDomain:
    """Test single-domain cookie extraction."""

    def test_raises_when_db_missing(self):
        with pytest.raises(FileNotFoundError):
            get_cookies_for_domain("example.com", cookie_path=Path("/nonexistent/Cookies"))

    @patch("src.collectors.chrome_cookies._get_encryption_key")
    def test_extracts_plain_cookies(self, mock_key, tmp_path):
        mock_key.return_value = b"x" * 16

        db_path = tmp_path / "Cookies"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE meta (key TEXT, value TEXT)")
        conn.execute("INSERT INTO meta VALUES ('version', '20')")
        conn.execute(
            "CREATE TABLE cookies "
            "(host_key TEXT, name TEXT, value TEXT, encrypted_value BLOB)"
        )
        conn.execute(
            "INSERT INTO cookies VALUES (?, ?, ?, ?)",
            (".example.com", "session", "plain-value", b""),
        )
        conn.commit()
        conn.close()

        cookies = get_cookies_for_domain("example.com", cookie_path=db_path)
        assert cookies == {"session": "plain-value"}

    @patch("src.collectors.chrome_cookies._get_encryption_key")
    def test_matches_exact_and_dotted_domain(self, mock_key, tmp_path):
        mock_key.return_value = b"x" * 16

        db_path = tmp_path / "Cookies"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE meta (key TEXT, value TEXT)")
        conn.execute("INSERT INTO meta VALUES ('version', '20')")
        conn.execute(
            "CREATE TABLE cookies "
            "(host_key TEXT, name TEXT, value TEXT, encrypted_value BLOB)"
        )
        conn.execute(
            "INSERT INTO cookies VALUES (?, ?, ?, ?)",
            ("example.com", "a", "val-a", b""),
        )
        conn.execute(
            "INSERT INTO cookies VALUES (?, ?, ?, ?)",
            (".example.com", "b", "val-b", b""),
        )
        conn.commit()
        conn.close()

        cookies = get_cookies_for_domain("example.com", cookie_path=db_path)
        assert cookies == {"a": "val-a", "b": "val-b"}

    @patch("src.collectors.chrome_cookies._get_encryption_key")
    def test_returns_empty_for_no_matches(self, mock_key, tmp_path):
        mock_key.return_value = b"x" * 16

        db_path = tmp_path / "Cookies"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE meta (key TEXT, value TEXT)")
        conn.execute("INSERT INTO meta VALUES ('version', '20')")
        conn.execute(
            "CREATE TABLE cookies "
            "(host_key TEXT, name TEXT, value TEXT, encrypted_value BLOB)"
        )
        conn.commit()
        conn.close()

        cookies = get_cookies_for_domain("example.com", cookie_path=db_path)
        assert cookies == {}


# ── get_cookies_for_domains ──────────────────────────────────────


class TestGetCookiesForDomains:
    """Test multi-domain cookie extraction."""

    def test_raises_when_db_missing(self):
        with pytest.raises(FileNotFoundError):
            get_cookies_for_domains(["example.com"], cookie_path=Path("/nonexistent/Cookies"))

    @patch("src.collectors.chrome_cookies._get_encryption_key")
    def test_extracts_multiple_domains(self, mock_key, tmp_path):
        mock_key.return_value = b"x" * 16

        db_path = tmp_path / "Cookies"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE meta (key TEXT, value TEXT)")
        conn.execute("INSERT INTO meta VALUES ('version', '20')")
        conn.execute(
            "CREATE TABLE cookies "
            "(host_key TEXT, name TEXT, value TEXT, encrypted_value BLOB)"
        )
        conn.execute(
            "INSERT INTO cookies VALUES (?, ?, ?, ?)",
            (".claude.ai", "sessionKey", "sk-123", b""),
        )
        conn.execute(
            "INSERT INTO cookies VALUES (?, ?, ?, ?)",
            (".chatgpt.com", "token", "tok-456", b""),
        )
        conn.commit()
        conn.close()

        result = get_cookies_for_domains(
            ["claude.ai", "chatgpt.com"], cookie_path=db_path,
        )
        assert result["claude.ai"] == {"sessionKey": "sk-123"}
        assert result["chatgpt.com"] == {"token": "tok-456"}

    @patch("src.collectors.chrome_cookies._get_encryption_key")
    def test_returns_empty_dicts_for_unmatched_domains(self, mock_key, tmp_path):
        mock_key.return_value = b"x" * 16

        db_path = tmp_path / "Cookies"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE meta (key TEXT, value TEXT)")
        conn.execute("INSERT INTO meta VALUES ('version', '20')")
        conn.execute(
            "CREATE TABLE cookies "
            "(host_key TEXT, name TEXT, value TEXT, encrypted_value BLOB)"
        )
        conn.commit()
        conn.close()

        result = get_cookies_for_domains(
            ["claude.ai", "chatgpt.com"], cookie_path=db_path,
        )
        assert result == {"claude.ai": {}, "chatgpt.com": {}}
