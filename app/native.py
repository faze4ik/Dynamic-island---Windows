"""Native Windows integration: media, notifications, microphone and camera.

The Windows Runtime (WinRT) APIs are asynchronous, while Qt lives on the GUI
thread.  A dedicated QThread runs a small asyncio loop and publishes plain
dictionaries through Qt signals.  Nothing in this module touches the user's
mouse or keyboard.
"""

from __future__ import annotations

import asyncio
import logging
import os
import queue
import threading
import time
import winreg
from typing import Any, Optional

from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)

try:
    from winsdk.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus,
    )
    from winsdk.windows.ui.notifications.management import (
        UserNotificationListener,
        UserNotificationListenerAccessStatus,
    )

    WINSDK_AVAILABLE = True
except Exception:  # pragma: no cover - only on systems without WinRT
    GlobalSystemMediaTransportControlsSessionManager = None  # type: ignore[assignment]
    GlobalSystemMediaTransportControlsSessionPlaybackStatus = None  # type: ignore[assignment]
    UserNotificationListener = None  # type: ignore[assignment]
    UserNotificationListenerAccessStatus = None  # type: ignore[assignment]
    WINSDK_AVAILABLE = False


PRIVACY_ROOT = (
    r"Software\Microsoft\Windows\CurrentVersion"
    r"\CapabilityAccessManager\ConsentStore"
)
DEVICES = {
    "mic": "microphone",
    "camera": "webcam",
}

APP_NAMES = {
    "chrome": "Google Chrome",
    "msedge": "Microsoft Edge",
    "firefox": "Firefox",
    "discord": "Discord",
    "telegram": "Telegram",
    "teams": "Microsoft Teams",
    "ms-teams": "Microsoft Teams",
    "obs64": "OBS Studio",
    "obs": "OBS Studio",
    "zoom": "Zoom",
    "skype": "Skype",
    "slack": "Slack",
    "whatsapp": "WhatsApp",
    "spotify": "Spotify",
    "soundrecorder": "Диктофон",
    "camera": "Камера",
    "windowsoundrecorder": "Диктофон",
    "ivcam": "iVCam",
    "riff": "Riff",
}

MEDIA_COMMANDS = {"toggle", "next", "previous"}


def _friendly_app(key: str) -> str:
    """Turn a registry key / package name into a human readable app name."""
    raw = key
    if "#" in raw:
        parts = [p for p in raw.split("#") if p]
        raw = parts[-1] if parts else raw
    raw = raw.replace(".exe", "").replace(".EXE", "")
    lowered = raw.lower()
    for needle, name in APP_NAMES.items():
        if needle in lowered:
            return name
    if raw.startswith("Microsoft."):
        raw = raw.split("_", 1)[0].replace("Microsoft.", "")
        raw = raw.replace("Windows", "").strip()
        if not raw:
            raw = "Windows"
    raw = raw.replace("_", " ").replace("-", " ").strip()
    return raw[:1].upper() + raw[1:] if raw else "Приложение"


def _read_active_devices() -> dict[str, list[str]]:
    """Best-effort privacy indicator from the Windows capability registry.

    Windows writes ``LastUsedTimeStart`` and ``LastUsedTimeStop`` FILETIME
    values for packaged and desktop apps.  A start newer than the stop means
    that the device is currently in use.  ``stop == 0`` is also active.
    """
    result: dict[str, list[str]] = {"mic": [], "camera": []}

    def walk(path: str, device: str, depth: int = 0) -> None:
        if depth > 6:
            return
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
        except OSError:
            return
        try:
            start = stop = 0
            try:
                start = int(winreg.QueryValueEx(key, "LastUsedTimeStart")[0])
            except OSError:
                pass
            try:
                stop = int(winreg.QueryValueEx(key, "LastUsedTimeStop")[0])
            except OSError:
                pass
            if start > 0 and (stop == 0 or start > stop):
                name = _friendly_app(path.rsplit("\\", 1)[-1])
                if name and name not in result[device]:
                    result[device].append(name)
            try:
                sub_count = winreg.QueryInfoKey(key)[0]
            except OSError:
                sub_count = 0
            for index in range(sub_count):
                try:
                    child = winreg.EnumKey(key, index)
                except OSError:
                    break
                walk(path + "\\" + child, device, depth + 1)
        finally:
            try:
                winreg.CloseKey(key)
            except OSError:
                pass

    for device, registry_name in DEVICES.items():
        walk(PRIVACY_ROOT + "\\" + registry_name, device)
    return result


def _notification_text(notification: Any) -> str:
    try:
        visual = notification.notification.visual
        bindings = visual.bindings
        if bindings.size:
            elements = bindings[0].get_text_elements()
            for element in elements:
                text = getattr(element, "text", "") or ""
                if text.strip():
                    return text.strip()
    except Exception:
        pass
    return ""


def _notification_app(notification: Any) -> str:
    try:
        info = notification.app_info
        if info is not None:
            name = info.display_info.display_name
            if name:
                return str(name)
            app_id = info.app_user_model_id or ""
            return _friendly_app(str(app_id))
    except Exception:
        pass
    return "Уведомление"


