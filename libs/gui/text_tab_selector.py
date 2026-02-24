# -*- coding: utf-8 -*-

"""
Text Tab Selector - Custom selector with text buttons instead of icons
"""

from __future__ import annotations
from typing import Optional

from pygame import Rect, Surface, Color, MOUSEBUTTONDOWN, MOUSEMOTION
from pygame.event import Event
from pygame.font import SysFont
from pygame.draw import rect as draw_rect

from .pygame_ui import UIWidget


class TextTabSelector(UIWidget):
    """
    Selector using text buttons instead of icons.
    Perfect for tabbed navigation with labels like "Session", "Combat", "Resources".
    
    Usage:
        selector = TextTabSelector(
            parent,
            Rect(0, 0, 600, 50),
            tabs=["Session", "Combat", "Ressources"],
            default_tab="Session"
        )
    """
    
    def __init__(
        self,
        parent: Optional[UIWidget],
        rect: Rect,
        tabs: list[str],
        default_tab: str | None = None,
        font_size: int = 18,
        tab_padding: int = 25,
        spacing: int = 0
    ) -> None:
        super().__init__(parent, rect)
        
        self.tabs = tabs
        self.font = SysFont("consolas", font_size, bold=True)
        self.tab_padding = tab_padding
        self.spacing = spacing
        
        # Selection state
        self.selected_index = tabs.index(default_tab) if default_tab and default_tab in tabs else 0
        self.hover_index = -1
        
        # Calculate tab positions and sizes
        self._calculate_tab_rects()
        
        # Colors
        self.color_bg = Color(40, 44, 52)
        self.color_tab_normal = Color(60, 64, 72)
        self.color_tab_hover = Color(70, 74, 82)
        self.color_tab_selected = Color(45, 130, 220)
        self.color_text_normal = Color(180, 180, 180)
        self.color_text_selected = Color(255, 255, 255)
    
    def _calculate_tab_rects(self) -> None:
        """Calculate the rect for each tab button."""
        self.tab_rects = []
        x_offset = 0
        
        max_width = max(self.font.size(tab)[0] for tab in self.tabs) + 2 * self.tab_padding
        height = self.rect.height
        for tab in self.tabs:
            tab_rect = Rect(x_offset, 0, max_width, height)
            self.tab_rects.append(tab_rect)
            x_offset += max_width + self.spacing
    
    @property
    def selected_name(self) -> str:
        """Return the name of the currently selected tab."""
        return self.tabs[self.selected_index]

    def handle_event(self, event: Event) -> bool:
        if not self.displayed:
            return False
        
        if event.type == MOUSEMOTION:
            mouse_pos = event.pos
            # Convert to local coordinates
            local_x = mouse_pos[0] - self.global_rect.x
            local_y = mouse_pos[1] - self.global_rect.y
            
            # Check which tab is hovered
            self.hover_index = -1
            for i, tab_rect in enumerate(self.tab_rects):
                if tab_rect.collidepoint(local_x, local_y):
                    self.hover_index = i
                    break
            return True
        
        elif event.type == MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            local_x = mouse_pos[0] - self.global_rect.x
            local_y = mouse_pos[1] - self.global_rect.y
            
            # Check which tab was clicked
            for i, tab_rect in enumerate(self.tab_rects):
                if tab_rect.collidepoint(local_x, local_y):
                    self.selected_index = i
                    return True
        
        return False

    def render(self, surface: Surface) -> None:
        if not self.displayed:
            return

        # Draw background (using local coordinates)
        draw_rect(surface, self.app.theme.colors["bg"], self.rect)

        # Draw tabs
        for i, tab in enumerate(self.tabs):
            tab_rect = self.tab_rects[i]
            tab_color = self.color_tab_normal
            text_color = self.color_text_normal

            if i == self.selected_index:
                tab_color = self.color_tab_selected
                text_color = self.color_text_selected
            elif i == self.hover_index:
                tab_color = self.color_tab_hover

            # Draw tab background (local coordinates + rect offset)
            draw_rect(surface, tab_color, Rect(
                self.rect.x + tab_rect.x,
                self.rect.y + tab_rect.y,
                tab_rect.width,
                tab_rect.height
            ))

            # Draw tab text (local coordinates + rect offset)
            text_surf = self.font.render(tab, True, text_color)
            text_rect = text_surf.get_rect(center=(
                self.rect.x + tab_rect.x + tab_rect.width // 2,
                self.rect.y + tab_rect.y + tab_rect.height // 2
            ))
            surface.blit(text_surf, text_rect)
