"""Small, modern, frameless popup with painting info. Stays until closed by hand."""
import sys

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QGraphicsDropShadowEffect,
)

import compose_wallpaper
import store

CARD_WIDTH = 620
MARGIN = 24
BODY_MARGIN = 28
# actual width available for wrapped text, once outer + body margins are subtracted
CONTENT_WIDTH = CARD_WIDTH - 2 * MARGIN - 2 * BODY_MARGIN
MAX_DESC_CHARS = 1400

CARD_BG = "#fbfaf7"
TEXT_PRIMARY = "#2b2823"
TEXT_SECONDARY = "#6f6a60"
ACCENT = "#b08d57"


class PaintingPopup(QWidget):
    def __init__(self, info: dict):
        super().__init__()
        self.info = info
        self._drag_pos = None

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(CARD_WIDTH)

        self._build_ui()

        # Qt under-reports wrapped QLabel heights (sizeHint/heightForWidth)
        # until the widget has actually been shown and its stylesheet fonts
        # polished — measuring before that silently truncates long
        # descriptions. So: show off-screen first, flush the event loop so a
        # real layout pass happens, THEN measure/position/reveal.
        self.move(-10000, -10000)
        self.show()
        QApplication.processEvents()
        self.adjustSize()

        self._position_bottom_right()
        self._slide_in()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)

        card = QWidget(self)
        card.setObjectName("card")
        card.setStyleSheet(
            f"""
            #card {{
                background-color: {CARD_BG};
                border-radius: 18px;
            }}
            """
        )
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 90))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # slim header bar with just the close button
        header = QWidget()
        header.setStyleSheet(f"background-color: {CARD_BG};")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 10, 10, 0)
        header_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: #f1ede4;
                color: {TEXT_SECONDARY};
                border-radius: 12px;
                font-size: 12px;
                border: none;
            }}
            QPushButton:hover {{ background-color: #e6e0d2; color: {TEXT_PRIMARY}; }}
            """
        )
        close_btn.clicked.connect(self._fade_out)
        header_layout.addWidget(close_btn)
        card_layout.addWidget(header)

        # text body
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(BODY_MARGIN, 4, BODY_MARGIN, 20)
        body_layout.setSpacing(4)

        title = QLabel(self.info.get("title", "Untitled"))
        title.setWordWrap(True)
        title.setFixedWidth(CONTENT_WIDTH)
        title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 21px; font-weight: 600;"
        )
        body_layout.addWidget(title)

        artist_bits = [self.info.get("artist", "")]
        if self.info.get("date"):
            artist_bits.append(f"· {self.info['date']}")
        subtitle = QLabel(" ".join(b for b in artist_bits if b))
        subtitle.setStyleSheet(f"color: {ACCENT}; font-size: 14.5px; font-weight: 500;")
        body_layout.addWidget(subtitle)

        if self.info.get("medium"):
            medium = QLabel(self.info["medium"])
            medium.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
            body_layout.addWidget(medium)

        body_layout.addSpacing(10)

        desc_text = self.info.get("description", "").strip()
        if desc_text:
            if len(desc_text) > MAX_DESC_CHARS:
                desc_text = desc_text[:MAX_DESC_CHARS].rsplit(" ", 1)[0] + "…"

            desc_label = QLabel(desc_text)
            desc_label.setWordWrap(True)
            desc_label.setFixedWidth(CONTENT_WIDTH)
            desc_label.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: 15px; line-height: 160%;"
            )
            body_layout.addWidget(desc_label)

        wikipedia_url = self.info.get("wikipediaURL")
        if wikipedia_url:
            body_layout.addSpacing(12)
            link = QLabel(f'<a href="{wikipedia_url}">Read on Wikipedia →</a>')
            link.setOpenExternalLinks(True)
            link.setStyleSheet(
                f"""
                QLabel {{ font-size: 13.5px; }}
                a {{ color: {ACCENT}; text-decoration: none; font-weight: 600; }}
                """
            )
            link.setCursor(Qt.PointingHandCursor)
            body_layout.addWidget(link)

        card_layout.addWidget(body)
        outer.addWidget(card)

    def _position_bottom_right(self):
        # Qt's availableGeometry() doesn't detect the panel on this
        # Wayland/KDE session (see compose_wallpaper.py) — query Plasma
        # directly instead so the popup doesn't sit under the panel.
        full = QApplication.primaryScreen().geometry()
        area_x, area_y, area_w, area_h = compose_wallpaper.safe_area(full.width(), full.height())
        x = area_x + area_w - self.width() - 20
        y = area_y + area_h - self.height() - 20
        self._target_pos = QPoint(x, y)

    def _slide_in(self):
        # Wayland doesn't support animating whole-window opacity for this
        # window type, so we slide up from below instead of fading.
        start = QPoint(self._target_pos.x(), self._target_pos.y() + 40)
        self.move(start)
        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(260)
        self._anim.setStartValue(start)
        self._anim.setEndValue(self._target_pos)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()

    def _fade_out(self):
        end = QPoint(self._target_pos.x(), self._target_pos.y() + 40)
        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(200)
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(end)
        self._anim.setEasingCurve(QEasingCurve.InCubic)
        self._anim.finished.connect(self.close)
        self._anim.start()

    # allow dragging the card by clicking anywhere on it
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


def main():
    info = store.load_current()
    if info is None:
        print("error: no current painting, run fetch_painting.py first", file=sys.stderr)
        sys.exit(1)

    app = QApplication(sys.argv)
    popup = PaintingPopup(info)  # shows itself once sized correctly
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
