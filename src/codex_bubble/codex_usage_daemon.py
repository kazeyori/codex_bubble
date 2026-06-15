import subprocess
import sys
import time
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parents[1]
FETCHER = APP_DIR / "codex_usage_fetcher.py"
LOG_PATH = PROJECT_ROOT / "logs" / "codex_usage_daemon.log"


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
