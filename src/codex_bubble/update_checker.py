import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from runtime_paths import PROJECT_ROOT


REPO_API_URL = "https://api.github.com/repos/chinnkenni/codex_bubble/releases/latest"
REPO_RELEASES_URL = "https://github.com/chinnkenni/codex_bubble/releases/latest"
REPO_RELEASE_TAG_URL = "https://github.com/chinnkenni/codex_bubble/releases/tag/{tag}"
REPO_DOWNLOAD_URL = "https://github.com/chinnkenni/codex_bubble/releases/download/{tag}/codex-bubble-setup-{tag}.exe"
REQUEST_TIMEOUT_SECONDS = 8


@dataclass
class UpdateInfo:
    current_version: str
    latest_version: str
    has_update: bool
    release_url: str
    asset_url: str
    release_name: str


def normalize_version(version):
    return str(version or "").strip().lstrip("vV")


def version_tuple(version):
    normalized = normalize_version(version)
    parts = re.findall(r"\d+", normalized)
    if not parts:
        return (0,)
    return tuple(int(part) for part in parts[:4])


def is_newer_version(latest, current):
    latest_tuple = version_tuple(latest)
    current_tuple = version_tuple(current)
    width = max(len(latest_tuple), len(current_tuple))
    latest_tuple += (0,) * (width - len(latest_tuple))
    current_tuple += (0,) * (width - len(current_tuple))
    return latest_tuple > current_tuple


def read_current_version():
    version_path = PROJECT_ROOT / "VERSION"
    try:
        return normalize_version(version_path.read_text(encoding="utf-8-sig"))
    except OSError:
        return "0.0.0"


def request_url(url, accept="text/html"):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": "CodexBubble",
        },
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.geturl(), response.read().decode("utf-8", errors="replace")


def release_from_tag(tag):
    normalized = normalize_version(tag)
    if not normalized:
        return {}
    canonical_tag = f"v{normalized}"
    asset_url = REPO_DOWNLOAD_URL.format(tag=canonical_tag)
    return {
        "tag_name": canonical_tag,
        "name": canonical_tag,
        "html_url": REPO_RELEASE_TAG_URL.format(tag=canonical_tag),
        "assets": [
            {
                "name": f"codex-bubble-setup-{canonical_tag}.exe",
                "browser_download_url": asset_url,
            }
        ],
    }


def fetch_latest_release_from_redirect():
    final_url, body = request_url(REPO_RELEASES_URL)
    match = re.search(r"/releases/tag/([^/?#]+)", final_url)
    if not match:
        match = re.search(r"/chinnkenni/codex_bubble/releases/tag/([^\"?#]+)", body)
    if not match:
        raise ValueError("无法从 GitHub Release 页面解析最新版本号。")
    return release_from_tag(match.group(1))


def fetch_latest_release_from_api():
    _final_url, body = request_url(REPO_API_URL, accept="application/vnd.github+json")
    return json.loads(body)


def fetch_latest_release():
    errors = []
    for fetcher in (fetch_latest_release_from_redirect, fetch_latest_release_from_api):
        try:
            return fetcher()
        except Exception as error:
            errors.append(error)
    if errors and all(isinstance(error, urllib.error.URLError) for error in errors):
        raise errors[0]
    raise RuntimeError("; ".join(str(error) for error in errors))


def extract_asset_url(release_data):
    fallback = ""
    for asset in release_data.get("assets", []):
        name = asset.get("name", "")
        if name.endswith(".exe") and "codex-bubble-setup" in name:
            return asset.get("browser_download_url", "")
        if name.endswith(".zip") and "codex-bubble" in name:
            fallback = asset.get("browser_download_url", "")
    return fallback


def check_for_update():
    current = read_current_version()
    release_data = fetch_latest_release()
    latest = normalize_version(release_data.get("tag_name") or release_data.get("name"))
    release_url = release_data.get("html_url") or REPO_RELEASES_URL
    asset_url = extract_asset_url(release_data)
    return UpdateInfo(
        current_version=current,
        latest_version=latest or current,
        has_update=is_newer_version(latest, current),
        release_url=release_url,
        asset_url=asset_url,
        release_name=release_data.get("name", ""),
    )


def friendly_error(error):
    if isinstance(error, urllib.error.URLError):
        return "网络连接失败，请稍后再试。"
    return "检查更新失败，请稍后再试。"
