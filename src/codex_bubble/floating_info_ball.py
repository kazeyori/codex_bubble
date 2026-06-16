import json
import subprocess
import sys
import threading
import traceback
import tkinter as tk
import webbrowser
from ctypes import WINFUNCTYPE, Structure, byref, c_int, c_ulong, c_void_p, sizeof, windll, wintypes
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

from runtime_paths import CONFIG_PATH, DATA_PATH, DEFAULT_CONFIG_PATH, FLOATING_LOG_PATH, PROJECT_ROOT
from single_instance import SingleInstance
from update_checker import check_for_update, friendly_error

LOG_PATH = FLOATING_LOG_PATH
TRANSPARENT = "#010203"
SCREEN_MARGIN = 8
DEFAULT_POSITION = {"x": 1380, "y": 220}
CREATE_NO_WINDOW = 0x08000000

DEFAULT_CONFIG = {
    "collapsed": True,
    "refresh_label": "刷新",
    "active_window": "five_hour",
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
        "line": "#D9D9DE",
        "shadow": "#C7C7CC",
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
        self.menu = None
        self.font_main = ("Microsoft YaHei UI", 10, "bold")
        self.font_meta = ("Microsoft YaHei UI", 9)
        self.font_chip = ("Microsoft YaHei UI", 9, "bold")
        self.font_refresh = ("Microsoft YaHei UI", 8)

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
        self.ensure_daemon_running()
        self.render()
        self.schedule_refresh()
        self.root.after(3000, self.refresh_now)

    def apply_window_icon(self):
        icon_path = PROJECT_ROOT / "docs" / "assets" / "codex-bubble.ico"
        try:
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass

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
            return
        try:
            data = json.loads(DATA_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(data.get("usage_windows"), dict):
                self.config_data["usage_windows"] = deep_merge(
                    self.config_data.get("usage_windows", {}),
                    data["usage_windows"],
                )
            if data.get("active_window") in ("five_hour", "weekly"):
                self.config_data["active_window"] = data["active_window"]
            self.config_data["data_source"] = data.get("data_source", "file")
        except Exception:
            self.config_data["data_source"] = "static"
            self.config_data["usage_windows"] = disconnected_usage_windows()
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOG_PATH.write_text(traceback.format_exc(), encoding="utf-8")

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

    def refresh_text(self):
        label = str(self.config_data.get("refresh_label", "刷新"))
        if self.config_data.get("data_source", "static") == "static":
            return f"未连接 {self.last_refresh:%H:%M}"
        return f"{label} {self.last_refresh:%H:%M}"

    def active_usage(self):
        windows = self.config_data.get("usage_windows", {})
        active = self.config_data.get("active_window", "five_hour")
        return windows.get(active) or windows.get("five_hour") or {
            "label": "-",
            "remaining": "-",
            "reset": "-",
        }

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

    def schedule_refresh(self):
        self.load_usage_data()
        self.last_refresh = datetime.now()
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
        row = self.active_usage()
        width, height = 172, 54
        self.canvas.configure(width=width, height=height)

        self.rounded_rect(6, 8, width - 3, height - 3, 20, fill=colors["shadow"], outline="")
        self.rounded_rect(3, 3, width - 7, height - 7, 20, fill=colors["glass"], outline=colors["line"])
        self.draw_codex_icon(14, 16, 22)
        self.canvas.create_text(
            44,
            18,
            text=str(row.get("label", "")),
            fill=colors["text"],
            font=self.font_chip,
            anchor="w",
        )
        self.canvas.create_text(
            width - 20,
            18,
            text=str(row.get("remaining", "")),
            fill=colors["text"],
            font=self.font_chip,
            anchor="e",
        )
        self.canvas.create_text(
            44,
            37,
            text=self.refresh_text(),
            fill=colors["muted"],
            font=self.font_refresh,
            anchor="w",
        )
        self.canvas.create_text(
            width - 20,
            37,
            text=str(row.get("reset", "")),
            fill=colors["muted"],
            font=self.font_refresh,
            anchor="e",
        )

    def render_panel(self):
        colors = self.config_data["colors"]
        active = self.config_data.get("active_window", "five_hour")
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
                fill=colors["text"] if key == active else colors["muted"],
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
        self.draw_switch_button(62, 121, 92, 30, "5小时", active == "five_hour", "five_hour")
        self.draw_switch_button(162, 121, 78, 30, "1周", active == "weekly", "weekly")
        self.canvas.create_text(
            width - 30,
            162,
            text=self.refresh_text(),
            fill=colors["muted"],
            font=self.font_refresh,
            anchor="e",
        )

    def keep_on_screen(self):
        if self.drag_start:
            return
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
        self.config_data["active_window"] = target
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
        self.load_usage_data()
        self.last_refresh = datetime.now()
        self.render()
        self.save_position()

    def check_update_now(self):
        if self.update_checking:
            messagebox.showinfo("检查更新", "正在检查更新，请稍等。")
            return
        self.update_checking = True
        thread = threading.Thread(target=self.check_update_worker, daemon=True)
        thread.start()

    def check_update_worker(self):
        try:
            update_info = check_for_update()
            self.root.after(1, lambda: self.show_update_result(update_info))
        except Exception as error:
            message = friendly_error(error)
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOG_PATH.write_text(traceback.format_exc(), encoding="utf-8")
            self.root.after(1, lambda: messagebox.showerror("检查更新", message))
        finally:
            self.root.after(1, self.finish_update_check)

    def finish_update_check(self):
        self.update_checking = False

    def show_update_result(self, update_info):
        if update_info.has_update:
            message = (
                f"发现新版本 v{update_info.latest_version}\n"
                f"当前版本 v{update_info.current_version}\n\n"
                "是否打开下载页面？"
            )
            if messagebox.askyesno("发现更新", message):
                webbrowser.open(update_info.asset_url or update_info.release_url)
            return

        messagebox.showinfo(
            "检查更新",
            f"当前已是最新版本 v{update_info.current_version}",
        )

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
        active = self.config_data.get("active_window", "five_hour")
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(
            label="收起" if self.expanded else "展开",
            command=lambda: self.run_menu_action(self.toggle_expanded_without_animation),
        )
        menu.add_separator()
        menu.add_command(
            label=("✓ " if active == "five_hour" else "  ") + "显示 5小时",
            command=lambda: self.run_menu_action(self.set_active_window, "five_hour"),
        )
        menu.add_command(
            label=("✓ " if active == "weekly" else "  ") + "显示 1周",
            command=lambda: self.run_menu_action(self.set_active_window, "weekly"),
        )
        menu.add_separator()
        menu.add_command(label="刷新", command=lambda: self.run_menu_action(self.refresh_now))
        menu.add_command(label="检查更新", command=lambda: self.run_menu_action(self.check_update_now))
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
            if target:
                self.config_data["active_window"] = target
                self.render()
            else:
                self.toggle_expanded()
                self.drag_start = None
                return
            self.save_position()
        self.drag_start = None

    def quit(self):
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
