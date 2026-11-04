"""Generate assets/icon.ico and assets/icon.png without external dependencies."""

from __future__ import annotations

import struct
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]


def render(size: int) -> QImage:
    scale = 4
    px = size * scale
    image = QImage(px, px, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    radius = px * 0.23
    background = QPainterPath()
    background.addRoundedRect(QRectF(0, 0, px, px), radius, radius)

    gradient = QLinearGradient(0, 0, px, px)
    gradient.setColorAt(0.0, QColor("#7c9cff"))
    gradient.setColorAt(0.55, QColor("#8b7bff"))
    gradient.setColorAt(1.0, QColor("#b06bff"))
    painter.fillPath(background, QBrush(gradient))

    painter.save()
    painter.setClipPath(background)
    gloss = QLinearGradient(0, 0, 0, px * 0.55)
    gloss.setColorAt(0.0, QColor(255, 255, 255, 52))
    gloss.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.fillRect(QRectF(0, 0, px, px * 0.55), gloss)
    painter.restore()

    pill_w = px * 0.66
    pill_h = px * 0.28
    pill_x = (px - pill_w) / 2
    pill_y = (px - pill_h) / 2
    pill = QPainterPath()
    pill.addRoundedRect(
        QRectF(pill_x, pill_y, pill_w, pill_h), pill_h / 2, pill_h / 2
    )
    painter.fillPath(pill, QColor("#090b12"))
    painter.setPen(QPen(QColor(255, 255, 255, 46), max(1.0, px * 0.004)))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(pill)

    dot = pill_h * 0.30
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#9fb0ff"))
    painter.drawEllipse(
        QPointF(pill_x + pill_w * 0.24, pill_y + pill_h / 2), dot / 2, dot / 2
    )

    bar = QRectF(
        pill_x + pill_w * 0.41,
        pill_y + pill_h / 2 - pill_h * 0.13,
        pill_w * 0.35,
        pill_h * 0.26,
    )
    painter.setBrush(QColor("#b9c4ff"))
    painter.drawRoundedRect(bar, pill_h * 0.13, pill_h * 0.13)
    painter.end()

    return image.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    _ = QGuiApplication.instance()
    ASSETS.mkdir(parents=True, exist_ok=True)

    images: list[tuple[int, bytes]] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for size in SIZES:
            image = render(size)
            path = tmp_dir / f"icon_{size}.png"
            if not image.save(str(path), "PNG"):
                print(f"Failed to render {size}px icon", file=sys.stderr)
                return 1
            images.append((size, path.read_bytes()))

    large = render(256)
    large.save(str(ASSETS / "icon.png"), "PNG")

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b""
    payload = b""
    for size, data in images:
        width = 0 if size >= 256 else size
        entries += struct.pack(
            "<BBBBHHII", width, width, 0, 0, 1, 32, len(data), offset
        )
        offset += len(data)
        payload += data

    (ASSETS / "icon.ico").write_bytes(header + entries + payload)
    print(f"Wrote {ASSETS / 'icon.ico'} and {ASSETS / 'icon.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
