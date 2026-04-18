# -*- coding: utf-8 -*-
"""
CharacterCard - carte miniature d'un Character (asset).

Preview orientee editeur d'assets:
  - Nom + badge Niveau
  - Barres PV / Stamina
  - Badges des 5 stats de combat
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ..character import Character

_CARD_BG = "#1e1e2e"
_CARD_BORDER = "#45475a"
_CARD_HOVER = "#8060c0"
_HEADER_BG = "#282838"
_HEADER_BORDER = "#585878"
_SECTION_BG = "#23233a"
_TEXT_PRIMARY = "#cdd6f4"
_TEXT_SECONDARY = "#9399b2"
_BAR_BG = "#313244"
_BAR_HP = "#f38ba8"
_BAR_STA = "#fab387"

_CARD_STYLE = f"""
    CharacterCard {{
        background: {_CARD_BG};
        border: 1px solid {_CARD_BORDER};
        border-radius: 8px;
    }}
    CharacterCard:hover {{
        border: 1px solid {_CARD_HOVER};
    }}
"""

_KEY_STATS = [
    ("str", "FOR"),
    ("dex", "DEX"),
    ("con", "CON"),
    ("int", "INT"),
    ("wis", "SAG"),
]


class CharacterCard(QFrame):
    """Carte de preview d'un Character."""

    def __init__(self, character: Character, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.character = character

        self.setObjectName("CharacterCard")
        self.setStyleSheet(_CARD_STYLE)
        self.setFixedWidth(280)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self._build_ui()

    def set_character(self, character: Character) -> None:
        self.character = character
        self._build_ui()

    def _build_ui(self) -> None:
        existing = self.layout()
        if existing is None:
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)
        else:
            root = existing
            while root.count():
                item = root.takeAt(0)
                if (w := item.widget()) is not None:
                    w.deleteLater()

        root.addWidget(self._make_header())
        root.addWidget(self._make_vitals_widget())
        root.addWidget(self._make_key_stats_widget())

    def _make_header(self) -> QWidget:
        header = QFrame()
        header.setStyleSheet(
            f"""
            QFrame {{
                background: {_HEADER_BG};
                border: none;
                border-bottom: 1px solid {_HEADER_BORDER};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
            """
        )
        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        name_lbl = QLabel(self.character.name)
        f = QFont()
        f.setBold(True)
        f.setPointSize(10)
        name_lbl.setFont(f)
        name_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        name_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(name_lbl, 1)

        lvl_badge = QLabel(f"Niv.{self.character.stats.lvl}")
        lvl_badge.setStyleSheet(
            "background:#2a3a2a; border:1px solid #50a050; border-radius:4px;"
            "color:#a6e3a1; font-size:9px; font-weight:bold;"
            "padding:1px 5px; font-family:Consolas,monospace;"
        )
        layout.addWidget(lvl_badge)
        return header

    def _make_vitals_widget(self) -> QWidget:
        container = QFrame()
        container.setStyleSheet(
            f"QFrame {{ background:{_SECTION_BG}; border:none; border-bottom:1px solid {_CARD_BORDER}; }}"
        )
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(5)

        hp_cur = int(self.character.hp)
        hp_max = max(1, int(self.character.hp))
        sta_cur = int(self.character.stamina)
        sta_max = 100

        for label, cur, maximum, color in [
            ("PV", hp_cur, hp_max, _BAR_HP),
            ("STA", sta_cur, sta_max, _BAR_STA),
        ]:
            ratio = max(0.0, min(1.0, cur / max(1, maximum)))
            row = QHBoxLayout()
            row.setSpacing(6)

            lbl = QLabel(label)
            lbl.setFixedWidth(26)
            lbl.setStyleSheet(f"color:{_TEXT_SECONDARY}; font-size:9px; background:transparent;")
            row.addWidget(lbl)

            bar_bg = QFrame()
            bar_bg.setFixedHeight(8)
            bar_bg.setStyleSheet(f"background:{_BAR_BG}; border-radius:4px;")
            bar_bg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            bar_inner = QHBoxLayout(bar_bg)
            bar_inner.setContentsMargins(0, 0, 0, 0)
            bar_inner.setSpacing(0)
            fill_stretch = int(ratio * 1000)
            if fill_stretch > 0:
                fill = QFrame()
                fill.setFixedHeight(8)
                fill.setStyleSheet(f"background:{color}; border-radius:4px;")
                fill.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                bar_inner.addWidget(fill, fill_stretch)
            bar_inner.addStretch(max(1, 1000 - fill_stretch))
            row.addWidget(bar_bg)

            val_lbl = QLabel(f"{cur}/{maximum}")
            val_lbl.setFixedWidth(50)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val_lbl.setStyleSheet(
                f"color:{_TEXT_PRIMARY}; font-size:9px; font-family:Consolas,monospace; background:transparent;"
            )
            row.addWidget(val_lbl)
            layout.addLayout(row)

        return container

    def _make_key_stats_widget(self) -> QWidget:
        container = QFrame()
        container.setStyleSheet(f"QFrame {{ background:{_CARD_BG}; border:none; }}")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 7, 8, 9)
        layout.setSpacing(4)

        for stat_key, label in _KEY_STATS:
            total = int(getattr(self.character, stat_key, 0))
            base = int(getattr(self.character.stats, stat_key, 0))

            if total > base:
                val_color = "#a6e3a1"
                border_col = "#40a06a"
            elif total < base:
                val_color = "#f38ba8"
                border_col = "#e06060"
            else:
                val_color = _TEXT_PRIMARY
                border_col = "#45475a"

            badge = QFrame()
            badge.setStyleSheet(
                f"QFrame {{ background:{_SECTION_BG}; border:1px solid {border_col}; border-radius:4px; }}"
            )
            badge.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            b_layout = QVBoxLayout(badge)
            b_layout.setContentsMargins(2, 3, 2, 3)
            b_layout.setSpacing(1)

            lbl_key = QLabel(label)
            lbl_key.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_key.setStyleSheet(f"color:{_TEXT_SECONDARY}; font-size:8px; background:transparent;")
            b_layout.addWidget(lbl_key)

            lbl_val = QLabel(str(total))
            lbl_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_val.setStyleSheet(
                f"color:{val_color}; font-size:11px; font-weight:bold;"
                f"font-family:Consolas,monospace; background:transparent;"
            )
            b_layout.addWidget(lbl_val)

            layout.addWidget(badge)

        return container
