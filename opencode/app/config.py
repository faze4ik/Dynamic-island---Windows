"""Application settings, paths and built-in themes."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

APP_NAME = "DynamicIslandWindows"
APP_TITLE = "Dynamic Island"
VERSION = "2.0.0"
SCHEMA = 2


def _base_dir() -> Path:
    """Directory that contains bundled assets (works for source and PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def asset_dir() -> Path:
    return _base_dir() / "assets"


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


CONFIG_PATH = app_data_dir() / "config.json"
LOG_PATH = app_data_dir() / "app.log"
DEFAULT_HTML = asset_dir() / "island.html"


# Every island is black. Themes only change the glow, accents, glass and icons.
THEMES: dict[str, dict[str, Any]] = {
    "iphone": {
        "label": "iPhone · Liquid Glass",
        "accent": "#0a84ff",
        "accent2": "#64d2ff",
        "accent3": "#bf5af2",
        "accent4": "#30d158",
        "bg": "rgba(0, 0, 0, 0.84)",
        "bg2": "rgba(30, 30, 34, 0.92)",
        "text": "#ffffff",
        "muted": "#a1a1aa",
        "border": "rgba(255, 255, 255, 0.15)",
        "chip": "rgba(255, 255, 255, 0.075)",
        "font": "'SF Pro Display', 'Segoe UI Variable Display', 'Segoe UI', sans-serif",
        "glass": "1",
    },
    "standard": {
        "label": "Стандартная · чёрная",
        "accent": "#f5f5f7",
        "accent2": "#c7c7cc",
        "accent3": "#8e8e93",
        "accent4": "#636366",
        "bg": "rgba(0, 0, 0, 0.90)",
        "bg2": "rgba(22, 22, 24, 0.95)",
        "text": "#f5f5f7",
        "muted": "#9a9aa1",
        "border": "rgba(255, 255, 255, 0.13)",
        "chip": "rgba(255, 255, 255, 0.065)",
        "font": "'Segoe UI Variable Display', 'Segoe UI', sans-serif",
        "glass": "0",
    },
    "google": {
        "label": "Google · Material",
        "accent": "#4285f4",
        "accent2": "#ea4335",
        "accent3": "#fbbc05",
        "accent4": "#34a853",
        "bg": "rgba(0, 0, 0, 0.87)",
        "bg2": "rgba(25, 27, 33, 0.94)",
        "text": "#f8f9fa",
        "muted": "#9aa0a6",
        "border": "rgba(255, 255, 255, 0.13)",
        "chip": "rgba(255, 255, 255, 0.07)",
        "font": "'Google Sans', 'Product Sans', 'Segoe UI', sans-serif",
        "glass": "0",
    },
    "midnight": {
        "label": "Midnight · синий",
        "accent": "#7c9cff",
        "accent2": "#a78bfa",
        "accent3": "#38bdf8",
        "accent4": "#818cf8",
        "bg": "rgba(5, 6, 10, 0.92)",
        "bg2": "rgba(22, 25, 38, 0.95)",
        "text": "#f2f5ff",
        "muted": "#98a2b8",
        "border": "rgba(255, 255, 255, 0.13)",
        "chip": "rgba(255, 255, 255, 0.065)",
        "font": "'Segoe UI Variable Display', 'Segoe UI', sans-serif",
        "glass": "0",
    },
    "ocean": {
        "label": "Ocean · океан",
        "accent": "#38bdf8",
        "accent2": "#22d3ee",
        "accent3": "#818cf8",
        "accent4": "#2dd4bf",
        "bg": "rgba(2, 7, 14, 0.92)",
        "bg2": "rgba(7, 27, 44, 0.95)",
        "text": "#eff6ff",
        "muted": "#8fa8c2",
        "border": "rgba(255, 255, 255, 0.13)",
        "chip": "rgba(255, 255, 255, 0.065)",
        "font": "'Segoe UI Variable Display', 'Segoe UI', sans-serif",
        "glass": "0",
    },
    "sunset": {
        "label": "Sunset · закат",
        "accent": "#fb7185",
        "accent2": "#f59e0b",
        "accent3": "#f97316",
        "accent4": "#facc15",
        "bg": "rgba(15, 5, 8, 0.92)",
        "bg2": "rgba(43, 17, 21, 0.95)",
        "text": "#fff1f2",
        "muted": "#c7a3a8",
        "border": "rgba(255, 255, 255, 0.13)",
        "chip": "rgba(255, 255, 255, 0.07)",
        "font": "'Segoe UI Variable Display', 'Segoe UI', sans-serif",
        "glass": "0",
    },
    "aurora": {
        "label": "Aurora · изумруд",
        "accent": "#34d399",
        "accent2": "#22d3ee",
        "accent3": "#a3e635",
        "accent4": "#2dd4bf",
        "bg": "rgba(2, 9, 9, 0.92)",
        "bg2": "rgba(8, 30, 28, 0.95)",
        "text": "#ecfeff",
        "muted": "#8db8b3",
        "border": "rgba(255, 255, 255, 0.13)",
        "chip": "rgba(255, 255, 255, 0.065)",
        "font": "'Segoe UI Variable Display', 'Segoe UI', sans-serif",
        "glass": "0",
    },
    "cyber": {
        "label": "Cyberpunk · неон",
        "accent": "#f0abfc",
        "accent2": "#22d3ee",
        "accent3": "#a78bfa",
        "accent4": "#f472b6",
        "bg": "rgba(6, 3, 12, 0.93)",
        "bg2": "rgba(24, 10, 34, 0.95)",
        "text": "#fdf4ff",
        "muted": "#b39ac4",
        "border": "rgba(240, 171, 252, 0.20)",
        "chip": "rgba(255, 255, 255, 0.07)",
        "font": "'Segoe UI Variable Display', 'Segoe UI', sans-serif",
        "glass": "0",
    },
    "graphite": {
        "label": "Graphite · графит",
        "accent": "#e5e7eb",
        "accent2": "#9ca3af",
        "accent3": "#d1d5db",
        "accent4": "#6b7280",
        "bg": "rgba(9, 10, 12, 0.93)",
        "bg2": "rgba(29, 31, 36, 0.96)",
        "text": "#f9fafb",
        "muted": "#9ca3af",
        "border": "rgba(255, 255, 255, 0.14)",
        "chip": "rgba(255, 255, 255, 0.07)",
        "font": "'Segoe UI Variable Display', 'Segoe UI', sans-serif",
        "glass": "0",
    },
    "candy": {
        "label": "Candy · розовый",
        "accent": "#ff6b9d",
        "accent2": "#c084fc",
        "accent3": "#f472b6",
        "accent4": "#fb7185",
        "bg": "rgba(12, 4, 9, 0.92)",
        "bg2": "rgba(37, 13, 27, 0.95)",
        "text": "#fff1f7",
        "muted": "#c7a3b5",
        "border": "rgba(255, 255, 255, 0.14)",
        "chip": "rgba(255, 255, 255, 0.07)",
        "font": "'Segoe UI Variable Display', 'Segoe UI', sans-serif",
        "glass": "0",
    },
}

POSITIONS: dict[str, str] = {
    "top-left": "Сверху слева",
    "top-center": "Сверху по центру",
    "top-right": "Сверху справа",
    "bottom-left": "Снизу слева",
    "bottom-center": "Снизу по центру",
    "bottom-right": "Снизу справа",
}

STYLES: dict[str, str] = {
    "island": "Dynamic Island · плавающий остров",
    "notch": "iPhone XR · чёлка",
}


@dataclass
class Config:
    schema: int = SCHEMA
    position: str = "top-center"
    style: str = "island"
    monitor: int = 0
    offset_x: int = 0
    offset_y: int = 10
    scale: float = 1.0
    theme: str = "iphone"
    accent_override: str = ""
    opacity: float = 1.0
    glow: int = 65
    hover_expand: bool = True
    hover_delay: int = 200
    always_on_top: bool = True
    autostart: bool = False
    show_battery: bool = True
    show_seconds: bool = False
    show_music: bool = True
    show_privacy: bool = True
    show_notifications: bool = True
    notification_timeout: int = 60

    def normalize(self) -> "Config":
        self.schema = SCHEMA
        if self.position not in POSITIONS:
            self.position = "top-center"
        if self.style not in STYLES:
            self.style = "island"
        if self.theme not in THEMES:
            self.theme = "iphone"
        self.monitor = max(0, int(self.monitor))
        self.offset_x = max(0, min(120, int(self.offset_x)))
        self.offset_y = max(0, min(120, int(self.offset_y)))
        self.scale = max(0.75, min(1.6, float(self.scale)))
        self.opacity = max(0.55, min(1.0, float(self.opacity)))
        self.glow = max(0, min(100, int(self.glow)))
        self.hover_delay = max(0, min(1500, int(self.hover_delay)))
        self.notification_timeout = max(10, min(300, int(self.notification_timeout)))
        if self.accent_override and not _is_hex_color(self.accent_override):
            self.accent_override = ""
        return self

    def is_bottom(self) -> bool:
        return self.position.startswith("bottom")

    def theme_values(self) -> dict[str, str]:
        values = dict(THEMES.get(self.theme, THEMES["iphone"]))
        if self.accent_override:
            values["accent"] = self.accent_override
            values["accent2"] = _mix(self.accent_override, "#ffffff", 0.35)
            values["accent3"] = _mix(self.accent_override, "#ffffff", 0.65)
            values["accent4"] = _mix(self.accent_override, "#000000", 0.28)
        return values


def _is_hex_color(value: str) -> bool:
    value = value.strip()
    if not value.startswith("#"):
        return False
    if len(value) not in (4, 7):
        return False
    try:
        int(value[1:], 16)
    except ValueError:
        return False
    return True


def _mix(color_a: str, color_b: str, ratio: float = 0.5) -> str:
    """Mix two hex colors, returns #rrggbb."""

    def expand(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        if len(value) == 3:
            value = "".join(ch * 2 for ch in value)
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    try:
        a = expand(color_a)
        b = expand(color_b)
    except (ValueError, IndexError):
        return color_a
    out = tuple(round(a[i] + (b[i] - a[i]) * ratio) for i in range(3))
    return "#{:02x}{:02x}{:02x}".format(*out)


def load_config() -> Config:
    data: dict[str, Any] = {}
    try:
        if CONFIG_PATH.is_file():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}

    # Version 2 is a fresh, black iPhone-style UI. Older configs contained
    # the removed custom-HTML options and different position names.
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return Config().normalize()

    known = {f.name for f in fields(Config)}
    clean = {k: v for k, v in data.items() if k in known}
    try:
        cfg = Config(**clean)
    except TypeError:
        cfg = Config()
    return cfg.normalize()


def save_config(cfg: Config) -> None:
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tmp.replace(CONFIG_PATH)
