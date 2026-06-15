import os
import tempfile
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parents[1]
APP_NAME = "CodexBubble"


def runtime_root_candidates():
    candidates = []

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / APP_NAME)
    candidates.append(Path.home() / "AppData" / "Local" / APP_NAME)
    candidates.append(Path(tempfile.gettempdir()) / APP_NAME)
    return candidates


def root_candidates():
    user_roots = runtime_root_candidates()
    if (PROJECT_ROOT / ".git").exists():
        return [*user_roots, PROJECT_ROOT]
    return [PROJECT_ROOT, *user_roots]


def is_writable_dir(path):
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def runtime_dir(project_relative):
    for root in root_candidates():
        candidate = root / project_relative
        if is_writable_dir(candidate):
            return candidate

    last_resort = Path(tempfile.gettempdir()) / APP_NAME / project_relative
    last_resort.mkdir(parents=True, exist_ok=True)
    return last_resort


CONFIG_DIR = runtime_dir("config")
DATA_DIR = runtime_dir("data")
LOG_DIR = runtime_dir("logs")

CONFIG_PATH = CONFIG_DIR / "floating_info_ball_config.json"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "floating_info_ball_config.json"
DATA_PATH = DATA_DIR / "codex_usage_data.json"
FLOATING_LOG_PATH = LOG_DIR / "floating_info_ball.log"
FETCHER_LOG_PATH = LOG_DIR / "codex_usage_fetcher.log"
DAEMON_LOG_PATH = LOG_DIR / "codex_usage_daemon.log"
