"""Path utilities for ensuring directories exist."""
from pathlib import Path
from src.app.config import get_settings

def ensure_dirs() -> None:
    settings = get_settings()
    for d in [
        settings.output_path,
        settings.bundles_path,
        settings.morning_path,
        settings.db_path.parent,
        settings.log_path.parent,
        settings.screenshot_dir,
        settings.html_dump_dir,
    ]:
        d.mkdir(parents=True, exist_ok=True)
