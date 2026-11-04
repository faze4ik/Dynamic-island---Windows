"""Settings dialog for the Dynamic Island."""

from __future__ import annotations

import os
import subprocess
from dataclasses import replace

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .config import (
    APP_TITLE,
    POSITIONS,
    STYLES,
    THEMES,
    VERSION,
    Config,
    app_data_dir,
    asset_dir,
)
from .native import open_action_center, open_privacy_settings
from .style import APP_QSS


def _section(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Section")
    return label


def _card() -> tuple[QFrame, QGridLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QGridLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setHorizontalSpacing(14)
    layout.setVerticalSpacing(10)
    layout.setColumnStretch(1, 1)
    return frame, layout


class SettingsDialog(QDialog):
    applied = Signal(object)
    saved = Signal(object)
    cancelled = Signal()

    def __init__(self, config: Config, parent=None) -> None:
        super().__init__(parent)
        self._original = replace(config)
        self._accent = config.accent_override
        self._explicit_cancel = False
        self._saved_once = False
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(120)
        self._preview_timer.timeout.connect(self._emit_preview)

        self.setWindowTitle(f"{APP_TITLE} — Настройки")
        self.setStyleSheet(APP_QSS)
        self.setMinimumSize(660, 600)
        self.resize(720, 690)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        icon_path = asset_dir() / "icon.ico"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(14)

        root.addLayout(self._build_header())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(config), "Общие")
        self.tabs.addTab(self._build_appearance_tab(config), "Оформление")
        self.tabs.addTab(self._build_notifications_tab(config), "Уведомления")
        self.tabs.addTab(self._build_system_tab(config), "Система")
        root.addWidget(self.tabs, 1)

        root.addLayout(self._build_footer())

        self._update_swatch()
        self._update_theme_preview()
        self._connect_preview_signals()

    # ------------------------------------------------------------------- ui

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        icon_label = QLabel()
        icon_path = asset_dir() / "icon.ico"
        if icon_path.is_file():
            icon_label.setPixmap(QIcon(str(icon_path)).pixmap(46, 46))
        icon_label.setFixedSize(46, 46)
        row.addWidget(icon_label)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        title = QLabel("Dynamic Island")
        title.setObjectName("Title")
        subtitle = QLabel(f"Настройки острова · версия {VERSION}")
        subtitle.setObjectName("Subtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        row.addLayout(titles)
        row.addStretch(1)

        badge = QLabel("Windows · iPhone style")
        badge.setObjectName("Hint")
        row.addWidget(badge)
        return row

    def _scroll_area(self) -> tuple[QScrollArea, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("TabInner")
        scroll.setWidget(inner)
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(9)
        return scroll, layout

    def _build_general_tab(self, cfg: Config) -> QScrollArea:
        scroll, layout = self._scroll_area()

        layout.addWidget(_section("ПОЛОЖЕНИЕ И СТИЛЬ"))
        card, grid = _card()
        self.position_combo = QComboBox()
        for key, label in POSITIONS.items():
            self.position_combo.addItem(label, key)
        self._select_data(self.position_combo, cfg.position)
        self._add_row(grid, 0, "Расположение", self.position_combo)

        self.style_combo = QComboBox()
        for key, label in STYLES.items():
            self.style_combo.addItem(label, key)
        self._select_data(self.style_combo, cfg.style)
        self._add_row(grid, 1, "Форма", self.style_combo)

        self.monitor_combo = QComboBox()
        screens = QGuiApplication.screens()
        primary = QGuiApplication.primaryScreen()
        for index, screen in enumerate(screens):
            geo = screen.geometry()
            name = f"Экран {index + 1} · {geo.width()}×{geo.height()}"
            if screen is primary:
                name += " · основной"
            self.monitor_combo.addItem(name, index)
        self._select_data(self.monitor_combo, cfg.monitor)
        self._add_row(grid, 2, "Монитор", self.monitor_combo)

        self.offset_x = QSpinBox()
        self.offset_x.setRange(0, 120)
        self.offset_x.setValue(cfg.offset_x)
        self.offset_x.setSuffix(" px")
        self._add_row(grid, 3, "Отступ слева / справа", self.offset_x)

        self.offset_y = QSpinBox()
        self.offset_y.setRange(0, 120)
        self.offset_y.setValue(cfg.offset_y)
        self.offset_y.setSuffix(" px")
        self._add_row(grid, 4, "Отступ сверху / снизу", self.offset_y)

        hint = QLabel(
            "Чёлка iPhone XR по умолчанию прилегает к краю экрана. "
            "Для остальных форм отступы задают свободное поле вокруг острова."
        )
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        grid.addWidget(hint, 5, 0, 1, 2)
        layout.addWidget(card)

        layout.addWidget(_section("ПОВЕДЕНИЕ"))
        card, grid = _card()
        self.hover_check = QCheckBox("Раскрывать при наведении курсора")
        self.hover_check.setChecked(cfg.hover_expand)
        grid.addWidget(self.hover_check, 0, 0, 1, 2)

        self.hover_delay = QSpinBox()
        self.hover_delay.setRange(0, 1500)
        self.hover_delay.setSingleStep(50)
        self.hover_delay.setValue(cfg.hover_delay)
        self.hover_delay.setSuffix(" мс")
        self._add_row(grid, 1, "Задержка раскрытия", self.hover_delay)

        self.top_check = QCheckBox("Поверх всех окон")
        self.top_check.setChecked(cfg.always_on_top)
        grid.addWidget(self.top_check, 2, 0, 1, 2)

        self.battery_check = QCheckBox("Показывать заряд батареи")
        self.battery_check.setChecked(cfg.show_battery)
        grid.addWidget(self.battery_check, 3, 0, 1, 2)

        self.seconds_check = QCheckBox("Показывать секунды")
        self.seconds_check.setChecked(cfg.show_seconds)
        grid.addWidget(self.seconds_check, 4, 0, 1, 2)

        self.autostart_check = QCheckBox("Запускать вместе с Windows")
        self.autostart_check.setChecked(cfg.autostart)
        grid.addWidget(self.autostart_check, 5, 0, 1, 2)

        hint = QLabel(
            "Автозапуск добавляет приложение в раздел Windows "
            "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run."
        )
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        grid.addWidget(hint, 6, 0, 1, 2)
        layout.addWidget(card)

        layout.addStretch(1)
        return scroll

    def _build_appearance_tab(self, cfg: Config) -> QScrollArea:
        scroll, layout = self._scroll_area()

        layout.addWidget(_section("ТЕМА"))
        card, grid = _card()
        self.theme_combo = QComboBox()
        for key, theme in THEMES.items():
            self.theme_combo.addItem(theme["label"], key)
        self._select_data(self.theme_combo, cfg.theme)
        self._add_row(grid, 0, "Цветовая тема", self.theme_combo)

        self.theme_preview = QFrame()
        self.theme_preview.setObjectName("ThemePreview")
        self.theme_preview.setMinimumHeight(58)
        preview_layout = QVBoxLayout(self.theme_preview)
        preview_layout.setContentsMargins(13, 9, 13, 9)
        preview_layout.setSpacing(2)
        self.preview_title = QLabel()
        self.preview_title.setObjectName("PreviewTitle")
        self.preview_sub = QLabel()
        self.preview_sub.setObjectName("PreviewSub")
        preview_layout.addWidget(self.preview_title)
        preview_layout.addWidget(self.preview_sub)
        grid.addWidget(self.theme_preview, 1, 0, 1, 2)

        accent_row = QHBoxLayout()
        accent_row.setSpacing(8)
        self.swatch = QPushButton()
        self.swatch.setFixedSize(54, 26)
        self.swatch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.swatch.clicked.connect(self._pick_accent)
        accent_row.addWidget(self.swatch)
        pick = QPushButton("Выбрать цвет…")
        pick.clicked.connect(self._pick_accent)
        accent_row.addWidget(pick)
        reset_accent = QPushButton("Сбросить")
        reset_accent.setObjectName("Ghost")
        reset_accent.clicked.connect(self._reset_accent)
        accent_row.addWidget(reset_accent)
        accent_row.addStretch(1)
        grid.addWidget(QLabel("Акцентный цвет"), 2, 0)
        grid.addLayout(accent_row, 2, 1)
        layout.addWidget(card)

        layout.addWidget(_section("РАЗМЕР И ЭФФЕКТЫ"))
        card, grid = _card()
        self.scale_slider, self.scale_value = self._slider_row(
            grid, 0, "Масштаб", 75, 160, round(cfg.scale * 100), "%"
        )
        self.opacity_slider, self.opacity_value = self._slider_row(
            grid, 1, "Прозрачность", 55, 100, round(cfg.opacity * 100), "%"
        )
        self.glow_slider, self.glow_value = self._slider_row(
            grid, 2, "Свечение", 0, 100, cfg.glow, "%"
        )
        hint = QLabel(
            "Изменения сразу отображаются на острове. Нажмите «Сохранить», "
            "чтобы оставить их после закрытия настроек."
        )
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        grid.addWidget(hint, 3, 0, 1, 2)
        layout.addWidget(card)

        layout.addStretch(1)
        return scroll

    def _build_notifications_tab(self, cfg: Config) -> QScrollArea:
        scroll, layout = self._scroll_area()

        layout.addWidget(_section("ЧТО ПОКАЗЫВАТЬ"))
        card, grid = _card()
        self.music_check = QCheckBox("Музыка: трек, исполнитель и управление")
        self.music_check.setChecked(cfg.show_music)
        grid.addWidget(self.music_check, 0, 0, 1, 2)

        self.privacy_check = QCheckBox("Микрофон и камера: кто использует")
        self.privacy_check.setChecked(cfg.show_privacy)
        grid.addWidget(self.privacy_check, 1, 0, 1, 2)

        self.notifications_check = QCheckBox("Звоночек при новом уведомлении")
        self.notifications_check.setChecked(cfg.show_notifications)
        grid.addWidget(self.notifications_check, 2, 0, 1, 2)

        self.notification_timeout = QSpinBox()
        self.notification_timeout.setRange(10, 300)
        self.notification_timeout.setSingleStep(5)
        self.notification_timeout.setValue(cfg.notification_timeout)
        self.notification_timeout.setSuffix(" сек")
        self._add_row(grid, 3, "Скрыть звоночек через", self.notification_timeout)
        layout.addWidget(card)

        hint = QLabel(
            "Музыка берётся из системного медиаплеера Windows. "
            "Индикаторы микрофона и камеры читаются из журнала доступа Windows; "
            "они появляются, пока устройство действительно используется. "
            "Нажмите на звоночек, чтобы открыть центр уведомлений."
        )
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addWidget(_section("БЫСТРЫЕ ДЕЙСТВИЯ"))
        card, grid = _card()
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        center = QPushButton("Центр уведомлений")
        center.clicked.connect(open_action_center)
        buttons.addWidget(center)
        privacy = QPushButton("Конфиденциальность")
        privacy.clicked.connect(open_privacy_settings)
        buttons.addWidget(privacy)
        buttons.addStretch(1)
        grid.addLayout(buttons, 0, 0, 1, 2)

        hint = QLabel(
            "При первом запуске Windows может запросить разрешение на доступ "
            "к уведомлениям. Если доступ запрещён, звоночек просто не появится."
        )
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        grid.addWidget(hint, 1, 0, 1, 2)
        layout.addWidget(card)

        layout.addStretch(1)
        return scroll

    def _build_system_tab(self, cfg: Config) -> QScrollArea:
        scroll, layout = self._scroll_area()

        layout.addWidget(_section("СИСТЕМНЫЕ НАСТРОЙКИ"))
        card, grid = _card()
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        windows_settings = QPushButton("Параметры Windows")
        windows_settings.clicked.connect(
            lambda: self._open_uri("ms-settings:")
        )
        buttons.addWidget(windows_settings)
        task_manager = QPushButton("Диспетчер задач")
        task_manager.clicked.connect(self._open_task_manager)
        buttons.addWidget(task_manager)
        buttons.addStretch(1)
        grid.addLayout(buttons, 0, 0, 1, 2)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        notifications = QPushButton("Центр уведомлений")
        notifications.clicked.connect(open_action_center)
        buttons.addWidget(notifications)
        privacy = QPushButton("Конфиденциальность")
        privacy.clicked.connect(open_privacy_settings)
        buttons.addWidget(privacy)
        folder = QPushButton("Папка настроек")
        folder.setObjectName("Ghost")
        folder.clicked.connect(self._open_folder)
        buttons.addWidget(folder)
        buttons.addStretch(1)
        grid.addLayout(buttons, 1, 0, 1, 2)

        hint = QLabel(
            "Загрузка процессора и оперативной памяти показывается прямо "
            "в раскрытом острове, рядом с часами и музыкой."
        )
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        grid.addWidget(hint, 2, 0, 1, 2)
        layout.addWidget(card)

        layout.addStretch(1)
        return scroll

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        reset = QPushButton("Сбросить")
        reset.setObjectName("Ghost")
        reset.clicked.connect(self._reset_all)
        row.addWidget(reset)
        row.addStretch(1)

        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self._on_cancel)
        row.addWidget(cancel)

        apply_button = QPushButton("Применить")
        apply_button.clicked.connect(self._on_apply)
        row.addWidget(apply_button)

        save = QPushButton("Сохранить")
        save.setObjectName("Primary")
        save.clicked.connect(self._on_save)
        row.addWidget(save)
        return row

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _select_data(combo: QComboBox, data) -> None:
        index = combo.findData(data)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _add_row(self, grid: QGridLayout, row: int, label: str, widget) -> None:
        text = QLabel(label)
        text.setMinimumWidth(160)
        grid.addWidget(text, row, 0)
        grid.addWidget(widget, row, 1)

    def _slider_row(
        self,
        grid: QGridLayout,
        row: int,
        label: str,
        minimum: int,
        maximum: int,
        value: int,
        suffix: str,
    ) -> tuple[QSlider, QLabel]:
        text = QLabel(label)
        text.setMinimumWidth(160)
        grid.addWidget(text, row, 0)

        box = QHBoxLayout()
        box.setSpacing(10)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(max(minimum, min(maximum, value)))
        box.addWidget(slider, 1)
        value_label = QLabel(f"{slider.value()}{suffix}")
        value_label.setObjectName("Value")
        value_label.setFixedWidth(42)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        box.addWidget(value_label)
        slider.valueChanged.connect(
            lambda val, lbl=value_label, s=suffix: lbl.setText(f"{val}{s}")
        )
        grid.addLayout(box, row, 1)
        return slider, value_label

    def _connect_preview_signals(self) -> None:
        self.position_combo.currentIndexChanged.connect(self._schedule_preview)
        self.style_combo.currentIndexChanged.connect(self._schedule_preview)
        self.monitor_combo.currentIndexChanged.connect(self._schedule_preview)
        self.offset_x.valueChanged.connect(self._schedule_preview)
        self.offset_y.valueChanged.connect(self._schedule_preview)
        self.hover_check.toggled.connect(self._schedule_preview)
        self.hover_delay.valueChanged.connect(self._schedule_preview)
        self.top_check.toggled.connect(self._schedule_preview)
        self.battery_check.toggled.connect(self._schedule_preview)
        self.seconds_check.toggled.connect(self._schedule_preview)
        self.theme_combo.currentIndexChanged.connect(self._schedule_preview)
        self.theme_combo.currentIndexChanged.connect(self._update_theme_preview)
        self.scale_slider.valueChanged.connect(self._schedule_preview)
        self.opacity_slider.valueChanged.connect(self._schedule_preview)
        self.glow_slider.valueChanged.connect(self._schedule_preview)
        self.music_check.toggled.connect(self._schedule_preview)
        self.privacy_check.toggled.connect(self._schedule_preview)
        self.notifications_check.toggled.connect(self._schedule_preview)
        self.notification_timeout.valueChanged.connect(self._schedule_preview)

    def _schedule_preview(self, *_args) -> None:
        self._preview_timer.start()

    def _current_theme(self) -> dict:
        key = self.theme_combo.currentData()
        return THEMES.get(key, THEMES["iphone"])

    def _update_swatch(self) -> None:
        color = self._accent or self._current_theme()["accent"]
        self.swatch.setStyleSheet(
            f"QPushButton {{ background: {color}; border: 1px solid rgba(255,255,255,.28);"
            " border-radius: 7px; }}"
            "QPushButton:hover { border-color: rgba(255,255,255,.6); }"
        )
        self.swatch.setToolTip(color)

    def _update_theme_preview(self, *_args) -> None:
        theme = self._current_theme()
        accent = self._accent or theme["accent"]
        self.preview_title.setText(theme["label"])
        self.preview_sub.setText(f"Акцент: {accent} · всегда чёрный остров")
        self.preview_title.setStyleSheet(
            f"color: {theme['text']}; font-size: 13px; font-weight: 650; background: transparent;"
        )
        self.preview_sub.setStyleSheet(
            f"color: {theme['muted']}; font-size: 10px; background: transparent;"
        )
        self.theme_preview.setStyleSheet(
            f"QFrame#ThemePreview {{ background: {theme['bg2']};"
            f" border: 1px solid {theme['border']}; border-radius: 12px; }}"
        )
        self._update_swatch()

    def _pick_accent(self) -> None:
        start = QColor(self._accent or self._current_theme()["accent"])
        color = QColorDialog.getColor(start, self, "Акцентный цвет острова")
        if color.isValid():
            self._accent = color.name()
            self._update_swatch()
            self._update_theme_preview()
            self._schedule_preview()

    def _reset_accent(self) -> None:
        self._accent = ""
        self._update_swatch()
        self._update_theme_preview()
        self._schedule_preview()

    # --------------------------------------------------------------- system

    def _open_uri(self, uri: str) -> None:
        try:
            os.startfile(uri)  # type: ignore[attr-defined]
        except OSError:
            QMessageBox.warning(self, APP_TITLE, f"Не удалось открыть:\n{uri}")

    def _open_task_manager(self) -> None:
        try:
            subprocess.Popen(["taskmgr.exe"])
        except OSError:
            QMessageBox.warning(self, APP_TITLE, "Не удалось открыть диспетчер задач.")

    def _open_folder(self) -> None:
        try:
            os.startfile(str(app_data_dir()))  # type: ignore[attr-defined]
        except OSError:
            pass

    # ----------------------------------------------------------------- state

    def _reset_all(self) -> None:
        defaults = Config()
        self._select_data(self.position_combo, defaults.position)
        self._select_data(self.style_combo, defaults.style)
        self._select_data(self.monitor_combo, 0)
        self.offset_x.setValue(defaults.offset_x)
        self.offset_y.setValue(defaults.offset_y)
        self.hover_check.setChecked(defaults.hover_expand)
        self.hover_delay.setValue(defaults.hover_delay)
        self.top_check.setChecked(defaults.always_on_top)
        self.battery_check.setChecked(defaults.show_battery)
        self.seconds_check.setChecked(defaults.show_seconds)
        self.autostart_check.setChecked(defaults.autostart)
        self.music_check.setChecked(defaults.show_music)
        self.privacy_check.setChecked(defaults.show_privacy)
        self.notifications_check.setChecked(defaults.show_notifications)
        self.notification_timeout.setValue(defaults.notification_timeout)
        self._select_data(self.theme_combo, defaults.theme)
        self._accent = ""
        self.scale_slider.setValue(round(defaults.scale * 100))
        self.opacity_slider.setValue(round(defaults.opacity * 100))
        self.glow_slider.setValue(defaults.glow)
        self._update_swatch()
        self._update_theme_preview()
        self._schedule_preview()

    def _collect(self, validate: bool = False) -> Config | None:
        cfg = Config(
            position=self.position_combo.currentData(),
            style=self.style_combo.currentData(),
            monitor=int(self.monitor_combo.currentData() or 0),
            offset_x=self.offset_x.value(),
            offset_y=self.offset_y.value(),
            scale=self.scale_slider.value() / 100.0,
            theme=self.theme_combo.currentData(),
            accent_override=self._accent,
            opacity=self.opacity_slider.value() / 100.0,
            glow=self.glow_slider.value(),
            hover_expand=self.hover_check.isChecked(),
            hover_delay=self.hover_delay.value(),
            always_on_top=self.top_check.isChecked(),
            autostart=self.autostart_check.isChecked(),
            show_battery=self.battery_check.isChecked(),
            show_seconds=self.seconds_check.isChecked(),
            show_music=self.music_check.isChecked(),
            show_privacy=self.privacy_check.isChecked(),
            show_notifications=self.notifications_check.isChecked(),
            notification_timeout=self.notification_timeout.value(),
        )
        return cfg.normalize()

    def _emit_preview(self) -> None:
        if not self.isVisible():
            return
        cfg = self._collect(validate=False)
        if cfg is not None:
            self.applied.emit(cfg)

    def _on_apply(self) -> None:
        cfg = self._collect(validate=True)
        if cfg is None:
            return
        self.applied.emit(cfg)

    def _on_cancel(self) -> None:
        self._explicit_cancel = True
        self.cancelled.emit()
        self.reject()

    def _on_save(self) -> None:
        cfg = self._collect(validate=True)
        if cfg is None:
            return
        self._saved_once = True
        self.saved.emit(cfg)
        self.accept()

    def closeEvent(self, event) -> None:  # noqa: N802
        # Closing with the window X keeps everything that was changed in the
        # live preview.  Only the explicit "Отмена" button reverts changes.
        if not self._explicit_cancel and not self._saved_once:
            cfg = self._collect(validate=True)
            if cfg is not None:
                self._saved_once = True
                self.saved.emit(cfg)
        event.accept()
        self.done(QDialog.DialogCode.Accepted)
