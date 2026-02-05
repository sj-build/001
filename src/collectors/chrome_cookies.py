"""Extract and decrypt cookies from Chrome on macOS.

Reads the Cookies SQLite database and decrypts values using the
Chrome Safe Storage key from macOS Keychain.  A temporary copy of
the DB is used so Chrome does not need to be closed.
"""
import hashlib
import logging
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from Cryptodome.Cipher import AES
from Cryptodome.Protocol.KDF import PBKDF2

logger = logging.getLogger("sj_home_agent.collectors.chrome_cookies")

_CHROME_COOKIES_PATH = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Google"
    / "Chrome"
    / "Default"
    / "Cookies"
)

_SALT = b"saltysalt"
_IV = b" " * 16
_KEY_LENGTH = 16
_ITERATIONS = 1003


def _get_encryption_key() -> bytes:
    """Derive AES key from the Chrome Safe Storage password in Keychain."""
    result = subprocess.run(
        ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage"],
        capture_output=True,
        text=True,
        check=True,
    )
    password = result.stdout.strip()
    if not password:
        raise RuntimeError("Empty password from Keychain")
    return PBKDF2(password.encode("utf-8"), _SALT, dkLen=_KEY_LENGTH, count=_ITERATIONS)


def _decrypt_value(
    encrypted: bytes,
    key: bytes,
    domain: str,
    db_version: int,
) -> str:
    """Decrypt a single cookie value (v10 AES-128-CBC)."""
    if not encrypted or len(encrypted) <= 3:
        return ""

    prefix = encrypted[:3]
    if prefix != b"v10":
        logger.debug("Unsupported cookie encryption version: %s", prefix)
        return ""

    cipher = AES.new(key, AES.MODE_CBC, iv=_IV)
    decrypted = cipher.decrypt(encrypted[3:])

    # Remove PKCS7 padding
    padding_len = decrypted[-1]
    if 0 < padding_len <= 16:
        decrypted = decrypted[:-padding_len]

    # Chrome 130+ (db version >= 24): strip 32-byte SHA-256 domain hash
    if db_version >= 24 and len(decrypted) > 32:
        decrypted = decrypted[32:]

    return decrypted.decode("utf-8", errors="replace")


def _get_db_version(conn: sqlite3.Connection) -> int:
    """Read the schema version from the meta table."""
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='version'").fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0


def get_cookies_for_domain(
    domain: str,
    cookie_path: Path = _CHROME_COOKIES_PATH,
) -> dict[str, str]:
    """Return ``{name: value}`` for all cookies matching *domain*.

    Checks both the exact domain and the wildcard (``.domain``) form.
    The Cookies DB is copied to a temp file first so Chrome can stay open.
    """
    if not cookie_path.exists():
        raise FileNotFoundError(f"Chrome Cookies DB not found: {cookie_path}")

    key = _get_encryption_key()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp_path = Path(tmp.name)
    tmp.close()

    try:
        shutil.copy2(cookie_path, tmp_path)
        conn = sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True)
        db_version = _get_db_version(conn)

        hosts = [domain, f".{domain}"]
        placeholders = ",".join("?" * len(hosts))
        rows = conn.execute(
            f"SELECT host_key, name, value, encrypted_value FROM cookies "
            f"WHERE host_key IN ({placeholders})",
            hosts,
        ).fetchall()
        conn.close()

        cookies: dict[str, str] = {}
        for host_key, name, plain_value, encrypted_value in rows:
            if plain_value:
                cookies[name] = plain_value
            elif encrypted_value:
                decrypted = _decrypt_value(encrypted_value, key, host_key, db_version)
                if decrypted:
                    cookies[name] = decrypted

        return cookies

    finally:
        tmp_path.unlink(missing_ok=True)


def get_cookies_for_domains(
    domains: list[str],
    cookie_path: Path = _CHROME_COOKIES_PATH,
) -> dict[str, dict[str, str]]:
    """Return cookies for multiple domains in one pass.

    Returns ``{domain: {name: value, ...}, ...}``.
    """
    if not cookie_path.exists():
        raise FileNotFoundError(f"Chrome Cookies DB not found: {cookie_path}")

    key = _get_encryption_key()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp_path = Path(tmp.name)
    tmp.close()

    try:
        shutil.copy2(cookie_path, tmp_path)
        conn = sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True)
        db_version = _get_db_version(conn)

        hosts: list[str] = []
        for d in domains:
            hosts.extend([d, f".{d}"])

        placeholders = ",".join("?" * len(hosts))
        rows = conn.execute(
            f"SELECT host_key, name, value, encrypted_value FROM cookies "
            f"WHERE host_key IN ({placeholders})",
            hosts,
        ).fetchall()
        conn.close()

        result: dict[str, dict[str, str]] = {d: {} for d in domains}
        for host_key, name, plain_value, encrypted_value in rows:
            # Map host_key back to the original domain
            matched_domain = host_key.lstrip(".")
            if matched_domain not in result:
                for d in domains:
                    if host_key in (d, f".{d}"):
                        matched_domain = d
                        break

            value = ""
            if plain_value:
                value = plain_value
            elif encrypted_value:
                value = _decrypt_value(encrypted_value, key, host_key, db_version)

            if value and matched_domain in result:
                result[matched_domain][name] = value

        return result

    finally:
        tmp_path.unlink(missing_ok=True)
