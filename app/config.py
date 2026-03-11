import json
import sys
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict


DEFAULT_CONFIG: Dict[str, Any] = {
    "mode": "keyboard",
    "selected_key": "F13",
    "interval_value": 5,
    "interval_unit": "minutes",
    "end_time_enabled": False,
    "end_time": "",
}


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def ensure_config_file() -> Path:
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", encoding="utf-8") as handle:
            json.dump(DEFAULT_CONFIG, handle, ensure_ascii=False, indent=2)
    return path


def get_config_path() -> Path:
    config_dir = get_base_dir() / "config"
    return config_dir / "config.json"


def load_config() -> Dict[str, Any]:
    path = ensure_config_file()

    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError):
        save_config(DEFAULT_CONFIG)
        return deepcopy(DEFAULT_CONFIG)

    config = deepcopy(DEFAULT_CONFIG)
    if isinstance(raw, dict):
        legacy_minutes = raw.get("interval_minutes")
        if "interval_value" not in raw and isinstance(legacy_minutes, int):
            raw["interval_value"] = legacy_minutes
        if "interval_unit" not in raw and "interval_value" in raw:
            raw["interval_unit"] = "minutes"
        raw["end_time"] = normalize_end_time(raw.get("end_time", ""))
        for key in DEFAULT_CONFIG:
            if key in raw:
                config[key] = raw[key]
    else:
        save_config(DEFAULT_CONFIG)
        return deepcopy(DEFAULT_CONFIG)

    save_config(config)
    return config


def save_config(config: Dict[str, Any]) -> None:
    path = ensure_config_file()
    merged = deepcopy(DEFAULT_CONFIG)
    for key in DEFAULT_CONFIG:
        if key in config:
            merged[key] = config[key]
    with path.open("w", encoding="utf-8") as handle:
        json.dump(merged, handle, ensure_ascii=False, indent=2)


def normalize_end_time(value: Any) -> str:
    if not isinstance(value, str):
        return DEFAULT_CONFIG["end_time"]

    text = value.strip()
    if not text:
        return DEFAULT_CONFIG["end_time"]

    try:
        parsed = datetime.strptime(text, "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%H:%M")
        except ValueError:
            return DEFAULT_CONFIG["end_time"]
        now = datetime.now()
        parsed = now.replace(hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0)
        if parsed <= now:
            parsed += timedelta(days=1)

    return parsed.strftime("%Y-%m-%d %H:%M")
