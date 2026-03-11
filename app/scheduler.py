from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional


@dataclass
class RuntimeSettings:
    mode: str
    selected_key: str
    interval_value: int
    interval_unit: str
    end_time_enabled: bool
    end_time: str

    @property
    def interval_seconds(self) -> int:
        if self.interval_unit == "minutes":
            return self.interval_value * 60
        return self.interval_value


class ActivityScheduler:
    def __init__(
        self,
        root,
        settings_provider: Callable[[], RuntimeSettings],
        action_callback: Callable[[RuntimeSettings], None],
        tick_callback: Callable[[Optional[int]], None],
        state_callback: Callable[[str], None],
        error_callback: Callable[[str], None],
    ) -> None:
        self.root = root
        self.settings_provider = settings_provider
        self.action_callback = action_callback
        self.tick_callback = tick_callback
        self.state_callback = state_callback
        self.error_callback = error_callback
        self._after_id = None
        self._running = False
        self._next_run_at: Optional[datetime] = None
        self._end_at: Optional[datetime] = None

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        settings = self.settings_provider()
        self.stop(update_state=False)
        self._running = True
        self._next_run_at = datetime.now() + timedelta(seconds=settings.interval_seconds)
        self._end_at = self._resolve_end_at(settings) if settings.end_time_enabled else None
        self.state_callback("動作中")
        self._schedule_tick()

    def stop(self, update_state: bool = True, state_text: str = "停止中") -> None:
        self._running = False
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self._next_run_at = None
        self._end_at = None
        self.tick_callback(None)
        if update_state:
            self.state_callback(state_text)

    def _schedule_tick(self) -> None:
        if not self._running:
            return
        self._tick()
        self._after_id = self.root.after(1000, self._schedule_tick)

    def _tick(self) -> None:
        if not self._running or self._next_run_at is None:
            return

        now = datetime.now()
        if self._end_at is not None and now >= self._end_at:
            self.stop(update_state=True, state_text="終了時刻到達により停止")
            return

        remaining = max(0, int((self._next_run_at - now).total_seconds()))
        self.tick_callback(remaining)
        if now < self._next_run_at:
            return

        settings = self.settings_provider()
        try:
            self.action_callback(settings)
        except Exception as exc:  # pragma: no cover - GUI path
            self.stop(update_state=True, state_text="エラーにより停止")
            self.error_callback(str(exc))
            return

        now = datetime.now()
        self._end_at = self._resolve_end_at(settings) if settings.end_time_enabled else None
        self._next_run_at = now + timedelta(seconds=settings.interval_seconds)
        self.tick_callback(max(0, int((self._next_run_at - now).total_seconds())))

    @staticmethod
    def _resolve_end_at(settings: RuntimeSettings) -> datetime:
        return datetime.strptime(settings.end_time, "%Y-%m-%d %H:%M")
