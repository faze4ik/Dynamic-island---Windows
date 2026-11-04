"""Application entry point."""

from __future__ import annotations

import ctypes
import logging
import sys

from PySide6.QtCore import QLockFile, Qt, QTimer
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from . import autostart
from .config import APP_NAME, APP_TITLE, LOG_PATH, VERSION, app_data_dir, asset_dir, load_config, save_config
from .window import IslandWindow

log = logging.getLogger(__name__)


def _setup_logging() -> None:
    handlers: list[logging.Handler] = []
    try:
        handlers.append(
            logging.FileHandler(LOG_PATH, encoding="utf-8", mode="a")
        )
    except OSError:
        pass
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def _install_excepthook() -> None:
    def hook(exc_type, exc_value, exc_tb):
        log.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = hook


def _set_app_user_model_id() -> None:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Vorder.DynamicIsland.Windows.1"
        )
    except Exception:
        pass


def main() -> int:
    _setup_logging()
    _install_excepthook()
    _set_app_user_model_id()
    log.info("Starting %s %s", APP_TITLE, VERSION)

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setApplicationDisplayName(APP_TITLE)
    app.setOrganizationName("Vorder")
    app.setQuitOnLastWindowClosed(False)

    icon_path = asset_dir() / "icon.ico"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    autostart_arg = "--autostart" in sys.argv

    lock = QLockFile(str(app_data_dir() / "dynamic-island.lock"))
    lock.setStaleLockTime(30_000)
    if not lock.tryLock(200):
        log.info("Another instance is already running")
        if not autostart_arg:
            QMessageBox.information(
                None, APP_TITLE, "Dynamic Island уже запущен.\n"
                "Настройки доступны по правому клику на острове."
            )
        return 0

    cfg = load_config()
    registry_autostart = autostart.is_enabled()
    if cfg.autostart != registry_autostart:
        cfg.autostart = registry_autostart
        try:
            save_config(cfg)
        except OSError:
            log.warning("Could not persist autostart state")

    def quit_app() -> None:
        log.info("Exit requested")
        tray.hide()
        app.quit()

    window = IslandWindow(cfg, on_quit=quit_app)

    tray = QSystemTrayIcon(app.windowIcon(), app)
    tray.setToolTip(f"{APP_TITLE} · {VERSION}")

    def show_tray_menu() -> None:
        menu = window.build_menu(tray=True)
        menu.exec(QCursor.pos())
        menu.deleteLater()

    def on_tray_activated(reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.Context,
        ):
            show_tray_menu()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            window.show_island()

    tray.activated.connect(on_tray_activated)
    tray.show()

    def cleanup() -> None:
        tray.hide()
        window.shutdown()

    app.aboutToQuit.connect(cleanup)

    if "--settings" in sys.argv:
        QTimer.singleShot(400, window.open_settings)

    log.info("Ready")
    return app.exec()
