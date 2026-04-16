# -*- coding: utf-8 -*-
"""
ItemCard — widget PyQt6 représentant un item de l'inventaire.

Affiche :
  - Nom de l'item (bold)
  - Contrôle de quantité : [−] [n] [+]
  - Description (texte wrappé)
  - Modificateurs de stats (badges colorés vert/rouge)

Signals :
  - quantity_changed(item_name: str, new_qty: int)
      Émis à chaque modification de quantité.
      Si new_qty == 0, l'item peut être retiré de l'inventaire par le parent.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from ..item import Item


# ── Palette (cohérente avec le thème sombre de l'app v1) ───────────────────

_CARD_BG         = "#282838"
_CARD_BORDER     = "#4b4b6b"
_TEXT_PRIMARY    = "#cdd6f4"   # blanc-bleu clair
_TEXT_SECONDARY  = "#9399b2"   # gris-bleu
_MOD_POS_BG      = "#1e3a2f"
_MOD_POS_BORDER  = "#40a06a"
_MOD_POS_TEXT    = "#a6e3a1"   # vert Catppuccin
_MOD_NEG_BG      = "#3a1e1e"
_MOD_NEG_BORDER  = "#e06060"
_MOD_NEG_TEXT    = "#f38ba8"   # rouge Catppuccin
_BTN_MINUS_BG    = "#5a2828"
_BTN_MINUS_HOVER = "#7a3838"
_BTN_PLUS_BG     = "#285a28"
_BTN_PLUS_HOVER  = "#387a38"
_BTN_TEXT_MINUS  = "#f38ba8"
_BTN_TEXT_PLUS   = "#a6e3a1"
_QTY_BG          = "#111118"
_QTY_BORDER      = "#55556a"
_QTY_TEXT        = "#cdd6f4"


# ── Feuille de style globale de la carte ───────────────────────────────────

_CARD_STYLE = f"""
    ItemCard {{
        background: {_CARD_BG};
        border: 1px solid {_CARD_BORDER};
        border-radius: 6px;
    }}
"""

_MOD_STYLE_POS = f"""
    QLabel {{
        background: {_MOD_POS_BG};
        border: 1px solid {_MOD_POS_BORDER};
        border-radius: 3px;
        color: {_MOD_POS_TEXT};
        padding: 1px 6px;
        font-family: Consolas, monospace;
        font-size: 11px;
    }}
"""

_MOD_STYLE_NEG = f"""
    QLabel {{
        background: {_MOD_NEG_BG};
        border: 1px solid {_MOD_NEG_BORDER};
        border-radius: 3px;
        color: {_MOD_NEG_TEXT};
        padding: 1px 6px;
        font-family: Consolas, monospace;
        font-size: 11px;
    }}
"""

_QTY_BTN_BASE = """
    QPushButton {{
        background: {bg};
        color: {fg};
        border: 1px solid {border};
        border-radius: 3px;
        font-weight: bold;
        font-size: 14px;
        min-width: 24px;
        max-width: 24px;
        min-height: 24px;
        max-height: 24px;
        padding: 0;
    }}
    QPushButton:hover {{ background: {hover}; }}
