"""Application configuration loaded from .env and defaults."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    obsidian_vault: Path = Path("/Users/sjbaek/Desktop/001")
    output_folder: str = "AI대화정리"
    chrome_profile: Path = Path.home() / "Library/Application Support/Google/Chrome/Default"
    db_path: Path = PROJECT_ROOT / "data" / "sj.db"
    web_host: str = "127.0.0.1"
    web_port: int = 8787
    llm_provider: str = "none"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    log_path: Path = PROJECT_ROOT / "data" / "logs" / "app.log"
    screenshot_dir: Path = PROJECT_ROOT / "data" / "logs" / "screens"
    html_dump_dir: Path = PROJECT_ROOT / "data" / "logs" / "html"
    vector_search_enabled: bool = False
    vector_model_name: str = "intfloat/multilingual-e5-small"
    cdp_port: int = 9222
    chrome_path: str = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    rss_feeds: str = ""
    nitter_instance: str = "nitter.net"
    twitter_accounts: str = ""

    def get_rss_feeds(self) -> dict[str, str]:
        """Parse RSS_FEEDS env var into {name: url} dict.

        Format: "name1:https://url1,name2:https://url2"
        Uses split(":", 1) so the URL's "://" is preserved.
        """
        if not self.rss_feeds:
            return {}
        result: dict[str, str] = {}
        for entry in self.rss_feeds.split(","):
            entry = entry.strip()
            if ":" in entry:
                name, url = entry.split(":", 1)
                name = name.strip()
                url = url.strip()
                if name and url:
                    result[name] = url
        return result

    def get_twitter_accounts(self) -> list[str]:
        """Parse TWITTER_ACCOUNTS env var into list of usernames."""
        if not self.twitter_accounts:
            return []
        return [a.strip() for a in self.twitter_accounts.split(",") if a.strip()]

    @property
    def vector_path(self) -> Path:
        return PROJECT_ROOT / "data" / "vector"

    @property
    def output_path(self) -> Path:
        return self.obsidian_vault / self.output_folder

    @property
    def bundles_path(self) -> Path:
        return self.output_path / "bundles"

    @property
    def morning_path(self) -> Path:
        return self.output_path / "morning"

    @property
    def cdp_profiles_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "chrome_cdp_profiles"

    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"

def get_settings() -> Settings:
    return Settings()
