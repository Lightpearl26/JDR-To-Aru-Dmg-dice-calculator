# -*- coding: utf-8 -*-
"""
EntityCard - carte miniature d'une entite (PJ, PNJ, boss).

Affiche de facon compacte :
  - Nom + badge Niveau (+ badge MJ si gm_mode)
  - Barres vitales : PV et Stamina
  - Badges des 5 stats de combat principales

Double-clic -> ouvre la fiche complete (EntitySheet) dans un QDialog modale.

Signals :
  - double_clicked()
      Emis juste avant l'ouverture de la fiche complete.
  - sheet_closed()
      Emis quand la fiche est fermee (la carte se rafraichit automatiquement).
  - unload_requested(entity_name)
      Emis quand le bouton de dechargement est clique (mode MJ).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..character import Entity
from .entity_sheet import EntitySheet, _breakdown


# -- Palette (coherente avec entity_sheet) ------------------------------------

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
    EntityCard {{
        background: {_CARD_BG};
        border: 1px solid {_CARD_BORDER};
        border-radius: 8px;
    }}
    EntityCard:hover {{
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


# -- EntityCard ----------------------------------------------------------------

class EntityCard(QFrame):
    """
    Carte miniature pour une entite. Double-clic -> fiche complete.
    """

    double_clicked = pyqtSignal()
    sheet_closed = pyqtSignal()
    unload_requested = pyqtSignal(str)

    def __init__(
        self,
        entity: Entity,
        gm_mode: bool = False,
        show_cast_buttons: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.entity = entity
        self.gm_mode = gm_mode
        self.show_cast_buttons = show_cast_buttons

        self.setObjectName("EntityCard")
        self.setStyleSheet(_CARD_STYLE)
        self.setFixedWidth(240)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self._build_ui()

    # -- Construction ----------------------------------------------------------

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

        name_lbl = QLabel(self.entity.name)
        f = QFont()
        f.setBold(True)
        f.setPointSize(10)
        name_lbl.setFont(f)
        name_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        name_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        name_lbl.setWordWrap(False)
        layout.addWidget(name_lbl, 1)

        lvl = self.entity.character.stats.lvl
        lvl_badge = QLabel(f"Niv.{lvl}")
        lvl_badge.setStyleSheet(
            "background:#2a3a2a; border:1px solid #50a050; border-radius:4px;"
            "color:#a6e3a1; font-size:9px; font-weight:bold;"
            "padding:1px 5px; font-family:Consolas,monospace;"
        )
        layout.addWidget(lvl_badge)

        if self.gm_mode:
            gm_badge = QLabel("MJ")
            gm_badge.setStyleSheet(
                "background:#3a1a3a; border:1px solid #c060c0; border-radius:4px;"
                "color:#e0a0e0; font-size:9px; font-weight:bold;"
                "padding:1px 5px; font-family:Consolas,monospace;"
            )
            layout.addWidget(gm_badge)

            unload_btn = QPushButton("x")
            unload_btn.setFixedSize(18, 18)
            unload_btn.setToolTip("Decharger cette entite")
            unload_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            unload_btn.setStyleSheet(
                "QPushButton {"
                "background:#3a2a2a; border:1px solid #a05050; border-radius:4px;"
                "color:#f38ba8; font-weight:bold; font-size:10px;"
                "padding:0px;"
                "}"
                "QPushButton:hover { background:#4a3a3a; }"
            )
            unload_btn.clicked.connect(
                lambda _=False: self.unload_requested.emit(str(self.entity.name))
            )
            layout.addWidget(unload_btn)

        return header

    def _make_vitals_widget(self) -> QWidget:
        container = QFrame()
        container.setStyleSheet(
            f"QFrame {{ background:{_SECTION_BG}; border:none; border-bottom:1px solid {_CARD_BORDER}; }}"
        )
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(5)

        for stat_key, label, bar_color in [
            ("hp", "PV", _BAR_HP),
            ("stamina", "STA", _BAR_STA),
        ]:
            base, mj_mod, item_mod, spell_mod = _breakdown(self.entity, stat_key)
            current = base + mj_mod + item_mod + spell_mod
            maximum = (base + mj_mod + item_mod) if stat_key == "hp" else 100
            maximum = max(maximum, 1)
            ratio = max(0.0, min(1.0, current / maximum))

            row = QHBoxLayout()
            row.setSpacing(6)

            lbl = QLabel(label)
            lbl.setFixedWidth(26)
            lbl.setStyleSheet(
                f"color:{_TEXT_SECONDARY}; font-size:9px; background:transparent;"
            )
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
                fill.setStyleSheet(f"background:{bar_color}; border-radius:4px;")
                fill.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                bar_inner.addWidget(fill, fill_stretch)
            bar_inner.addStretch(max(1, 1000 - fill_stretch))
            row.addWidget(bar_bg)

            val_color = _TEXT_PRIMARY if current >= (base + mj_mod + item_mod) else "#f38ba8"
            val_lbl = QLabel(f"{current}/{maximum}")
            val_lbl.setFixedWidth(50)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val_lbl.setStyleSheet(
                f"color:{val_color}; font-size:9px; font-family:Consolas,monospace; background:transparent;"
            )
            row.addWidget(val_lbl)

            layout.addLayout(row)

        return container

    def _make_key_stats_widget(self) -> QWidget:
        """Rangee de 5 badges compacts (FOR/DEX/CON/INT/SAG)."""
        container = QFrame()
        container.setStyleSheet(f"QFrame {{ background:{_CARD_BG}; border:none; }}")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 7, 8, 9)
        layout.setSpacing(4)

        for stat_key, label in _KEY_STATS:
            base, mj_mod, item_mod, spell_mod = _breakdown(self.entity, stat_key)
            total = base + mj_mod + item_mod + spell_mod

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
            lbl_key.setStyleSheet(
                f"color:{_TEXT_SECONDARY}; font-size:8px; background:transparent;"
            )
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

    # -- Evenements ------------------------------------------------------------

    def mouseDoubleClickEvent(self, event) -> None:
        self.double_clicked.emit()
        dialog = _EntitySheetDialog(
            entity=self.entity,
            gm_mode=self.gm_mode,
            show_cast_buttons=self.show_cast_buttons,
            parent=self,
        )
        dialog.exec()
        self._build_ui()
        self.sheet_closed.emit()
        super().mouseDoubleClickEvent(event)

    # -- API publique ----------------------------------------------------------

    def refresh(self) -> None:
        """Reconstruit la carte (ex. apres un changement d'etat exterieur)."""
        self._build_ui()


# -- Dialog fiche complete -----------------------------------------------------

class _EntitySheetDialog(QDialog):
    """Boite de dialogue modale qui embarque une EntitySheet complete."""

    def __init__(
        self,
        entity: Entity,
        gm_mode: bool = False,
        show_cast_buttons: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(entity.name)
        self.setModal(True)
        self.setMinimumSize(820, 660)
        self.resize(900, 740)
        self.setStyleSheet("QDialog { background: #11111b; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self._sheet = EntitySheet(
            entity,
            show_cast_buttons=show_cast_buttons,
            gm_mode=gm_mode,
        )
        self._sheet.cast_requested.connect(
            lambda key: print(f"[EntityCard] cast_requested -> {key}")
        )
        layout.addWidget(self._sheet)
