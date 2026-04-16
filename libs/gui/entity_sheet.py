# -*- coding: utf-8 -*-
"""
EntitySheet — fiche complète d'une entité (PJ, PNJ, boss).

Affiche l'objet Entity v2 avec :
  - En-tête : nom de l'entité + badge Niveau
  - Barres vitales : PV / Stamina / Santé mentale / Santé chimique
  - Onglets :
      Stats      — grille avec décomposition Base | MJ | Items | Sorts | Total
      Sorts      — liste compacte de tous les sorts du personnage
      Inventaire — items avec quantité et modificateurs
      Effets     — spell_effects actifs sur l'entité

Signals :
  - cast_requested(spell_key: str)
      Émis quand on clique le bouton "Lancer" sur un sort.
"""

from __future__ import annotations
from uuid import uuid4
from random import randint

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..character import Entity
from ..dice import DiceCheck
from ..item import Item
from ..spells.spell_def import Effect, Formula
from ..spells.spell_effect import SpellEffect
from .item_card import ItemCard
from .spell_card import SpellCard


# ── Palette ──────────────────────────────────────────────────────────────────

_APP_BG           = "#11111b"
_CARD_BG          = "#1e1e2e"
_CARD_BORDER      = "#45475a"
_HEADER_BG        = "#282838"
_HEADER_BORDER    = "#585878"
_SECTION_BG       = "#23233a"

_TEXT_PRIMARY     = "#cdd6f4"
_TEXT_SECONDARY   = "#9399b2"
_TEXT_MUTED       = "#45475a"

# Colonnes du tableau de stats
_COL_BASE         = "#cdd6f4"   # blanc-bleu
_COL_MJ_POS       = "#f9e2af"   # jaune (bonus MJ)
_COL_MJ_NEG       = "#f38ba8"   # rouge (malus MJ)
_COL_ITEM_POS     = "#89b4fa"   # bleu (bonus item)
_COL_ITEM_NEG     = "#f38ba8"   # rouge (malus item)
_COL_SPELL_POS    = "#cba6f7"   # violet (buff sort)
_COL_SPELL_NEG    = "#f38ba8"   # rouge (debuff sort)
_COL_TOTAL_POS    = "#a6e3a1"   # vert si total > base
_COL_TOTAL_NEG    = "#f38ba8"   # rouge si total < base
_COL_TOTAL_NORM   = "#cdd6f4"   # neutre

# Barres vitales
_BAR_BG           = "#313244"
_BAR_HP           = "#f38ba8"   # rouge-rose
_BAR_STA          = "#fab387"   # orange
_BAR_MNT          = "#89dceb"   # cyan
_BAR_DRG          = "#a6e3a1"   # vert
_BAR_MOD_POS      = "#a6e3a1"   # vert bonus
_BAR_MOD_NEG      = "#f38ba8"   # rouge malus

# Sorts
# Bouton (utilisé dans l'en-tête niveau uniquement)
_BTN_BORDER       = "#8060c0"   # violet, accentuation onglet actif


# ── Métadonnées des stats ─────────────────────────────────────────────────────

_STATS_LAYOUT: list[tuple[str, str, str]] = [
    # (clé, étiquette, section)
    ("hp",            "PV",             "Vitaux"),
    ("stamina",       "Stamina",        "Vitaux"),
    ("mental_health", "Santé mentale",  "Vitaux"),
    ("drug_health",   "Santé chimique", "Vitaux"),
    ("str",           "FOR",            "Combat"),
    ("dex",           "DEX",            "Combat"),
    ("con",           "CON",            "Combat"),
    ("int",           "INT",            "Combat"),
    ("wis",           "SAG",            "Combat"),
    ("cha",           "CHA",            "Combat"),
    ("per",           "PER",            "Combat"),
    ("agi",           "AGI",            "Combat"),
    ("luc",           "LUC",            "Divers"),
    ("sur",           "SUR",            "Divers"),
]

_RESOURCE_STATS = {"hp", "stamina", "mental_health", "drug_health"}
_STAT_KEYS = [key for key, _, _ in _STATS_LAYOUT]