class NativeMonitor(QThread):
    """Polls WinRT media/notifications and the privacy registry."""

    media = Signal(object)
    privacy = Signal(object)
    notification = Signal(object)
    ready = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._stop_event = threading.Event()
        self._commands: "queue.Queue[str]" = queue.Queue()
        self._session: Any = None
        self._listener: Any = None
        self._media_props_seen: Any = None
        self._last_notification_ids: set[int] = set()
        self._baseline_done = False
        self._access_checked = False
        self._access_allowed = False

    # ------------------------------------------------------------- public API

    def stop(self) -> None:
        self._stop_event.set()

    def request_media(self, command: str) -> None:
        if command in MEDIA_COMMANDS:
            self._commands.put(command)

    # --------------------------------------------------------------- lifecycle

    def run(self) -> None:  # noqa: D401 - QThread entry point
        if not WINSDK_AVAILABLE:
            log.info("winsdk is not available; music and notification detection disabled")
            self.ready.emit(False)
            return
        try:
            asyncio.run(self._main())
        except Exception:
            log.exception("Native monitor crashed")
        finally:
            self.ready.emit(False)

    async def _main(self) -> None:
        manager = None
        try:
            manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        except Exception:
            log.exception("Could not initialize Windows media session manager")

        try:
            self._listener = UserNotificationListener.current
        except Exception:
            log.exception("Could not initialize Windows notification listener")

        self.ready.emit(True)
        last_privacy: Optional[dict[str, list[str]]] = None

        while not self._stop_event.is_set():
            started = time.monotonic()

            if self._listener is not None:
                await self._poll_notifications()

            if manager is not None:
                await self._poll_media(manager)

            privacy = _read_active_devices()
            if privacy != last_privacy:
                last_privacy = privacy
                self.privacy.emit(privacy)

            await self._drain_commands()

            try:
                elapsed = time.monotonic() - started
                await asyncio.sleep(max(0.55, 1.35 - elapsed))
            except asyncio.CancelledError:
                break

    async def _poll_media(self, manager: Any) -> None:
        try:
            session = manager.get_current_session()
            self._session = session
            if session is None:
                self.media.emit({"active": False})
                return
            properties = await session.try_get_media_properties_async()
            playback = session.get_playback_info()
            timeline = session.get_timeline_properties()
            status = playback.playback_status if playback is not None else None
            playing = status == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING
            position = 0.0
            duration = 0.0
            try:
                position = max(0.0, timeline.position.total_seconds())
            except Exception:
                pass
            try:
                duration = max(0.0, timeline.end_time.total_seconds())
            except Exception:
                pass
            data = {
                "active": True,
                "title": str(properties.title or "").strip(),
                "artist": str(properties.artist or "").strip(),
                "album": str(properties.album_title or "").strip(),
                "playing": bool(playing),
                "position": round(position, 1),
                "duration": round(duration, 1),
                "app": _friendly_app(str(session.source_app_user_model_id or "")),
            }
            self.media.emit(data)
        except Exception:
            # A media session can disappear between get_current_session() and
            # reading its properties.  Don't spam the log every 1.3 seconds.
            self.media.emit({"active": False})

    async def _poll_notifications(self) -> None:
        if not self._access_checked:
            self._access_checked = True
            try:
                status = await self._listener.request_access_async()
                self._access_allowed = (
                    status == UserNotificationListenerAccessStatus.ALLOWED
                )
                log.info("Notification listener access: %s", status)
            except Exception:
                self._access_allowed = False
                log.exception("Notification listener access request failed")
        if not self._access_allowed:
            return

        try:
            notifications = await self._listener.get_notifications_async(0)
        except Exception:
            return

        current_ids: set[int] = set()
        newest = None
        for item in notifications:
            try:
                item_id = int(item.id)
            except Exception:
                continue
            current_ids.add(item_id)
            if item_id in self._last_notification_ids:
                continue
            if not self._baseline_done:
                continue
            creation = getattr(item, "creation_time", None)
            if newest is None or (
                creation is not None
                and (newest[0] is None or creation > newest[0])
            ):
                newest = (creation, item)

        if not self._baseline_done:
            self._baseline_done = True
        elif newest is not None:
            _, item = newest
            self.notification.emit(
                {
                    "app": _notification_app(item),
                    "text": _notification_text(item),
                    "id": int(getattr(item, "id", 0)),
                }
            )

        # Keep only IDs that Windows still knows about, plus a little history.
        self._last_notification_ids = current_ids

    async def _drain_commands(self) -> None:
        session = self._session
        while True:
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                return
            if session is None:
                continue
            try:
                if command == "toggle":
                    await session.try_toggle_play_pause_async()
                elif command == "next":
                    await session.try_skip_next_async()
                elif command == "previous":
                    await session.try_skip_previous_async()
            except Exception:
                log.debug("Media command failed: %s", command, exc_info=True)


def open_action_center() -> None:
    """Open the Windows notification center."""
    try:
        os.startfile("ms-actioncenter:")  # type: ignore[attr-defined]
        return
    except Exception:
        pass
    try:
        os.startfile("ms-settings:notifications")  # type: ignore[attr-defined]
    except Exception:
        log.warning("Could not open Windows notification center")


def open_privacy_settings(kind: str = "") -> None:
    uri = {
        "mic": "ms-settings:privacy-microphone",
        "camera": "ms-settings:privacy-webcam",
    }.get(kind, "ms-settings:privacy")
    try:
        os.startfile(uri)  # type: ignore[attr-defined]
    except Exception:
        log.warning("Could not open Windows privacy settings")
