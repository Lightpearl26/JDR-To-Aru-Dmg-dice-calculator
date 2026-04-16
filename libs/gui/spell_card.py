# -*- coding: utf-8 -*-
"""
SpellCard — widget PyQt6 représentant un sort.

Affiche :
  - En-tête : Nom | [targeting badge] [policy badge]
  - Coût en stamina (barre + valeur numérique)
  - Description
  - Effets détaillés : cible • stat • opérateur • formule (un effet par ligne)
  - Bouton "Lancer" (désactivable si pas de proprio ou sort passif)

Signals :
  - cast_requested(spell_key: str)
      Émis quand le joueur clique "Lancer".
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
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

from ..spells.spell_def import Spell, Effect, Operator


# ── Palette ─────────────────────────────────────────────────────────────────

_CARD_BG          = "#1e1e2e"
_CARD_BORDER      = "#45475a"

# En-tête (fond légèrement plus clair)
_HEADER_BG        = "#282838"
_HEADER_BORDER    = "#585878"

# Textes
_TEXT_PRIMARY     = "#cdd6f4"
_TEXT_SECONDARY   = "#9399b2"
_TEXT_COST        = "#fab387"   # orange

# Badges targeting / policy
_BADGE_SINGLE_BG     = "#2a2a4a"
_BADGE_SINGLE_BORDER = "#7070c0"
_BADGE_SINGLE_TEXT   = "#b4b4f4"
_BADGE_MULTI_BG      = "#2a1a3a"
_BADGE_MULTI_BORDER  = "#c070d0"
_BADGE_MULTI_TEXT    = "#d4a4f4"

_BADGE_INSTANT_BG     = "#1a2a1a"
_BADGE_INSTANT_BORDER = "#50a050"
_BADGE_INSTANT_TEXT   = "#a4d4a4"
_BADGE_MAINTAIN_BG    = "#2a2a1a"
_BADGE_MAINTAIN_BORDER= "#a0a050"
_BADGE_MAINTAIN_TEXT  = "#d4d4a4"
_BADGE_REFRESH_BG     = "#1a2a2a"
_BADGE_REFRESH_BORDER = "#50a0a0"
_BADGE_REFRESH_TEXT   = "#a4d4d4"
_BADGE_DELAY_BG       = "#2a1a1a"
_BADGE_DELAY_BORDER   = "#c05050"
_BADGE_DELAY_TEXT     = "#f4a4a4"

# Effets
_FX_USER_BG       = "#1e2a1e"
_FX_USER_BORDER   = "#40804a"
_FX_TARGET_BG     = "#2a1e1e"
_FX_TARGET_BORDER = "#804040"
_FX_BONUS_TEXT    = "#a6e3a1"   # vert
_FX_MALUS_TEXT    = "#f38ba8"   # rouge

# Barre de coût
_COST_BAR_BG      = "#313244"
_COST_BAR_FILL    = "#fab387"
_COST_MAX_STAMINA = 50          # référence visuelle (50 = coût max raisonnable)

# Bouton lancer
_BTN_BG           = "#3a2a5a"
_BTN_HOVER        = "#5a3a8a"
_BTN_BORDER       = "#8060c0"
_BTN_TEXT         = "#cba6f7"


# ── Helpers de style ─────────────────────────────────────────────────────────

def _badge_style(bg: str, border: str, color: str) -> str:
    return (
        f"background:{bg}; border:1px solid {border}; border-radius:3px;"
        f"color:{color}; font-size:10px; font-family:Consolas,monospace;"
        f"padding:1px 5px;"
    )


_TARGETING_STYLES: dict[str, tuple[str, str, str, str]] = {
    "single": ("⊙ single", _BADGE_SINGLE_BG, _BADGE_SINGLE_BORDER, _BADGE_SINGLE_TEXT),
    "multi":  ("⊕ multi",  _BADGE_MULTI_BG,  _BADGE_MULTI_BORDER,  _BADGE_MULTI_TEXT),
}

_POLICY_STYLES: dict[str, tuple[str, str, str, str]] = {
    "instant":  ("⚡ instant",  _BADGE_INSTANT_BG,  _BADGE_INSTANT_BORDER,  _BADGE_INSTANT_TEXT),
    "maintain": ("⏳ maintain", _BADGE_MAINTAIN_BG, _BADGE_MAINTAIN_BORDER, _BADGE_MAINTAIN_TEXT),
    "refresh":  ("🔁 refresh",  _BADGE_REFRESH_BG,  _BADGE_REFRESH_BORDER,  _BADGE_REFRESH_TEXT),
    "delay":    ("⏱ delay",    _BADGE_DELAY_BG,    _BADGE_DELAY_BORDER,    _BADGE_DELAY_TEXT),
}

# Noms lisibles pour stats
_STAT_LABELS: dict[str, str] = {
    "hp": "PV", "stamina": "Stamina",
    "str": "FOR", "dex": "DEX", "con": "CON", "int": "INT",
    "wis": "SAG", "cha": "CHA", "per": "PER", "agi": "AGI",
    "luc": "LUC", "sur": "SUR",
    "mental_health": "Santé mentale", "drug_health": "Santé chimique",
}


def _fmt_stat(stat: str) -> str:
    return _STAT_LABELS.get(stat, stat.upper())


def _fmt_formula(expr: str) -> str:
    """Rend la formule brute un peu plus lisible."""
    return (
        expr
        .replace("diceratio(user.", "ratio(")
        .replace("diceratio(target.", "ratio(cible.")
        .replace("diceattack(", "attaque(")
        .replace("user.", "")
        .replace("target.", "cible.")
    )


# ── Widget principal ─────────────────────────────────────────────────────────

class SpellCard(QFrame):
    """
    Carte de sort PyQt6 — équivalent de SpellCardWidget (Pygame), enrichi v2.
    """

    cast_requested = pyqtSignal(str)   # spell_key

    def __init__(
        self,
        spell: Spell,
        spell_key: str,
        enable_cast: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.spell = spell
        self.spell_key = spell_key
        self.enable_cast = enable_cast

        self.setObjectName("SpellCard")
        self.setStyleSheet(f"""
            SpellCard {{
                background: {_CARD_BG};
                border: 1px solid {_CARD_BORDER};
                border-radius: 8px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._build_ui()

    # ── Construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 10)
        root.setSpacing(0)

        root.addWidget(self._make_header())
        
        body = QVBoxLayout()
        body.setContentsMargins(12, 8, 12, 0)
        body.setSpacing(6)

        body.addWidget(self._make_cost_row())
        body.addWidget(self._make_description())

        if self.spell.effects:
            body.addWidget(self._make_effects_section())

        if self.enable_cast:
            body.addLayout(self._make_cast_row())

        root.addLayout(body)

    def _make_header(self) -> QWidget:
        """Ligne d'en-tête sur fond légèrement différent : Nom | badges."""
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
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # Nom
        name_lbl = QLabel(self.spell.name)
        f = QFont()
        f.setBold(True)
        f.setPointSize(12)
        name_lbl.setFont(f)
        name_lbl.setStyleSheet(f"color:{_TEXT_PRIMARY}; background:transparent;")
        layout.addWidget(name_lbl)

        layout.addStretch()

        # Badge targeting
        t_label, t_bg, t_border, t_color = _TARGETING_STYLES.get(
            self.spell.targeting,
            (self.spell.targeting, _BADGE_SINGLE_BG, _BADGE_SINGLE_BORDER, _BADGE_SINGLE_TEXT)
        )
        t_badge = QLabel(t_label)
        t_badge.setStyleSheet(_badge_style(t_bg, t_border, t_color))
        layout.addWidget(t_badge)

        # Badge runtime policy
        p_label, p_bg, p_border, p_color = _POLICY_STYLES.get(
            self.spell.runtime_policy,
            (self.spell.runtime_policy, _BADGE_INSTANT_BG, _BADGE_INSTANT_BORDER, _BADGE_INSTANT_TEXT)
        )
        p_badge = QLabel(p_label)
        p_badge.setStyleSheet(_badge_style(p_bg, p_border, p_color))
        layout.addWidget(p_badge)

        # Badge delay (si applicable)
        if self.spell.delay != float("inf"):
            delay_lbl = QLabel(f"⏱ {self.spell.delay}t")
            delay_lbl.setStyleSheet(_badge_style(_BADGE_DELAY_BG, _BADGE_DELAY_BORDER, _BADGE_DELAY_TEXT))
            layout.addWidget(delay_lbl)

        return header

    def _make_cost_row(self) -> QWidget:
        """Ligne : 'Coût :' [barre stamina] valeur numérique."""
        container = QWidget()
        container.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        cost_lbl = QLabel("Coût :")
        cost_lbl.setStyleSheet(f"color:{_TEXT_SECONDARY}; font-size:11px; background:transparent;")
        layout.addWidget(cost_lbl)

        # Mini barre de coût
        bar_bg = QFrame()
        bar_bg.setFixedHeight(8)
        bar_bg.setStyleSheet(
            f"background:{_COST_BAR_BG}; border-radius:4px;"
        )
        bar_bg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        fill_ratio = min(1.0, self.spell.cost / _COST_MAX_STAMINA)
        # La barre remplie est superposée via un layout interne
        bar_inner = QHBoxLayout(bar_bg)
        bar_inner.setContentsMargins(0, 0, 0, 0)
        bar_inner.setSpacing(0)

        fill = QFrame()
        fill.setFixedHeight(8)
        fill.setStyleSheet(
            f"background:{_COST_BAR_FILL}; border-radius:4px;"
        )
        fill.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # La largeur sera calculée dynamiquement via sizeHint impossible ici,
        # on utilise une proportion fixe relative à 200px (largeur typique)
        fill.setFixedWidth(max(6, int(200 * fill_ratio)))

        bar_inner.addWidget(fill)
        bar_inner.addStretch()

        layout.addWidget(bar_bg)

        val_lbl = QLabel(f"{self.spell.cost} stamina")
        val_lbl.setStyleSheet(
            f"color:{_TEXT_COST}; font-size:11px; font-weight:bold; background:transparent;"
        )
        layout.addWidget(val_lbl)

        return container

    def _make_description(self) -> QLabel:
        """Description du sort, wrappée automatiquement."""
        lbl = QLabel(self.spell.description or "—")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color:{_TEXT_SECONDARY}; font-size:11px; background:transparent;"
        )
        return lbl

    def _make_effects_section(self) -> QWidget:
        """Section effets : un ligne par Effect avec badge cible + formule."""
        section = QWidget()
        section.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Titre de section
        title = QLabel("Effets")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(9)
        title.setFont(title_font)
        title.setStyleSheet(f"color:{_TEXT_SECONDARY}; background:transparent;")
        layout.addWidget(title)

        for effect in self.spell.effects:
            layout.addWidget(self._make_effect_row(effect))

        return section

    def _make_effect_row(self, effect: Effect) -> QFrame:
        """
        Une ligne d'effet :
          [user/cible badge]  [stat badge]  [▲/▼ opérateur]  formule lisible
        """
        scope, stat = effect.target
        operator: Operator = effect.operator
        formula_str = _fmt_formula(effect.formula.expression)

        is_user  = scope == "user"
        is_bonus = operator == "bonus"

        row_bg     = _FX_USER_BG   if is_user  else _FX_TARGET_BG
        row_border = _FX_USER_BORDER if is_user else _FX_TARGET_BORDER

        row = QFrame()
        row.setStyleSheet(
            f"QFrame {{ background:{row_bg}; border:1px solid {row_border}; border-radius:4px; }}"
        )

        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # Badge scope
        scope_text = "Soi" if is_user else "Cible"
        scope_lbl = QLabel(scope_text)
        scope_lbl.setStyleSheet(
            f"color: {'#a6e3a1' if is_user else '#f38ba8'};"
            f"font-size:10px; font-family:Consolas,monospace;"
            f"background:transparent;"
        )
        layout.addWidget(scope_lbl)

        # Séparateur
        sep = QLabel("›")
        sep.setStyleSheet(f"color:{_TEXT_SECONDARY}; background:transparent; font-size:10px;")
        layout.addWidget(sep)

        # Stat badge
        stat_lbl = QLabel(_fmt_stat(stat))
        stat_lbl.setStyleSheet(
            f"color:{_TEXT_PRIMARY}; font-size:10px; font-weight:bold;"
            f"font-family:Consolas,monospace; background:transparent;"
        )
        layout.addWidget(stat_lbl)

        # Opérateur ▲ / ▼
        op_lbl = QLabel("▲" if is_bonus else "▼")
        op_lbl.setStyleSheet(
            f"color:{'#a6e3a1' if is_bonus else '#f38ba8'};"
            f"font-size:12px; background:transparent;"
        )
        layout.addWidget(op_lbl)

        # Formule
        formula_lbl = QLabel(formula_str)
        formula_lbl.setStyleSheet(
            f"color:{'#a6e3a1' if is_bonus else '#f38ba8'};"
            f"font-size:10px; font-family:Consolas,monospace; background:transparent;"
        )
        formula_lbl.setToolTip(f"Formule brute : {effect.formula.expression}")
        layout.addWidget(formula_lbl)

        layout.addStretch()
        return row

    def _make_cast_row(self) -> QHBoxLayout:
        """Ligne avec le bouton 'Lancer' aligné à droite."""
        layout = QHBoxLayout()
        layout.addStretch()

        btn = QPushButton("✦ Lancer")
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {_BTN_BG};
                color: {_BTN_TEXT};
                border: 1px solid {_BTN_BORDER};
                border-radius: 4px;
                padding: 4px 16px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: {_BTN_HOVER}; }}
            QPushButton:pressed {{ background: {_CARD_BG}; }}
        """)
        btn.clicked.connect(lambda: self.cast_requested.emit(self.spell_key))
        layout.addWidget(btn)
        return layout

    # ── API publique ─────────────────────────────────────────────────────────

    def set_spell(self, spell: Spell, spell_key: str) -> None:
        """Remplace le sort affiché (recrée l'UI)."""
        self.spell = spell
        self.spell_key = spell_key

        old = self.layout()
        if old:
            while old.count():
                item = old.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
                sub = item.layout()
                if sub:
                    # on ne peut pas deleteLater un layout, on le vide
                    while sub.count():
                        sub.takeAt(0)

        self._build_ui()
