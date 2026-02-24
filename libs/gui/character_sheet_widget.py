# -*- coding: utf-8 -*-

"""
Character sheet widget for pygame_ui based apps.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
from random import randint
from os import listdir
from os.path import splitext

from pygame import Surface, Rect, MOUSEBUTTONUP, MOUSEWHEEL, mouse, KEYDOWN, K_ESCAPE, K_RETURN, K_BACKSPACE, K_DELETE, K_LEFT, K_RIGHT, K_UP, K_DOWN
from pygame.event import Event
from pygame.draw import rect as draw_rect, line as draw_line
from pygame.time import get_ticks
from pygame.font import SysFont

from .pygame_ui import UIWidget
from libs.dice import DiceCheck, Dice
from .spell_card_widget import SpellCardWidget
from .item_card_widget import ItemCardWidget

if TYPE_CHECKING:
    from libs.character import Character


class CharacterSheetWidget(UIWidget):
    """
    Display a character sheet with tabs for stats (with dice checks),
    modifiers, inventory and spells.
    """

    STAT_ORDER = ["str", "dex", "con", "int", "wis", "cha", "per", "agi", "luc", "sur"]
    RESOURCE_ORDER = ["hp", "stamina", "mental_health", "drug_health"]
    TABS = ["Stats", "Modifs", "Inventaire", "Sorts"]
    STAT_CAP = 250

    def __init__(
        self,
        parent: Optional[UIWidget],
        rect: Rect,
        character: Optional[Character] = None,
    ) -> None:
        super().__init__(parent, rect)
        self.character = character
        self.active_tab: int = 0
        self.scroll_y: int = 0
        self._max_scroll: int = 0
        self._dice_button_rects: dict[str, Rect] = {}
        self._popup_active: bool = False
        self._popup_stat: Optional[str] = None
        self._popup_roll_value: int = 1
        self._popup_animating: bool = False
        self._popup_anim_start_ms: int = 0
        self._popup_anim_end_ms: int = 0
        self._popup_next_tick_ms: int = 0
        self._popup_result_ms: int = 0
        self._popup_result: Optional[DiceCheck] = None
        self._popup_rect: Optional[Rect] = None
        self._popup_close_rect: Optional[Rect] = None
        self._popup_dice_font = SysFont("consolas", 44)
        self._popup_dice_small_font = SysFont("consolas", 14)
        self._modifier_input_rects: dict[str, Rect] = {}
        self._modifier_focused_stat: Optional[str] = None
        self._modifier_cursor_pos: int = 0
        self._modifier_text_buffer: str = ""
        self._inventory_add_mode: bool = False
        self._inventory_add_search: str = ""
        self._inventory_add_rect: Optional[Rect] = None
        self._inventory_add_list_rects: dict[str, Rect] = {}
        self._inventory_available_items: Optional[list[str]] = None
        self._inventory_card_widgets: dict[str, ItemCardWidget] = {}
        self._inventory_remove_buttons: dict[str, Rect] = {}
        self._spell_remove_rects: dict[str, Rect] = {}
        self._spell_card_widgets: dict[str, SpellCardWidget] = {}
        self._spell_add_button_rect: Optional[Rect] = None
        self._spell_add_mode: bool = False
        self._spell_add_search: str = ""
        self._spell_add_rect: Optional[Rect] = None
        self._spell_add_list_rects: dict[str, Rect] = {}
        self._spell_available_spells: Optional[list[str]] = None
        self._save_button_rect: Optional[Rect] = None

    def set_character(self, character: Optional[Character]) -> None:
        self.character = character
        self.scroll_y = 0
        self._max_scroll = 0
        self._popup_active = False
        self._popup_stat = None
        self._popup_result = None
        self._modifier_focused_stat = None
        self._modifier_text_buffer = ""
        self._modifier_cursor_pos = 0
        self._inventory_add_mode = False
        self._inventory_add_search = ""

    def _open_dice_popup(self, stat: str) -> None:
        self._popup_active = True
        self._popup_stat = stat
        self._popup_result = None
        self._popup_animating = True
        self._popup_roll_value = randint(1, 100)
        now = get_ticks()
        self._popup_anim_start_ms = now
        self._popup_anim_end_ms = now + 1450
        self._popup_next_tick_ms = now
        self._popup_result_ms = 0

    def _close_dice_popup(self) -> None:
        self._popup_active = False
        self._popup_stat = None
        self._popup_animating = False
        self._popup_result = None
        self._popup_result_ms = 0

    def _popup_progress(self) -> float:
        if not self._popup_animating:
            return 1.0
        duration = max(1, self._popup_anim_end_ms - self._popup_anim_start_ms)
        return max(0.0, min(1.0, (get_ticks() - self._popup_anim_start_ms) / duration))

    def _update_popup_animation(self) -> None:
        if not self._popup_animating or not self.character or not self._popup_stat:
            return

        now = get_ticks()
        if now < self._popup_anim_start_ms:
            return
        if now >= self._popup_anim_end_ms:
            self._popup_animating = False
            self._popup_result_ms = now
            self._popup_result = DiceCheck(Dice.roll("1d100"), self.character, self._popup_stat)
            return

        if now >= self._popup_next_tick_ms:
            self._popup_roll_value = randint(1, 100)
            self._popup_next_tick_ms = now + 60

    def _draw_overlay(self, surface: Surface) -> None:
        overlay = Surface(self.rect.size)
        overlay.set_alpha(140)
        overlay.fill((0, 0, 0))
        surface.blit(overlay, self.rect.topleft)

    def _to_local_pos(self, pos: tuple[int, int]) -> tuple[int, int]:
        offset_x = self.global_rect.x - self.rect.x
        offset_y = self.global_rect.y - self.rect.y
        return (pos[0] - offset_x, pos[1] - offset_y)

    def _render_popup_die(self, surface: Surface, popup_rect: Rect) -> None:
        progress = self._popup_progress() if self._popup_animating else 1.0
        shake = int((1.0 - progress) * 10) if self._popup_animating else 0
        jitter_x = randint(-shake, shake) if shake > 0 else 0
        jitter_y = randint(-shake, shake) if shake > 0 else 0

        size_base = 96
        pulse = int((1.0 - progress) * 12) if self._popup_animating else 0
        dice_size = size_base + pulse

        dice_rect = Rect(0, 0, dice_size, dice_size)
        dice_rect.center = (popup_rect.centerx + jitter_x, popup_rect.y + 102 + jitter_y)

        shadow_rect = Rect(dice_rect.x + 4, dice_rect.y + 5, dice_rect.width, dice_rect.height)
        draw_rect(surface, (20, 20, 20), shadow_rect, border_radius=14)

        draw_rect(surface, (240, 240, 240), dice_rect, border_radius=14)
        draw_rect(surface, (30, 30, 30), dice_rect, 2, border_radius=14)

        inset = dice_rect.inflate(-14, -14)
        draw_rect(surface, (252, 252, 252), inset, border_radius=10)

        value_surf = self._popup_dice_font.render(f"{self._popup_roll_value:02d}", True, (25, 25, 25))
        value_rect = value_surf.get_rect(center=dice_rect.center)
        surface.blit(value_surf, value_rect)

        d100_surf = self._popup_dice_small_font.render("d100", True, (70, 70, 70))
        d100_rect = d100_surf.get_rect(topright=(dice_rect.right - 8, dice_rect.y + 6))
        surface.blit(d100_surf, d100_rect)

        if self._popup_animating:
            phase = (get_ticks() // 90) % 4
            glow_color = (120, 220, 120)
            if phase in (0, 2):
                draw_line(surface, glow_color, (dice_rect.x - 12, dice_rect.centery), (dice_rect.x - 4, dice_rect.centery), 2)
                draw_line(surface, glow_color, (dice_rect.right + 4, dice_rect.centery), (dice_rect.right + 12, dice_rect.centery), 2)
            if phase in (1, 3):
                draw_line(surface, glow_color, (dice_rect.centerx, dice_rect.y - 12), (dice_rect.centerx, dice_rect.y - 4), 2)
                draw_line(surface, glow_color, (dice_rect.centerx, dice_rect.bottom + 4), (dice_rect.centerx, dice_rect.bottom + 12), 2)

    def _render_dice_popup(self, surface: Surface) -> None:
        if not self._popup_active or not self.character or not self._popup_stat:
            return

        self._update_popup_animation()
        self._draw_overlay(surface)

        theme = self.app.theme
        popup_w = min(420, self.rect.width - 40)
        popup_h = 230
        popup_rect = Rect(
            self.rect.centerx - popup_w // 2,
            self.rect.centery - popup_h // 2,
            popup_w,
            popup_h,
        )
        self._popup_rect = popup_rect
        close_rect = Rect(popup_rect.centerx - 56, popup_rect.bottom - 44, 112, 30)
        self._popup_close_rect = close_rect

        draw_rect(surface, theme.colors["bg"], popup_rect, border_radius=6)
        draw_rect(surface, (0, 0, 0), popup_rect, 2, border_radius=6)

        stat_total = self.character.get_current_stat(self._popup_stat)
        title = f"DiceCheck {self._popup_stat.upper()}"
        subtitle = f"Objectif: d100 <= {stat_total}"

        title_surf = theme.font.render(title, True, theme.colors["text"])
        subtitle_surf = theme.font.render(subtitle, True, theme.colors["text"])
        surface.blit(title_surf, (popup_rect.x + 14, popup_rect.y + 12))
        surface.blit(subtitle_surf, (popup_rect.x + 14, popup_rect.y + 40))

        self._render_popup_die(surface, popup_rect)

        if self._popup_animating:
            dots = "." * ((get_ticks() // 180) % 4)
            anim_text = theme.font.render(f"Lancement du d{dots}", True, theme.colors["text"])
            anim_rect = anim_text.get_rect(center=(popup_rect.centerx, popup_rect.y + 152))
            surface.blit(anim_text, anim_rect)
        elif self._popup_result:
            result_label = "SUCCESS" if self._popup_result.success else "ECHEC"
            result_color = (155, 255, 55) if self._popup_result.success else (255, 120, 120)
            result_surf = theme.font.render(result_label, True, result_color)
            result_rect = result_surf.get_rect(center=(popup_rect.centerx, popup_rect.y + 152))
            surface.blit(result_surf, result_rect)

            if get_ticks() - self._popup_result_ms <= 220:
                flash_rect = popup_rect.inflate(8, 8)
                draw_rect(surface, result_color, flash_rect, 3, border_radius=8)

        progress_track = Rect(popup_rect.x + 16, popup_rect.bottom - 62, popup_rect.width - 32, 8)
        draw_rect(surface, (35, 35, 35), progress_track, border_radius=4)
        progress_ratio = self._popup_progress() if self._popup_animating else 1.0
        progress_fill = Rect(
            progress_track.x,
            progress_track.y,
            int(progress_track.width * progress_ratio),
            progress_track.height,
        )
        draw_rect(surface, theme.colors["accent"], progress_fill, border_radius=4)

        local_mouse = self._to_local_pos(mouse.get_pos())
        hovered_close = close_rect.collidepoint(local_mouse)
        close_color = theme.colors["accent"] if hovered_close else theme.colors["hover"]
        draw_rect(surface, close_color, close_rect, border_radius=4)
        draw_rect(surface, (0, 0, 0), close_rect, 1, border_radius=4)
        close_surf = theme.font.render("Fermer", True, theme.colors["text"])
        close_text_rect = close_surf.get_rect(center=close_rect.center)
        surface.blit(close_surf, close_text_rect)

    def _stats_layout(self) -> tuple[int, int, int, int, int, int]:
        row_h = 28
        row_gap = 8
        label_w = 52
        value_w = 56
        button_w = 88
        top_margin = 8
        return row_h, row_gap, label_w, value_w, button_w, top_margin

    def _get_stat_rows(self, content_rect: Rect) -> list[tuple[str, Rect, Rect]]:
        row_h, row_gap, _, _, button_w, top_margin = self._stats_layout()
        rows: list[tuple[str, Rect, Rect]] = []
        right_padding = 6
        for index, stat in enumerate(self.STAT_ORDER):
            y = content_rect.y + top_margin + index * (row_h + row_gap) - self.scroll_y
            row_rect = Rect(content_rect.x + 4, y, content_rect.width - 8, row_h)
            button_rect = Rect(
                content_rect.right - right_padding - button_w,
                y + 2,
                button_w,
                row_h - 4,
            )
            rows.append((stat, row_rect, button_rect))
        return rows

    def _refresh_stats_scroll_bounds(self, content_rect: Rect) -> None:
        row_h, row_gap, _, _, _, top_margin = self._stats_layout()
        total_h = top_margin + len(self.STAT_ORDER) * (row_h + row_gap)
        self._max_scroll = max(0, total_h - content_rect.height)
        self.scroll_y = max(0, min(self.scroll_y, self._max_scroll))

    def _render_stats_tab(self, surface: Surface, content_rect: Rect) -> None:
        if not self.character:
            empty_surf = self.app.theme.font.render("Aucun personnage sélectionné.", True, self.app.theme.colors["text"])
            surface.blit(empty_surf, (content_rect.x + 8, content_rect.y + 8))
            return

        self._refresh_stats_scroll_bounds(content_rect)
        self._dice_button_rects = {}

        theme = self.app.theme
        _, _, label_w, value_w, button_w, _ = self._stats_layout()
        bar_x = content_rect.x + label_w + 14
        bar_right_limit = content_rect.right - value_w - button_w - 22
        bar_max_w = max(40, bar_right_limit - bar_x)
        px_per_stat = bar_max_w / self.STAT_CAP if self.STAT_CAP else 1
        mouse_pos = self._to_local_pos(mouse.get_pos())

        prev_clip = surface.get_clip()
        surface.set_clip(content_rect)

        for stat, row_rect, button_rect in self._get_stat_rows(content_rect):
            if row_rect.bottom < content_rect.top or row_rect.top > content_rect.bottom:
                continue

            base, modifier, inventory_mod, current = self._get_stat_breakdown(stat)
            total_extra = modifier + inventory_mod

            label_surf = theme.font.render(stat.upper(), True, theme.colors["text"])
            label_rect = label_surf.get_rect(midleft=(row_rect.x + 2, row_rect.centery))
            surface.blit(label_surf, label_rect)

            bar_bg_rect = Rect(bar_x, row_rect.centery - 6, bar_max_w, 12)
            draw_rect(surface, (20, 20, 20), bar_bg_rect)

            base_w = int(max(0, min(self.STAT_CAP, base)) * px_per_stat)
            base_w = min(base_w, bar_max_w)
            base_bar_rect = Rect(bar_x, row_rect.centery - 5, base_w, 10)
            draw_rect(surface, self._stat_color(base), base_bar_rect)

            if total_extra != 0 and base_w < bar_max_w:
                delta_w = int(abs(total_extra) * px_per_stat)
                delta_w = min(delta_w, bar_max_w - base_w)
                if delta_w > 0:
                    if total_extra > 0:
                        delta_rect = Rect(bar_x + base_w, row_rect.centery - 4, delta_w, 8)
                        draw_rect(surface, (255, 55, 155), delta_rect)
                    else:
                        neg_start = max(bar_x, bar_x + base_w - delta_w)
                        neg_w = (bar_x + base_w) - neg_start
                        if neg_w > 0:
                            delta_rect = Rect(neg_start, row_rect.centery - 4, neg_w, 8)
                            draw_rect(surface, (80, 170, 255), delta_rect)

            value_surf = theme.font.render(str(current), True, theme.colors["text"])
            value_rect = value_surf.get_rect(midright=(content_rect.right - button_w - 14, row_rect.centery))
            surface.blit(value_surf, value_rect)

            hovered_button = button_rect.collidepoint(mouse_pos)
            button_color = theme.colors["accent"] if hovered_button else theme.colors["hover"]
            draw_rect(surface, button_color, button_rect, border_radius=3)
            draw_rect(surface, (0, 0, 0), button_rect, 1, border_radius=3)
            btn_surf = theme.font.render("DiceCheck", True, theme.colors["text"])
            btn_rect = btn_surf.get_rect(center=button_rect.center)
            surface.blit(btn_surf, btn_rect)

            self._dice_button_rects[stat] = button_rect

        surface.set_clip(prev_clip)

    def _modifs_layout(self) -> tuple[int, int, int, int, int, int]:
        row_h = 28
        row_gap = 8
        label_w = 80
        base_w = 140
        input_w = 90
        top_margin = 8
        return row_h, row_gap, label_w, base_w, input_w, top_margin

    def _get_modifier_rows(self, content_rect: Rect) -> list[tuple[str, Rect, Rect, Rect]]:
        row_h, row_gap, label_w, base_w, input_w, top_margin = self._modifs_layout()
        rows: list[tuple[str, Rect, Rect, Rect]] = []
        for index, stat in enumerate(self.STAT_ORDER + self.RESOURCE_ORDER):
            y = content_rect.y + top_margin + index * (row_h + row_gap) - self.scroll_y
            row_rect = Rect(content_rect.x + 4, y, content_rect.width - 8, row_h)
            base_rect = Rect(row_rect.x + label_w + 10, y, base_w, row_h)
            input_rect = Rect(row_rect.x + label_w + base_w + 26, y, input_w, row_h)
            rows.append((stat, row_rect, base_rect, input_rect))
        return rows

    def _refresh_modifs_scroll_bounds(self, content_rect: Rect) -> None:
        row_h, row_gap, _, _, _, top_margin = self._modifs_layout()
        total_stats = len(self.STAT_ORDER) + len(self.RESOURCE_ORDER)
        total_h = top_margin + total_stats * (row_h + row_gap)
        self._max_scroll = max(0, total_h - content_rect.height)
        self.scroll_y = max(0, min(self.scroll_y, self._max_scroll))

    def _render_modifs_tab(self, surface: Surface, content_rect: Rect) -> None:
        if not self.character:
            empty_surf = self.app.theme.font.render("Aucun personnage sélectionné.", True, self.app.theme.colors["text"])
            surface.blit(empty_surf, (content_rect.x + 8, content_rect.y + 8))
            return

        self._refresh_modifs_scroll_bounds(content_rect)
        self._modifier_input_rects = {}

        theme = self.app.theme
        mouse_pos = self._to_local_pos(mouse.get_pos())

        prev_clip = surface.get_clip()
        surface.set_clip(content_rect)

        for stat, row_rect, base_rect, input_rect in self._get_modifier_rows(content_rect):
            if row_rect.bottom < content_rect.top or row_rect.top > content_rect.bottom:
                continue

            base_value = self._get_stat_base(stat)
            modifier_value = getattr(self.character.stats_modifiers, stat, 0)
            inventory_mod = self.character.inventory.get_stat_modifier(stat)
            total = base_value + modifier_value + inventory_mod

            label_text = f"{stat.upper()}"
            label_surf = theme.font.render(label_text, True, theme.colors["text"])
            label_rect_centered = label_surf.get_rect(midleft=(row_rect.x + 4, row_rect.centery))
            surface.blit(label_surf, label_rect_centered)

            base_text = f"Base: {base_value}"
            base_surf = theme.font.render(base_text, True, theme.colors["text"])
            base_text_rect = base_surf.get_rect(midleft=(base_rect.x + 4, base_rect.centery))
            surface.blit(base_surf, base_text_rect)

            is_focused = self._modifier_focused_stat == stat
            hovered_input = input_rect.collidepoint(mouse_pos)
            input_color = theme.colors["accent"] if is_focused else theme.colors["hover"] if hovered_input else (50, 50, 50)
            draw_rect(surface, input_color, input_rect, border_radius=3)
            draw_rect(surface, (0, 0, 0), input_rect, 1, border_radius=3)

            if is_focused:
                text_display = self._modifier_text_buffer
            else:
                text_display = self._format_signed(modifier_value)

            text_surf = theme.font.render(text_display, True, theme.colors["text"])
            text_render_rect = text_surf.get_rect(midleft=(input_rect.x + 6, input_rect.centery))
            surface.blit(text_surf, text_render_rect)

            if is_focused:
                cursor_x = input_rect.x + 6 + theme.font.size(text_display[:self._modifier_cursor_pos])[0]
                cursor_top = input_rect.centery - 8
                cursor_bottom = input_rect.centery + 8
                if (get_ticks() // 400) % 2 == 0:
                    draw_line(surface, theme.colors["text"], (cursor_x, cursor_top), (cursor_x, cursor_bottom), 1)

            total_text = f"Total: {total}"
            total_surf = theme.font.render(total_text, True, theme.colors["text"])
            total_rect = total_surf.get_rect(midleft=(input_rect.right + 18, row_rect.centery))
            surface.blit(total_surf, total_rect)

            self._modifier_input_rects[stat] = input_rect

        surface.set_clip(prev_clip)

    def _handle_modifier_input(self, event: Event) -> bool:
        if not self.character or not self._modifier_focused_stat:
            return False

        if event.type != KEYDOWN:
            return False

        current_value = getattr(self.character.stats_modifiers, self._modifier_focused_stat, 0)

        if event.key == K_RETURN:
            try:
                new_value = int(self._modifier_text_buffer) if self._modifier_text_buffer else 0
            except ValueError:
                new_value = current_value
            setattr(self.character.stats_modifiers, self._modifier_focused_stat, new_value)
            self._modifier_focused_stat = None
            self._modifier_text_buffer = ""
            self._modifier_cursor_pos = 0
            return True
        if event.key == K_ESCAPE:
            self._modifier_focused_stat = None
            self._modifier_text_buffer = ""
            self._modifier_cursor_pos = 0
            return True
        if event.key == K_BACKSPACE:
            if self._modifier_cursor_pos > 0:
                self._modifier_text_buffer = (
                    self._modifier_text_buffer[:self._modifier_cursor_pos - 1] +
                    self._modifier_text_buffer[self._modifier_cursor_pos:]
                )
                self._modifier_cursor_pos -= 1
            return True
        if event.key == K_DELETE:
            if self._modifier_cursor_pos < len(self._modifier_text_buffer):
                self._modifier_text_buffer = (
                    self._modifier_text_buffer[:self._modifier_cursor_pos] +
                    self._modifier_text_buffer[self._modifier_cursor_pos + 1:]
                )
            return True
        if event.key == K_LEFT:
            if self._modifier_cursor_pos > 0:
                self._modifier_cursor_pos -= 1
            return True
        if event.key == K_RIGHT:
            if self._modifier_cursor_pos < len(self._modifier_text_buffer):
                self._modifier_cursor_pos += 1
            return True
        if event.key == K_UP:
            new_value = current_value + 1
            self._modifier_text_buffer = str(new_value)
            self._modifier_cursor_pos = len(self._modifier_text_buffer)
            setattr(self.character.stats_modifiers, self._modifier_focused_stat, new_value)
            return True
        if event.key == K_DOWN:
            new_value = current_value - 1
            self._modifier_text_buffer = str(new_value)
            self._modifier_cursor_pos = len(self._modifier_text_buffer)
            setattr(self.character.stats_modifiers, self._modifier_focused_stat, new_value)
            return True
        if event.unicode and event.unicode in ["+", "-"]:
            if self._modifier_text_buffer.startswith("+") or self._modifier_text_buffer.startswith("-"):
                self._modifier_text_buffer = event.unicode + self._modifier_text_buffer[1:]
            else:
                self._modifier_text_buffer = event.unicode + self._modifier_text_buffer
            self._modifier_cursor_pos = len(self._modifier_text_buffer)
            return True
        if event.unicode and (event.unicode.isdigit() or event.unicode == "-"):
            if len(self._modifier_text_buffer) < 6:
                self._modifier_text_buffer = (
                    self._modifier_text_buffer[:self._modifier_cursor_pos] +
                    event.unicode +
                    self._modifier_text_buffer[self._modifier_cursor_pos:]
                )
                self._modifier_cursor_pos += 1
                return True

        return False

    def _handle_inventory_input(self, event: Event) -> bool:
        """Handle keyboard input for inventory item search."""
        if not self.character or not self._inventory_add_mode:
            return False

        if event.type != KEYDOWN:
            return False

        if event.key == K_ESCAPE:
            self._inventory_add_mode = False
            self._inventory_add_search = ""
            return True
        if event.key == K_BACKSPACE:
            if self._inventory_add_search:
                self._inventory_add_search = self._inventory_add_search[:-1]
            return True
        if event.key == K_RETURN:
            available = self._get_available_items()
            search_lower = self._inventory_add_search.lower()
            filtered = [
                item for item in available
                if search_lower in item.lower() and item not in self.character.inventory.items
            ]
            if filtered:
                self.character.inventory.add_item(filtered[0])
                self._inventory_add_mode = False
                self._inventory_add_search = ""
            return True

        if event.unicode and event.unicode.isprintable() and len(self._inventory_add_search) < 40:
            self._inventory_add_search += event.unicode
            return True

        return False

    def _handle_spell_add_input(self, event: Event) -> bool:
        """Handle keyboard input for spell search."""
        if not self.character or not self._spell_add_mode:
            return False

        if event.type != KEYDOWN:
            return False

        if event.key == K_ESCAPE:
            self._spell_add_mode = False
            self._spell_add_search = ""
            return True
        if event.key == K_BACKSPACE:
            if self._spell_add_search:
                self._spell_add_search = self._spell_add_search[:-1]
            return True
        if event.key == K_RETURN:
            available = self._get_available_spells()
            search_lower = self._spell_add_search.lower()
            filtered = [
                spell for spell in available
                if search_lower in spell.lower() and spell not in self.character.spells
            ]
            if filtered:
                from libs.spell import Spell

                spell_obj = Spell.from_name(filtered[0])
                if spell_obj:
                    self.character.spells[filtered[0]] = spell_obj
                self._spell_add_mode = False
                self._spell_add_search = ""
            return True

        if event.unicode and event.unicode.isprintable() and len(self._spell_add_search) < 40:
            self._spell_add_search += event.unicode
            return True

        return False

    def _format_signed(self, value: int) -> str:
        return f"{value:+}" if value >= 0 else str(value)

    def _get_stat_base(self, stat: str) -> int:
        if not self.character:
            return 0
        return getattr(self.character.stats, stat, 0)

    def _get_stat_breakdown(self, stat: str) -> tuple[int, int, int, int]:
        if not self.character:
            return 0, 0, 0, 0
        base_value = getattr(self.character.stats, stat, 0)
        modifier_value = getattr(self.character.stats_modifiers, stat, 0)
        inventory_mod = self.character.inventory.get_stat_modifier(stat)
        current_value = base_value + modifier_value + inventory_mod
        return base_value, modifier_value, inventory_mod, current_value

    def _stat_color(self, base_stat_value: int) -> tuple[int, int, int]:
        if base_stat_value <= 30:
            return (255, 0, 0)
        if base_stat_value <= 50:
            return (255, 155, 0)
        if base_stat_value <= 100:
            return (155, 255, 55)
        return (55, 155, 255)

    def _refresh_inventory_scroll_bounds(self, content_rect: Rect) -> None:
        """Calculate scroll bounds for inventory tab using card heights."""
        if not self.character:
            self._max_scroll = 0
            return
        
        from libs.item import Item
        
        y_offset = 10
        card_margin = 10
        remove_button_size = 26
        remove_button_margin = 4
        
        # Calculate total height by summing card heights
        items = self.character.inventory.to_list()
        card_w = content_rect.width - 16 - remove_button_size - remove_button_margin
        
        for item_name, quantity in items:
            item = Item.from_name(item_name)
            if not item:
                continue
            
            # Get or create widget to calculate height
            if item_name not in self._inventory_card_widgets:
                self._inventory_card_widgets[item_name] = ItemCardWidget(
                    parent=self,
                    rect=Rect(0, 0, 100, 100),
                    item=item,
                    item_name=item_name,
                    quantity=quantity
                )
            
            widget = self._inventory_card_widgets[item_name]
            card_h = widget.get_required_height(card_w)
            y_offset += card_h + card_margin
        
        # Add space for "Add item" section
        add_section_h = 150
        total_h = y_offset + 20 + add_section_h
        
        self._max_scroll = max(0, total_h - content_rect.height)
        self.scroll_y = max(0, min(self.scroll_y, self._max_scroll))

    def _render_inventory_tab(self, surface: Surface, content_rect: Rect) -> None:
        """Render inventory tab with item cards."""
        if not self.character:
            return
        
        self._refresh_inventory_scroll_bounds(content_rect)
        self._inventory_remove_buttons = {}

        theme = self.app.theme
        mouse_pos = self._to_local_pos(mouse.get_pos())

        prev_clip = surface.get_clip()
        surface.set_clip(content_rect)

        # Calculate positions for item cards
        y_offset = 10
        card_margin = 10
        remove_button_size = 26
        remove_button_margin = 4
        
        items = self.character.inventory.to_list()
        
        for item_name, quantity in items:
            # Load item from assets
            from libs.item import Item
            item = Item.from_name(item_name)
            if not item:
                continue
            
            # Create widget if not exists, or update item
            if item_name not in self._inventory_card_widgets:
                self._inventory_card_widgets[item_name] = ItemCardWidget(
                    parent=self,
                    rect=Rect(0, 0, 100, 100),
                    item=item,
                    item_name=item_name,
                    quantity=quantity
                )
            else:
                self._inventory_card_widgets[item_name].set_item(item, item_name, quantity)
            
            widget = self._inventory_card_widgets[item_name]
            
            # Calculate widget dimensions
            card_w = content_rect.width - 16 - remove_button_size - remove_button_margin
            card_h = widget.get_required_height(card_w)
            
            # Position card with scroll offset (leave space for remove button on the left)
            card_y = content_rect.y + y_offset - self.scroll_y
            card_x = content_rect.x + 8 + remove_button_size + remove_button_margin
            card_rect = Rect(card_x, card_y, card_w, card_h)
            
            # Update widget rect
            widget.rect = card_rect
            
            # Only render if visible in content area
            if card_rect.bottom >= content_rect.top and card_rect.top <= content_rect.bottom:
                widget.render(surface)
                
                # Render remove button to the left of the card
                remove_rect = Rect(content_rect.x + 8, card_y + 4, remove_button_size, remove_button_size)
                hovered_remove = remove_rect.collidepoint(mouse_pos)
                remove_color = (200, 50, 50) if hovered_remove else (150, 50, 50)
                draw_rect(surface, remove_color, remove_rect, border_radius=3)
                draw_rect(surface, (0, 0, 0), remove_rect, 1, border_radius=3)
                
                remove_surf = theme.font.render("X", True, (255, 255, 255))
                remove_text_rect = remove_surf.get_rect(center=remove_rect.center)
                surface.blit(remove_surf, remove_text_rect)
                
                self._inventory_remove_buttons[item_name] = remove_rect
            
            y_offset += card_h + card_margin

        # Add item section
        add_y = content_rect.y + y_offset + 20 - self.scroll_y
        
        if add_y < content_rect.bottom:
            separator_y = add_y - 15
            if separator_y > content_rect.y:
                draw_line(surface, (100, 100, 100), 
                         (content_rect.x + 10, separator_y),
                         (content_rect.right - 10, separator_y), 1)

            add_label = theme.font.render("Ajouter un objet:", True, theme.colors["text"])
            surface.blit(add_label, (content_rect.x + 10, add_y))

            # Position search box to the right of the label
            label_width = add_label.get_width()
            search_rect = Rect(content_rect.x + 20 + label_width, add_y - 2, 220, 26)
            self._inventory_add_rect = search_rect
            
            hovered_search = search_rect.collidepoint(mouse_pos)
            search_color = theme.colors["accent"] if self._inventory_add_mode else theme.colors["hover"] if hovered_search else (50, 50, 50)
            draw_rect(surface, search_color, search_rect, border_radius=3)
            draw_rect(surface, (0, 0, 0), search_rect, 1, border_radius=3)

            search_text = self._inventory_add_search if self._inventory_add_mode else "Rechercher..."
            search_surf = theme.font.render(search_text, True, theme.colors["text"] if self._inventory_add_mode else (150, 150, 150))
            search_text_rect = search_surf.get_rect(midleft=(search_rect.x + 6, search_rect.centery))
            surface.blit(search_surf, search_text_rect)

            # Show filtered item list if in add mode
            if self._inventory_add_mode:
                available = self._get_available_items()
                search_lower = self._inventory_add_search.lower()
                filtered = [item for item in available if search_lower in item.lower() and item not in self.character.inventory.items]
                
                self._inventory_add_list_rects = {}
                list_y = add_y + 28
                for idx, item_name in enumerate(filtered[:10]):  # Limit to 10 results
                    item_rect = Rect(content_rect.x + 10, list_y + idx * 26, content_rect.width - 20, 24)
                    if item_rect.bottom > content_rect.bottom:
                        break
                    
                    hovered_item = item_rect.collidepoint(mouse_pos)
                    item_bg = theme.colors["hover"] if hovered_item else (40, 40, 45)
                    draw_rect(surface, item_bg, item_rect, border_radius=3)
                    draw_rect(surface, (80, 80, 85), item_rect, 1, border_radius=3)
                    
                    item_surf = theme.font.render(item_name, True, theme.colors["text"])
                    item_text_rect = item_surf.get_rect(midleft=(item_rect.x + 8, item_rect.centery))
                    surface.blit(item_surf, item_text_rect)
                    
                    self._inventory_add_list_rects[item_name] = item_rect

        surface.set_clip(prev_clip)

    def _get_available_items(self) -> list[str]:
        if self._inventory_available_items is None:
            self._inventory_available_items = []
            for filename in listdir("assets/items"):
                if filename.endswith(".json"):
                    self._inventory_available_items.append(splitext(filename)[0])
            self._inventory_available_items.sort()
        return self._inventory_available_items

    def _refresh_spells_scroll_bounds(self, content_rect: Rect) -> None:
        if not self.character:
            self._max_scroll = 0
            return

        total_h = 10
        card_margin = 12
        for spell_key, spell in self.character.spells.items():
            if spell_key not in self._spell_card_widgets:
                self._spell_card_widgets[spell_key] = SpellCardWidget(
                    parent=self,
                    rect=Rect(0, 0, 100, 100),
                    spell=spell,
                    spell_key=spell_key,
                    owner=self.character
                )
            card_w = content_rect.width - 16 - 28 - 4
            card_h = self._spell_card_widgets[spell_key].get_required_height(card_w)
            total_h += card_h + card_margin

        total_h += 40 + card_margin

        if self._spell_add_mode:
            total_h += 30  # Label and search box
            available = self._get_available_spells()
            search_lower = self._spell_add_search.lower()
            filtered = [spell for spell in available if search_lower in spell.lower() and spell not in self.character.spells]
            total_h += min(len(filtered), 10) * 28  # List items (max 10)
        
        self._max_scroll = max(0, total_h - content_rect.height)
        self.scroll_y = max(0, min(self.scroll_y, self._max_scroll))

    def _render_spells_tab(self, surface: Surface, content_rect: Rect) -> None:
        """Render spells tab with detailed spell cards."""
        if not self.character:
            return
        
        self._refresh_spells_scroll_bounds(content_rect)
        self._spell_remove_rects = {}
        
        mouse_pos = self._to_local_pos(mouse.get_pos())
        
        prev_clip = surface.get_clip()
        surface.set_clip(content_rect)
        
        # Calculate positions for spell cards
        y_offset = 10
        card_margin = 12
        
        for spell_key, spell in self.character.spells.items():
            # Create widget if not exists, or update spell
            if spell_key not in self._spell_card_widgets:
                # Dummy rect, will be updated below
                self._spell_card_widgets[spell_key] = SpellCardWidget(
                    parent=self,
                    rect=Rect(0, 0, 100, 100),
                    spell=spell,
                    spell_key=spell_key,
                    owner=self.character
                )
            else:
                self._spell_card_widgets[spell_key].set_spell(spell, spell_key)
            
            widget = self._spell_card_widgets[spell_key]
            
            # Calculate widget dimensions
            remove_button_size = 28
            remove_button_margin = 4
            card_w = content_rect.width - 16 - remove_button_size - remove_button_margin
            card_h = widget.get_required_height(card_w)
            
            # Position card with scroll offset (leave space for remove button on the left)
            card_y = content_rect.y + y_offset - self.scroll_y
            card_x = content_rect.x + 8 + remove_button_size + remove_button_margin
            card_rect = Rect(card_x, card_y, card_w, card_h)
            
            # Update widget rect
            widget.rect = card_rect
            
            # Only render if visible in content area
            if card_rect.bottom >= content_rect.top and card_rect.top <= content_rect.bottom:
                widget.render(surface)
                
                # Render remove button to the left of the card
                remove_rect = Rect(content_rect.x + 8, card_y + 4, remove_button_size, remove_button_size)
                hovered_remove = remove_rect.collidepoint(mouse_pos)
                remove_color = (200, 50, 50) if hovered_remove else (150, 50, 50)
                draw_rect(surface, remove_color, remove_rect, border_radius=3)
                draw_rect(surface, (0, 0, 0), remove_rect, 1, border_radius=3)
                
                theme = self.app.theme
                remove_surf = theme.font.render("X", True, (255, 255, 255))
                remove_text_rect = remove_surf.get_rect(center=remove_rect.center)
                surface.blit(remove_surf, remove_text_rect)
                
                self._spell_remove_rects[spell_key] = remove_rect
            
            y_offset += card_h + card_margin
        
        # Add "Add Spell" button at the end
        button_w = 150
        button_h = 40
        button_y = content_rect.y + y_offset - self.scroll_y
        add_button_rect = Rect(content_rect.x + 8, button_y, button_w, button_h)
        
        # Only render if visible
        if add_button_rect.bottom >= content_rect.top and add_button_rect.top <= content_rect.bottom:
            self._spell_add_button_rect = add_button_rect
            
            hovered_add = add_button_rect.collidepoint(mouse_pos)
            add_color = (70, 120, 200) if hovered_add else (50, 100, 180)
            draw_rect(surface, add_color, add_button_rect, border_radius=5)
            draw_rect(surface, (100, 150, 220), add_button_rect, 2, border_radius=5)
            
            theme = self.app.theme
            add_text = "+ Add Spell"
            add_surf = theme.font.render(add_text, True, (255, 255, 255))
            add_text_rect = add_surf.get_rect(center=add_button_rect.center)
            surface.blit(add_surf, add_text_rect)
        else:
            self._spell_add_button_rect = None
        
        y_offset += button_h + card_margin
        
        # Show spell selection interface if in add mode
        if self._spell_add_mode:
            theme = self.app.theme
            
            # Separator
            separator_y = content_rect.y + y_offset - self.scroll_y - 15
            if separator_y > content_rect.y and separator_y < content_rect.bottom:
                draw_line(surface, (100, 100, 100), 
                         (content_rect.x + 10, separator_y),
                         (content_rect.right - 10, separator_y), 1)
            
            # Label and search box
            label_y = content_rect.y + y_offset - self.scroll_y
            add_label = theme.font.render("Rechercher un sort:", True, theme.colors["text"])
            if label_y > content_rect.y and label_y < content_rect.bottom:
                surface.blit(add_label, (content_rect.x + 10, label_y))
            
            label_width = add_label.get_width()
            search_rect = Rect(content_rect.x + 20 + label_width, label_y - 2, 220, 26)
            self._spell_add_rect = search_rect
            
            if search_rect.bottom > content_rect.top and search_rect.top < content_rect.bottom:
                hovered_search = search_rect.collidepoint(mouse_pos)
                search_color = theme.colors["accent"] if hovered_search else (50, 50, 50)
                draw_rect(surface, search_color, search_rect, border_radius=3)
                draw_rect(surface, (0, 0, 0), search_rect, 1, border_radius=3)
                
                search_text = self._spell_add_search if self._spell_add_search else "Rechercher..."
                search_surf = theme.font.render(search_text, True, theme.colors["text"] if self._spell_add_search else (150, 150, 150))
                search_text_rect = search_surf.get_rect(midleft=(search_rect.x + 6, search_rect.centery))
                surface.blit(search_surf, search_text_rect)
            
            # Show filtered spell list
            available = self._get_available_spells()
            search_lower = self._spell_add_search.lower()
            filtered = [spell for spell in available if search_lower in spell.lower() and spell not in self.character.spells]
            
            self._spell_add_list_rects = {}
            list_y = label_y + 28
            for idx, spell_name in enumerate(filtered[:10]):  # Limit to 10 results
                spell_rect = Rect(content_rect.x + 10, list_y + idx * 28, content_rect.width - 20, 26)
                if spell_rect.bottom > content_rect.bottom:
                    break
                
                if spell_rect.top >= content_rect.top:
                    hovered_spell = spell_rect.collidepoint(mouse_pos)
                    spell_bg = theme.colors["hover"] if hovered_spell else (40, 40, 45)
                    draw_rect(surface, spell_bg, spell_rect, border_radius=3)
                    draw_rect(surface, (80, 80, 85), spell_rect, 1, border_radius=3)
                    
                    spell_surf = theme.font.render(spell_name, True, theme.colors["text"])
                    spell_text_rect = spell_surf.get_rect(midleft=(spell_rect.x + 8, spell_rect.centery))
                    surface.blit(spell_surf, spell_text_rect)
                    
                    self._spell_add_list_rects[spell_name] = spell_rect
        
        surface.set_clip(prev_clip)

    def _get_available_spells(self) -> list[str]:
        if self._spell_available_spells is None:
            self._spell_available_spells = []
            for filename in listdir("assets/spells"):
                if filename.endswith(".json"):
                    self._spell_available_spells.append(splitext(filename)[0])
            self._spell_available_spells.sort()
        return self._spell_available_spells

    def _build_stats_lines(self) -> list[str]:
        if not self.character:
            return ["Aucun personnage sélectionné."]
        lines = []
        for stat in self.STAT_ORDER + self.RESOURCE_ORDER:
            _, modifier, inventory_mod, current = self._get_stat_breakdown(stat)
            line = f"{stat.upper():<8} {current:<4}"
            if modifier != 0:
                line += f" ({self._format_signed(modifier)})"
            if inventory_mod != 0:
                line += f" [{self._format_signed(inventory_mod)}]"
            lines.append(line)
        return lines

    def _build_mod_lines(self) -> list[str]:
        lines: list[str] = []
        if not self.character:
            return lines
        for stat_name, value in self.character.stats_modifiers.dict.items():
            if value != 0:
                lines.append(f"{stat_name.upper():<14} {self._format_signed(value)}")
        if not lines:
            lines.append("Aucun modificateur actif.")
        return lines

    def _build_inventory_lines(self) -> list[str]:
        if not self.character:
            return []
        items = self.character.inventory.to_list()
        if not items:
            return ["Inventaire vide."]
        return [f"x{quantity:<3} {name}" for name, quantity in items]

    def _build_spells_lines(self) -> list[str]:
        if not self.character:
            return []
        spells = list(self.character.spells.values())
        if not spells:
            return ["Aucun sort appris."]
        lines: list[str] = []
        for spell in spells:
            lines.append(f"{spell.name} (coût: {spell.cost})")
            if spell.description:
                lines.append(f"  {spell.description}")
        return lines

    def _current_lines(self) -> list[str]:
        if not self.character:
            return ["Aucun personnage sélectionné."]
        if self.active_tab == 0:
            return self._build_stats_lines()
        if self.active_tab == 1:
            return self._build_mod_lines()
        if self.active_tab == 2:
            return self._build_inventory_lines()
        return self._build_spells_lines()

    def _refresh_scroll_bounds(self, lines_count: int) -> None:
        content_h = self._content_rect().height
        total_h = lines_count * self._line_height()
        self._max_scroll = max(0, total_h - content_h)
        self.scroll_y = max(0, min(self.scroll_y, self._max_scroll))

    def handle_event(self, event: Event) -> bool:
        if not self.displayed:
            return False

        if self._popup_active:
            if event.type == KEYDOWN and event.key in (K_ESCAPE, K_RETURN):
                if not self._popup_animating:
                    self._close_dice_popup()
                return True
            if event.type == MOUSEBUTTONUP and event.button == 1:
                local_pos = self._to_local_pos(event.pos)
                if self._popup_close_rect and self._popup_close_rect.collidepoint(local_pos):
                    if not self._popup_animating:
                        self._close_dice_popup()
                    return True
                if self._popup_rect and self._popup_rect.collidepoint(local_pos):
                    return True
                return True
            if event.type == MOUSEWHEEL:
                return True
            return False

        if event.type == MOUSEBUTTONUP and event.button == 1:
            # Check if click is within widget bounds
            if not self.global_rect.collidepoint(event.pos):
                return False

            local_pos = self._to_local_pos(event.pos)
            
            # Handle Save button click
            if self._save_button_rect and self._save_button_rect.collidepoint(local_pos):
                if self.character:
                    self.character.save()
                    from libs import logger
                    logger.info(f"Character '{self.character.name}' saved successfully")
                return True
                
            for index, tab_rect in enumerate(self._tab_rects()):
                if tab_rect.collidepoint(local_pos):
                    self.active_tab = index
                    self.scroll_y = 0
                    self.app.focused_widget = self
                    return True

            if self.active_tab == 0 and self.character:
                for stat, button_rect in self._dice_button_rects.items():
                    if button_rect.collidepoint(local_pos):
                        self._open_dice_popup(stat)
                        self.app.focused_widget = self
                        return True

            if self.active_tab == 1 and self.character:
                for stat, input_rect in self._modifier_input_rects.items():
                    if input_rect.collidepoint(local_pos):
                        self._modifier_focused_stat = stat
                        current_modifier = getattr(self.character.stats_modifiers, stat, 0)
                        self._modifier_text_buffer = str(current_modifier)
                        self._modifier_cursor_pos = len(self._modifier_text_buffer)
                        self.app.focused_widget = self
                        return True

            if self.active_tab == 2 and self.character:
                # Handle quantity buttons in item cards
                for item_name, widget in self._inventory_card_widgets.items():
                    if widget.handle_event(event):
                        # Quantity changed
                        if widget.quantity == 0:
                            # Remove item from inventory
                            if item_name in self.character.inventory.items:
                                del self.character.inventory.items[item_name]
                            # Remove widget from cache
                            if item_name in self._inventory_card_widgets:
                                del self._inventory_card_widgets[item_name]
                        else:
                            # Update quantity in inventory
                            self.character.inventory.items[item_name] = widget.quantity
                        return True
                
                # Handle remove button clicks
                for item_name, remove_rect in self._inventory_remove_buttons.items():
                    if remove_rect.collidepoint(local_pos):
                        if item_name in self.character.inventory.items:
                            del self.character.inventory.items[item_name]
                            # Remove widget from cache
                            if item_name in self._inventory_card_widgets:
                                del self._inventory_card_widgets[item_name]
                        return True
                
                # Handle add search box click
                if self._inventory_add_rect and self._inventory_add_rect.collidepoint(local_pos):
                    self._inventory_add_mode = True
                    self._inventory_add_search = ""
                    self.app.focused_widget = self
                    return True
                
                # Handle add list item clicks
                for item_name, item_rect in self._inventory_add_list_rects.items():
                    if item_rect.collidepoint(local_pos):
                        self.character.inventory.add_item(item_name)
                        self._inventory_add_mode = False
                        self._inventory_add_search = ""
                        return True

            if self.active_tab == 3 and self.character:
                # Handle Remove Spell button clicks
                for spell_name, remove_rect in self._spell_remove_rects.items():
                    if remove_rect.collidepoint(local_pos):
                        if spell_name in self.character.spells:
                            del self.character.spells[spell_name]
                            # Also remove the widget
                            if spell_name in self._spell_card_widgets:
                                del self._spell_card_widgets[spell_name]
                        return True
                
                # Handle Cast Spell button clicks via widget
                for widget in self._spell_card_widgets.values():
                    if widget.handle_event(event):
                        return True
                
                # Handle Add Spell button click
                if self._spell_add_button_rect and self._spell_add_button_rect.collidepoint(local_pos):
                    self._spell_add_mode = True
                    self._spell_add_search = ""
                    self.app.focused_widget = self
                    return True
                
                # Handle spell search box click
                if self._spell_add_rect and self._spell_add_rect.collidepoint(local_pos):
                    self._spell_add_mode = True
                    self.app.focused_widget = self
                    return True
                
                # Handle spell list item clicks
                for spell_name, spell_rect in self._spell_add_list_rects.items():
                    if spell_rect.collidepoint(local_pos):
                        from libs.spell import Spell
                        spell_obj = Spell.from_name(spell_name)
                        if spell_obj:
                            self.character.spells[spell_name] = spell_obj
                        self._spell_add_mode = False
                        self._spell_add_search = ""
                        return True

        if self.active_tab == 1 and self._modifier_focused_stat:
            if self._handle_modifier_input(event):
                return True

        if self.active_tab == 2 and self._inventory_add_mode:
            if self._handle_inventory_input(event):
                return True
        
        if self.active_tab == 3 and self._spell_add_mode:
            if self._handle_spell_add_input(event):
                return True

        if event.type == MOUSEWHEEL:
            # Check if mouse is within widget bounds
            mouse_pos = self._to_local_pos(mouse.get_pos())
            if self.global_rect.collidepoint(mouse_pos):
                step = self._line_height() * 2
                self.scroll_y -= event.y * step
                self.scroll_y = max(0, min(self.scroll_y, self._max_scroll))
                return True

        return super().handle_event(event)

    def render(self, surface: Surface) -> None:
        if not self.displayed:
            return

        theme = self.app.theme
        content_rect = self._content_rect()

        draw_rect(surface, theme.colors["bg"], self.rect)
        draw_rect(surface, (0, 0, 0), self.rect, 2)

        if self.character:
            # Title (bold, larger font)
            title = f"Fiche personnage: {self.character.name}"
            title_font = SysFont("arial", 22, bold=True)
            title_surf = title_font.render(title, True, theme.colors["text"])
            surface.blit(title_surf, (self.rect.x + 10, self.rect.y + 8))
            
            # Save button (aligned with title, to the right of it)
            mouse_pos = self._to_local_pos(mouse.get_pos())
            save_button_w = 70
            save_button_h = 26
            title_width = title_surf.get_width()
            save_button_x = self.rect.x + 20 + title_width
            save_button_y = self.rect.y + 8
            self._save_button_rect = Rect(save_button_x, save_button_y, save_button_w, save_button_h)
            
            hovered_save = self._save_button_rect.collidepoint(mouse_pos)
            save_color = (70, 150, 70) if hovered_save else (50, 120, 50)
            draw_rect(surface, save_color, self._save_button_rect, border_radius=4)
            draw_rect(surface, (100, 180, 100), self._save_button_rect, 2, border_radius=4)
            
            save_text = "Save"
            save_surf = theme.font.render(save_text, True, (255, 255, 255))
            save_text_rect = save_surf.get_rect(center=self._save_button_rect.center)
            surface.blit(save_surf, save_text_rect)
            
            # Level (15px below title)
            level_text = f"Niveau {self.character.stats.lvl}"
            level_surf = theme.font.render(level_text, True, theme.colors["text"])
            surface.blit(level_surf, (self.rect.x + 10, self.rect.y + 8 + 26 + 15))
            
            # HP and Stamina bars (right side, stacked)
            hp_base, _, _, hp_current = self._get_stat_breakdown("hp")
            stamina_base, _, _, stamina_current = self._get_stat_breakdown("stamina")
            
            bar_w = 250
            bar_h = 20
            bar_x = self.rect.right - bar_w - 10
            hp_bar_y = self.rect.y + 10
            stamina_bar_y = hp_bar_y + bar_h + 6
            
            # HP bar
            draw_rect(surface, (50, 50, 50), Rect(bar_x, hp_bar_y, bar_w, bar_h), border_radius=3)
            if hp_base > 0:
                hp_fill_w = int((hp_current / hp_base) * bar_w)
                hp_fill_w = max(0, min(hp_fill_w, bar_w))
                draw_rect(surface, (200, 50, 50), Rect(bar_x, hp_bar_y, hp_fill_w, bar_h), border_radius=3)
            hp_text = f"HP: {hp_current}/{hp_base}"
            hp_text_surf = theme.font.render(hp_text, True, theme.colors["text"])
            hp_text_rect = hp_text_surf.get_rect(center=(bar_x + bar_w // 2, hp_bar_y + bar_h // 2))
            surface.blit(hp_text_surf, hp_text_rect)
            
            # Stamina bar
            draw_rect(surface, (50, 50, 50), Rect(bar_x, stamina_bar_y, bar_w, bar_h), border_radius=3)
            if stamina_base > 0:
                stamina_fill_w = int((stamina_current / stamina_base) * bar_w)
                stamina_fill_w = max(0, min(stamina_fill_w, bar_w))
                draw_rect(surface, (50, 200, 50), Rect(bar_x, stamina_bar_y, stamina_fill_w, bar_h), border_radius=3)
            stamina_text = f"Stamina: {stamina_current}/{stamina_base}"
            stamina_text_surf = theme.font.render(stamina_text, True, theme.colors["text"])
            stamina_text_rect = stamina_text_surf.get_rect(center=(bar_x + bar_w // 2, stamina_bar_y + bar_h // 2))
            surface.blit(stamina_text_surf, stamina_text_rect)
        
        # Render tabs and content
        self._render_tabs(surface)
        self._render_current_tab(surface, content_rect)
        
        # Render dice popup if active
        if self._popup_active:
            self._render_dice_popup(surface)

    def _content_rect(self) -> Rect:
        return Rect(self.rect.x + 10, self.rect.y + 100, self.rect.width - 20, self.rect.height - 110)

    def _line_height(self) -> int:
        return self.app.theme.font.get_linesize() + 4

    def _tab_rects(self) -> list[Rect]:
        if not self.character:
            return []
        base_x = self.rect.x + 10
        base_y = self.rect.y + 70
        tab_w = 100
        tab_h = 28
        gap = 6
        rects = []
        for idx, _ in enumerate(self.TABS):
            rects.append(Rect(base_x + idx * (tab_w + gap), base_y, tab_w, tab_h))
        return rects

    def _render_tabs(self, surface: Surface) -> None:
        if not self.character:
            return
        theme = self.app.theme
        mouse_pos = self._to_local_pos(mouse.get_pos())
        for idx, rect in enumerate(self._tab_rects()):
            is_active = idx == self.active_tab
            hovered = rect.collidepoint(mouse_pos)
            color = theme.colors["accent"] if is_active else theme.colors["hover"] if hovered else theme.colors["bg"]
            draw_rect(surface, color, rect, border_radius=4)
            draw_rect(surface, (0, 0, 0), rect, 1, border_radius=4)
            text_surf = theme.font.render(self.TABS[idx], True, theme.colors["text"])
            text_rect = text_surf.get_rect(center=rect.center)
            surface.blit(text_surf, text_rect)

    def _render_current_tab(self, surface: Surface, content_rect: Rect) -> None:
        if self.active_tab == 0:
            self._render_stats_tab(surface, content_rect)
        elif self.active_tab == 1:
            self._render_modifs_tab(surface, content_rect)
        elif self.active_tab == 2:
            self._render_inventory_tab(surface, content_rect)
        else:
            self._render_spells_tab(surface, content_rect)
