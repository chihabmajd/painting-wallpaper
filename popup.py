"""Frameless popup showing the current painting's info; stays open until closed by hand.

Wayland does not let a client position its own window, so placement (bottom-right
corner, no taskbar entry) is done by the KWin script in kwin/, matched on the app id.
"""
import sys

from PySide6.QtCore import Qt
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

import store

APP_ID = "painting-wallpaper"   # Wayland app id; the KWin script matches on it

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

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(CARD_WIDTH)

        self._build_ui()

        # Qt under-reports wrapped QLabel heights until the widget is polished,
        # so the size is settled before the window is mapped.
        self.ensurePolished()
        self.adjustSize()
        self.show()

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
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)
        card_layout.addWidget(header)

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
        if desc_text and self.info.get("descriptionSource") == "artist":
            about = QLabel(f"About {self.info.get('artist', 'the artist')}")
            about.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: 11px; font-weight: 600;"
                " letter-spacing: 1px; text-transform: uppercase;"
            )
            body_layout.addWidget(about)
            body_layout.addSpacing(2)

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
            label = ("Read about the artist on Wikipedia →"
                     if self.info.get("descriptionSource") == "artist"
                     else "Read on Wikipedia →")
            link = QLabel(f'<a href="{wikipedia_url}">{label}</a>')
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

    def mousePressEvent(self, event):
        # Wayland: dragging has to be handed to the compositor
        if event.button() == Qt.LeftButton and self.windowHandle():
            self.windowHandle().startSystemMove()


def main():
    info = store.load_current()
    if info is None:
        print("error: no current painting, run fetch_painting.py first", file=sys.stderr)
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setDesktopFileName(APP_ID)
    app.setApplicationDisplayName("Painting of the day")
    popup = PaintingPopup(info)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
