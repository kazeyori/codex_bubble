import os
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parents[1]
APP_NAME = "CodexBubble"


def user_runtime_root():
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_NAME
    return Path.home() / "AppData" / "Local" / APP_NAME


USER_RUNTIME_ROOT = user_runtime_root()


def is_writable_dir(path):
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def runtime_dir(project_relative):
    preferred = PROJECT_ROOT / project_relative
    if is_writable_dir(preferred):
        return preferred

    fallback = USER_RUNTIME_ROOT / project_relative
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


CONFIG_DIR = runtime_dir("config")
DATA_DIR = runtime_dir("data")
LOG_DIR = runtime_dir("logs")

CONFIG_PATH = CONFIG_DIR / "floating_info_ball_config.json"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "floating_info_ball_config.json"
DATA_PATH = DATA_DIR / "codex_usage_data.json"
FLOATING_LOG_PATH = LOG_DIR / "floating_info_ball.log"
FETCHER_LOG_PATH = LOG_DIR / "codex_usage_fetcher.log"
DAEMON_LOG_PATH = LOG_DIR / "codex_usage_daemon.log"
