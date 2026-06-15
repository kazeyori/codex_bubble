import base64
import json
import locale
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
DATA_PATH = APP_DIR / "codex_usage_data.json"
LOG_PATH = APP_DIR / "codex_usage_fetcher.log"
WHAM_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"

LABEL_USAGE = "\u7528\u91cf"
LABEL_FIVE_HOUR = "5\u5c0f\u65f6"
LABEL_WEEKLY = "1\u5468"
LABEL_DAY = "1\u5929"
LABEL_MINUTE = "\u5206\u949f"


def write_log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LOG_PATH.write_text(f"[{timestamp}] {message}\n", encoding="utf-8")


def decode_base64url(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def chatgpt_account_id_from_token(token):
    parts = token.split(".")
    if len(parts) < 2:
        return None
    try:
        payload = json.loads(decode_base64url(parts[1]).decode("utf-8"))
    except Exception:
        return None
    auth = payload.get("https://api.openai.com/auth")
    if isinstance(auth, dict) and isinstance(auth.get("chatgpt_account_id"), str):
        return auth["chatgpt_account_id"]
    return None


def percent_remaining_from_used(used_percent):
    value = float(used_percent or 0)
    remaining = max(0, min(100, 100 - value))
    if remaining >= 10 or remaining.is_integer():
        return f"{remaining:.0f}%"
    return f"{remaining:.1f}%"


def format_reset(value):
    if value in (None, "", "--"):
        return "--"
    try:
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        reset = datetime.fromtimestamp(timestamp)
    except (TypeError, ValueError, OSError):
        return str(value)

    now = datetime.now()
    if reset.date() == now.date():
        return reset.strftime("%H:%M")
    return f"{reset.month}\u6708{reset.day}\u65e5"


def window_label(minutes=None, seconds=None, fallback=LABEL_USAGE):
    if seconds is not None and minutes is None:
        minutes = float(seconds) / 60
    if minutes is None:
        return fallback
    minutes = float(minutes)
    if abs(minutes - 300) <= 20:
        return LABEL_FIVE_HOUR
    if abs(minutes - 10080) <= 600:
        return LABEL_WEEKLY
    if abs(minutes - 1440) <= 120:
        return LABEL_DAY
    if minutes >= 60:
        return f"{round(minutes / 60)}\u5c0f\u65f6"
    return f"{round(minutes)}{LABEL_MINUTE}"


def normalize_codex_window(window, fallback_label):
    if not isinstance(window, dict):
        return None
    used = window.get("used_percent", window.get("usedPercent"))
    remaining = window.get("remaining_percent", window.get("remainingPercent"))
    reset = window.get(
        "reset_at",
        window.get("resets_at", window.get("resetAt", window.get("resetsAt"))),
    )
    seconds = window.get("limit_window_seconds")
    minutes = window.get("windowDurationMins", window.get("window_minutes"))

    if remaining is None and used is not None:
        remaining = percent_remaining_from_used(used)
    elif remaining is not None:
        if isinstance(remaining, (int, float)):
            remaining = f"{float(remaining):.0f}%"
        else:
            remaining = str(remaining)
    else:
        remaining = "--"

    return {
        "label": window_label(minutes=minutes, seconds=seconds, fallback=fallback_label),
        "remaining": remaining,
        "reset": format_reset(reset),
    }


def normalize_codex_rate_limit(payload):
    rate_limit = payload.get("rate_limit")
    if not isinstance(rate_limit, dict):
        rate_limit = payload.get("rate_limits")
    if not isinstance(rate_limit, dict):
        return None

    windows = []
    for name in ("primary_window", "secondary_window", "primary", "secondary"):
        item = normalize_codex_window(rate_limit.get(name), LABEL_USAGE)
        if item:
            windows.append(item)

    if not windows:
        return None

    five_hour = next((w for w in windows if w["label"] == LABEL_FIVE_HOUR), windows[0])
    weekly = next(
        (w for w in windows if w["label"] == LABEL_WEEKLY),
        windows[1] if len(windows) > 1 else windows[0],
    )

    return {
        "data_source": "codex-rate-limits",
        "active_window": "five_hour",
        "usage_windows": {
            "five_hour": five_hour,
            "weekly": weekly,
        },
    }


def normalize_payload(payload, source):
    if "usage_windows" in payload:
        payload.setdefault("data_source", source)
        return payload

    codex_payload = normalize_codex_rate_limit(payload)
    if codex_payload is not None:
        codex_payload["data_source"] = source
        return codex_payload

    five_hour = payload.get("five_hour") or payload.get("fiveHour") or {}
    weekly = payload.get("weekly") or payload.get("week") or {}
    if five_hour or weekly:
        return {
            "data_source": source,
            "active_window": payload.get("active_window", "five_hour"),
            "usage_windows": {
                "five_hour": {
                    "label": five_hour.get("label", LABEL_FIVE_HOUR),
                    "remaining": str(five_hour.get("remaining", five_hour.get("percent", "--"))),
                    "reset": str(five_hour.get("reset", five_hour.get("resets_at", "--"))),
                },
                "weekly": {
                    "label": weekly.get("label", LABEL_WEEKLY),
                    "remaining": str(weekly.get("remaining", weekly.get("percent", "--"))),
                    "reset": str(weekly.get("reset", weekly.get("resets_at", "--"))),
                },
            },
        }

    raise ValueError("Payload does not contain usage data.")


def fetch_from_command():
    command = os.environ.get("CODEX_USAGE_COMMAND")
    if not command:
        return None
    completed = subprocess.run(
        command,
        shell=True,
        check=True,
        capture_output=True,
    )
    raw = completed.stdout
    for encoding in ("utf-8", locale.getpreferredencoding(False), "gbk"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            text = ""
    if not text:
        text = raw.decode("utf-8", errors="replace")
    return normalize_payload(json.loads(text), "cli")


def fetch_from_http():
    source = os.environ.get("CODEX_USAGE_SOURCE", "").strip().lower()
    url = os.environ.get("CODEX_USAGE_URL")
    token = os.environ.get("CODEX_ACCESS_TOKEN")
    if source == "wham" and not url:
        url = WHAM_USAGE_URL
    if not url:
        return None

    headers = {
        "Accept": "application/json",
        "originator": "codex_desktop",
        "User-Agent": "Codex Desktop floating usage helper",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        account_id = chatgpt_account_id_from_token(token)
        if account_id:
            headers["ChatGPT-Account-Id"] = account_id

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return normalize_payload(payload, "api")


def parse_event_timestamp(value, fallback):
    if not value:
        return fallback
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value).timestamp()
    except Exception:
        return fallback


def codex_home():
    configured = os.environ.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".codex"


def iter_session_files():
    root = codex_home()
    candidates = []
    for base in (root / "sessions", root / "archived_sessions"):
        if not base.exists():
            continue
        candidates.extend(path for path in base.rglob("rollout-*.jsonl") if path.is_file())
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[:250]


def latest_session_rate_limits():
    latest = None
    for path in iter_session_files():
        fallback_ts = path.stat().st_mtime
        try:
            handle = path.open("r", encoding="utf-8", errors="replace")
        except OSError:
            continue
        with handle:
            for line in handle:
                if '"rate_limits"' not in line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rate_limits = event.get("rate_limits")
                if not isinstance(rate_limits, dict):
                    payload = event.get("payload")
                    if isinstance(payload, dict):
                        rate_limits = payload.get("rate_limits")
                if not isinstance(rate_limits, dict):
                    continue
                if not (rate_limits.get("primary") or rate_limits.get("secondary")):
                    continue
                event_ts = parse_event_timestamp(event.get("timestamp"), fallback_ts)
                if latest is None or event_ts > latest[0]:
                    latest = (event_ts, rate_limits, str(path))
    return latest


def fetch_from_codex_sessions():
    latest = latest_session_rate_limits()
    if latest is None:
        return None
    event_ts, rate_limits, source_path = latest
    payload = normalize_payload({"rate_limits": rate_limits}, "codex-local-sessions")
    payload["snapshot_time"] = datetime.fromtimestamp(event_ts, tz=timezone.utc).isoformat()
    payload["snapshot_source"] = source_path
    return payload


def main():
    try:
        source = os.environ.get("CODEX_USAGE_SOURCE", "").strip().lower()
        if source in {"codex_sessions", "sessions", "local_sessions"}:
            payload = fetch_from_codex_sessions()
        else:
            payload = fetch_from_command()
            if payload is None:
                payload = fetch_from_http()
            if payload is None and source not in {"wham", "http", "api"}:
                payload = fetch_from_codex_sessions()

        if payload is None:
            raise RuntimeError(
                "No Codex rate-limit data found. Use Codex once, or set CODEX_USAGE_COMMAND/CODEX_USAGE_URL."
            )

        DATA_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"wrote {DATA_PATH}")
    except (urllib.error.HTTPError, urllib.error.URLError, Exception) as exc:
        write_log(f"{type(exc).__name__}: {exc}")
        print(f"failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
