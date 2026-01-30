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

    @property
    def output_path(self) -> Path:
        return self.obsidian_vault / self.output_folder

    @property
    def bundles_path(self) -> Path:
        return self.output_path / "bundles"

    @property
    def morning_path(self) -> Path:
        return self.output_path / "morning"

    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"

def get_settings() -> Settings:
    return Settings()