# Pour les barres vitales : couleur + valeur max
_VITAL_BARS: list[tuple[str, str, str, int]] = [
    ("hp",            "PV",             _BAR_HP,  None),   # max HP dynamique
    ("stamina",       "STA",            _BAR_STA, 100),
    ("mental_health", "Santé mentale",  _BAR_MNT, 100),
    ("drug_health",   "Santé chimique", _BAR_DRG, 100),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _breakdown(entity: Entity, stat: str) -> tuple[int, int, int, int]:
    """
    Décompose une stat en (base, mj_mod, item_mod, spell_mod).
    - base     : stats.stat (propriété calculée ou champ direct)
    - mj_mod   : stats_modifier.stat (bonus/malus donné par le MJ)
    - item_mod : somme des modificateurs des items de l'inventaire
    - spell_mod: somme des deltas des SpellEffects actifs sur cette stat
    """
    base      = getattr(entity.character.stats,          stat, 0)
    mj_mod    = getattr(entity.character.stats_modifier, stat, 0)
    item_mod  = entity.character.inventory.get_stat_modifier(stat)
    spell_mod = sum(e.delta for e in entity.spell_effects if e.target_stat == stat)
    return base, mj_mod, item_mod, spell_mod


def _mod_label(value: int, pos_color: str, neg_color: str) -> tuple[str, str]:
    """Retourne (texte, couleur) pour un modificateur entier."""
    if value == 0:
        return "—", _TEXT_MUTED
    sign = "+" if value > 0 else ""
    color = pos_color if value > 0 else neg_color
    return f"{sign}{value}", color


def _badge_style(bg: str, border: str, color: str) -> str:
    return (
        f"background:{bg}; border:1px solid {border}; border-radius:3px;"
        f"color:{color}; font-size:10px; font-family:Consolas,monospace;"
        f"padding:1px 6px;"
    )


def _lbl(text: str, color: str = _TEXT_PRIMARY, bold: bool = False,
          size: int = 10, mono: bool = False, align=Qt.AlignmentFlag.AlignLeft) -> QLabel:
    """Crée un QLabel stylisé minimal."""
    w = QLabel(text)
    font_family = "Consolas,monospace" if mono else "inherit"
    weight = "bold" if bold else "normal"
    w.setStyleSheet(
        f"color:{color}; font-size:{size}px; font-weight:{weight};"
        f"font-family:{font_family}; background:transparent;"
    )
    w.setAlignment(align)
    return w


def _lerp_color(start_hex: str, end_hex: str, t: float) -> str:
    """Interpolation linéaire entre 2 couleurs hexadécimales."""
    t = max(0.0, min(1.0, t))
    s = start_hex.lstrip("#")
    e = end_hex.lstrip("#")
    sr, sg, sb = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    er, eg, eb = int(e[0:2], 16), int(e[2:4], 16), int(e[4:6], 16)
    r = int(sr + (er - sr) * t)
    g = int(sg + (eg - sg) * t)
    b = int(sb + (eb - sb) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _base_color_from_ratio(ratio: float) -> str:
    """
    Couleur de stat de base en 4 zones :
    rouge -> jaune -> vert -> bleu.
    """
    ratio = max(0.0, min(1.0, ratio))
    if ratio <= 1 / 3:
        return _lerp_color("#f38ba8", "#f9e2af", ratio / (1 / 3))
    if ratio <= 2 / 3:
        return _lerp_color("#f9e2af", "#a6e3a1", (ratio - 1 / 3) / (1 / 3))
    return _lerp_color("#a6e3a1", "#89b4fa", (ratio - 2 / 3) / (1 / 3))


def _stat_reference(stat_key: str) -> int:
    """Référence d'échelle pour les barres de stats."""
    # Les ressources gardent leur propre échelle.
    if stat_key in {"stamina", "mental_health", "drug_health"}:
        return 100
    if stat_key == "hp":
        return 60
    # Les stats classiques (FOR/DEX/...) sont normalisées sur 300.
    return 300


# ── Widget principal ──────────────────────────────────────────────────────────

class EntitySheet(QFrame):
    """
    Fiche complète d'une entité v2. Peut être embarquée dans n'importe quel layout.
    """

    cast_requested = pyqtSignal(str)   # spell_key

    def __init__(
        self,
        entity: Entity,
        show_cast_buttons: bool = True,
        gm_mode: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.entity = entity
        self.show_cast_buttons = show_cast_buttons
        self.gm_mode = gm_mode
        self._dice_result_by_stat: dict[str, tuple[str, str]] = {}
        self._rolling_stats: set[str] = set()
        self._tab_index: int = 0
        self._tab_scroll_positions: dict[int, tuple[int, int]] = {}

        self.setObjectName("EntitySheet")
        self.setStyleSheet(f"""
            EntitySheet {{
                background: {_CARD_BG};
                border: 1px solid {_CARD_BORDER};
                border-radius: 8px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._build_ui()

    # ── Construction ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        saved_tab_index = self._tab_index
        existing = self.layout()
        if existing is None:
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)
        else:
            for i in range(existing.count()):
                w = existing.itemAt(i).widget()
                if isinstance(w, QTabWidget):
                    saved_tab_index = w.currentIndex()
                    self._capture_tab_scroll_positions(w)
                    break
            root = existing
            while root.count():
                item = root.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        root.addWidget(self._make_header())
        root.addWidget(self._make_vitals())

        tabs = self._make_tabs()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: {_CARD_BG};
            }}
            QTabBar::tab {{
                background: {_HEADER_BG};
                color: {_TEXT_SECONDARY};
                border: 1px solid {_CARD_BORDER};
                border-bottom: none;
                padding: 5px 14px;
                font-size: 11px;
            }}
            QTabBar::tab:selected {{
                background: {_CARD_BG};
                color: {_TEXT_PRIMARY};
                border-bottom: 2px solid {_BTN_BORDER};
            }}
            QTabBar::tab:hover:!selected {{
                color: {_TEXT_PRIMARY};
            }}
        """)
        if tabs.count() > 0:
            tabs.setCurrentIndex(min(saved_tab_index, tabs.count() - 1))
        self._tab_index = tabs.currentIndex()
        tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(tabs)
        QTimer.singleShot(0, lambda t=tabs: self._restore_tab_scroll_positions(t))

    def _capture_tab_scroll_positions(self, tabs: QTabWidget) -> None:
        """Mémorise les positions de scroll de chaque onglet avant reconstruction."""
        positions: dict[int, tuple[int, int]] = {}
        for index in range(tabs.count()):
            widget = tabs.widget(index)
            if isinstance(widget, QScrollArea):
                positions[index] = (
                    int(widget.horizontalScrollBar().value()),
                    int(widget.verticalScrollBar().value()),
                )
        self._tab_scroll_positions = positions

    def _restore_tab_scroll_positions(self, tabs: QTabWidget) -> None:
        """Restaure les positions de scroll après reconstruction de l'UI."""
        for index, (h_value, v_value) in self._tab_scroll_positions.items():
            if index >= tabs.count():
                continue
            widget = tabs.widget(index)
            if isinstance(widget, QScrollArea):
                widget.horizontalScrollBar().setValue(int(h_value))
                widget.verticalScrollBar().setValue(int(v_value))

    def _on_tab_changed(self, index: int) -> None:
        """Mémorise l'onglet actif pour le restaurer après un refresh UI."""
        self._tab_index = index

    def _make_header(self) -> QWidget:
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background: {_HEADER_BG};
                border: none;
                border-bottom: 1px solid {_HEADER_BORDER};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
        """)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        name_lbl = QLabel(self.entity.name)
        f = QFont(); f.setBold(True); f.setPointSize(13)
        name_lbl.setFont(f)
        name_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        layout.addWidget(name_lbl)

        # Nom du perso si différent de l'entité
        char_name = self.entity.character.name
        if char_name != self.entity.name:
            char_lbl = QLabel(f"({char_name})")
            char_lbl.setStyleSheet(f"color:{_TEXT_SECONDARY}; font-size:11px; background:transparent;")
            layout.addWidget(char_lbl)

        layout.addStretch()

        lvl = self.entity.character.stats.lvl
        lvl_badge = QLabel(f"Niv. {lvl}")
        lvl_badge.setStyleSheet(
            f"background:#2a3a2a; border:1px solid #50a050; border-radius:4px;"
            f"color:#a6e3a1; font-size:10px; font-weight:bold;"
            f"padding:2px 8px; font-family:Consolas,monospace;"
        )
        layout.addWidget(lvl_badge)

        if self.gm_mode:
            gm_badge = QLabel("MJ")
            gm_badge.setStyleSheet(
                f"background:#3a1a3a; border:1px solid #c060c0; border-radius:4px;"
                f"color:#e0a0e0; font-size:10px; font-weight:bold;"
                f"padding:2px 8px; font-family:Consolas,monospace; letter-spacing:1px;"
            )
            layout.addWidget(gm_badge)

        return header

    def _make_vitals(self) -> QWidget:
        """Section barres vitales (PV / Stamina / Santé mentale / Santé chimique)."""
        container = QFrame()
        container.setStyleSheet(
            f"QFrame {{ background:{_SECTION_BG}; border:none; border-bottom:1px solid {_CARD_BORDER}; }}"
        )
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(5)

        _HIDDEN_STATS = set() if self.gm_mode else {"mental_health", "drug_health"}
        for stat_key, label, bar_color, fixed_max in _VITAL_BARS:
            if stat_key in _HIDDEN_STATS:
                continue
            base, mj_mod, item_mod, spell_mod = _breakdown(self.entity, stat_key)
            current = base + mj_mod + item_mod + spell_mod
            if fixed_max is not None:
                maximum = fixed_max
            else:
                # Max dynamique = valeur de base + modifs persistantes (hors effets temporaires)
                maximum = base + mj_mod + item_mod
            maximum = max(maximum, 1)

            row = QHBoxLayout()
            row.setSpacing(8)

            # Étiquette
            lbl = _lbl(label, _TEXT_SECONDARY, size=10)
            lbl.setFixedWidth(100)
            row.addWidget(lbl)

            # Barre
            bar_bg = QFrame()
            bar_bg.setFixedHeight(10)
            bar_bg.setStyleSheet(f"background:{_BAR_BG}; border-radius:5px;")
            bar_bg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            bar_inner = QHBoxLayout(bar_bg)
            bar_inner.setContentsMargins(0, 0, 0, 0)
            bar_inner.setSpacing(0)
            ratio = max(0.0, min(1.0, current / maximum))
            fill_stretch = int(ratio * 1000)
            if fill_stretch > 0:
                fill = QFrame()
                fill.setFixedHeight(10)
                fill.setStyleSheet(f"background:{bar_color}; border-radius:5px;")
                fill.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                bar_inner.addWidget(fill, fill_stretch)
            bar_inner.addStretch(max(1, 1000 - fill_stretch))
            row.addWidget(bar_bg)

            # Valeur numérique
            val_color = _TEXT_PRIMARY if current >= base else _COL_TOTAL_NEG
            val_lbl = _lbl(f"{current} / {maximum}", val_color, bold=True, size=10, mono=True)
            val_lbl.setFixedWidth(80)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(val_lbl)

            layout.addLayout(row)

        return container

    def _make_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.addTab(self._make_stats_tab(),     "Stats")
        tabs.addTab(self._make_spells_tab(),    "Sorts")
        tabs.addTab(self._make_inventory_tab(), "Inventaire")
        tabs.addTab(self._make_effects_tab(),   "Effets actifs")
        return tabs

    # ── Onglet Stats ──────────────────────────────────────────────────────────

    def _make_stats_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border:none; background:{_CARD_BG}; }}")

        content = QWidget()
        content.setStyleSheet(f"background:{_CARD_BG};")
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(12, 10, 12, 10)
        vbox.setSpacing(2)

        # En-têtes de colonnes
        vbox.addLayout(self._make_stat_header_row())
        vbox.addWidget(self._hline())

        # Côté joueur : les vitaux sont déjà visibles en haut, on ne les répète pas ici.
        _HIDDEN_STATS = set() if self.gm_mode else set(_RESOURCE_STATS)
        current_section = None
        for stat_key, label, section in _STATS_LAYOUT:
            if stat_key in _HIDDEN_STATS:
                continue
            if section != current_section:
                if current_section is not None:
                    vbox.addWidget(self._hline(light=True))
                vbox.addWidget(self._section_title(section))
                current_section = section
            vbox.addWidget(self._make_stat_row(stat_key, label))

        vbox.addStretch()
        scroll.setWidget(content)
        return scroll

    def _make_stat_header_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(0)
        mj_width = 120 if self.gm_mode else 55
        header_data = [
            ("Stat",    120, _TEXT_SECONDARY, Qt.AlignmentFlag.AlignLeft),
            ("Jet",      92, _TEXT_SECONDARY, Qt.AlignmentFlag.AlignCenter),
            ("Base",     55, _TEXT_SECONDARY, Qt.AlignmentFlag.AlignCenter),
            ("MJ",   mj_width, _COL_MJ_POS,    Qt.AlignmentFlag.AlignCenter),
            ("Items",    55, _COL_ITEM_POS,   Qt.AlignmentFlag.AlignCenter),
            ("Sorts",    55, _COL_SPELL_POS,  Qt.AlignmentFlag.AlignCenter),
            ("Total",    70, _TEXT_PRIMARY,   Qt.AlignmentFlag.AlignRight),
        ]
        for text, width, color, align in header_data:
            lbl = _lbl(text, color, bold=True, size=9, align=align)
            lbl.setFixedWidth(width)
            row.addWidget(lbl)
        row.addStretch()
        return row

    def _on_mj_modifier_changed(self, stat_key: str, value: int) -> None:
        """Met à jour un modifier MJ puis rafraîchit l'UI pour recalculer totaux/barres."""
        setattr(self.entity.character.stats_modifier, stat_key, int(value))
        self._build_ui()

    def _nudge_mj_modifier(self, stat_key: str, delta: int) -> None:
        """Applique un ajustement rapide (+/-) au modificateur MJ."""
        current = int(getattr(self.entity.character.stats_modifier, stat_key, 0))
        setattr(self.entity.character.stats_modifier, stat_key, current + int(delta))
        self._build_ui()

    def _start_stat_dice_roll(self, stat_key: str, result_lbl: QLabel, roll_btn: QPushButton) -> None:
        """Lance une animation courte puis résout un DiceCheck sur la stat."""
        if stat_key in self._rolling_stats:
            return

        self._rolling_stats.add(stat_key)
        roll_btn.setEnabled(False)

        def animate(remaining: int) -> None:
            if stat_key not in self._rolling_stats:
                return

            if remaining > 0:
                try:
                    result_lbl.setText(f"{randint(1, 100):02d}...")
                    result_lbl.setStyleSheet(
                        f"color:{_TEXT_SECONDARY}; font-size:9px; "
                        f"font-family:Consolas,monospace; background:transparent;"
                    )
                except RuntimeError:
                    self._rolling_stats.discard(stat_key)
                    return
                QTimer.singleShot(65, lambda: animate(remaining - 1))
                return

            try:
                check = DiceCheck.resolve(self.entity, stat_key)
                target_value = int(self.entity.get_current_stat(stat_key))
                roll_value = int(check.dice.total)
                ok = bool(check.success)

                if check.dice.critical_failure:
                    txt = f"{roll_value:02d}/{target_value} 💀"
                    color = "#cba6f7"  # violet
                elif check.dice.critical_success:
                    txt = f"{roll_value:02d}/{target_value} !!"
                    color = "#89b4fa"  # bleu
                elif ok:
                    txt = f"{roll_value:02d}/{target_value} !"
                    color = "#a6e3a1"  # vert
                else:
                    txt = f"{roll_value:02d}/{target_value} ❌"
                    color = "#f38ba8"  # rouge

                self._dice_result_by_stat[stat_key] = (txt, color)
                result_lbl.setText(txt)
                result_lbl.setStyleSheet(
                    f"color:{color}; font-size:9px; "
                    f"font-family:Consolas,monospace; background:transparent;"
                )
            except RuntimeError:
                pass
            finally:
                self._rolling_stats.discard(stat_key)
                try:
                    roll_btn.setEnabled(True)
                except RuntimeError:
                    pass

        animate(9)

    def _make_stat_row(self, stat_key: str, label: str) -> QWidget:
        base, mj_mod, item_mod, spell_mod = _breakdown(self.entity, stat_key)
        total = base + mj_mod + item_mod + spell_mod
        mods_total = mj_mod + item_mod + spell_mod
        stat_ref = _stat_reference(stat_key)

        container = QWidget()
        container.setStyleSheet("background:transparent;")
        cbox = QVBoxLayout(container)
        cbox.setContentsMargins(0, 1, 0, 2)
        cbox.setSpacing(2)

        row = QHBoxLayout()
        row.setSpacing(0)
        row.setContentsMargins(0, 0, 0, 0)

        # Étiquette
        name_lbl = _lbl(label, _TEXT_PRIMARY, size=10)
        name_lbl.setFixedWidth(120)
        row.addWidget(name_lbl)

        # Jet de dé (bouton + dernier résultat)
        roll_cell = QWidget()
        roll_cell.setFixedWidth(92)
        roll_cell.setStyleSheet("background:transparent;")
        roll_layout = QHBoxLayout(roll_cell)
        roll_layout.setContentsMargins(0, 0, 0, 0)
        roll_layout.setSpacing(4)

        roll_btn = QPushButton("d100")
        roll_btn.setFixedWidth(34)
        roll_btn.setStyleSheet(
            "QPushButton {"
            "background:#1f2a3f; color:#89b4fa; border:1px solid #4b4b6b;"
            "border-radius:3px; font-size:9px; font-weight:bold; padding:0px;"
            "}"
            "QPushButton:hover { background:#2a3a55; }"
            "QPushButton:disabled { color:#6c7086; background:#1a1b2b; }"
        )

        prev_text, prev_color = self._dice_result_by_stat.get(stat_key, ("--", _TEXT_MUTED))
        result_lbl = QLabel(prev_text)
        result_lbl.setStyleSheet(
            f"color:{prev_color}; font-size:9px; "
            f"font-family:Consolas,monospace; background:transparent;"
        )
        result_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        roll_btn.clicked.connect(lambda checked, s=stat_key: self._start_stat_dice_roll(s, result_lbl, roll_btn))

        roll_layout.addWidget(roll_btn)
        roll_layout.addWidget(result_lbl)
        row.addWidget(roll_cell)

        # Base
        base_lbl = _lbl(str(base), _COL_BASE, mono=True, size=10,
                        align=Qt.AlignmentFlag.AlignCenter)
        base_lbl.setFixedWidth(55)
        row.addWidget(base_lbl)

        # MJ modifier (éditable en mode MJ)
        if self.gm_mode:
            mj_cell = QWidget()
            mj_cell.setFixedWidth(120)
            mj_cell.setStyleSheet("background:transparent;")
            mj_layout = QHBoxLayout(mj_cell)
            mj_layout.setContentsMargins(0, 0, 0, 0)
            mj_layout.setSpacing(4)

            btn_minus = QPushButton("-5")
            btn_minus.setFixedWidth(28)
            btn_minus.setStyleSheet(
                "QPushButton {"
                "background:#3a1e1e; color:#f38ba8; border:1px solid #804040;"
                "border-radius:3px; font-size:9px; font-weight:bold; padding:0px;"
                "}"
                "QPushButton:hover { background:#4a2626; }"
            )
            btn_minus.clicked.connect(lambda checked, s=stat_key: self._nudge_mj_modifier(s, -5))
            mj_layout.addWidget(btn_minus)

            mj_input = QSpinBox()
            mj_input.setRange(-999, 999)
            mj_input.setValue(int(mj_mod))
            mj_input.setFixedWidth(56)
            mj_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            mj_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
            mj_input.setStyleSheet(
                "QSpinBox {"
                f"background:#1a1a2f; color:{_COL_MJ_POS}; border:1px solid {_CARD_BORDER};"
                "border-radius:3px; font-family:Consolas,monospace; font-size:10px;"
                "padding:1px 2px;"
                "}"
                "QSpinBox:focus { border:1px solid #f9e2af; }"
            )
            mj_input.valueChanged.connect(
                lambda value, s=stat_key: self._on_mj_modifier_changed(s, value)
            )
            mj_layout.addWidget(mj_input)

            btn_plus = QPushButton("+5")
            btn_plus.setFixedWidth(28)
            btn_plus.setStyleSheet(
                "QPushButton {"
                "background:#1e3a2f; color:#a6e3a1; border:1px solid #40804a;"
                "border-radius:3px; font-size:9px; font-weight:bold; padding:0px;"
                "}"
                "QPushButton:hover { background:#264a3a; }"
            )
            btn_plus.clicked.connect(lambda checked, s=stat_key: self._nudge_mj_modifier(s, +5))
            mj_layout.addWidget(btn_plus)

            row.addWidget(mj_cell)
        else:
            mj_txt, mj_col = _mod_label(mj_mod, _COL_MJ_POS, _COL_MJ_NEG)
            mj_lbl = _lbl(mj_txt, mj_col, mono=True, size=10,
                          align=Qt.AlignmentFlag.AlignCenter)
            mj_lbl.setFixedWidth(55)
            row.addWidget(mj_lbl)

        # Item modifier
        it_txt, it_col = _mod_label(item_mod, _COL_ITEM_POS, _COL_ITEM_NEG)
        it_lbl = _lbl(it_txt, it_col, mono=True, size=10,
                      align=Qt.AlignmentFlag.AlignCenter)
        it_lbl.setFixedWidth(55)
        row.addWidget(it_lbl)

        # Spell modifier
        sp_txt, sp_col = _mod_label(spell_mod, _COL_SPELL_POS, _COL_SPELL_NEG)
        sp_lbl = _lbl(sp_txt, sp_col, mono=True, size=10,
                      align=Qt.AlignmentFlag.AlignCenter)
        sp_lbl.setFixedWidth(55)
        row.addWidget(sp_lbl)

        # Total
        all_mods = mj_mod + item_mod + spell_mod
        if all_mods > 0:
            total_color = _COL_TOTAL_POS
        elif all_mods < 0:
            total_color = _COL_TOTAL_NEG
        else:
            total_color = _COL_TOTAL_NORM
        total_lbl = _lbl(str(total), total_color, bold=True, mono=True, size=11,
                         align=Qt.AlignmentFlag.AlignRight)
        total_lbl.setFixedWidth(70)
        row.addWidget(total_lbl)

        row.addStretch()
        cbox.addLayout(row)

        # Barre unique segmentée:
        # [stat modifiée] [malus] [reste]  (et bonus en vert si total > base)
        bar_row = QHBoxLayout()
        bar_row.setContentsMargins(120, 0, 8, 0)
        bar_row.setSpacing(8)

        bar_bg = QFrame()
        bar_bg.setFixedHeight(8)
        bar_bg.setStyleSheet(f"background:{_BAR_BG}; border-radius:4px;")
        bar_bg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bar_inner = QHBoxLayout(bar_bg)
        bar_inner.setContentsMargins(0, 0, 0, 0)
        bar_inner.setSpacing(0)

        base_clamped = max(0.0, min(float(stat_ref), float(base)))
        total_clamped = max(0.0, min(float(stat_ref), float(total)))

        if total_clamped >= base_clamped:
            # Base pleine + bonus à droite
            stat_part = base_clamped
            malus_part = 0.0
            bonus_part = total_clamped - base_clamped
        else:
            # Stat modifiée + malus rouge à droite dans la même barre
            stat_part = total_clamped
            malus_part = base_clamped - total_clamped
            bonus_part = 0.0

        stat_stretch = int((stat_part / max(1, stat_ref)) * 1000)
        malus_stretch = int((malus_part / max(1, stat_ref)) * 1000)
        bonus_stretch = int((bonus_part / max(1, stat_ref)) * 1000)

        if stat_stretch > 0:
            stat_fill = QFrame()
            stat_fill.setFixedHeight(8)
            stat_fill.setStyleSheet(
                f"background:{_base_color_from_ratio(max(0.0, min(1.0, base / max(1, stat_ref))))};"
                "border-top-left-radius:4px; border-bottom-left-radius:4px;"
            )
            stat_fill.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            bar_inner.addWidget(stat_fill, stat_stretch)

        if malus_stretch > 0:
            malus_fill = QFrame()
            malus_fill.setFixedHeight(8)
            malus_fill.setStyleSheet(f"background:{_BAR_MOD_NEG};")
            malus_fill.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            bar_inner.addWidget(malus_fill, malus_stretch)

        if bonus_stretch > 0:
            bonus_fill = QFrame()
            bonus_fill.setFixedHeight(8)
            bonus_fill.setStyleSheet(f"background:{_BAR_MOD_POS};")
            bonus_fill.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            bar_inner.addWidget(bonus_fill, bonus_stretch)

        used = stat_stretch + malus_stretch + bonus_stretch
        bar_inner.addStretch(max(1, 1000 - used))
        bar_row.addWidget(bar_bg)

        legend_text = f"stat:{total}"
        legend_color = _TEXT_PRIMARY
        legend_lbl = _lbl(legend_text, legend_color, mono=True, size=9, align=Qt.AlignmentFlag.AlignRight)
        legend_lbl.setFixedWidth(130)
        bar_row.addWidget(legend_lbl)
        cbox.addLayout(bar_row)

        mods_text = f"mods:{mods_total:+d}"
        mods_color = _TEXT_SECONDARY if mods_total == 0 else (_BAR_MOD_POS if mods_total > 0 else _BAR_MOD_NEG)
        mods_row = QHBoxLayout()
        mods_row.setContentsMargins(120, 0, 8, 0)
        mods_row.setSpacing(8)
        mods_row.addStretch()
        mods_lbl = _lbl(mods_text, mods_color, mono=True, size=9, align=Qt.AlignmentFlag.AlignRight)
        mods_lbl.setFixedWidth(130)
        mods_row.addWidget(mods_lbl)
        cbox.addLayout(mods_row)
        return container

    # ── Onglet Sorts ──────────────────────────────────────────────────────────

    def _make_spells_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border:none; background:{_CARD_BG}; }}")

        content = QWidget()
        content.setStyleSheet(f"background:{_CARD_BG};")
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(12, 10, 12, 10)
        vbox.setSpacing(6)

        spells = self.entity.character.spells
        if not spells:
            vbox.addWidget(_lbl("Aucun sort connu.", _TEXT_SECONDARY))
        else:
            for spell_key, spell in spells.items():
                card = SpellCard(spell, spell_key, enable_cast=self.show_cast_buttons)
                card.cast_requested.connect(self.cast_requested)
                vbox.addWidget(card)

        vbox.addStretch()
        scroll.setWidget(content)
        return scroll


    # ── Onglet Inventaire ─────────────────────────────────────────────────────

    def _on_item_quantity_changed(self, item_name: str, new_qty: int) -> None:
        """Mise à jour de l'inventaire local quand la quantité change."""
        if new_qty <= 0:
            self.entity.character.inventory.items.pop(item_name, None)
            self.entity.character.inventory._item_cache.pop(item_name, None)
        else:
            self.entity.character.inventory.items[item_name] = new_qty
        # Rafraîchir l'UI pour recalculer les stats (items modifient les stats !)
        self._build_ui()

    # ── Onglet Inventaire ─────────────────────────────────────────────────────

    def _make_inventory_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border:none; background:{_CARD_BG}; }}")

        content = QWidget()
        content.setStyleSheet(f"background:{_CARD_BG};")
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(12, 10, 12, 10)
        vbox.setSpacing(8)

        items = self.entity.character.inventory.items
        if not items:
            vbox.addWidget(_lbl("Inventaire vide.", _TEXT_SECONDARY))
        else:
            for item_name, qty in items.items():
                item_obj = Item.from_name(item_name)
                if item_obj is None:
                    vbox.addWidget(_lbl(f"⚠ {item_name} (introuvable)", "#f38ba8", size=10))
                    continue
                card = ItemCard(
                    item_obj,
                    item_name,
                    quantity=qty,
                    allow_quantity_edit=self.gm_mode,
                )
                card.quantity_changed.connect(self._on_item_quantity_changed)
                vbox.addWidget(card)

        vbox.addStretch()
        scroll.setWidget(content)
        return scroll


    # ── Onglet Effets actifs ──────────────────────────────────────────────────

    def _make_effects_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border:none; background:{_CARD_BG}; }}")

        content = QWidget()
        content.setStyleSheet(f"background:{_CARD_BG};")
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(12, 10, 12, 10)
        vbox.setSpacing(6)

        if self.gm_mode:
            vbox.addWidget(self._section_title("Ajout manuel d'effet"))
            vbox.addWidget(self._make_effect_editor())
            vbox.addWidget(self._hline(light=True))

        vbox.addWidget(self._section_title("SpellEffects actifs"))

        effects = [e for e in self.entity.spell_effects if e.target_id == self.entity.name]
        if not effects:
            vbox.addWidget(_lbl("Aucun effet actif.", _TEXT_SECONDARY))
        else:
            for effect in effects:
                vbox.addWidget(self._make_effect_row(effect))

        vbox.addWidget(self._hline(light=True))
        vbox.addWidget(self._section_title("SpellEvents en cours"))

        events = [ev for ev in self.entity.spell_events if not ev.finished]
        if not events:
            vbox.addWidget(_lbl("Aucun event actif.", _TEXT_SECONDARY))
        else:
            for idx, event in enumerate(events):
                vbox.addWidget(self._make_event_row(event, idx))

        vbox.addStretch()
        scroll.setWidget(content)
        return scroll

    def _make_effect_editor(self) -> QFrame:
        """Petit panneau MJ pour ajouter manuellement un SpellEffect."""
        box = QFrame()
        box.setStyleSheet(
            f"QFrame {{ background:{_HEADER_BG}; border:1px solid {_CARD_BORDER}; border-radius:5px; }}"
        )
        layout = QHBoxLayout(box)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        stat_combo = QComboBox()
        stat_combo.addItems(_STAT_KEYS)
        stat_combo.setCurrentText("str")
        stat_combo.setStyleSheet(
            f"QComboBox {{ background:#1a1a2f; color:{_TEXT_PRIMARY}; border:1px solid {_CARD_BORDER};"
            "border-radius:3px; padding:2px 6px; font-size:10px; }"
        )
        layout.addWidget(stat_combo)

        delta_input = QSpinBox()
        delta_input.setRange(-999, 999)
        delta_input.setValue(10)
        delta_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        delta_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        delta_input.setFixedWidth(62)
        delta_input.setStyleSheet(
            f"QSpinBox {{ background:#1a1a2f; color:{_TEXT_PRIMARY}; border:1px solid {_CARD_BORDER};"
            "border-radius:3px; font-family:Consolas,monospace; font-size:10px; padding:1px 2px; }"
        )
        layout.addWidget(delta_input)

        source_input = QLineEdit("MJ Manual")
        source_input.setStyleSheet(
            f"QLineEdit {{ background:#1a1a2f; color:{_TEXT_PRIMARY}; border:1px solid {_CARD_BORDER};"
            "border-radius:3px; padding:2px 6px; font-size:10px; }"
        )
        source_input.setPlaceholderText("source spell/event")
        layout.addWidget(source_input)

        add_btn = QPushButton("Ajouter")
        add_btn.setStyleSheet(
            "QPushButton {"
            "background:#1e3a2f; color:#a6e3a1; border:1px solid #40804a;"
            "border-radius:3px; font-size:10px; font-weight:bold; padding:2px 8px;"
            "}"
            "QPushButton:hover { background:#264a3a; }"
        )
        add_btn.clicked.connect(
            lambda checked: self._on_add_manual_effect(
                stat_combo.currentText(),
                int(delta_input.value()),
                source_input.text().strip() or "MJ Manual",
            )
        )
        layout.addWidget(add_btn)
        return box

    def _on_add_manual_effect(self, stat_key: str, delta: int, source_name: str) -> None:
        """Ajoute un SpellEffect manuel (sans créer de SpellEvent)."""
        formula = Formula(str(abs(delta)))
        formula.compilate()
        operator = "bonus" if delta >= 0 else "malus"
        effect_def = Effect(target=("target", stat_key), operator=operator, formula=formula)
        spell_effect = SpellEffect(
            uuid=uuid4(),
            effect_def=effect_def,
            target_id=self.entity.name,
            target_stat=stat_key,
            delta=delta,
            link_key=(source_name, self.entity.name),
        )
        self.entity.spell_effects.append(spell_effect)
        self._build_ui()

    def _on_remove_effect(self, effect_uuid: str) -> None:
        """Retire un SpellEffect de l'entité + des events qui le référencent."""
        self.entity.spell_effects = [e for e in self.entity.spell_effects if str(e.uuid) != effect_uuid]
        for event in self.entity.spell_events:
            event.effects = [e for e in event.effects if str(e.uuid) != effect_uuid]
        self._build_ui()

    def _on_remove_event(self, event_index: int) -> None:
        """Retire un SpellEvent actif et purge localement ses effets de l'entité affichée."""
        active_events = [ev for ev in self.entity.spell_events if not ev.finished]
        if event_index < 0 or event_index >= len(active_events):
            return
        event = active_events[event_index]
        event_effect_ids = {str(e.uuid) for e in event.effects}
        self.entity.spell_effects = [
            e for e in self.entity.spell_effects if str(e.uuid) not in event_effect_ids
        ]
        try:
            self.entity.spell_events.remove(event)
        except ValueError:
            pass
        self._build_ui()

    def _make_effect_row(self, effect) -> QFrame:
        is_pos = effect.delta >= 0
        bg     = "#1e2a1e" if is_pos else "#2a1e1e"
        border = "#40804a" if is_pos else "#804040"
        color  = "#a6e3a1" if is_pos else "#f38ba8"
        sign   = "+" if is_pos else ""

        row = QFrame()
        row.setStyleSheet(
            f"QFrame {{ background:{bg}; border:1px solid {border}; border-radius:4px; }}"
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        # Stat affectée
        stat_lbl = _lbl(effect.target_stat.upper(), _TEXT_PRIMARY, bold=True, size=11, mono=True)
        layout.addWidget(stat_lbl)

        # Delta
        delta_lbl = _lbl(f"{sign}{effect.delta}", color, bold=True, size=13, mono=True)
        layout.addWidget(delta_lbl)

        layout.addStretch()

        # Lien vers le sort (link_key = (spell_id, caster_id))
        if effect.link_key:
            spell_id  = effect.link_key[0] if isinstance(effect.link_key, tuple) else str(effect.link_key)
            source_lbl = _lbl(f"← {spell_id}", _TEXT_SECONDARY, size=9, mono=True)
            layout.addWidget(source_lbl)

        if self.gm_mode:
            remove_btn = QPushButton("Retirer")
            remove_btn.setStyleSheet(
                "QPushButton {"
                "background:#3a1e1e; color:#f38ba8; border:1px solid #804040;"
                "border-radius:3px; font-size:9px; font-weight:bold; padding:1px 6px;"
                "}"
                "QPushButton:hover { background:#4a2626; }"
            )
            remove_btn.clicked.connect(lambda checked, u=str(effect.uuid): self._on_remove_effect(u))
            layout.addWidget(remove_btn)

        return row

    def _make_event_row(self, event, event_index: int) -> QFrame:
        """Ligne de tracking d'un SpellEvent actif."""
        row = QFrame()
        row.setStyleSheet(
            f"QFrame {{ background:{_HEADER_BG}; border:1px solid {_CARD_BORDER}; border-radius:4px; }}"
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        title = _lbl(event.spell_id, _TEXT_PRIMARY, bold=True, size=10)
        layout.addWidget(title)
        layout.addStretch()

        infos = _lbl(
            f"policy:{event.runtime_policy}  cast:{event.nb_cast}  targets:{len(event.targets_ids)}",
            _TEXT_SECONDARY,
            mono=True,
            size=9,
        )
        layout.addWidget(infos)

        if self.gm_mode:
            rm_btn = QPushButton("Retirer event")
            rm_btn.setStyleSheet(
                "QPushButton {"
                "background:#3a1e1e; color:#f38ba8; border:1px solid #804040;"
                "border-radius:3px; font-size:9px; font-weight:bold; padding:1px 6px;"
                "}"
                "QPushButton:hover { background:#4a2626; }"
            )
            rm_btn.clicked.connect(lambda checked, i=event_index: self._on_remove_event(i))
            layout.addWidget(rm_btn)

        return row

    # ── Helpers UI ────────────────────────────────────────────────────────────

    def _hline(self, light: bool = False) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        color = _CARD_BORDER if not light else "#2e2e4a"
        line.setStyleSheet(f"border:none; border-top:1px solid {color}; background:transparent;")
        line.setFixedHeight(1)
        return line

    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"color:{_TEXT_SECONDARY}; font-size:9px; font-weight:bold; letter-spacing:1px;"
            f"background:transparent; padding-top:4px;"
        )
        return lbl

    # ── API publique ──────────────────────────────────────────────────────────

    def simulate_spell_effect(
        self,
        target_stat: str,
        delta: int,
        spell_name: str = "Simulation",
        caster_id: str = "MJ",
    ) -> None:
        """
        Simule un effet de sort sur l'entité affichée.
        Ajoute un SpellEffect puis reconstruit la feuille.
        """
        formula = Formula(str(abs(delta)))
        formula.compilate()
        operator = "bonus" if delta >= 0 else "malus"
        effect_def = Effect(target=("target", target_stat), operator=operator, formula=formula)
        effect = SpellEffect(
            uuid=uuid4(),
            effect_def=effect_def,
            target_id=self.entity.name,
            target_stat=target_stat,
            delta=delta,
            link_key=(spell_name, caster_id),
        )
        self.entity.spell_effects.append(effect)
        self.set_entity(self.entity)

    def set_entity(self, entity: Entity) -> None:
        """Remplace l'entité affichée (recrée l'UI complète)."""
        self.entity = entity
        self._build_ui()

    def set_active_tab(self, index: int) -> None:
        """Change l'onglet actif (0-based) et rafraîchit la vue."""
        self._tab_index = max(0, int(index))
        self._build_ui()
