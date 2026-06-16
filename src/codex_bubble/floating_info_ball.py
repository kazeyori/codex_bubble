import json
import subprocess
import sys
import threading
import traceback
import tkinter as tk
import webbrowser
from ctypes import (
    WINFUNCTYPE,
    Structure,
    byref,
    c_int,
    c_uint,
    c_ulong,
    c_void_p,
    sizeof,
    windll,
    wintypes,
)
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

from runtime_paths import CONFIG_PATH, DATA_PATH, DEFAULT_CONFIG_PATH, FLOATING_LOG_PATH, PROJECT_ROOT
from single_instance import SingleInstance
from update_checker import check_for_update, download_update_installer, friendly_error, read_current_version

LOG_PATH = FLOATING_LOG_PATH
TRANSPARENT = "#010203"
SCREEN_MARGIN = 8
DEFAULT_POSITION = {"x": 1380, "y": 220}
CREATE_NO_WINDOW = 0x08000000
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_USER = 0x0400
WM_TRAY_MESSAGE = WM_USER + 23
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010
NIIF_INFO = 0x00000001
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
LR_DEFAULTSIZE = 0x00000040
IDI_APPLICATION = 32512
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020
GA_ROOT = 2
DEFAULT_TRAY_TIP = "Codex 额度悬浮球 - 双击定位"
UPDATE_BADGE_TARGET = "__open_update__"
UPDATE_STARTUP_DELAY_MS = 15000
UPDATE_CHECK_INTERVAL_MS = 60 * 60 * 1000

DEFAULT_CONFIG = {
    "collapsed": True,
    "refresh_label": "刷新",
    "active_window": "five_hour",
    "visible_windows": ["five_hour"],
    "data_source": "static",
    "usage_windows": {
        "five_hour": {"label": "5小时", "remaining": "-", "reset": "-"},
        "weekly": {"label": "1周", "remaining": "-", "reset": "-"},
    },
    "position": dict(DEFAULT_POSITION),
    "colors": {
        "accent": "#007AFF",
        "glass": "#F7F7F8",
        "glass_soft": "#FFFFFF",
        "text": "#111111",
        "muted": "#8E8E93",
        "subtle": "#B8B8BE",
        "line": "#D9D9DE",
        "shadow": "#C7C7CC",
        "warning": "#FF9500",
        "icon": "#111111",
        "icon_text": "#FFFFFF",
    },
}


def deep_merge(base, update):
    result = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def disconnected_usage_windows():
    return {
        "five_hour": {"label": "5小时", "remaining": "-", "reset": "-"},
        "weekly": {"label": "1周", "remaining": "-", "reset": "-"},
    }


class Rect(Structure):
    _fields_ = [
        ("left", c_int),
        ("top", c_int),
        ("right", c_int),
        ("bottom", c_int),
    ]


class MonitorInfo(Structure):
    _fields_ = [
        ("cbSize", c_ulong),
        ("rcMonitor", Rect),
        ("rcWork", Rect),
        ("dwFlags", c_ulong),
    ]


def rect_to_tuple(rect):
    return (rect.left, rect.top, rect.right, rect.bottom)


