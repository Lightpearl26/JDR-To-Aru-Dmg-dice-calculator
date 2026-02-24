# -*- coding: utf-8 -*-

"""
Character card widget for pygame_ui based apps.
"""

from __future__ import annotations
from typing import Optional

from pygame import Surface, Rect, MOUSEBUTTONUP, display, mouse
from pygame.draw import rect as draw_rect
from pygame.font import SysFont

from .pygame_ui import UIWidget, Popup
from .character_sheet_widget import CharacterSheetWidget
from ..character import Character


class CharacterCardWidget(UIWidget):
    """
    Display a character summary card with name, HP, stamina, level and a button
    to open the full character sheet in a Popup.
    """

    def __init__(
        self,
        parent: Optional[UIWidget],
        rect: Rect,
        character: Optional[Character] = None,
        show_action_buttons: bool = True,
    ) -> None:
        super().__init__(parent, rect)
        self.character = character
        self.show_action_buttons = show_action_buttons
        self._title_font = SysFont("arial", 18, bold=True)
        self._button_rect: Optional[Rect] = None
        self._strike_button_rect: Optional[Rect] = None
        self._shoot_button_rect: Optional[Rect] = None

    def set_character(self, character: Character) -> None:
        """Update the displayed character."""
        self.character = character

    def _open_character_sheet(self) -> None:
        if not self.character:
            return
        surface = display.get_surface()
        if not surface:
            return

        popup_w = min(980, surface.get_width() - 40)
        popup_h = min(680, surface.get_height() - 60)
        popup_rect = Rect(
            (surface.get_width() - popup_w) // 2,
            (surface.get_height() - popup_h) // 2,
            popup_w,
            popup_h,
        )
        popup = Popup(self.app, surface, popup_rect, title=self.character.name)
        CharacterSheetWidget(popup, Rect(10, 10, popup_rect.width - 20, popup_rect.height - 20), self.character)
        popup.run()

    def handle_event(self, event) -> bool:
        if not self.displayed or event.type != MOUSEBUTTONUP or event.button != 1:
            return False

        if self._button_rect and self._button_rect.collidepoint(event.pos):
            self._open_character_sheet()
            return True
        
        if self._strike_button_rect and self._strike_button_rect.collidepoint(event.pos):
            self._on_strike()
            return True
        
        if self._shoot_button_rect and self._shoot_button_rect.collidepoint(event.pos):
            self._on_shoot()
            return True

        return UIWidget.handle_event(self, event)
    
    def _on_strike(self) -> None:
        """Handle strike button click - opens strike form."""
        if self.character:
            self.app.open_strike_form(self.character)
    
    def _on_shoot(self) -> None:
        """Handle shoot button click - opens shoot form."""
        if self.character:
            self.app.open_shoot_form(self.character)

    def render(self, surface: Surface) -> None:
        if not self.displayed or not self.character:
            return

        theme = self.app.theme
        mouse_pos = mouse.get_pos()
        padding = 12

        # Card background
        draw_rect(surface, (36, 40, 46), self.rect, border_radius=6)
        draw_rect(surface, (80, 86, 94), self.rect, 2, border_radius=6)

        # Header strip
        header_h = 32
        header_rect = Rect(self.rect.x + 2, self.rect.y + 2, self.rect.width - 4, header_h)
        draw_rect(surface, (44, 49, 56), header_rect, border_radius=5)

        # Title and level
        name_surf = self._title_font.render(self.character.name, True, theme.colors["text"])
        name_rect = name_surf.get_rect(midleft=(self.rect.x + padding, header_rect.centery))
        surface.blit(name_surf, name_rect)

        level_text = f"Lvl {self.character.stats.lvl}"
        level_surf = theme.font.render(level_text, True, (230, 230, 230))
        level_pad_x = 8
        level_pad_y = 4
        level_bg = Rect(0, 0, level_surf.get_width() + level_pad_x * 2, level_surf.get_height() + level_pad_y * 2)
        level_bg.topright = (self.rect.right - padding, header_rect.centery - level_bg.height // 2)
        draw_rect(surface, (60, 66, 75), level_bg, border_radius=9)
        draw_rect(surface, (95, 102, 112), level_bg, 1, border_radius=9)
        surface.blit(level_surf, (level_bg.x + level_pad_x, level_bg.y + level_pad_y))

        # HP and Stamina bars
        bar_x = self.rect.x + padding
        bar_w = self.rect.width - padding * 2
        bar_h = 12

        hp_current = self.character.get_current_stat("hp")
        hp_max = max(1, self.character.stats.hp)
        hp_ratio = max(0.0, min(1.0, hp_current / hp_max))

        hp_y = header_rect.bottom + 26
        draw_rect(surface, (24, 26, 30), Rect(bar_x, hp_y, bar_w, bar_h), border_radius=5)
        draw_rect(surface, (200, 85, 85), Rect(bar_x, hp_y, int(bar_w * hp_ratio), bar_h), border_radius=5)
        hp_text = f"HP {hp_current}/{hp_max}"
        hp_surf = theme.font.render(hp_text, True, (200, 200, 200))
        surface.blit(hp_surf, (bar_x, hp_y - 18))

        stamina_current = self.character.get_current_stat("stamina")
        stamina_max = max(1, self.character.stats.stamina)
        stamina_ratio = max(0.0, min(1.0, stamina_current / stamina_max))

        stamina_y = hp_y + 30
        draw_rect(surface, (24, 26, 30), Rect(bar_x, stamina_y, bar_w, bar_h), border_radius=5)
        draw_rect(surface, (80, 185, 95), Rect(bar_x, stamina_y, int(bar_w * stamina_ratio), bar_h), border_radius=5)
        stamina_text = f"Stamina {stamina_current}/{stamina_max}"
        stamina_surf = theme.font.render(stamina_text, True, (200, 200, 200))
        surface.blit(stamina_surf, (bar_x, stamina_y - 18))

        # Strike and Shoot buttons (only if enabled)
        if self.show_action_buttons:
            action_button_w = 80
            action_button_h = 28
            action_button_spacing = 8
            action_buttons_y = self.rect.bottom - padding - action_button_h
            
            offset = self.global_rect.topleft[0] - self.rect.topleft[0], self.global_rect.topleft[1] - self.rect.topleft[1]
            
            # Strike button (bottom left)
            strike_button_rect = Rect(
                self.rect.x + padding,
                action_buttons_y,
                action_button_w,
                action_button_h,
            )
            self._strike_button_rect = strike_button_rect.move(offset)
            
            strike_hovered = self._strike_button_rect.collidepoint(mouse_pos)
            strike_color = (200, 100, 70) if strike_hovered else (170, 80, 55)
            draw_rect(surface, strike_color, strike_button_rect, border_radius=5)
            draw_rect(surface, (30, 40, 55), strike_button_rect, 1, border_radius=5)
            
            strike_text = "Strike"
            strike_surf = theme.font.render(strike_text, True, (245, 245, 245))
            strike_text_rect = strike_surf.get_rect(center=strike_button_rect.center)
            surface.blit(strike_surf, strike_text_rect)
            
            # Shoot button (next to Strike)
            shoot_button_rect = Rect(
                self.rect.x + padding + action_button_w + action_button_spacing,
                action_buttons_y,
                action_button_w,
                action_button_h,
            )
            self._shoot_button_rect = shoot_button_rect.move(offset)
            
            shoot_hovered = self._shoot_button_rect.collidepoint(mouse_pos)
            shoot_color = (70, 150, 200) if shoot_hovered else (55, 120, 170)
            draw_rect(surface, shoot_color, shoot_button_rect, border_radius=5)
            draw_rect(surface, (30, 40, 55), shoot_button_rect, 1, border_radius=5)
            
            shoot_text = "Shoot"
            shoot_surf = theme.font.render(shoot_text, True, (245, 245, 245))
            shoot_text_rect = shoot_surf.get_rect(center=shoot_button_rect.center)
            surface.blit(shoot_surf, shoot_text_rect)

        # Open sheet button (draw using local coords, hit-test using global coords)
        if self.show_action_buttons:
            button_w = 140
            button_h = 30
            button_rect = Rect(
                self.rect.right - padding - button_w,
                self.rect.bottom - padding - button_h,
                button_w,
                button_h,
            )
            offset = self.global_rect.topleft[0] - self.rect.topleft[0], self.global_rect.topleft[1] - self.rect.topleft[1]
            self._button_rect = button_rect.move(offset)

            hovered = self._button_rect.collidepoint(mouse_pos)
            button_color = (70, 120, 200) if hovered else (55, 95, 170)
            draw_rect(surface, button_color, button_rect, border_radius=5)
            draw_rect(surface, (30, 40, 55), button_rect, 1, border_radius=5)

            button_text = "Ouvrir fiche"
            button_surf = theme.font.render(button_text, True, (245, 245, 245))
            button_text_rect = button_surf.get_rect(center=button_rect.center)
            surface.blit(button_surf, button_text_rect)
