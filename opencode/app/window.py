"""Frameless, always-on-top Dynamic Island window."""

from __future__ import annotations

import ctypes
import json
import logging
import os
import time
from dataclasses import replace
from datetime import datetime
from typing import Any, Optional

from PySide6.QtCore import (
    QEvent,
    QObject,
    QRect,
    QRectF,
    Qt,
    QTimer,
    QUrl,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QGuiApplication,
    QIcon,
    QPainterPath,
    QRegion,
)
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QWidget

from . import autostart
from .config import (
    APP_TITLE,
    DEFAULT_HTML,
    POSITIONS,
    STYLES,
    THEMES,
    Config,
    app_data_dir,
    asset_dir,
    save_config,
)
from .native import NativeMonitor, open_action_center, open_privacy_settings
from .style import MENU_QSS

log = logging.getLogger(__name__)

try:
    import psutil
except Exception:  # pragma: no cover - optional at runtime
    psutil = None

BASE_W, BASE_H = 490, 450
ISLAND_COMPACT_W, ISLAND_COMPACT_H = 236, 42
NOTCH_COMPACT_W, NOTCH_COMPACT_H = 286, 34
EXPANDED_W, EXPANDED_H = 460, 406

WEEKDAYS = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]
MONTHS = [
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]


class _SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]


def read_battery() -> tuple[Optional[int], bool]:
    """Return (percent or None, charging)."""
    try:
        status = _SYSTEM_POWER_STATUS()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return None, False
        if status.BatteryLifePercent > 100:
            return None, status.ACLineStatus == 1
        return int(status.BatteryLifePercent), status.ACLineStatus == 1
    except Exception:
        return None, False


def _island_region(
    rect: QRect, radius: float, flat_top: bool = False, flat_bottom: bool = False
) -> QRegion:
    """Rounded rectangle with optionally square top/bottom edges (notch)."""
    r = max(0.0, min(radius, rect.width() / 2.0, rect.height() / 2.0))
    left = float(rect.left())
    top = float(rect.top())
    right = left + rect.width()
    bottom = top + rect.height()

    path = QPainterPath()
    path.moveTo(left + (0.0 if flat_top else r), top)
    path.lineTo(right - (0.0 if flat_top else r), top)
    if not flat_top:
        path.quadTo(right, top, right, top + r)
    path.lineTo(right, bottom - (0.0 if flat_bottom else r))
    if not flat_bottom:
        path.quadTo(right, bottom, right - r, bottom)
    path.lineTo(left + (0.0 if flat_bottom else r), bottom)
    if not flat_bottom:
        path.quadTo(left, bottom, left, bottom - r)
    path.lineTo(left, top + (0.0 if flat_top else r))
    if not flat_top:
        path.quadTo(left, top, left + r, top)
    path.closeSubpath()
    return QRegion(path.toFillPolygon().toPolygon())


class _Bridge(QObject):
    def __init__(self, window: "IslandWindow") -> None:
        super().__init__(window)
        self._window = window

    @Slot(str)
    def action(self, name: str) -> None:
        self._window.handle_action(str(name))