class NotifyIconData(Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", wintypes.BYTE * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


WNDPROC = WINFUNCTYPE(wintypes.LPARAM, wintypes.HWND, c_uint, wintypes.WPARAM, wintypes.LPARAM)


class WindowClass(Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", c_int),
        ("cbWndExtra", c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class Message(Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


class TrayIcon:
    def __init__(self, root, on_locate, on_menu):
        self.root = root
        self.on_locate = on_locate
        self.on_menu = on_menu
        self.hwnd = None
        self.hicon = None
        self.class_name = f"CodexBubbleTray{threading.get_ident()}{id(self)}"
        self._wnd_proc = WNDPROC(self._window_proc)
        self.thread = None
        self.tip = DEFAULT_TRAY_TIP

    def start(self):
        if sys.platform != "win32":
            return
        self.thread = threading.Thread(target=self._run, name="CodexBubbleTray", daemon=True)
        self.thread.start()

    def stop(self):
        if self.hwnd:
            try:
                windll.user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
            except Exception:
                pass

    def _run(self):
        try:
            self._configure_win32_api()
            hinstance = windll.kernel32.GetModuleHandleW(None)
            wndclass = WindowClass()
            wndclass.style = 0
            wndclass.lpfnWndProc = self._wnd_proc
            wndclass.cbClsExtra = 0
            wndclass.cbWndExtra = 0
            wndclass.hInstance = hinstance
            wndclass.hIcon = 0
            wndclass.hCursor = 0
            wndclass.hbrBackground = 0
            wndclass.lpszMenuName = None
            wndclass.lpszClassName = self.class_name
            windll.user32.RegisterClassW(byref(wndclass))

            self.hwnd = windll.user32.CreateWindowExW(
                0,
                self.class_name,
                self.class_name,
                0,
                0,
                0,
                0,
                0,
                None,
                None,
                hinstance,
                None,
            )
            if not self.hwnd:
                return
            self._add_icon()
            msg = Message()
            while windll.user32.GetMessageW(byref(msg), None, 0, 0) > 0:
                windll.user32.TranslateMessage(byref(msg))
                windll.user32.DispatchMessageW(byref(msg))
        except Exception:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOG_PATH.write_text(traceback.format_exc(), encoding="utf-8")

    def _configure_win32_api(self):
        windll.kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
        windll.user32.CreateWindowExW.argtypes = [
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            c_int,
            c_int,
            c_int,
            c_int,
            wintypes.HWND,
            wintypes.HANDLE,
            wintypes.HINSTANCE,
            c_void_p,
        ]
        windll.user32.CreateWindowExW.restype = wintypes.HWND
        windll.user32.LoadImageW.restype = wintypes.HANDLE
        windll.user32.LoadIconW.restype = wintypes.HICON
        windll.user32.DefWindowProcW.restype = wintypes.LPARAM
        windll.shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, c_void_p]

    def _load_icon(self):
        icon_path = PROJECT_ROOT / "docs" / "assets" / "codex-bubble.ico"
        if icon_path.exists():
            icon = windll.user32.LoadImageW(
                None,
                str(icon_path),
                IMAGE_ICON,
                0,
                0,
                LR_LOADFROMFILE | LR_DEFAULTSIZE,
            )
            if icon:
                return icon
        return windll.user32.LoadIconW(None, IDI_APPLICATION)

    def _icon_data(self):
        data = NotifyIconData()
        data.cbSize = sizeof(NotifyIconData)
        data.hWnd = self.hwnd
        data.uID = 1
        return data

    def _add_icon(self):
        self.hicon = self._load_icon()
        data = self._icon_data()
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        data.uCallbackMessage = WM_TRAY_MESSAGE
        data.hIcon = self.hicon
        data.szTip = self.tip
        if not windll.shell32.Shell_NotifyIconW(NIM_ADD, byref(data)):
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOG_PATH.write_text("Shell_NotifyIconW(NIM_ADD) failed.\n", encoding="utf-8")
            return
        self.show_balloon("Codex 额度悬浮球", "双击托盘图标可定位悬浮球。")

    def set_tip(self, tip):
        self.tip = str(tip or DEFAULT_TRAY_TIP)[:127]
        if not self.hwnd:
            return
        data = self._icon_data()
        data.uFlags = NIF_TIP
        data.szTip = self.tip
        windll.shell32.Shell_NotifyIconW(NIM_MODIFY, byref(data))

    def show_balloon(self, title, message):
        if not self.hwnd:
            return
        data = self._icon_data()
        data.uFlags = NIF_INFO
        data.szInfoTitle = str(title)[:63]
        data.szInfo = str(message)[:255]
        data.dwInfoFlags = NIIF_INFO
        data.uTimeoutOrVersion = 3000
        windll.shell32.Shell_NotifyIconW(NIM_MODIFY, byref(data))

    def _delete_icon(self):
        if self.hwnd:
            data = self._icon_data()
            windll.shell32.Shell_NotifyIconW(NIM_DELETE, byref(data))
        if self.hicon:
            windll.user32.DestroyIcon(self.hicon)
            self.hicon = None

    def _window_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAY_MESSAGE:
            if int(lparam) == WM_LBUTTONDBLCLK:
                self.root.after(1, self.on_locate)
            elif int(lparam) == WM_RBUTTONUP:
                self.root.after(1, self.on_menu)
            return 0
        if msg == WM_CLOSE:
            windll.user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            self._delete_icon()
            windll.user32.PostQuitMessage(0)
            return 0
        return windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)


class FloatingInfoBall:
    def __init__(self):
        self.config_data = self.load_config()
        self.root = tk.Tk()
        self.root.title("Codex 额度悬浮球")
        self.apply_window_icon()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 1.0)
        self.root.configure(bg=TRANSPARENT)
        self.root.after(200, self.hide_from_taskbar)
        self.root.after(1200, self.hide_from_taskbar)

        try:
            self.root.wm_attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            self.root.configure(bg=self.config_data["colors"]["glass"])

        self.expanded = not bool(self.config_data.get("collapsed", True))
        self.last_refresh = datetime.now()
        self.drag_start = None
        self.was_dragged = False
        self.click_targets = []
        self.drag_threshold = 10
        self.is_animating = False
        self.update_checking = False
        self.update_downloading = False
        self.update_info = None
        self.update_notice_shown = False
        self.update_download_dialog = None
        self.location_hint = None
        self.menu = None
        self.tray_icon = TrayIcon(self.root, self.locate_from_tray, self.show_tray_menu)
        self.font_main = ("Microsoft YaHei UI", 10, "bold")
        self.font_meta = ("Microsoft YaHei UI", 9)
        self.font_chip = ("Microsoft YaHei UI", 9, "bold")
        self.font_refresh = ("Microsoft YaHei UI", 8)
        self.font_compact = ("Microsoft YaHei UI", 8, "bold")
        self.font_compact_refresh = ("Microsoft YaHei UI", 7)

        self.canvas = tk.Canvas(
            self.root,
            bg=TRANSPARENT,
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        self.canvas.pack()

        for target in (self.root, self.canvas):
            target.bind("<ButtonPress-1>", self.start_drag)
            target.bind("<B1-Motion>", self.drag)
            target.bind("<ButtonRelease-1>", self.end_drag)
            target.bind("<Button-3>", self.show_menu)
            target.bind("<Escape>", lambda _event: self.quit())

        pos = self.safe_start_position(self.config_data.get("position", {}))
        self.root.geometry("+0+0")
        self.set_window_position(int(pos.get("x", 1200)), int(pos.get("y", 220)))
        self.tray_icon.start()
        self.ensure_daemon_running()
        self.render()
        self.schedule_refresh()
        self.schedule_visibility_check()
        self.root.after(3000, self.refresh_now)
        self.root.after(UPDATE_STARTUP_DELAY_MS, self.schedule_update_check)

    def apply_window_icon(self):
        icon_path = PROJECT_ROOT / "docs" / "assets" / "codex-bubble.ico"
        try:
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass

    def hide_from_taskbar(self):
        if sys.platform != "win32":
            return
        try:
            hwnd = self.root.winfo_id()
            try:
                self.root.attributes("-toolwindow", True)
            except tk.TclError:
                pass
            windll.user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
            windll.user32.GetAncestor.restype = wintypes.HWND
            native_hwnd = windll.user32.GetAncestor(c_void_p(hwnd), GA_ROOT)
            if native_hwnd:
                hwnd = native_hwnd
            get_long = getattr(windll.user32, "GetWindowLongPtrW", windll.user32.GetWindowLongW)
            set_long = getattr(windll.user32, "SetWindowLongPtrW", windll.user32.SetWindowLongW)
            get_long.argtypes = [wintypes.HWND, c_int]
            get_long.restype = wintypes.LPARAM
            set_long.argtypes = [wintypes.HWND, c_int, wintypes.LPARAM]
            set_long.restype = wintypes.LPARAM
            style = int(get_long(hwnd, GWL_EXSTYLE))
            style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            set_long(hwnd, GWL_EXSTYLE, style)
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            self.root.withdraw()
            self.root.update_idletasks()
            windll.user32.SetWindowPos(
                hwnd,
                None,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
            )
            self.root.deiconify()
            self.set_window_position(x, y)
            self.root.lift()
        except Exception:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOG_PATH.write_text(traceback.format_exc(), encoding="utf-8")

    def load_config(self):
        if not CONFIG_PATH.exists() and DEFAULT_CONFIG_PATH.exists():
            return deep_merge(
                DEFAULT_CONFIG,
                json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8-sig")),
            )
        if not CONFIG_PATH.exists():
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(
                json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return dict(DEFAULT_CONFIG)

        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
            merged = deep_merge(DEFAULT_CONFIG, loaded)
            if "visible_windows" not in loaded and loaded.get("active_window") in ("five_hour", "weekly"):
                merged["visible_windows"] = [loaded["active_window"]]
            if "usage_windows" not in loaded and loaded.get("rows"):
                rows = loaded["rows"]
                if len(rows) > 0:
                    merged["usage_windows"]["five_hour"] = {
                        "label": rows[0].get("left", "5小时"),
                        "remaining": rows[0].get("middle", "-"),
                        "reset": rows[0].get("right", "-"),
                    }
                if len(rows) > 1:
                    merged["usage_windows"]["weekly"] = {
                        "label": rows[1].get("left", "1周"),
                        "remaining": rows[1].get("middle", "-"),
                        "reset": rows[1].get("right", "-"),
                    }
            return merged
        except Exception:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOG_PATH.write_text(traceback.format_exc(), encoding="utf-8")
            return dict(DEFAULT_CONFIG)

    def load_usage_data(self):
        if not DATA_PATH.exists():
            self.config_data["data_source"] = "static"
            self.config_data["usage_windows"] = disconnected_usage_windows()
            self.last_refresh = datetime.now()
            return
        try:
            data = json.loads(DATA_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(data.get("usage_windows"), dict):
                self.config_data["usage_windows"] = deep_merge(
                    self.config_data.get("usage_windows", {}),
                    data["usage_windows"],
                )
            self.config_data["data_source"] = data.get("data_source", "file")
            if not self.apply_snapshot_time(data.get("snapshot_time")):
                self.last_refresh = datetime.fromtimestamp(DATA_PATH.stat().st_mtime)
        except Exception:
            self.config_data["data_source"] = "static"
            self.config_data["usage_windows"] = disconnected_usage_windows()
            self.last_refresh = datetime.now()
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOG_PATH.write_text(traceback.format_exc(), encoding="utf-8")

    def apply_snapshot_time(self, value):
        if not value:
            return False
        try:
            text = str(value)
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            snapshot = datetime.fromisoformat(text)
            if snapshot.tzinfo is not None:
                snapshot = snapshot.astimezone().replace(tzinfo=None)
            self.last_refresh = snapshot
            return True
        except Exception:
            return False

    def save_config(self):
        saved_config = deep_merge(DEFAULT_CONFIG, self.config_data)
        saved_config["data_source"] = "static"
        saved_config["usage_windows"] = disconnected_usage_windows()
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(saved_config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def ensure_daemon_running(self):
        daemon_path = Path(__file__).resolve().parent / "codex_usage_daemon.py"
        try:
            subprocess.Popen(
                [sys.executable, str(daemon_path)],
                cwd=str(daemon_path.parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOG_PATH.write_text(traceback.format_exc(), encoding="utf-8")

    def run_fetcher_once(self):
        fetcher_path = Path(__file__).resolve().parent / "codex_usage_fetcher.py"
        try:
            completed = subprocess.run(
                [sys.executable, str(fetcher_path)],
                cwd=str(fetcher_path.parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
                creationflags=CREATE_NO_WINDOW,
            )
            if completed.returncode != 0:
                LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                LOG_PATH.write_text((completed.stderr or "fetch failed").strip(), encoding="utf-8")
                return False
            return True
        except Exception:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOG_PATH.write_text(traceback.format_exc(), encoding="utf-8")
            return False

    def save_position(self):
        self.config_data["position"] = {
            "x": self.root.winfo_x(),
            "y": self.root.winfo_y(),
        }
        self.config_data["collapsed"] = not self.expanded
        self.save_config()

    def set_window_position(self, x, y):
        self.set_toplevel_position(self.root, x, y)

    def set_toplevel_position(self, window, x, y):
        window.geometry(f"+{int(x)}+{int(y)}")
        window.update_idletasks()

    def safe_start_position(self, position):
        try:
            x = int(position.get("x", DEFAULT_POSITION["x"]))
            y = int(position.get("y", DEFAULT_POSITION["y"]))
        except Exception:
            return dict(DEFAULT_POSITION)
        if abs(x) <= SCREEN_MARGIN and abs(y) <= SCREEN_MARGIN:
            return dict(DEFAULT_POSITION)
        return {"x": x, "y": y}

    def display_work_areas(self):
        monitors = []

        def callback(monitor, _hdc, _rect, _data):
            info = MonitorInfo()
            info.cbSize = c_ulong(sizeof(MonitorInfo))
            if windll.user32.GetMonitorInfoW(c_void_p(monitor), byref(info)):
                monitors.append(rect_to_tuple(info.rcWork))
            return 1

        try:
            windll.user32.EnumDisplayMonitors(
                None,
                None,
                WINFUNCTYPE(c_int, wintypes.HMONITOR, wintypes.HDC, wintypes.LPRECT, wintypes.LPARAM)(callback),
                0,
            )
        except Exception:
            monitors = []

        if not monitors:
            monitors.append((0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()))
        return monitors

    def work_area_for_point(self, x, y):
        areas = self.display_work_areas()
        for area in areas:
            left, top, right, bottom = area
            if left <= x < right and top <= y < bottom:
                return area

        def distance(area):
            left, top, right, bottom = area
            clamped_x = min(max(x, left), right)
            clamped_y = min(max(y, top), bottom)
            return (x - clamped_x) ** 2 + (y - clamped_y) ** 2

        return min(areas, key=distance)

    def work_area_for_window(self):
        win_w = max(1, self.root.winfo_width())
        win_h = max(1, self.root.winfo_height())
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        center_x = x + win_w // 2
        center_y = y + win_h // 2
        areas = self.display_work_areas()

        def overlap(area):
            left, top, right, bottom = area
            overlap_w = max(0, min(x + win_w, right) - max(x, left))
            overlap_h = max(0, min(y + win_h, bottom) - max(y, top))
            return overlap_w * overlap_h

        best = max(areas, key=overlap)
        if overlap(best) > 0:
            return best
        return self.work_area_for_point(center_x, center_y)

    def clamp_to_area(self, x, y, width, height, area):
        left, top, right, bottom = area
        min_x = left + SCREEN_MARGIN
        min_y = top + SCREEN_MARGIN
        max_x = right - width - SCREEN_MARGIN
        max_y = bottom - height - SCREEN_MARGIN
        if max_x < min_x:
            x = min_x
        else:
            x = min(max(x, min_x), max_x)
        if max_y < min_y:
            y = min_y
        else:
            y = min(max(y, min_y), max_y)
        return int(x), int(y)

    def rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def compact_refresh_time_text(self):
        return f"{self.last_refresh:%H:%M}"

    def draw_refresh_glyph(self, x, y, color):
        self.canvas.create_arc(
            x,
            y - 5,
            x + 10,
            y + 5,
            start=35,
            extent=285,
            style="arc",
            outline=color,
            width=1,
        )
        self.canvas.create_polygon(
            x + 9,
            y - 5,
            x + 12,
            y - 6,
            x + 10,
            y - 2,
            fill=color,
            outline=color,
        )

    def draw_reset_glyph(self, x, y, color):
        self.canvas.create_oval(
            x,
            y - 5,
            x + 10,
            y + 5,
            outline=color,
            width=1,
        )
        self.canvas.create_line(x + 5, y, x + 5, y - 3, fill=color, width=1)
        self.canvas.create_line(x + 5, y, x + 8, y, fill=color, width=1)

    def active_usage(self):
        windows = self.config_data.get("usage_windows", {})
        active = self.config_data.get("active_window", "five_hour")
        return windows.get(active) or windows.get("five_hour") or {
            "label": "-",
            "remaining": "-",
            "reset": "-",
        }

    def visible_window_keys(self):
        windows = self.config_data.get("usage_windows", {})
        configured = self.config_data.get("visible_windows")
        if not isinstance(configured, list):
            configured = [self.config_data.get("active_window", "five_hour")]
        keys = []
        for key in configured:
            if key in ("five_hour", "weekly") and key in windows and key not in keys:
                keys.append(key)
        if not keys:
            active = self.config_data.get("active_window", "five_hour")
            keys = [active if active in windows else "five_hour"]
        return keys

    def visible_usage_rows(self):
        windows = self.config_data.get("usage_windows", {})
        return [(key, windows.get(key, {})) for key in self.visible_window_keys()]

    def compact_window_label(self, key, row):
        if key == "five_hour":
            return "5h"
        if key == "weekly":
            return "1w"
        label = str(row.get("label", ""))
        return label.replace("小时", "h").replace("周", "w")

    def compact_usage_lines(self, rows):
        lines = []
        for key, row in rows[:2]:
            lines.append(
                {
                    "label": self.compact_window_label(key, row),
                    "remaining": str(row.get("remaining", "-")),
                    "reset": self.compact_reset_text(row.get("reset", "-")),
                }
            )
        return lines

    def compact_reset_text(self, value):
        text = str(value or "-")
        if text == "-":
            return text
        return text.replace("月", "/").replace("日", "")

    def usage_rows(self):
        windows = self.config_data.get("usage_windows", {})
        return [
            ("five_hour", windows.get("five_hour", {})),
            ("weekly", windows.get("weekly", {})),
        ]

    def draw_codex_icon(self, x, y, size):
        colors = self.config_data["colors"]
        radius = max(5, int(size * 0.28))
        self.rounded_rect(
            x,
            y,
            x + size,
            y + size,
            radius,
            fill=colors["icon"],
            outline="",
        )
        self.canvas.create_text(
            x + size / 2,
            y + size / 2 + 0.5,
            text="C",
            fill=colors["icon_text"],
            font=("Segoe UI", max(8, int(size * 0.52)), "bold"),
        )

    def draw_switch_button(self, x, y, width, height, text, selected, target):
        colors = self.config_data["colors"]
        fill = colors["icon"] if selected else colors["glass"]
        outline = colors["icon"] if selected else colors["line"]
        text_color = colors["icon_text"] if selected else colors["text"]
        self.rounded_rect(x, y, x + width, y + height, 14, fill=fill, outline=outline)
        self.canvas.create_text(
            x + width / 2,
            y + height / 2,
            text=text,
            fill=text_color,
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        self.click_targets.append((x, y, x + width, y + height, target))

    def has_pending_update(self):
        return bool(self.update_info and self.update_info.has_update)

    def update_badge_label(self):
        return "更新"

    def draw_update_badge(self, x, y, width=44, height=22):
        colors = self.config_data["colors"]
        fill = colors.get("warning", "#FF9500")
        self.rounded_rect(x, y, x + width, y + height, 11, fill=fill, outline="")
        self.canvas.create_text(
            x + width / 2,
            y + height / 2,
            text=self.update_badge_label(),
            fill="#FFFFFF",
            font=("Microsoft YaHei UI", 8, "bold"),
        )
        self.click_targets.append((x, y, x + width, y + height, UPDATE_BADGE_TARGET))

    def schedule_refresh(self):
        self.load_usage_data()
        if not self.is_animating:
            self.render()
        self.root.after(60000, self.schedule_refresh)

    def render(self):
        self.click_targets = []
        self.canvas.delete("all")
        if self.expanded:
            self.render_panel()
        else:
            self.render_chip()
        self.root.update_idletasks()
        self.keep_on_screen()
        self.root.lift()

    def render_chip(self):
        colors = self.config_data["colors"]
        subtle = colors.get("subtle", "#B8B8BE")
        rows = self.visible_usage_rows()
        single_row = len(rows) <= 1
        row = rows[0][1] if rows else self.active_usage()
        has_update = self.has_pending_update()
        if single_row:
            width, height = (212 if has_update else 178), 54
            text_x = 42
            icon_x = 12
            remaining_x = width - 74 if has_update else width - 18
        else:
            width, height = (212 if has_update else 178), 54
            text_x = 42
            icon_x = 12
        self.canvas.configure(width=width, height=height)

        self.rounded_rect(6, 8, width - 3, height - 3, 20, fill=colors["shadow"], outline="")
        self.rounded_rect(3, 3, width - 7, height - 7, 20, fill=colors["glass"], outline=colors["line"])
        self.draw_codex_icon(icon_x, 16, 22)
        if single_row:
            self.canvas.create_text(
                text_x,
                18,
                text=str(row.get("label", "")),
                fill=colors["text"],
                font=self.font_chip,
                anchor="w",
            )
            self.canvas.create_text(
                remaining_x,
                18,
                text=str(row.get("remaining", "")),
                fill=colors["text"],
                font=self.font_chip,
                anchor="e",
            )
            self.draw_reset_glyph(text_x, 37, subtle)
            self.canvas.create_text(
                text_x + 14,
                37,
                text=str(row.get("reset", "")),
                fill=subtle,
                font=self.font_refresh,
                anchor="w",
            )
            refresh_x = width - 51
            self.draw_refresh_glyph(refresh_x, 37, colors["muted"])
            self.canvas.create_text(
                refresh_x + 15,
                37,
                text=self.compact_refresh_time_text(),
                fill=colors["muted"],
                font=self.font_refresh,
                anchor="w",
            )
        else:
            label_x = text_x
            remaining_x = text_x + 25
            reset_x = text_x + 58
            for index, line in enumerate(self.compact_usage_lines(rows)):
                y = 18 + index * 19
                self.canvas.create_text(
                    label_x,
                    y,
                    text=line["label"],
                    fill=colors["text"],
                    font=self.font_compact,
                    anchor="w",
                )
                self.canvas.create_text(
                    remaining_x,
                    y,
                    text=line["remaining"],
                    fill=colors["text"],
                    font=self.font_compact,
                    anchor="w",
                )
                self.canvas.create_text(
                    reset_x,
                    y,
                    text=line["reset"],
                    fill=subtle,
                    font=self.font_compact_refresh,
                    anchor="w",
                )
            refresh_x = width - 51
            self.draw_refresh_glyph(refresh_x, 41, colors["muted"])
            self.canvas.create_text(
                refresh_x + 15,
                41,
                text=self.compact_refresh_time_text(),
                fill=colors["muted"],
                font=self.font_compact_refresh,
                anchor="w",
            )
        if has_update:
            self.draw_update_badge(width - 58, 8)

    def render_panel(self):
        colors = self.config_data["colors"]
        visible_keys = set(self.visible_window_keys())
        has_update = self.has_pending_update()
        width, height = 294, 178
        self.canvas.configure(width=width, height=height)

        self.rounded_rect(8, 10, width - 4, height - 4, 22, fill=colors["shadow"], outline="")
        self.rounded_rect(4, 4, width - 10, height - 10, 22, fill=colors["glass"], outline=colors["line"])
        self.rounded_rect(13, 13, width - 19, height - 19, 16, fill=colors["glass_soft"], outline="")

        self.draw_codex_icon(24, 23, 22)
        self.canvas.create_text(
            56,
            34,
            text="Codex 用量" if self.config_data.get("data_source") != "static" else "Codex 用量 · 静态",
            fill=colors["text"],
            font=("Microsoft YaHei UI", 9, "bold"),
            anchor="w",
        )
        if has_update:
            self.draw_update_badge(width - 72, 22)
        self.canvas.create_line(24, 54, width - 30, 54, fill=colors["line"])

        y_positions = [72, 100]
        for index, (key, row) in enumerate(self.usage_rows()):
            y = y_positions[index]
            left_x = 26
            self.canvas.create_text(
                left_x,
                y,
                text=str(row.get("label", "")),
                fill=colors["text"],
                font=self.font_main,
                anchor="w",
            )
            self.canvas.create_text(
                182,
                y,
                text=str(row.get("remaining", "")),
                fill=colors["text"] if key in visible_keys else colors["muted"],
                font=self.font_meta,
                anchor="e",
            )
            self.canvas.create_text(
                width - 30,
                y,
                text=str(row.get("reset", "")),
                fill=colors["muted"],
                font=self.font_meta,
                anchor="e",
            )

        self.canvas.create_line(24, 116, width - 30, 116, fill=colors["line"])
        self.canvas.create_text(
            26,
            130,
            text="显示",
            fill=colors["muted"],
            font=self.font_refresh,
            anchor="w",
        )
        self.draw_switch_button(62, 121, 92, 30, "5小时", "five_hour" in visible_keys, "five_hour")
        self.draw_switch_button(162, 121, 78, 30, "1周", "weekly" in visible_keys, "weekly")
        self.draw_refresh_glyph(width - 82, 162, colors["muted"])
        self.canvas.create_text(
            width - 67,
            162,
            text=self.compact_refresh_time_text(),
            fill=colors["muted"],
            font=self.font_refresh,
            anchor="w",
        )

    def keep_on_screen(self):
        if self.drag_start:
            return
        old_x = self.root.winfo_x()
        old_y = self.root.winfo_y()
        win_w = self.root.winfo_width()
        win_h = self.root.winfo_height()
        x, y = self.clamp_to_area(
            self.root.winfo_x(),
            self.root.winfo_y(),
            win_w,
            win_h,
            self.work_area_for_window(),
        )
        self.set_window_position(x, y)
        return (old_x, old_y) != (x, y)

    def schedule_visibility_check(self):
        if not self.drag_start and not self.is_animating:
            moved = self.keep_on_screen()
            if moved:
                self.save_position()
        self.root.after(10000, self.schedule_visibility_check)

    def keep_on_screen_for_point(self, point_x, point_y):
        win_w = self.root.winfo_width()
        win_h = self.root.winfo_height()
        x, y = self.clamp_to_area(
            self.root.winfo_x(),
            self.root.winfo_y(),
            win_w,
            win_h,
            self.work_area_for_point(point_x, point_y),
        )
        self.set_window_position(x, y)

    def target_at(self, x, y):
        for x1, y1, x2, y2, target in self.click_targets:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return target
        return None

    def set_active_window(self, target):
        if self.is_animating:
            return
        self.toggle_visible_window(target)

    def toggle_visible_window(self, target):
        if target not in ("five_hour", "weekly"):
            return
        visible = self.visible_window_keys()
        if target in visible:
            if len(visible) > 1:
                visible.remove(target)
        else:
            visible.append(target)
        self.config_data["visible_windows"] = visible
        self.config_data["active_window"] = visible[0]
        self.render()
        self.save_position()

    def toggle_expanded(self):
        if self.is_animating:
            return
        self.animate_toggle(not self.expanded)

    def animate_toggle(self, next_expanded):
        self.is_animating = True
        self.drag_start = None
        self.animate_alpha([0.96, 0.93, 0.91], lambda: self.swap_view(next_expanded))

    def animate_alpha(self, values, done):
        if not values:
            done()
            return
        self.root.attributes("-alpha", values[0])
        self.root.after(18, lambda: self.animate_alpha(values[1:], done))

    def swap_view(self, next_expanded):
        self.expanded = next_expanded
        self.render()
        self.animate_alpha([0.93, 0.96, 0.98], self.finish_animation)

    def finish_animation(self):
        try:
            self.root.attributes("-alpha", 1.0)
            self.save_position()
        finally:
            self.is_animating = False

    def toggle_expanded_without_animation(self):
        self.expanded = not self.expanded
        self.render()
        self.save_position()

    def refresh_now(self):
        self.run_fetcher_once()
        self.load_usage_data()
        self.render()
        self.save_position()

    def schedule_update_check(self):
        self.check_update_now(interactive=False)
        self.root.after(UPDATE_CHECK_INTERVAL_MS, self.schedule_update_check)

    def check_update_now(self, interactive=True):
        if self.update_checking:
            if interactive:
                messagebox.showinfo("检查更新", "正在检查更新，请稍等。")
            return
        self.update_checking = True
        thread = threading.Thread(target=self.check_update_worker, args=(interactive,), daemon=True)
        thread.start()

    def check_update_worker(self, interactive):
        try:
            update_info = check_for_update()
            self.root.after(1, lambda: self.show_update_result(update_info, interactive))
        except Exception as error:
            message = friendly_error(error)
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOG_PATH.write_text(traceback.format_exc(), encoding="utf-8")
            self.root.after(1, lambda: self.show_update_error(message, interactive))
        finally:
            self.root.after(1, self.finish_update_check)

    def finish_update_check(self):
        self.update_checking = False

    def show_update_error(self, message, interactive):
        if interactive:
            messagebox.showerror("检查更新", message)

    def show_update_result(self, update_info, interactive=True):
        if update_info.has_update:
            self.update_info = update_info
            self.tray_icon.set_tip(f"Codex 额度悬浮球 - 有新版本 v{update_info.latest_version}")
            if not self.update_notice_shown:
                self.tray_icon.show_balloon(
                    "发现新版本",
                    f"v{update_info.latest_version} 可更新，点击“更新”后可下载并安装。",
                )
                self.update_notice_shown = True
            self.render()
            message = (
                f"发现新版本 v{update_info.latest_version}\n"
                f"当前版本 v{update_info.current_version}\n\n"
                "是否下载新版安装器？\n"
                "下载完成后会再询问是否立即安装。"
            )
            if interactive and messagebox.askyesno("发现更新", message):
                self.open_update_download(confirm=False)
            return

        self.update_info = None
        self.update_notice_shown = False
        self.tray_icon.set_tip(DEFAULT_TRAY_TIP)
        self.render()
        if interactive:
            messagebox.showinfo(
                "检查更新",
                f"当前已是最新版本 v{update_info.current_version}",
            )

    def open_update_download(self, confirm=True):
        if not self.has_pending_update():
            self.check_update_now(interactive=True)
            return
        if self.update_downloading:
            messagebox.showinfo("下载更新", "新版安装器正在下载，请稍等。")
            return
        if not self.update_info.asset_url:
            messagebox.showwarning("下载更新", "没有找到新版安装器下载地址，将打开 Release 页面。")
            webbrowser.open(self.update_info.release_url)
            return
        if confirm:
            message = (
                f"将下载 v{self.update_info.latest_version} 安装器到临时目录。\n"
                "下载完成后会再询问是否立即安装。\n\n"
                "是否开始下载？"
            )
            if not messagebox.askyesno("下载更新", message):
                return
        self.start_update_download()

    def start_update_download(self):
        self.update_downloading = True
        self.show_update_download_dialog()
        self.tray_icon.show_balloon("下载更新", f"正在下载 v{self.update_info.latest_version} 安装器。")
        thread = threading.Thread(target=self.download_update_worker, daemon=True)
        thread.start()

    def download_update_worker(self):
        try:
            update_info = self.update_info

            def report(downloaded, total):
                self.root.after(
                    1,
                    lambda downloaded=downloaded, total=total: self.update_download_progress(downloaded, total),
                )

            installer_path = download_update_installer(update_info, progress_callback=report)
            self.root.after(1, lambda: self.finish_update_download(installer_path))
        except Exception as error:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOG_PATH.write_text(traceback.format_exc(), encoding="utf-8")
            self.root.after(1, lambda error=error: self.handle_update_download_error(error))

    def format_download_size(self, value):
        value = max(0, int(value or 0))
        if value >= 1024 * 1024:
            return f"{value / 1024 / 1024:.1f} MB"
        if value >= 1024:
            return f"{value / 1024:.0f} KB"
        return f"{value} B"

    def show_update_download_dialog(self):
        self.close_update_download_dialog()
        colors = self.config_data["colors"]
        dialog = tk.Toplevel(self.root)
        dialog.title("下载更新")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        dialog.configure(bg=colors["glass"])

        frame = tk.Frame(dialog, bg=colors["glass"], padx=18, pady=16)
        frame.pack(fill="both", expand=True)
        title = tk.Label(
            frame,
            text=f"正在下载 v{self.update_info.latest_version}",
            bg=colors["glass"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        )
        title.pack(fill="x")
        status = tk.Label(
            frame,
            text="准备下载...",
            bg=colors["glass"],
            fg=colors["muted"],
            font=("Microsoft YaHei UI", 9),
            anchor="w",
        )
        status.pack(fill="x", pady=(8, 6))
        canvas = tk.Canvas(frame, width=280, height=10, bg=colors["glass"], highlightthickness=0, bd=0)
        canvas.pack(fill="x")
        canvas.create_rectangle(0, 2, 280, 8, fill=colors["line"], outline="")
        progress = canvas.create_rectangle(0, 2, 0, 8, fill=colors["accent"], outline="")

        dialog.update_idletasks()
        x = self.root.winfo_x() + max(0, int((self.root.winfo_width() - dialog.winfo_width()) / 2))
        y = self.root.winfo_y() + self.root.winfo_height() + 10
        dialog.geometry(f"+{x}+{y}")

        self.update_download_dialog = {
            "window": dialog,
            "status": status,
            "canvas": canvas,
            "progress": progress,
        }

    def update_download_progress(self, downloaded, total):
        dialog = self.update_download_dialog
        if not dialog:
            return
        status = dialog["status"]
        canvas = dialog["canvas"]
        progress = dialog["progress"]
        if total:
            ratio = max(0, min(1, downloaded / total))
            status.configure(
                text=(
                    f"{self.format_download_size(downloaded)} / "
                    f"{self.format_download_size(total)} ({ratio * 100:.0f}%)"
                )
            )
            canvas.coords(progress, 0, 2, int(280 * ratio), 8)
        else:
            status.configure(text=f"已下载 {self.format_download_size(downloaded)}")
            canvas.coords(progress, 0, 2, 140, 8)

    def close_update_download_dialog(self):
        dialog = self.update_download_dialog
        self.update_download_dialog = None
        if dialog:
            try:
                dialog["window"].destroy()
            except Exception:
                pass

    def finish_update_download(self, installer_path):
        self.update_downloading = False
        self.update_download_progress(1, 1)
        self.close_update_download_dialog()
        message = (
            f"新版安装器已下载完成：\n{installer_path}\n\n"
            "是否立即安装？安装器会退出当前悬浮球并覆盖安装。"
        )
        if messagebox.askyesno("下载完成", message):
            self.launch_update_installer(installer_path)

    def handle_update_download_error(self, error):
        self.update_downloading = False
        self.close_update_download_dialog()
        message = f"下载新版安装器失败：\n{error}\n\n是否打开 Release 下载页面？"
        if messagebox.askyesno("下载失败", message):
            webbrowser.open(self.update_info.asset_url or self.update_info.release_url)

    def launch_update_installer(self, installer_path):
        try:
            subprocess.Popen(
                [str(installer_path)],
                cwd=str(Path(installer_path).parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
            self.root.after(500, self.quit)
        except Exception:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOG_PATH.write_text(traceback.format_exc(), encoding="utf-8")
            messagebox.showerror("启动安装器失败", "安装器已下载，但启动失败，请到临时目录中手动运行。")

    def locate_from_tray(self):
        self.close_menu()
        self.drag_start = None
        self.root.deiconify()
        self.root.update_idletasks()
        self.keep_on_screen()
        self.save_position()
        try:
            self.root.attributes("-topmost", False)
            self.root.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.root.lift()
        self.show_location_hint()

    def cursor_position(self):
        point = wintypes.POINT()
        try:
            if windll.user32.GetCursorPos(byref(point)):
                return int(point.x), int(point.y)
        except Exception:
            pass
        return self.root.winfo_x(), self.root.winfo_y()

    def show_tray_menu(self):
        self.close_menu()
        x, y = self.cursor_position()
        menu = tk.Menu(self.root, tearoff=0)
        if self.has_pending_update():
            menu.add_command(
                label=f"更新到 v{self.update_info.latest_version}",
                command=lambda: self.run_menu_action(self.open_update_download),
            )
            menu.add_separator()
        menu.add_command(label="定位悬浮球", command=lambda: self.run_menu_action(self.locate_from_tray))
        menu.add_separator()
        menu.add_command(label="退出", command=lambda: self.run_menu_action(self.quit))
        self.menu = menu
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def show_location_hint(self):
        self.destroy_location_hint()
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        width = max(1, self.root.winfo_width())
        height = max(1, self.root.winfo_height())
        hint_width = 210
        hint_height = 56
        area = self.work_area_for_point(x + width // 2, y + height // 2)
        hint_x = x + (width - hint_width) // 2
        hint_y = y - hint_height - 8
        if hint_y < area[1] + SCREEN_MARGIN:
            hint_y = y + height + 8
        hint_x, hint_y = self.clamp_to_area(hint_x, hint_y, hint_width, hint_height, area)

        hint = tk.Toplevel(self.root)
        hint.overrideredirect(True)
        hint.attributes("-topmost", True)
        hint.attributes("-alpha", 0.96)
        hint.configure(bg=TRANSPARENT)
        try:
            hint.wm_attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            hint.configure(bg="#111111")

        canvas = tk.Canvas(hint, width=hint_width, height=hint_height, bg=TRANSPARENT, highlightthickness=0, bd=0)
        canvas.pack()
        canvas.create_rectangle(8, 6, hint_width - 8, 40, fill="#111111", outline="#007AFF", width=2)
        canvas.create_text(
            hint_width / 2,
            23,
            text="悬浮球在这里",
            fill="#FFFFFF",
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        if hint_y < y:
            canvas.create_polygon(
                hint_width / 2 - 9,
                40,
                hint_width / 2 + 9,
                40,
                hint_width / 2,
                52,
                fill="#007AFF",
                outline="",
            )
        else:
            canvas.create_polygon(
                hint_width / 2 - 9,
                8,
                hint_width / 2 + 9,
                8,
                hint_width / 2,
                0,
                fill="#007AFF",
                outline="",
            )
        hint.geometry(f"{hint_width}x{hint_height}+{hint_x}+{hint_y}")
        self.location_hint = hint
        hint.after(1800, self.destroy_location_hint)

    def destroy_location_hint(self):
        if self.location_hint is not None:
            try:
                self.location_hint.destroy()
            except tk.TclError:
                pass
        self.location_hint = None

    def run_menu_action(self, action, *args):
        self.close_menu()
        self.drag_start = None
        self.was_dragged = False
        self.root.after(1, lambda: action(*args))

    def close_menu(self):
        if self.menu is not None:
            try:
                self.menu.unpost()
            except tk.TclError:
                pass
        self.menu = None

    def show_menu(self, event):
        self.close_menu()
        visible_keys = set(self.visible_window_keys())
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(
            label="收起" if self.expanded else "展开",
            command=lambda: self.run_menu_action(self.toggle_expanded_without_animation),
        )
        menu.add_separator()
        menu.add_command(
            label=("✓ " if "five_hour" in visible_keys else "  ") + "显示 5小时",
            command=lambda: self.run_menu_action(self.set_active_window, "five_hour"),
        )
        menu.add_command(
            label=("✓ " if "weekly" in visible_keys else "  ") + "显示 1周",
            command=lambda: self.run_menu_action(self.set_active_window, "weekly"),
        )
        menu.add_separator()
        menu.add_command(label="刷新", command=lambda: self.run_menu_action(self.refresh_now))
        if self.has_pending_update():
            menu.add_command(
                label=f"更新到 v{self.update_info.latest_version}",
                command=lambda: self.run_menu_action(self.open_update_download),
            )
        menu.add_command(label="检查更新", command=lambda: self.run_menu_action(self.check_update_now))
        menu.add_command(label=f"当前版本 v{read_current_version()}", state="disabled")
        menu.add_command(
            label="数据源: " + ("静态" if self.config_data.get("data_source") == "static" else "文件"),
            command=lambda: self.run_menu_action(self.refresh_now),
        )
        menu.add_separator()
        menu.add_command(label="退出", command=lambda: self.run_menu_action(self.quit))

        self.menu = menu
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def start_drag(self, event):
        if self.is_animating:
            self.drag_start = None
            return
        self.close_menu()
        self.drag_start = (
            event.x_root,
            event.y_root,
            self.root.winfo_x(),
            self.root.winfo_y(),
        )
        self.was_dragged = False

    def drag(self, event):
        if not self.drag_start:
            return
        start_x, start_y, win_x, win_y = self.drag_start
        dx = event.x_root - start_x
        dy = event.y_root - start_y
        if not self.was_dragged and abs(dx) <= self.drag_threshold and abs(dy) <= self.drag_threshold:
            return
        if not self.was_dragged:
            self.was_dragged = True
        self.set_window_position(win_x + dx, win_y + dy)

    def end_drag(self, event):
        if self.is_animating or not self.drag_start:
            self.drag_start = None
            return
        if self.drag_start and self.was_dragged:
            self.keep_on_screen_for_point(event.x_root, event.y_root)
            self.save_position()
        elif not self.was_dragged:
            target = self.target_at(event.x, event.y)
            if target == UPDATE_BADGE_TARGET:
                self.open_update_download()
            elif target in ("five_hour", "weekly"):
                self.toggle_visible_window(target)
            else:
                self.toggle_expanded()
                self.drag_start = None
                return
            self.save_position()
        self.drag_start = None

    def quit(self):
        self.destroy_location_hint()
        self.tray_icon.stop()
        self.save_position()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    instance = SingleInstance("Local\\CodexBubbleFloatingInfoBall")
    if not instance.acquire():
        sys.exit(0)
    try:
        FloatingInfoBall().run()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOG_PATH.write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        instance.release()
