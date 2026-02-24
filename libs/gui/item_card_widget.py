# -*- coding: utf-8 -*-

"""
Item card widget for pygame_ui based apps.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from pygame import Surface, Rect, MOUSEBUTTONUP
from pygame.event import Event
from pygame.draw import rect as draw_rect
from pygame.font import SysFont
from pygame.mouse import get_pos as mouse_get_pos

from .pygame_ui import UIWidget

if TYPE_CHECKING:
    from libs.item import Item


class ItemCardWidget(UIWidget):
    """
    Display a single item as a card with title, quantity, description and modifiers.
    """

    def __init__(
        self,
        parent: Optional[UIWidget],
        rect: Rect,
        item: Optional[Item] = None,
        item_name: Optional[str] = None,
        quantity: int = 1,
    ) -> None:
        super().__init__(parent, rect)
        self.item = item
        self.item_name = item_name
        self.quantity = quantity
        self._title_font = SysFont("arial", 16, bold=True)
        self._plus_button_rect: Optional[Rect] = None
        self._minus_button_rect: Optional[Rect] = None

    def set_item(self, item: Item, item_name: str, quantity: int = 1) -> None:
        """Set the item to display."""
        self.item = item
        self.item_name = item_name
        self.quantity = quantity

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
        """Calculate the required height for this item card."""
        if not self.item:
            return 80
        
        theme = self.app.theme
        padding = 8
        
        title_h = 22
        gap_title_desc = 12
        gap_desc_mods = 8
        
        desc_lines = self._wrap_text(self.item.description, theme.font, width - 2 * padding)
        desc_h = len(desc_lines) * 16 + 6
        
        mods_h = 0
        if self.item.modifier:
            mods_h = len(self.item.modifier) * 20 + 6
        
        card_h = title_h + gap_title_desc + desc_h + (gap_desc_mods if self.item.modifier else 0) + mods_h + padding * 2
        
        return card_h

    def handle_event(self, event: Event) -> bool:
        """Handle events for quantity buttons. Returns True if quantity changed."""
        if not self.displayed or event.type != MOUSEBUTTONUP or event.button != 1:
            return False
        
        # Recalculate button positions if needed (in case render hasn't been called yet)
        if not self._plus_button_rect or not self._minus_button_rect:
            padding = 8
            button_size = 22
            button_gap = 3
            qty_box_width = 36
            button_y = self.rect.y + padding
            
            total_width = button_size + button_gap + qty_box_width + button_gap + button_size
            start_x = self.rect.right - padding - total_width
            
            self._minus_button_rect = Rect(start_x, button_y, button_size, button_size)
            self._plus_button_rect = Rect(
                start_x + button_size + button_gap + qty_box_width + button_gap,
                button_y,
                button_size,
                button_size
            )
        
        local_pos = self._to_local_pos(event.pos)

        # Check minus button
        if self._minus_button_rect and self._minus_button_rect.collidepoint(local_pos):
            self.quantity = max(0, self.quantity - 1)
            return True
        
        # Check plus button
        if self._plus_button_rect and self._plus_button_rect.collidepoint(local_pos):
            self.quantity += 1
            return True
        
        return False

    def render(self, surface: Surface) -> None:
        if not self.displayed or not self.item:
            return
        
        theme = self.app.theme
        padding = 8
        mouse_pos = self._to_local_pos(mouse_get_pos())
        
        # Card background
        draw_rect(surface, (40, 45, 50), self.rect, border_radius=4)
        draw_rect(surface, (75, 80, 85), self.rect, 2, border_radius=4)
        
        # Quantity buttons (top right)
        button_size = 22
        button_gap = 3
        qty_box_width = 36
        button_y = self.rect.y + padding
        
        # Calculate total width needed: minus + gap + qty_box + gap + plus
        total_width = button_size + button_gap + qty_box_width + button_gap + button_size
        start_x = self.rect.right - padding - total_width
        
        # Minus button (leftmost)
        self._minus_button_rect = Rect(
            start_x,
            button_y,
            button_size,
            button_size
        )
        hovered_minus = self._minus_button_rect.collidepoint(mouse_pos)
        minus_color = (120, 60, 60) if hovered_minus else (90, 40, 40)
        draw_rect(surface, minus_color, self._minus_button_rect, border_radius=3)
        draw_rect(surface, (150, 80, 80), self._minus_button_rect, 1, border_radius=3)
        minus_text = self._title_font.render("-", True, (255, 200, 200))
        minus_text_rect = minus_text.get_rect(center=self._minus_button_rect.center)
        surface.blit(minus_text, minus_text_rect)
        
        # Quantity display box (middle)
        qty_box_x = self._minus_button_rect.right + button_gap
        qty_box_rect = Rect(
            qty_box_x,
            button_y,
            qty_box_width,
            button_size
        )
        # Black box with border
        draw_rect(surface, (20, 20, 20), qty_box_rect, border_radius=3)
        draw_rect(surface, (100, 100, 100), qty_box_rect, 1, border_radius=3)
        
        # Quantity text centered in box
        qty_text = f"{self.quantity}"
        qty_surf = self._title_font.render(qty_text, True, (200, 220, 255))
        qty_text_rect = qty_surf.get_rect(center=qty_box_rect.center)
        surface.blit(qty_surf, qty_text_rect)
        
        # Plus button (rightmost)
        self._plus_button_rect = Rect(
            qty_box_rect.right + button_gap,
            button_y,
            button_size,
            button_size
        )
        hovered_plus = self._plus_button_rect.collidepoint(mouse_pos)
        plus_color = (60, 120, 60) if hovered_plus else (40, 90, 40)
        draw_rect(surface, plus_color, self._plus_button_rect, border_radius=3)
        draw_rect(surface, (80, 150, 80), self._plus_button_rect, 1, border_radius=3)
        plus_text = self._title_font.render("+", True, (200, 255, 200))
        plus_text_rect = plus_text.get_rect(center=self._plus_button_rect.center)
        surface.blit(plus_text, plus_text_rect)
        
        # Item name (bold)
        title_text = self.item.name
        title_surf = self._title_font.render(title_text, True, theme.colors["text"])
        title_rect = title_surf.get_rect(topleft=(self.rect.x + padding, self.rect.y + padding))
        surface.blit(title_surf, title_rect)
        
        # Description (wrapped)
        desc_y = self.rect.y + padding + 22 + 12
        desc_lines = self._wrap_text(self.item.description, theme.font, self.rect.width - 2 * padding)
        for line in desc_lines:
            line_surf = theme.font.render(line, True, (190, 190, 190))
            surface.blit(line_surf, (self.rect.x + padding, desc_y))
            desc_y += 16
        
        # Modifiers (blue boxes)
        if self.item.modifier:
            desc_h = len(desc_lines) * 16 + 6
            mods_y = self.rect.y + padding + 22 + 12 + desc_h + 8
            
            for stat_name, value in self.item.modifier:
                mod_rect = Rect(self.rect.x + padding, mods_y, self.rect.width - 2 * padding, 18)
                
                draw_rect(surface, (30, 40, 60), mod_rect, border_radius=3)
                draw_rect(surface, (60, 80, 110), mod_rect, 1, border_radius=3)
                
                # Modifier text
                sign = "+" if value >= 0 else ""
                mod_text = f"{stat_name.upper()}: {sign}{value}"
                mod_surf = theme.font.render(mod_text, True, (150, 200, 255))
                mod_text_rect = mod_surf.get_rect(midleft=(mod_rect.x + 6, mod_rect.centery))
                surface.blit(mod_surf, mod_text_rect)
                
                mods_y += 20