"""


class ItemCard(QFrame):
    """
    Carte d'item PyQt6 — équivalent de ItemCardWidget (Pygame).
    """

    quantity_changed = pyqtSignal(str, int)   # (item_name, new_quantity)

    def __init__(
        self,
        item: Item,
        item_name: str,
        quantity: int = 1,
        allow_quantity_edit: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.item = item
        self.item_name = item_name
        self._quantity = quantity
        self.allow_quantity_edit = allow_quantity_edit

        self.setObjectName("ItemCard")
        self.setStyleSheet(_CARD_STYLE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self._build_ui()

    # ── Construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(6)

        root.addLayout(self._make_header())
        root.addWidget(self._make_description())

        mods_widget = self._make_modifiers()
        if mods_widget:
            root.addWidget(mods_widget)

    def _make_header(self) -> QHBoxLayout:
        """Ligne : [Nom du item] ←spacer→ ([−] [qty] [+] | [qty])."""
        layout = QHBoxLayout()
        layout.setSpacing(4)

        # Nom
        name_label = QLabel(self.item.name)
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(11)
        name_label.setFont(name_font)
        name_label.setStyleSheet(f"color: {_TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(name_label)

        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding))

        if self.allow_quantity_edit:
            # Bouton −
            self._btn_minus = QPushButton("−")
            self._btn_minus.setStyleSheet(_QTY_BTN_BASE.format(
                bg=_BTN_MINUS_BG, hover=_BTN_MINUS_HOVER,
                fg=_BTN_TEXT_MINUS, border=_MOD_NEG_BORDER,
            ))
            self._btn_minus.clicked.connect(self._on_minus)
            layout.addWidget(self._btn_minus)

        # Quantité
        self._qty_label = QLabel(str(self._quantity))
        self._qty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qty_label.setFixedWidth(36 if self.allow_quantity_edit else 44)
        self._qty_label.setStyleSheet(
            f"background: {_QTY_BG}; border: 1px solid {_QTY_BORDER}; "
            f"border-radius: 3px; color: {_QTY_TEXT}; "
            f"font-family: Consolas, monospace; font-size: 13px;"
        )
        layout.addWidget(self._qty_label)

        if self.allow_quantity_edit:
            # Bouton +
            self._btn_plus = QPushButton("+")
            self._btn_plus.setStyleSheet(_QTY_BTN_BASE.format(
                bg=_BTN_PLUS_BG, hover=_BTN_PLUS_HOVER,
                fg=_BTN_TEXT_PLUS, border=_MOD_POS_BORDER,
            ))
            self._btn_plus.clicked.connect(self._on_plus)
            layout.addWidget(self._btn_plus)

        return layout

    def _make_description(self) -> QLabel:
        """Description texte, wrappée automatiquement."""
        label = QLabel(self.item.description or "—")
        label.setWordWrap(True)
        label.setStyleSheet(
            f"color: {_TEXT_SECONDARY}; background: transparent; font-size: 11px;"
        )
        return label

    def _make_modifiers(self) -> QWidget | None:
        """Badge de modificateurs de stats. Retourne None si l'item n'en a pas."""
        if not self.item.modifier:
            return None

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        for stat_name, value in self.item.modifier:
            sign = "+" if value >= 0 else ""
            text = f"{stat_name.upper()} {sign}{value}"
            badge = QLabel(text)
            badge.setStyleSheet(_MOD_STYLE_POS if value >= 0 else _MOD_STYLE_NEG)
            layout.addWidget(badge)

        layout.addStretch()
        return container

    # ── Logique quantité ────────────────────────────────────────────────────

    @property
    def quantity(self) -> int:
        return self._quantity

    def set_quantity(self, qty: int) -> None:
        """Met à jour la quantité affichée sans émettre de signal."""
        self._quantity = max(0, qty)
        self._qty_label.setText(str(self._quantity))

    def set_item(self, item: Item, item_name: str, quantity: int = 1) -> None:
        """Remplace l'item affiché (recrée l'UI)."""
        self.item = item
        self.item_name = item_name
        self._quantity = quantity

        # Vide et reconstruit
        old_layout = self.layout()
        if old_layout:
            while old_layout.count():
                child = old_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        self._build_ui()

    def _on_minus(self) -> None:
        new_qty = max(0, self._quantity - 1)
        self._quantity = new_qty
        self._qty_label.setText(str(new_qty))
        self.quantity_changed.emit(self.item_name, new_qty)

    def _on_plus(self) -> None:
        self._quantity += 1
        self._qty_label.setText(str(self._quantity))
        self.quantity_changed.emit(self.item_name, self._quantity)
