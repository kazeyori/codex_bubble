import subprocess
import sys
import time
from pathlib import Path

from runtime_paths import DAEMON_LOG_PATH

APP_DIR = Path(__file__).resolve().parent
FETCHER = APP_DIR / "codex_usage_fetcher.py"
LOG_PATH = DAEMON_LOG_PATH


def log(message):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(message + "\n", encoding="utf-8")


def main():
    interval = 60
    while True:
        completed = subprocess.run(
            [sys.executable, str(FETCHER)],
            cwd=str(APP_DIR),
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            log((completed.stderr or completed.stdout or "fetch failed").strip())
        time.sleep(interval)


if __name__ == "__main__":
    main()