class IslandWindow(QWidget):
    def __init__(self, cfg: Config, on_quit) -> None:
        super().__init__(None)
        self.cfg = cfg
        self._on_quit = on_quit
        self._expanded = False
        self._mask_token = 0
        self._page_ready = False
        self._html_key: Any = None
        self._settings_dialog = None
        self._pre_settings: Optional[Config] = None
        self._enter_since: Optional[float] = None
        self._leave_since: Optional[float] = None
        self._closing = False
        self._menu_open = False

        self._media: Optional[dict[str, Any]] = None
        self._privacy: Optional[dict[str, Any]] = None
        self._notification: Optional[dict[str, Any]] = None
        self._stats: dict[str, Any] = {"cpu": 0, "ram": 0, "ram_used": 0.0, "ram_total": 0.0}

        self._setup_window()
        self._setup_view()
        self._setup_timers()
        self._setup_native()

        self.apply_config(cfg)
        self.show()

    # ------------------------------------------------------------------ setup

    def _setup_window(self) -> None:
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        if self.cfg.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowTitle(APP_TITLE)
        self.setMouseTracking(True)

        icon_path = asset_dir() / "icon.ico"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _setup_view(self) -> None:
        self.view = QWebEngineView(self)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.view.setStyleSheet("background: transparent;")
        self.view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.view.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        page = self.view.page()
        page.setBackgroundColor(QColor(0, 0, 0, 0))

        settings = self.view.settings()
        for attr, value in (
            (QWebEngineSettings.WebAttribute.ShowScrollBars, False),
            (QWebEngineSettings.WebAttribute.JavascriptEnabled, True),
            (QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True),
            (QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True),
            (QWebEngineSettings.WebAttribute.FocusOnNavigationEnabled, False),
            (QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False),
            (QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, False),
        ):
            try:
                settings.setAttribute(attr, value)
            except Exception:
                pass

        self._bridge = _Bridge(self)
        self._channel = QWebChannel(page)
        self._channel.registerObject("bridge", self._bridge)
        page.setWebChannel(self._channel)

        # Chromium draws its own context menu inside the render widget, so the
        # widget-level NoContextMenu policy alone is not enough. Filter the
        # native ContextMenu event on both the view and its focus proxy.
        self.view.installEventFilter(self)
        self._install_context_filter()

        self.view.loadFinished.connect(self._on_load_finished)

    def _setup_timers(self) -> None:
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._push_tick)
        self._clock_timer.start()

        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(70)
        self._hover_timer.timeout.connect(self._check_hover)
        self._hover_timer.start()

        self._notification_timer = QTimer(self)
        self._notification_timer.setSingleShot(True)
        self._notification_timer.timeout.connect(self._clear_notification)

        self._stats_timer = QTimer(self)
        self._stats_timer.setInterval(2000)
        self._stats_timer.timeout.connect(self._update_stats)
        self._stats_timer.start()
        self._update_stats()

    def _setup_native(self) -> None:
        self._native = NativeMonitor(self)
        self._native.media.connect(self._on_media)
        self._native.privacy.connect(self._on_privacy)
        self._native.notification.connect(self._on_notification)
        self._native.ready.connect(
            lambda ok: log.info("Native monitor ready: %s", ok)
        )
        self._native.start()

    # ----------------------------------------------------------------- config

    def apply_config(self, cfg: Config, persist: bool = False) -> None:
        cfg = replace(cfg).normalize()
        previous = self.cfg
        self.cfg = cfg
        if persist:
            save_config(cfg)

        self._apply_window_flags()
        self._recompute_geometry()
        new_key = self._html_key_for(cfg)
        if new_key != self._html_key:
            self._load_html(cfg)
        else:
            self._inject_config()
            self._sync_expanded_js()
            self._push_native()
        self._push_tick()
        self._push_stats()

        if not cfg.show_notifications:
            self._clear_notification()
        elif (
            self._notification is not None
            and cfg.notification_timeout != previous.notification_timeout
        ):
            self._notification_timer.start(cfg.notification_timeout * 1000)

    def _install_context_filter(self) -> None:
        proxy = self.view.focusProxy()
        if proxy is not None and proxy is not self.view:
            proxy.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.ContextMenu:
            if not self._menu_open:
                self._menu_open = True
                try:
                    self.show_context_menu()
                finally:
                    self._menu_open = False
            return True
        return super().eventFilter(watched, event)

    def _apply_window_flags(self) -> None:
        wanted = self.cfg.always_on_top
        current = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        if wanted != current:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, wanted)
            if self.isVisible():
                self.show()
            self._apply_mask()

    def _html_key_for(self, cfg: Config) -> Any:
        try:
            return ("builtin", str(DEFAULT_HTML), DEFAULT_HTML.stat().st_mtime_ns)
        except OSError:
            return ("builtin", str(DEFAULT_HTML), 0)

    def _load_html(self, cfg: Config) -> None:
        self._page_ready = False
        self._html_key = self._html_key_for(cfg)
        target = DEFAULT_HTML
        if not target.is_file():
            log.error("Island HTML is missing: %s", target)
            return
        log.info("Loading island HTML: %s", target)
        self.view.load(QUrl.fromLocalFile(str(target)))

    @Slot(bool)
    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            log.error("Failed to load island HTML: %s", self.view.url().toString())
            return
        log.info("Island HTML loaded")
        self._page_ready = True
        self._install_context_filter()
        self._inject_config()
        self._sync_expanded_js()
        self._push_tick()
        self._push_stats()
        self._push_native()

    # -------------------------------------------------------------- geometry

    def _screen(self):
        screens = QGuiApplication.screens()
        if not screens:
            return QGuiApplication.primaryScreen()
        index = self.cfg.monitor if 0 <= self.cfg.monitor < len(screens) else 0
        return screens[index]

    def _compact_dims(self) -> tuple[int, int]:
        if self.cfg.style == "notch":
            return NOTCH_COMPACT_W, NOTCH_COMPACT_H
        return ISLAND_COMPACT_W, ISLAND_COMPACT_H

    def _vertical_gap(self) -> int:
        if self.cfg.style == "notch":
            return 0
        return round(self.cfg.offset_y * self.cfg.scale)

    def _recompute_geometry(self) -> None:
        scale = self.cfg.scale
        width = round(BASE_W * scale)
        height = round(BASE_H * scale)
        screen = self._screen()
        if screen is not None:
            area = screen.availableGeometry()
            if self.cfg.position.endswith("left"):
                x = area.left()
            elif self.cfg.position.endswith("right"):
                x = area.right() - width + 1
            else:
                x = area.left() + (area.width() - width) // 2
            if self.cfg.is_bottom():
                y = area.bottom() - height + 1
            else:
                y = area.top()
        else:
            x, y = 100, 100
        self.setGeometry(x, y, width, height)
        self.view.setGeometry(0, 0, width, height)
        self.view.setZoomFactor(scale)
        self.setWindowOpacity(self.cfg.opacity)
        self._apply_mask()

    def _compact_local_rect(self) -> QRect:
        scale = self.cfg.scale
        cw, ch = self._compact_dims()
        cw, ch = round(cw * scale), round(ch * scale)
        margin = round(self.cfg.offset_x * scale)
        if self.cfg.position.endswith("left"):
            x = margin
        elif self.cfg.position.endswith("right"):
            x = self.width() - margin - cw
        else:
            x = (self.width() - cw) // 2
        gap = self._vertical_gap()
        y = self.height() - gap - ch if self.cfg.is_bottom() else gap
        return QRect(x, y, cw, ch)

    def _expanded_local_rect(self) -> QRect:
        scale = self.cfg.scale
        ew, eh = round(EXPANDED_W * scale), round(EXPANDED_H * scale)
        margin = round(self.cfg.offset_x * scale)
        if self.cfg.position.endswith("left"):
            x = margin
        elif self.cfg.position.endswith("right"):
            x = self.width() - margin - ew
        else:
            x = (self.width() - ew) // 2
        gap = self._vertical_gap()
        y = self.height() - gap - eh if self.cfg.is_bottom() else gap
        return QRect(x, y, ew, eh)

    def _apply_mask(self) -> None:
        if self._expanded:
            self._apply_expanded_mask()
        else:
            self._apply_compact_mask()

    def _apply_compact_mask(self) -> None:
        scale = self.cfg.scale
        rect = self._compact_local_rect()
        pad = round(22 * scale)
        outer = rect.adjusted(-pad, -pad, pad, pad).intersected(self.rect())
        if outer.isEmpty():
            return
        notch = self.cfg.style == "notch"
        flat_top = notch and not self.cfg.is_bottom()
        flat_bottom = notch and self.cfg.is_bottom()
        radius = (18 if notch else rect.height() / 2) + pad
        self.setMask(_island_region(outer, radius, flat_top, flat_bottom))

    def _apply_expanded_mask(self) -> None:
        scale = self.cfg.scale
        rect = self._expanded_local_rect()
        pad = round(16 * scale)
        outer = rect.adjusted(-pad - 2, -pad, pad + 2, pad).intersected(self.rect())
        if outer.isEmpty():
            return
        notch = self.cfg.style == "notch"
        flat_top = notch and not self.cfg.is_bottom()
        flat_bottom = notch and self.cfg.is_bottom()
        radius = (28 if notch else 30) * scale + pad
        self.setMask(_island_region(outer, radius, flat_top, flat_bottom))

    def _restore_compact_mask(self, token: int) -> None:
        if token == self._mask_token and not self._expanded:
            self._apply_compact_mask()

    # ---------------------------------------------------------------- expand

    def set_expanded(self, expanded: bool) -> None:
        expanded = bool(expanded)
        self._mask_token += 1
        token = self._mask_token
        changed = expanded != self._expanded
        self._expanded = expanded
        self._enter_since = None
        self._leave_since = None

        if expanded:
            self._apply_expanded_mask()
            self._sync_expanded_js()
        else:
            self._sync_expanded_js()
            QTimer.singleShot(430, lambda: self._restore_compact_mask(token))
        if changed:
            log.debug("Island expanded=%s", expanded)

    def _sync_expanded_js(self) -> None:
        if not self._page_ready:
            return
        flag = "true" if self._expanded else "false"
        self.view.page().runJavaScript(
            f"if (window.islandExpand) {{ window.islandExpand({flag}); }}"
        )

    def _hot_rect(self) -> QRect:
        rect = (
            self._expanded_local_rect()
            if self._expanded
            else self._compact_local_rect()
        )
        return QRect(self.mapToGlobal(rect.topLeft()), rect.size())

    def _check_hover(self) -> None:
        if not self.isVisible():
            self._enter_since = None
            self._leave_since = None
            return
        if not self.cfg.hover_expand:
            self._enter_since = None
            self._leave_since = None
            return

        inside = self._hot_rect().contains(QCursor.pos())
        now = time.monotonic()

        if inside:
            self._leave_since = None
            if not self._expanded:
                if self._enter_since is None:
                    self._enter_since = now
                elif (now - self._enter_since) * 1000.0 >= self.cfg.hover_delay:
                    self.set_expanded(True)
            else:
                self._enter_since = None
        else:
            self._enter_since = None
            if self._expanded:
                if self._leave_since is None:
                    self._leave_since = now
                elif (now - self._leave_since) >= 0.38:
                    self.set_expanded(False)
            else:
                self._leave_since = None

    # ------------------------------------------------------------------ data

    def _clock_data(self) -> dict[str, Any]:
        now = datetime.now()
        time_text = now.strftime("%H:%M:%S" if self.cfg.show_seconds else "%H:%M")
        date_text = f"{WEEKDAYS[now.weekday()]}, {now.day} {MONTHS[now.month - 1]}"
        hour = now.hour
        if 5 <= hour < 12:
            greeting = "Доброе утро"
        elif 12 <= hour < 17:
            greeting = "Добрый день"
        elif 17 <= hour < 23:
            greeting = "Добрый вечер"
        else:
            greeting = "Доброй ночи"
        return {"time": time_text, "date": date_text, "greeting": greeting}

    def _update_stats(self) -> None:
        if psutil is None:
            return
        try:
            memory = psutil.virtual_memory()
            self._stats = {
                "cpu": round(float(psutil.cpu_percent(interval=None))),
                "ram": round(float(memory.percent)),
                "ram_used": round(memory.used / (1024 ** 3), 1),
                "ram_total": round(memory.total / (1024 ** 3), 1),
            }
        except Exception:
            return
        self._push_stats()

    def _push_stats(self) -> None:
        if not self._page_ready:
            return
        js = (
            "if (window.islandStats) { window.islandStats("
            + json.dumps(self._stats, ensure_ascii=False)
            + "); }"
        )
        self.view.page().runJavaScript(js)

    def _push_tick(self) -> None:
        if not self._page_ready:
            return
        data = self._clock_data()
        percent, charging = read_battery()
        data["battery"] = percent
        data["charging"] = charging
        data["autostart"] = self.cfg.autostart
        js = (
            "if (window.islandTick) { window.islandTick("
            + json.dumps(data, ensure_ascii=False)
            + "); }"
        )
        self.view.page().runJavaScript(js)

    def _inject_config(self) -> None:
        if not self._page_ready:
            return
        values = self.cfg.theme_values()
        variables = {
            key: values.get(key, "")
            for key in (
                "accent",
                "accent2",
                "accent3",
                "accent4",
                "bg",
                "bg2",
                "text",
                "muted",
                "border",
                "chip",
                "font",
            )
        }
        payload = {
            "vars": variables,
            "theme": self.cfg.theme,
            "position": self.cfg.position,
            "style": self.cfg.style,
            "offsetX": self.cfg.offset_x,
            "offsetY": self.cfg.offset_y,
            "glow": self.cfg.glow / 100.0,
            "showBattery": self.cfg.show_battery,
            "showMusic": self.cfg.show_music,
            "showPrivacy": self.cfg.show_privacy,
            "showNotifications": self.cfg.show_notifications,
            "autostart": self.cfg.autostart,
        }
        js = (
            "if (window.islandSetConfig) { window.islandSetConfig("
            + json.dumps(payload, ensure_ascii=False)
            + "); }"
        )
        self.view.page().runJavaScript(js)

    def _push_native(self) -> None:
        if not self._page_ready:
            return
        payload = {
            "media": self._media,
            "privacy": self._privacy,
            "notification": self._notification,
        }
        js = (
            "if (window.islandNative) { window.islandNative("
            + json.dumps(payload, ensure_ascii=False)
            + "); }"
        )
        self.view.page().runJavaScript(js)

    def _toast(self, text: str) -> None:
        if not self._page_ready:
            return
        js = (
            "if (window.islandToast) { window.islandToast("
            + json.dumps(text, ensure_ascii=False)
            + "); }"
        )
        self.view.page().runJavaScript(js)

    # ---------------------------------------------------------- native state

    def _on_media(self, data: object) -> None:
        self._media = data if isinstance(data, dict) else None
        self._push_native()

    def _on_privacy(self, data: object) -> None:
        self._privacy = data if isinstance(data, dict) else None
        self._push_native()

    def _on_notification(self, data: object) -> None:
        if not self.cfg.show_notifications or not isinstance(data, dict):
            return
        self._notification = data
        self._notification_timer.start(self.cfg.notification_timeout * 1000)
        self._push_native()

    def _clear_notification(self) -> None:
        self._notification_timer.stop()
        if self._notification is None:
            return
        self._notification = None
        self._push_native()

    # --------------------------------------------------------------- actions

    def handle_action(self, name: str) -> None:
        log.debug("Action: %s", name)
        if name == "settings":
            self.open_settings()
        elif name == "menu":
            self.show_context_menu()
        elif name == "theme":
            self.cycle_theme()
        elif name == "autostart":
            self.toggle_autostart()
        elif name == "toggle":
            self.set_expanded(not self._expanded)
        elif name == "collapse":
            self.set_expanded(False)
        elif name == "hide":
            self.hide_island()
        elif name == "quit":
            self._on_quit()
        elif name == "media_toggle":
            self._native.request_media("toggle")
        elif name == "media_next":
            self._native.request_media("next")
        elif name == "media_prev":
            self._native.request_media("previous")
        elif name == "notifications":
            open_action_center()
            self._clear_notification()
        elif name == "privacy":
            kind = ""
            if isinstance(self._privacy, dict):
                if self._privacy.get("mic"):
                    kind = "mic"
                elif self._privacy.get("camera"):
                    kind = "camera"
            open_privacy_settings(kind)
        else:
            log.debug("Unknown action: %s", name)

    def cycle_theme(self) -> None:
        keys = list(THEMES.keys())
        try:
            index = keys.index(self.cfg.theme)
        except ValueError:
            index = 0
        theme = keys[(index + 1) % len(keys)]
        cfg = replace(self.cfg, theme=theme, accent_override="")
        self.apply_config(cfg, persist=True)
        self._toast(f"Тема: {THEMES[theme]['label']}")

    def toggle_autostart(self) -> None:
        enabled = not self.cfg.autostart
        if not autostart.set_enabled(enabled):
            QMessageBox.warning(
                None,
                APP_TITLE,
                "Не удалось изменить автозапуск.\n"
                "Проверьте права доступа к реестру Windows.",
            )
            return
        cfg = replace(self.cfg, autostart=enabled)
        self.apply_config(cfg, persist=True)
        self._toast("Автозапуск включён" if enabled else "Автозапуск выключен")

    def hide_island(self) -> None:
        self.hide()

    def show_island(self) -> None:
        self.show()
        self.raise_()
        self._apply_mask()
        self._inject_config()
        self._sync_expanded_js()
        self._push_tick()
        self._push_native()

    def open_config_folder(self) -> None:
        try:
            os.startfile(str(app_data_dir()))  # type: ignore[attr-defined]
        except OSError:
            pass

    def open_settings(self) -> None:
        from .settings import SettingsDialog

        if self._settings_dialog is not None and self._settings_dialog.isVisible():
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return

        self._pre_settings = replace(self.cfg)
        dialog = SettingsDialog(self.cfg)
        dialog.applied.connect(self._on_settings_preview)
        dialog.saved.connect(self._on_settings_saved)
        dialog.cancelled.connect(self._on_settings_cancelled)
        dialog.finished.connect(self._on_settings_closed)
        self._settings_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _on_settings_preview(self, cfg: Config) -> None:
        self.apply_config(cfg)

    def _on_settings_saved(self, cfg: Config) -> None:
        self._pre_settings = None
        if cfg.autostart != autostart.is_enabled():
            if not autostart.set_enabled(cfg.autostart):
                QMessageBox.warning(
                    None,
                    APP_TITLE,
                    "Не удалось изменить автозапуск.\n"
                    "Проверьте права доступа к реестру Windows.",
                )
        self.apply_config(cfg, persist=True)
        self._toast("Настройки сохранены")

    def _on_settings_cancelled(self) -> None:
        if self._pre_settings is not None:
            original = self._pre_settings
            self._pre_settings = None
            self.apply_config(original)

    def _on_settings_closed(self, _result: int) -> None:
        self._settings_dialog = None

    # ------------------------------------------------------------------ menu

    def build_menu(self, tray: bool = False) -> QMenu:
        menu = QMenu()
        menu.setStyleSheet(MENU_QSS)

        if tray:
            show_action = QAction("Показать остров", menu)
            show_action.triggered.connect(self.show_island)
            menu.addAction(show_action)
            hide_action = QAction("Скрыть остров", menu)
            hide_action.triggered.connect(self.hide_island)
            menu.addAction(hide_action)
            menu.addSeparator()

        settings = QAction("Настройки…", menu)
        settings.triggered.connect(self.open_settings)
        menu.addAction(settings)

        position_menu = menu.addMenu("Положение")
        position_menu.setStyleSheet(MENU_QSS)
        for key, label in POSITIONS.items():
            action = QAction(label, position_menu)
            action.setCheckable(True)
            action.setChecked(self.cfg.position == key)
            action.triggered.connect(
                lambda _checked=False, key=key: self.apply_config(
                    replace(self.cfg, position=key), persist=True
                )
            )
            position_menu.addAction(action)

        style_menu = menu.addMenu("Стиль")
        style_menu.setStyleSheet(MENU_QSS)
        for key, label in STYLES.items():
            action = QAction(label, style_menu)
            action.setCheckable(True)
            action.setChecked(self.cfg.style == key)
            action.triggered.connect(
                lambda _checked=False, key=key: self.apply_config(
                    replace(self.cfg, style=key), persist=True
                )
            )
            style_menu.addAction(action)

        theme_menu = menu.addMenu("Тема")
        theme_menu.setStyleSheet(MENU_QSS)
        for key, theme in THEMES.items():
            action = QAction(theme["label"], theme_menu)
            action.setCheckable(True)
            action.setChecked(self.cfg.theme == key and not self.cfg.accent_override)
            action.triggered.connect(
                lambda _checked=False, key=key: self.apply_config(
                    replace(self.cfg, theme=key, accent_override=""), persist=True
                )
            )
            theme_menu.addAction(action)

        hover_action = QAction("Раскрывать при наведении", menu)
        hover_action.setCheckable(True)
        hover_action.setChecked(self.cfg.hover_expand)
        hover_action.triggered.connect(
            lambda checked: self.apply_config(
                replace(self.cfg, hover_expand=bool(checked)), persist=True
            )
        )
        menu.addAction(hover_action)

        autostart_action = QAction("Запускать с Windows", menu)
        autostart_action.setCheckable(True)
        autostart_action.setChecked(self.cfg.autostart)
        autostart_action.triggered.connect(self.toggle_autostart)
        menu.addAction(autostart_action)

        menu.addSeparator()

        notifications_action = QAction("Центр уведомлений", menu)
        notifications_action.triggered.connect(open_action_center)
        menu.addAction(notifications_action)

        privacy_action = QAction("Параметры конфиденциальности", menu)
        privacy_action.triggered.connect(open_privacy_settings)
        menu.addAction(privacy_action)

        folder_action = QAction("Папка настроек", menu)
        folder_action.triggered.connect(self.open_config_folder)
        menu.addAction(folder_action)

        menu.addSeparator()

        quit_action = QAction("Выход", menu)
        quit_action.triggered.connect(self._on_quit)
        menu.addAction(quit_action)
        return menu

    def show_context_menu(self) -> None:
        menu = self.build_menu(tray=False)
        menu.exec(QCursor.pos())
        menu.deleteLater()

    # ------------------------------------------------------------- lifecycle

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "view"):
            self.view.setGeometry(0, 0, self.width(), self.height())
        if hasattr(self, "cfg"):
            self._apply_mask()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._closing:
            event.accept()
            return
        # A tool window should never silently disappear on Alt+F4.
        event.ignore()
        self.hide()

    def shutdown(self) -> None:
        self._closing = True
        self._clock_timer.stop()
        self._hover_timer.stop()
        self._notification_timer.stop()
        self._stats_timer.stop()
        try:
            self._native.stop()
            self._native.wait(3500)
        except Exception:
            log.debug("Could not stop native monitor", exc_info=True)
        try:
            self.view.stop()
            self.view.page().deleteLater()
            self.view.deleteLater()
        except Exception:
            pass
        self.close()
