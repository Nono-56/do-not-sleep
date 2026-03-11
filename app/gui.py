from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox, ttk

from datetime import datetime

from app.config import load_config, save_config
from app.input_controller import KEY_LAYOUT, available_key_labels, nudge_mouse, send_keypress
from app.scheduler import ActivityScheduler, RuntimeSettings


DATETIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} (?:[01]\d|2[0-3]):[0-5]\d$")


class DoNotSleepApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Do Not Sleep")
        self.root.minsize(980, 640)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.app_icon = self._create_app_icon()
        self.root.iconphoto(True, self.app_icon)

        config = load_config()
        self.available_keys = set(available_key_labels())
        selected_key = config.get("selected_key", "")
        if selected_key not in self.available_keys:
            selected_key = "F13"

        self.mode_var = tk.StringVar(value=config.get("mode", "keyboard"))
        self.interval_value_var = tk.StringVar(value=str(config.get("interval_value", 5)))
        self.interval_unit_var = tk.StringVar(value=config.get("interval_unit", "minutes"))
        self.end_time_enabled_var = tk.BooleanVar(value=bool(config.get("end_time_enabled", False)))
        self.end_time_var = tk.StringVar(value=config.get("end_time", ""))
        self.selected_key_var = tk.StringVar(value=selected_key)
        self.status_var = tk.StringVar(value="停止中")
        self.countdown_var = tk.StringVar(value="次の入力まで: --")
        self.mode_status_var = tk.StringVar(value=self._mode_text())
        self.interval_status_var = tk.StringVar(value=self._draft_interval_text())
        self.end_time_status_var = tk.StringVar(value=self._end_time_text())
        self.selected_key_status_var = tk.StringVar(value=selected_key or "未選択")
        self.active_settings: RuntimeSettings | None = None

        self.keyboard_buttons = {}
        self.scheduler = ActivityScheduler(
            root=self.root,
            settings_provider=self.get_runtime_settings,
            action_callback=self.perform_activity,
            tick_callback=self.update_countdown,
            state_callback=self.update_state,
            error_callback=self.show_runtime_error,
        )

        self._build_ui()
        self._bind_events()
        self._refresh_keyboard_state()
        self._update_selected_key_highlight()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _create_app_icon(self) -> tk.PhotoImage:
        image = tk.PhotoImage(width=32, height=32)
        image.put("#000000", to=(0, 0, 31, 31))
        background = "#05070b"
        border = "#f5f7fb"
        key_blue = "#39a0ff"
        key_white = "#f5f7fb"
        cursor_fill = "#39a0ff"
        cursor_outline = "#f5f7fb"

        self._fill_rounded_rect(image, 1, 1, 30, 30, 6, background)
        self._draw_rounded_rect(image, 3, 7, 28, 24, 4, border)
        self._draw_line(image, (16, 1), (16, 7), border)

        for x1, y1, x2, y2, color in [
            (6, 10, 7, 11, key_white),
            (9, 10, 10, 11, key_white),
            (12, 10, 13, 11, key_white),
            (15, 10, 16, 11, key_white),
            (18, 10, 19, 11, key_white),
            (21, 10, 22, 11, key_white),
            (24, 10, 25, 11, key_white),
            (6, 14, 7, 15, key_blue),
            (9, 14, 10, 15, key_blue),
            (12, 14, 13, 15, key_blue),
            (15, 14, 16, 15, key_blue),
            (18, 14, 19, 15, key_blue),
            (21, 14, 22, 15, key_blue),
            (24, 14, 25, 15, key_blue),
            (6, 18, 8, 19, key_blue),
            (11, 18, 12, 19, key_blue),
            (15, 18, 16, 19, key_blue),
            (19, 18, 20, 19, key_blue),
            (23, 18, 25, 19, key_blue),
            (10, 22, 21, 22, key_white),
        ]:
            image.put(color, to=(x1, y1, x2, y2))

        cursor_points = [
            (22, 4),
            (22, 15),
            (25, 12),
            (27, 18),
            (29, 17),
            (27, 11),
            (31, 11),
        ]
        self._fill_polygon(image, cursor_points, cursor_fill)
        self._draw_polyline(image, cursor_points + [cursor_points[0]], cursor_outline)
        return image

    def _fill_rounded_rect(self, image: tk.PhotoImage, x1: int, y1: int, x2: int, y2: int, radius: int, color: str) -> None:
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                corners = (
                    (x - (x1 + radius), y - (y1 + radius)),
                    (x - (x2 - radius), y - (y1 + radius)),
                    (x - (x1 + radius), y - (y2 - radius)),
                    (x - (x2 - radius), y - (y2 - radius)),
                )
                if x1 + radius <= x <= x2 - radius or y1 + radius <= y <= y2 - radius:
                    image.put(color, (x, y))
                    continue
                if any(dx * dx + dy * dy <= radius * radius for dx, dy in corners):
                    image.put(color, (x, y))

    def _draw_rounded_rect(self, image: tk.PhotoImage, x1: int, y1: int, x2: int, y2: int, radius: int, color: str) -> None:
        self._draw_line(image, (x1 + radius, y1), (x2 - radius, y1), color)
        self._draw_line(image, (x1 + radius, y2), (x2 - radius, y2), color)
        self._draw_line(image, (x1, y1 + radius), (x1, y2 - radius), color)
        self._draw_line(image, (x2, y1 + radius), (x2, y2 - radius), color)
        self._draw_arc_quadrant(image, x1 + radius, y1 + radius, radius, 2, color)
        self._draw_arc_quadrant(image, x2 - radius, y1 + radius, radius, 1, color)
        self._draw_arc_quadrant(image, x1 + radius, y2 - radius, radius, 3, color)
        self._draw_arc_quadrant(image, x2 - radius, y2 - radius, radius, 4, color)

    def _draw_arc_quadrant(
        self, image: tk.PhotoImage, center_x: int, center_y: int, radius: int, quadrant: int, color: str
    ) -> None:
        for y in range(-radius, radius + 1):
            for x in range(-radius, radius + 1):
                distance = x * x + y * y
                if radius * radius - radius <= distance <= radius * radius + radius:
                    if quadrant == 1 and x >= 0 and y <= 0:
                        image.put(color, (center_x + x, center_y + y))
                    elif quadrant == 2 and x <= 0 and y <= 0:
                        image.put(color, (center_x + x, center_y + y))
                    elif quadrant == 3 and x <= 0 and y >= 0:
                        image.put(color, (center_x + x, center_y + y))
                    elif quadrant == 4 and x >= 0 and y >= 0:
                        image.put(color, (center_x + x, center_y + y))

    def _fill_polygon(self, image: tk.PhotoImage, points: list[tuple[int, int]], color: str) -> None:
        min_y = min(y for _, y in points)
        max_y = max(y for _, y in points)
        for y in range(min_y, max_y + 1):
            intersections = []
            for index, (x1, y1) in enumerate(points):
                x2, y2 = points[(index + 1) % len(points)]
                if y1 == y2:
                    continue
                if y < min(y1, y2) or y >= max(y1, y2):
                    continue
                x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                intersections.append(int(round(x)))
            intersections.sort()
            for index in range(0, len(intersections), 2):
                if index + 1 < len(intersections):
                    image.put(color, to=(intersections[index], y, intersections[index + 1], y))

    def _draw_polyline(self, image: tk.PhotoImage, points: list[tuple[int, int]], color: str) -> None:
        for start, end in zip(points, points[1:]):
            self._draw_line(image, start, end, color)

    def _draw_line(
        self, image: tk.PhotoImage, start: tuple[int, int], end: tuple[int, int], color: str
    ) -> None:
        x1, y1 = start
        x2, y2 = end
        dx = abs(x2 - x1)
        dy = -abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        error = dx + dy

        while True:
            image.put(color, (x1, y1))
            if x1 == x2 and y1 == y2:
                break
            error2 = 2 * error
            if error2 >= dy:
                error += dy
                x1 += sx
            if error2 <= dx:
                error += dx
                y1 += sy

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.grid(sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        top = ttk.Frame(frame)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)

        mode_box = ttk.LabelFrame(top, text="動作方式", padding=12)
        mode_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ttk.Radiobutton(mode_box, text="キー入力", variable=self.mode_var, value="keyboard").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Radiobutton(mode_box, text="マウス移動", variable=self.mode_var, value="mouse").grid(
            row=0, column=1, sticky="w", padx=(12, 0)
        )

        settings_box = ttk.LabelFrame(top, text="実行設定", padding=12)
        settings_box.grid(row=0, column=1, sticky="nsew")
        ttk.Label(settings_box, text="実行間隔").grid(row=0, column=0, sticky="w")
        ttk.Entry(settings_box, textvariable=self.interval_value_var, width=8).grid(
            row=0, column=1, sticky="w", padx=(8, 0)
        )
        ttk.Combobox(
            settings_box,
            textvariable=self.interval_unit_var,
            values=("minutes", "seconds"),
            state="readonly",
            width=10,
        ).grid(row=0, column=2, sticky="w", padx=(8, 0))
        ttk.Label(settings_box, text="minutes / seconds").grid(row=0, column=3, sticky="w", padx=(8, 0))
        ttk.Checkbutton(
            settings_box,
            text="終了日時を有効にする",
            variable=self.end_time_enabled_var,
        ).grid(row=1, column=0, sticky="w", pady=(12, 0))
        ttk.Entry(settings_box, textvariable=self.end_time_var, width=18).grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=(12, 0)
        )
        ttk.Label(settings_box, text="形式: YYYY-MM-DD HH:MM").grid(row=1, column=2, sticky="w", padx=(8, 0), pady=(12, 0))

        middle = ttk.Frame(frame)
        middle.grid(row=1, column=0, sticky="nsew", pady=(16, 16))
        middle.columnconfigure(0, weight=3)
        middle.columnconfigure(1, weight=2)
        middle.rowconfigure(0, weight=1)

        keyboard_box = ttk.LabelFrame(middle, text="スクリーンキーボード", padding=12)
        keyboard_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        keyboard_box.columnconfigure(0, weight=1)
        ttk.Label(keyboard_box, text="選択中キー").grid(row=0, column=0, sticky="w")
        ttk.Label(keyboard_box, textvariable=self.selected_key_status_var, font=("", 12, "bold")).grid(
            row=0, column=1, sticky="w", padx=(8, 0)
        )

        key_frame = ttk.Frame(keyboard_box)
        key_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        for row_index, row_keys in enumerate(KEY_LAYOUT):
            for col_index, key_label in enumerate(row_keys):
                if key_label not in self.available_keys:
                    continue
                width = self._button_width(key_label)
                button = tk.Button(
                    key_frame,
                    text=key_label,
                    width=width,
                    relief="raised",
                    command=lambda value=key_label: self.select_key(value),
                )
                button.grid(row=row_index, column=col_index, padx=3, pady=3, sticky="nsew")
                self.keyboard_buttons[key_label] = button

        status_box = ttk.LabelFrame(middle, text="状態", padding=12)
        status_box.grid(row=0, column=1, sticky="nsew")
        status_box.columnconfigure(1, weight=1)
        self._status_row(status_box, 0, "現在状態", self.status_var)
        self._status_row(status_box, 1, "動作方式", self.mode_status_var)
        self._status_row(status_box, 2, "実行間隔", self.interval_status_var)
        self._status_row(status_box, 3, "終了日時", self.end_time_status_var)
        self._status_row(status_box, 4, "次の入力", self.countdown_var)
        self._status_row(status_box, 5, "選択キー", self.selected_key_status_var)

        controls = ttk.Frame(frame)
        controls.grid(row=2, column=0, sticky="ew")
        ttk.Button(controls, text="開始", command=self.start).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(controls, text="停止", command=self.stop).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(controls, text="終了", command=self.on_close).grid(row=0, column=2)

    def _bind_events(self) -> None:
        self.mode_var.trace_add("write", lambda *_: self.on_settings_changed())
        self.interval_value_var.trace_add("write", lambda *_: self.on_settings_changed())
        self.interval_unit_var.trace_add("write", lambda *_: self.on_settings_changed())
        self.end_time_enabled_var.trace_add("write", lambda *_: self.on_settings_changed())
        self.end_time_var.trace_add("write", lambda *_: self.on_settings_changed())
        self.selected_key_var.trace_add("write", lambda *_: self.on_settings_changed())

    def _status_row(self, parent, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Label(parent, textvariable=variable).grid(row=row, column=1, sticky="w", padx=(12, 0), pady=4)

    def _button_width(self, key_label: str) -> int:
        wide = {"Backspace": 10, "CapsLock": 10, "Shift": 8, "Ctrl": 7, "Alt": 7, "Space": 20, "Enter": 8, "Tab": 7}
        return wide.get(key_label, 5)

    def select_key(self, key_label: str) -> None:
        self.selected_key_var.set(key_label)

    def on_settings_changed(self) -> None:
        self.mode_status_var.set(self._mode_text())
        if not self.scheduler.is_running:
            self.interval_status_var.set(self._draft_interval_text())
        self.end_time_status_var.set(self._end_time_text())
        self.selected_key_status_var.set(self.selected_key_var.get() or "未選択")
        self._refresh_keyboard_state()
        self._update_selected_key_highlight()
        self._persist_current_settings()

    def _refresh_keyboard_state(self) -> None:
        enabled = self.mode_var.get() == "keyboard"
        state = "normal" if enabled else "disabled"
        for button in self.keyboard_buttons.values():
            button.configure(state=state)

    def _update_selected_key_highlight(self) -> None:
        for label, button in self.keyboard_buttons.items():
            if label == self.selected_key_var.get():
                button.configure(bg="#1f6aa5", fg="white", relief="sunken")
            else:
                button.configure(bg="SystemButtonFace", fg="black", relief="raised")

    def _persist_current_settings(self) -> None:
        try:
            payload = self._settings_payload()
        except ValueError:
            return
        save_config(payload)

    def _settings_payload(self) -> dict:
        interval_raw = self.interval_value_var.get().strip()
        interval_value = int(interval_raw)
        interval_unit = self.interval_unit_var.get().strip()
        if interval_unit not in {"minutes", "seconds"}:
            raise ValueError("invalid interval unit")
        if interval_unit == "minutes" and not 1 <= interval_value <= 240:
            raise ValueError("interval out of range")
        if interval_unit == "seconds" and not 1 <= interval_value <= 3600:
            raise ValueError("interval out of range")
        payload = {
            "mode": self.mode_var.get(),
            "selected_key": self.selected_key_var.get().strip(),
            "interval_value": interval_value,
            "interval_unit": interval_unit,
            "end_time_enabled": self.end_time_enabled_var.get(),
            "end_time": self.end_time_var.get().strip(),
        }
        if payload["end_time_enabled"] and not DATETIME_PATTERN.match(payload["end_time"]):
            raise ValueError("invalid end time")
        return payload

    def _mode_text(self) -> str:
        return "キー入力" if self.mode_var.get() == "keyboard" else "マウス移動"

    def _format_interval_text(self, value: int | str, unit: str) -> str:
        suffix = "分" if unit == "minutes" else "秒"
        return f"{value}{suffix}"

    def _draft_interval_text(self) -> str:
        value = self.interval_value_var.get() or "--"
        unit = self.interval_unit_var.get()
        if unit not in {"minutes", "seconds"}:
            return "--"
        return self._format_interval_text(value, unit)

    def _end_time_text(self) -> str:
        if not self.end_time_enabled_var.get():
            return "無効"
        return self.end_time_var.get() or "----/--/-- --:--"

    def validate_settings(self) -> RuntimeSettings:
        interval_raw = self.interval_value_var.get().strip()
        try:
            interval_value = int(interval_raw)
        except ValueError as exc:
            raise ValueError("実行間隔は整数で入力してください。") from exc

        interval_unit = self.interval_unit_var.get().strip()
        if interval_unit == "minutes":
            if not 1 <= interval_value <= 240:
                raise ValueError("分指定では実行間隔は1から240で入力してください。")
        elif interval_unit == "seconds":
            if not 1 <= interval_value <= 3600:
                raise ValueError("秒指定では実行間隔は1から3600で入力してください。")
        else:
            raise ValueError("実行間隔の単位が不正です。")

        end_time = self.end_time_var.get().strip()
        if self.end_time_enabled_var.get():
            if not DATETIME_PATTERN.match(end_time):
                raise ValueError("終了日時はYYYY-MM-DD HH:MM形式で入力してください。")
            try:
                end_at = datetime.strptime(end_time, "%Y-%m-%d %H:%M")
            except ValueError as exc:
                raise ValueError("終了日時は存在する日時を入力してください。") from exc
            if end_at <= datetime.now():
                raise ValueError("終了日時は現在より未来の日時を入力してください。")

        selected_key = self.selected_key_var.get().strip()
        if self.mode_var.get() == "keyboard" and not selected_key:
            raise ValueError("キー入力モードではキーを選択してください。")

        if self.mode_var.get() == "keyboard" and selected_key not in self.available_keys:
            raise ValueError("選択されたキーは利用できません。")

        try:
            payload = self._settings_payload()
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        return RuntimeSettings(**payload)

    def get_runtime_settings(self) -> RuntimeSettings:
        return self.validate_settings()

    def perform_activity(self, settings: RuntimeSettings) -> None:
        self.active_settings = settings
        self.interval_status_var.set(self._format_interval_text(settings.interval_value, settings.interval_unit))
        if settings.mode == "keyboard":
            send_keypress(settings.selected_key)
        else:
            nudge_mouse()

    def update_countdown(self, remaining_seconds) -> None:
        if remaining_seconds is None:
            self.countdown_var.set("次の入力まで: --")
        else:
            self.countdown_var.set(f"次の入力まで: {remaining_seconds}秒")

    def update_state(self, text: str) -> None:
        self.status_var.set(text)

    def show_runtime_error(self, message: str) -> None:
        messagebox.showerror("実行エラー", f"擬似入力の送信に失敗しました。\n{message}")

    def start(self) -> None:
        try:
            settings = self.validate_settings()
        except ValueError as exc:
            messagebox.showerror("入力エラー", str(exc))
            return
        self.active_settings = settings
        self.interval_status_var.set(self._format_interval_text(settings.interval_value, settings.interval_unit))
        self._persist_current_settings()
        self.scheduler.start()

    def stop(self) -> None:
        self.scheduler.stop()
        self.active_settings = None
        self.interval_status_var.set(self._draft_interval_text())

    def on_close(self) -> None:
        self.scheduler.stop(update_state=False)
        self._persist_current_settings()
        self.root.destroy()


def run_app() -> None:
    root = tk.Tk()
    try:
        root.iconname("Do Not Sleep")
    except tk.TclError:
        pass
    style = ttk.Style()
    if "vista" in style.theme_names():
        style.theme_use("vista")
    DoNotSleepApp(root)
    root.mainloop()
