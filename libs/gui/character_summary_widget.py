# -*- coding: utf-8 -*-

"""
Character summary widget for resource management.
Displays character stats, spells, and inventory without requiring
a full Character instance.
"""

from __future__ import annotations
from typing import Optional, Dict, Any

from pygame import Surface, Rect
from pygame.draw import rect as draw_rect
from pygame.font import SysFont

from .pygame_ui import UIWidget


class CharacterSummaryWidget(UIWidget):
    """
    Display a character summary with stats, spells, and inventory.
    Works with raw JSON data without requiring a Character instance.
    """

    def __init__(
        self,
        parent: Optional[UIWidget],
        rect: Rect,
        character_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(parent, rect)
        self.character_data = character_data
        self._title_font = SysFont("arial", 16, bold=True)
        self._section_font = SysFont("arial", 14, bold=True)
        self._small_font = SysFont("arial", 12)

    def set_character_data(self, character_data: Dict[str, Any]) -> None:
        """Update the displayed character data."""
        self.character_data = character_data

    def render(self, surface: Surface) -> None:
        if not self.displayed or not self.character_data:
            # Draw empty state
            draw_rect(surface, (36, 40, 46), self.rect, border_radius=6)
            draw_rect(surface, (80, 86, 94), self.rect, 2, border_radius=6)
            
            theme = self.app.theme
            text = "Sélectionnez un personnage"
            text_surf = theme.font.render(text, True, (150, 150, 150))
            text_rect = text_surf.get_rect(center=self.rect.center)
            surface.blit(text_surf, text_rect)
            return

        theme = self.app.theme
        padding = 12
        y = self.rect.y + padding

        # Card background
        draw_rect(surface, (36, 40, 46), self.rect, border_radius=6)
        draw_rect(surface, (80, 86, 94), self.rect, 2, border_radius=6)

        # Character name
        name = self.character_data.get("name", "Unknown")
        name_surf = self._title_font.render(name, True, theme.colors["text"])
        surface.blit(name_surf, (self.rect.x + padding, y))
        y += name_surf.get_height() + 8

        # Separator line
        draw_rect(surface, (80, 86, 94), Rect(self.rect.x + padding, y, self.rect.width - padding * 2, 1))
        y += 10

        # Stats section
        stats = self.character_data.get("stats", {})
        
        # Calculate HP from con and wis (formula: 10 + con//10 + wis//10)
        con = stats.get("con", 0)
        wis = stats.get("wis", 0)
        hp_total = 10 + con // 10 + wis // 10
        
        # Calculate Level from total stats (formula: (total - 500) // 5)
        total_stats = (
            stats.get("str", 0) + stats.get("dex", 0) + stats.get("con", 0) +
            stats.get("int", 0) + stats.get("wis", 0) + stats.get("cha", 0) +
            stats.get("per", 0) + stats.get("agi", 0) + stats.get("luc", 0) +
            stats.get("sur", 0)
        )
        level = (total_stats - 500) // 5
        xp = total_stats

        # Primary stats (HP, Level, XP, Stamina, Mental, Drug Health)
        primary_stats = [
            ("HP", hp_total, (200, 85, 85)),
            ("Level", level, (255, 215, 0)),
            ("XP", xp, (100, 200, 255)),
            ("Stamina", stats.get("stamina", 0), (80, 185, 95)),
            ("Mental", stats.get("mental_health", 0), (100, 150, 200)),
            ("Drug", stats.get("drug_health", 0), (180, 120, 180)),
        ]

        col_width = (self.rect.width - padding * 2) // 2
        for i, (label, value, color) in enumerate(primary_stats):
            col = i % 2
            row = i // 2
            x = self.rect.x + padding + col * col_width
            stat_y = y + row * 30

            # Label
            label_surf = self._small_font.render(label, True, (180, 180, 180))
            surface.blit(label_surf, (x, stat_y))

            # Value
            value_surf = self._small_font.render(str(value), True, color)
            surface.blit(value_surf, (x + 70, stat_y))

        y += 90 + 10

        # Stats section header
        stats_label = self._section_font.render("Stats", True, theme.colors["text"])
        surface.blit(stats_label, (self.rect.x + padding, y))
        y += stats_label.get_height() + 6

        # Main stats as progress bars (no modifiers, base values only)
        main_stats = [
            ("STR", stats.get("str", 0), (220, 100, 100)),
            ("DEX", stats.get("dex", 0), (100, 220, 100)),
            ("CON", stats.get("con", 0), (100, 180, 220)),
            ("INT", stats.get("int", 0), (180, 100, 220)),
            ("WIS", stats.get("wis", 0), (220, 180, 100)),
            ("CHA", stats.get("cha", 0), (220, 120, 180)),
            ("PER", stats.get("per", 0), (180, 220, 100)),
            ("AGI", stats.get("agi", 0), (100, 220, 180)),
            ("LUC", stats.get("luc", 0), (220, 220, 100)),
            ("SUR", stats.get("sur", 0), (160, 160, 220)),
        ]

        bar_width = self.rect.width - padding * 2
        bar_height = 12
        max_stat = 250  # Maximum stat value for bar scaling

        for i, (label, value, color) in enumerate(main_stats):
            stat_y = y + i * 26
            
            # Stat label and value text
            label_text = f"{label}: {value}"
            label_surf = self._small_font.render(label_text, True, (200, 200, 200))
            surface.blit(label_surf, (self.rect.x + padding, stat_y))
            
            # Progress bar background
            bar_y = stat_y + 14
            draw_rect(surface, (24, 26, 30), Rect(self.rect.x + padding, bar_y, bar_width, bar_height), border_radius=4)
            
            # Progress bar fill
            fill_ratio = min(1.0, max(0.0, value / max_stat))
            if fill_ratio > 0:
                draw_rect(surface, color, Rect(self.rect.x + padding, bar_y, int(bar_width * fill_ratio), bar_height), border_radius=4)
