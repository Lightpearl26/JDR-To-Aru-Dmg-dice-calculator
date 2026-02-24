# -*- coding: utf-8 -*-

"""
Spell card widget for pygame_ui based apps.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from pygame import Surface, Rect, mouse, MOUSEBUTTONUP
from pygame.event import Event
from pygame.draw import rect as draw_rect
from pygame.font import SysFont

from .pygame_ui import UIWidget

if TYPE_CHECKING:
    from libs.spell import Spell
    from libs.character import Character


class SpellCardWidget(UIWidget):
    """
    Display a single spell as a card with title, cost, description, formulas and cast button.
    """

    def __init__(
        self,
        parent: Optional[UIWidget],
        rect: Rect,
        spell: Optional[Spell] = None,
        spell_key: Optional[str] = None,
        enable_cast_button: bool = True,
        owner: Optional['Character'] = None,
    ) -> None:
        super().__init__(parent, rect)
        self.spell = spell
        self.spell_key = spell_key
        self.enable_cast_button = enable_cast_button
        self.owner = owner
        self._title_font = SysFont("arial", 18, bold=True)
        self._cast_button_rect: Optional[Rect] = None
        self._is_cast_hovered: bool = False

    def set_spell(self, spell: Spell, spell_key: str) -> None:
        """Set the spell to display."""
        self.spell = spell
        self.spell_key = spell_key

    def _to_local_pos(self, pos: tuple[int, int]) -> tuple[int, int]:
        offset_x = self.global_rect.x - self.rect.x
        offset_y = self.global_rect.y - self.rect.y
        return (pos[0] - offset_x, pos[1] - offset_y)

    def _wrap_text(self, text: str, font, max_width: int) -> list[str]:
        """Wrap text to fit within max_width."""
        words = text.split(' ')
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            test_width = font.size(test_line)[0]
            
            if test_width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines if lines else ['']

    def get_required_height(self, width: int) -> int:
        """Calculate the required height for this spell card."""
        if not self.spell:
            return 100
        
        theme = self.app.theme
        padding = 10
        
        title_h = 24
        gap_title_desc = 20
        gap_desc_formula = 12
        gap_formula_button = 12
        
        desc_lines = self._wrap_text(self.spell.description, theme.font, width - 2 * padding)
        desc_h = len(desc_lines) * 18 + 10
        
        formula_h = 0
        if self.spell.effects:
            formula_h = len(self.spell.effects) * 28 + 8
        
        button_h = 30
        card_h = title_h + gap_title_desc + desc_h + (gap_desc_formula if self.spell.effects else 0) + formula_h + gap_formula_button + button_h + padding * 2
        
        return card_h

    def is_cast_button_clicked(self, pos: tuple[int, int]) -> bool:
        """Check if the cast button was clicked at the given position."""
        if self._cast_button_rect and self._cast_button_rect.collidepoint(pos):
            return True
        return False

    def handle_event(self, event: Event) -> bool:
        """Handle cast button and popup interactions."""
        if not self.displayed or event.type != MOUSEBUTTONUP or event.button != 1:
            return False

        # Don't handle clicks if cast button is disabled
        if not self.enable_cast_button:
            return False

        local_pos = self._to_local_pos(event.pos)

        if self._cast_button_rect and self._cast_button_rect.collidepoint(local_pos):
            # Call app method to open cast spell form
            self.app.open_cast_spell_form(self.owner, self.spell_key)
            return True

        return False

    def render(self, surface: Surface) -> None:
        if not self.displayed or not self.spell:
            return
        
        theme = self.app.theme
        mouse_pos = self._to_local_pos(mouse.get_pos())
        padding = 10
        
        # Card background
        draw_rect(surface, (45, 45, 50), self.rect, border_radius=5)
        draw_rect(surface, (80, 80, 85), self.rect, 2, border_radius=5)
        
        # Spell name (bold, larger font)
        title_surf = self._title_font.render(self.spell.name, True, theme.colors["text"])
        title_rect = title_surf.get_rect(topleft=(self.rect.x + padding, self.rect.y + padding))
        surface.blit(title_surf, title_rect)
        
        # Cost (orange box, top right)
        cost_h = 28
        cost_rect = Rect(self.rect.right - 95, self.rect.y + padding, 85, cost_h)
        draw_rect(surface, (200, 120, 40), cost_rect, border_radius=4)
        draw_rect(surface, (220, 140, 60), cost_rect, 2, border_radius=4)
        cost_text = f"Cost: {self.spell.cost}"
        cost_surf = theme.font.render(cost_text, True, (255, 255, 255))
        cost_text_rect = cost_surf.get_rect(center=cost_rect.center)
        surface.blit(cost_surf, cost_text_rect)
        
        # Description (wrapped)
        desc_y = self.rect.y + padding + 24 + 20
        desc_lines = self._wrap_text(self.spell.description, theme.font, self.rect.width - 2 * padding)
        for line in desc_lines:
            line_surf = theme.font.render(line, True, (200, 200, 200))
            surface.blit(line_surf, (self.rect.x + padding, desc_y))
            desc_y += 18
        
        # Formulas (black boxes)
        if self.spell.effects:
            desc_h = len(desc_lines) * 18 + 10
            formula_y = self.rect.y + padding + 24 + 20 + desc_h + 12
            
            for effect in self.spell.effects:
                formula_rect = Rect(self.rect.x + padding, formula_y, self.rect.width - 2 * padding, 24)
                
                draw_rect(surface, (20, 20, 25), formula_rect, border_radius=3)
                draw_rect(surface, (60, 60, 65), formula_rect, 1, border_radius=3)
                
                # Effect info
                effect_text = f"{effect.target}.{effect.target_stat} {effect.effect}: {effect.formula.cmd}"
                formula_surf = theme.font.render(effect_text, True, (180, 255, 180))
                formula_text_rect = formula_surf.get_rect(midleft=(formula_rect.x + 6, formula_rect.centery))
                surface.blit(formula_surf, formula_text_rect)
                
                formula_y += 28
        
        # Cast button
        button_h = 30
        button_rect = Rect(self.rect.x + padding, self.rect.bottom - button_h - padding, 120, button_h)
        self._cast_button_rect = button_rect
        
        # Disable button visually if not enabled
        if self.enable_cast_button:
            self._is_cast_hovered = button_rect.collidepoint(mouse_pos)
            cast_color = (70, 150, 70) if self._is_cast_hovered else (50, 120, 50)
            border_color = (100, 180, 100)
            text_color = (255, 255, 255)
        else:
            self._is_cast_hovered = False
            cast_color = (40, 40, 45)
            border_color = (60, 60, 65)
            text_color = (120, 120, 120)
        
        draw_rect(surface, cast_color, button_rect, border_radius=4)
        draw_rect(surface, border_color, button_rect, 2, border_radius=4)
        
        cast_text = "Cast Spell"
        cast_surf = theme.font.render(cast_text, True, text_color)
        cast_text_rect = cast_surf.get_rect(center=button_rect.center)
        surface.blit(cast_surf, cast_text_rect)
