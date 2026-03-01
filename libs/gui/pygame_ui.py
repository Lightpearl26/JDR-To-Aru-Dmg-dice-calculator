# -*- coding: utf-8 -*-

"""
Pygame UI lib
____________________________________________________________________________________________________
UI lib for pygame based app
version : 1.1
____________________________________________________________________________________________________
Contains all ui objects for map editor
____________________________________________________________________________________________________
(c) Lafiteau Franck
"""

# import external modules
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Callable

# import pygame components
from pygame import (
    Surface,
    Rect,
    Vector2,
    quit as quit_pygame,
    MOUSEMOTION,
    MOUSEBUTTONDOWN,
    MOUSEBUTTONUP,
    MOUSEWHEEL,
    KEYDOWN,
    K_RETURN,
    K_BACKSPACE,
    K_DELETE,
    K_LEFT,
    K_RIGHT,
    SRCALPHA,
    KMOD_SHIFT,
    KMOD_RSHIFT,
    QUIT,
    KMOD_CTRL,
    K_c,
    K_v,
    K_x,
    K_a,
    SCRAP_TEXT,
    scrap
)
from pygame.font import (
    Font,
    SysFont
)
from pygame.event import (
    Event,
    get as get_events
)
from pygame.key import (
    get_mods
)
from pygame.draw import (
    rect as draw_rect,
    line as draw_line
)
from pygame.display import flip as flip_display

# ===================================================== #
##### ----- create base objects of the module ----- #####
# ===================================================== #

# Create Theme object
@dataclass
class Theme:
    """
    Theme of the app
    """
    colors: dict[str, tuple[int, int, int]]
    font: Font

    @classmethod
    def default(cls) -> Theme:
        """
        Get the default Theme
        """
        return cls(
            colors={
                "bg": (57, 61, 71),
                "hover": (80, 80, 80),
                "accent": (60, 120, 0),
                "text": (255, 255, 255)
            },
            font=SysFont("consolas", 16)
        )


# Create the App object
class UIApp:
    """
    Instance of the pygame ui App
    """
    def __init__(self, size: tuple[int, int], theme: Optional[Theme]=None) -> None:
        self.size = size
        self.layers: list[UILayer] = []
        self.focused_widget: Optional[UIWidget] = None
        self.hovered_widget: Optional[UIWidget]=  None
        self.theme: Theme = theme or Theme.default()

    def add_layer(self) -> UILayer:
        """
        Add a layer on top of the App layers
        """
        layer = UILayer(self)
        self.layers.append(layer)
        return layer

    def handle_events(self, event: Event) -> bool:
        """
        Handle a single pygame event 
        """
        if event.type == MOUSEMOTION:
            self.hovered_widget = self._get_widget_at(event.pos)
        elif event.type == MOUSEBUTTONDOWN and event.button in [1, 3]:
            self.focused_widget = self.hovered_widget

        for layer in reversed(self.layers):
            if layer.handle_event(event):
                return True
        return False

    def _get_widget_at(self, pos: tuple[int, int]) -> Optional[UIWidget]:
        """
        if their is a widget at the position then return it else return None
        """
        for layer in reversed(self.layers):  # topmost layer first
            stack = list(reversed(layer.widgets))  # preserve z-order
            fallback = None
            while stack:
                widget = stack.pop()
                # On ne saute PAS les widgets dont le parent ne contient pas la souris
                if widget.global_rect.collidepoint(pos):
                    if not widget.displayed:
                        continue
                    fallback = widget  # deepest valid hit in this layer
                # Toujours descendre dans les enfants (pour les dropdowns qui débordent)
                if widget.children:
                    stack.extend(reversed(widget.children))
            if fallback:
                return fallback  # deepest valid hit in this layer
        return None

    def render(self, surface: Surface) -> None:
        """
        Render the app on the surface
        """
        for layer in self.layers:
            layer.render(surface)


# Create The UILayer object
class UILayer:
    """
    Layer of a pygame ui App
    """
    def __init__(self, app: UIApp) -> None:
        self.app = app
        self.widgets: list[UIWidget] = []

    def add(self, widget: UIWidget) -> None:
        """
        Add a widget to the Layer
        """
        widget.app_ref = self.app
        self.widgets.append(widget)

    def handle_event(self, event: Event) -> bool:
        """
        Handle a single pygame event
        """
        for w in reversed(self.widgets):
            if w.handle_event(event):
                return True
        return False

    def render(self, surface: Surface) -> None:
        """
        Render the layer on the surface
        """
        for w in self.widgets:
            w.render(surface)


# Create the UIWidget base object
class UIWidget:
    """
    Widget of a pygame ui App
    """
    def __init__(self, parent: Optional[UIWidget], rect: Rect) -> None:
        self.parent = parent
        self.rect = rect
        self.children: list[UIWidget] = []
        self.displayed: bool = True
        if parent:
            parent.children.append(self)

    @property
    def app(self) -> UIApp:
        """
        App of this widget
        """
        p = self
        while p.parent:
            p = p.parent
        return getattr(p, "app_ref")

    @property
    def global_rect(self) -> Rect:
        """
        Rect of the Widget in global coordinates
        """
        if not self.parent:
            return self.rect
        pr = self.parent.global_rect
        scroll = getattr(self.parent, "scroll", Vector2(0, 0))
        return self.rect.move(Vector2(pr.topleft) - scroll)

    @property
    def hover(self) -> bool:
        """
        Boolean to detect if this widget is hovered
        """
        return self.app.hovered_widget is self

    @property
    def focus(self) -> bool:
        """
        Boolean to detect if this widget is focused
        """
        return self.app.focused_widget is self

    def handle_event(self, event: Event) -> bool:
        """
        Handle a single pygame event
        """
        if not self.displayed:
            return False
        for child in reversed(self.children):
            if child.handle_event(event):
                return True
        return False

    def render(self, surface: Surface) -> None:
        """
        Render the widget on surface
        """
        for child in self.children:
            child.render(surface)


# ===================================================== #
##### ----- create base widgets of the module ----- #####
# ===================================================== #
class Button(UIWidget):
    """
    Simple Button widget
    """
    def __init__(self, parent: UIWidget, rect: Rect, label: str, callback: Callable) -> None:
        UIWidget.__init__(self, parent, rect)
        self.label = label
        self.callback = callback

    def handle_event(self, event):
        if not self.displayed:
            return False
        if self.focus and event.type == MOUSEBUTTONUP and event.button == 1:
            self.callback()
            # needs to unfocus it (its a button)
            self.app.focused_widget = None
            return True
        return UIWidget.handle_event(self, event)

    def render(self, surface):
        if not self.displayed:
            return
        color = (
            self.app.theme.colors["accent"] if self.focus else
            self.app.theme.colors["hover"] if self.hover else
            self.app.theme.colors["bg"]
        )
        draw_rect(surface, color, self.rect)
        text = self.app.theme.font.render(self.label, True, self.app.theme.colors["text"])
        text_rect = text.get_rect(center=self.rect.center)
        surface.blit(text, text_rect)
        draw_rect(surface, (0, 0, 0), self.rect, 1)


class InvisibleButton(UIWidget):
    """
    Invisible clickable button for overlays - no visual rendering.
    """
    def __init__(self, parent: UIWidget, rect: Rect, callback: Callable) -> None:
        UIWidget.__init__(self, parent, rect)
        self.callback = callback

    def handle_event(self, event: Event) -> bool:
        if not self.displayed:
            return False
        if self.focus and event.type == MOUSEBUTTONUP and event.button == 1:
            self.callback()
            self.app.focused_widget = None
            return True
        return UIWidget.handle_event(self, event)

    def render(self, surface: Surface) -> None:
        """No rendering - invisible button"""
        pass


class IconButton(UIWidget):
    """
    IconButton widget
    """
    def __init__(self,
                 parent: UIWidget,
                 rect: Rect,
                 icon: Surface,
                 callback: Callable) -> None:
        UIWidget.__init__(self, parent, rect)
        self.icon = icon
        self.callback = callback

    def handle_event(self, event: Event) -> bool:
        if not self.displayed:
            return False
        if self.focus and event.type == MOUSEBUTTONUP and event.button == 1:
            self.callback()
            self.app.focused_widget = None
            return True
        return UIWidget.handle_event(self, event)

    def render(self, surface: Surface) -> None:
        if not self.displayed:
            return
        color = (
            self.app.theme.colors["accent"] if self.focus else
            self.app.theme.colors["hover"] if self.hover else
            self.app.theme.colors["bg"]
        )
        draw_rect(surface, color, self.rect, border_radius=4)
        icon_rect = self.icon.get_rect(center=self.rect.center)
        surface.blit(self.icon, icon_rect)


class Label(UIWidget):
    """
    Simple Label widget
    """
    def __init__(self, parent: Optional[UIWidget], pos: tuple[int, int], text: str) -> None:
        UIWidget.__init__(self, parent, Rect(0, 0, 0, 0))
        self._text = text
        size = self.app.theme.font.size(text)
        self.rect.size = size
        self.rect.topleft = pos

    def render(self, surface) -> None:
        text = self.app.theme.font.render(self.text, True, self.app.theme.colors["text"])
        surface.blit(text, self.rect)

    @property
    def text(self) -> str:
        """
        Text of the label
        """
        return self._text

    @text.setter
    def text(self, text: str) -> None:
        self._text = text
        self.rect.size = self.app.theme.font.size(text)


class TextEntry(UIWidget):
    """
    Simple TextEntry widget
    """
    def __init__(self,
                 parent: Optional[UIWidget],
                 rect: Rect,
                 default_text: str="",
                 max_length: int=50) -> None:
        UIWidget.__init__(self, parent, rect)
        self.text = default_text
        self.cursor_pos = len(self.text)
        self.max_length = max_length

    def handle_event(self, event: Event) -> bool:
        if not self.focus or not self.displayed:
            return False

        if event.type == KEYDOWN:
            if event.key == K_RETURN:
                self.app.focused_widget = None
                return True
            elif event.key == K_BACKSPACE:
                if self.cursor_pos > 0:
                    self.text = self.text[:self.cursor_pos-1] + self.text[self.cursor_pos:]
                    self.cursor_pos -= 1
                    return True
            elif event.key == K_DELETE:
                if self.cursor_pos < len(self.text):
                    self.text = self.text[:self.cursor_pos] + self.text[self.cursor_pos+1:]
                    return True
            elif event.key == K_LEFT:
                if self.cursor_pos > 0:
                    self.cursor_pos -= 1
                    return True
            elif event.key == K_RIGHT:
                if self.cursor_pos < len(self.text):
                    self.cursor_pos += 1
                    return True
            elif event.unicode and event.unicode.isprintable() and len(self.text) < self.max_length:
                self.text = (self.text[:self.cursor_pos] +
                             event.unicode +
                             self.text[self.cursor_pos:])
                self.cursor_pos += 1
                return True
        return False

    def render(self, surface: Surface) -> None:
        UIWidget.render(self, surface)
        draw_rect(surface, (255, 255, 255), self.rect)

        # draw text
        text = self.app.theme.font.render(self.text, True, (0, 0, 0))
        text_rect = text.get_rect(midleft=self.rect.move(10, 0).midleft)
        surface.blit(text, text_rect)

        if self.focus:
            # draw cursor
            cursor_x = text_rect.x + self.app.theme.font.size(self.text[:self.cursor_pos])[0]
            draw_line(
                surface,
                (0, 0, 0),
                (cursor_x, text_rect.top),
                (cursor_x, text_rect.bottom),
                2
            )

        # draw border
        border_color = (
            self.app.theme.colors["accent"] if self.focus else
            self.app.theme.colors["hover"] if self.hover else
            self.app.theme.colors["bg"]
        )
        draw_rect(surface, border_color, self.rect, 2)


class Checkbox(UIWidget):
    """
    Toggle lever style checkbox with label.
    Lever changes color based on on/off state.
    """
    def __init__(self, parent: UIWidget, rect: Rect, label: str, checked: bool = False):
        UIWidget.__init__(self, parent, rect)
        self.label = label
        self.checked = checked

    def handle_event(self, event: Event) -> bool:
        if self.focus and event.type == MOUSEBUTTONUP and event.button == 1:
            self.checked = not self.checked
            return True
        return UIWidget.handle_event(self, event)

    def render(self, surface: Surface) -> None:
        # Draw label on the left
        text_surf = self.app.theme.font.render(self.label, True, self.app.theme.colors["text"])
        text_rect = text_surf.get_rect(midleft=(self.rect.x, self.rect.centery))
        surface.blit(text_surf, text_rect)

        # Draw toggle track
        track_width = 50
        track_height = 20
        track_rect = Rect(
            self.rect.right - track_width - 4,
            self.rect.centery - track_height // 2,
            track_width,
            track_height
        )
        draw_rect(surface,
                  self.app.theme.colors["bg"],
                  track_rect,
                  border_radius=track_height // 2)
        draw_rect(surface,
                  self.app.theme.colors["hover"],
                  track_rect,
                  width=2,
                  border_radius=track_height // 2)

        # Draw the handle (circle) on the track
        handle_radius = track_height - 4
        handle_x = track_rect.right - handle_radius - 2 if self.checked else track_rect.left + 2
        handle_rect = Rect(handle_x, track_rect.y + 2, handle_radius, handle_radius)
        handle_color = (self.app.theme.colors["accent"] if self.checked else
                        self.app.theme.colors["hover"])
        draw_rect(surface, handle_color, handle_rect, border_radius=handle_radius // 2)


class Slider(UIWidget):
    """
    Horizontal slider with label, lever, and value display.
    """
    def __init__(self,
                 parent: Optional[UIWidget],
                 pos: tuple[int, int],
                 label: str,
                 min_val: float=0.0,
                 max_val: float=1.0,
                 step: float=0.1,
                 default: float=0.5,
                 bar_width: int=150) -> None:
        UIWidget.__init__(self, parent, Rect(0, 0, bar_width, 8))
        x = pos[0] + self.app.theme.font.size(label)[0] + 10
        y = pos[1] + self.app.theme.font.size(label)[1] // 2 - 4
        self.rect.topleft = (x, y)

        self.label = label
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.value = default
        self.dragging: bool = False

        self.bar_width = bar_width
        self.pos = pos
        self.bar_rect = self.rect.copy()
        self.cursor_rect = Rect(0, 0, 12, 16)
        self._update_cursor_pos()

    def _update_cursor_pos(self) -> None:
        ratio = (self.value - self.min_val) / (self.max_val - self.min_val)
        self.cursor_rect.centerx = int(self.bar_rect.x+ratio*self.bar_width)
        self.cursor_rect.centery = self.bar_rect.centery

    def _set_value_from_mouse(self, mx: int) -> None:
        relativ_x = mx - self.bar_rect.x
        ratio = max(0, min(1, relativ_x/self.bar_width))
        raw_val = self.min_val + ratio * (self.max_val - self.min_val)
        self.value = round(raw_val/self.step)*self.step
        self._update_cursor_pos()

    def handle_event(self, event: Event) -> bool:
        if not self.displayed:
            return False

        if (event.type == MOUSEBUTTONDOWN and
            event.button == 1 and
            self.cursor_rect.collidepoint(event.pos)):
            self.dragging = True
            self._set_value_from_mouse(event.pos[0])
            return True
        elif event.type == MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
            return True
        elif event.type == MOUSEMOTION and self.dragging:
            self._set_value_from_mouse(event.pos[0])
            return True

        return UIWidget.handle_event(self, event)

    def render(self, surface: Surface) -> None:
        # draw label
        label_surf = self.app.theme.font.render(self.label, True, self.app.theme.colors["text"])
        label_rect = label_surf.get_rect(topleft=self.pos)
        surface.blit(label_surf, label_rect)

        # draw bar and cursor
        draw_rect(surface, self.app.theme.colors["hover"], self.bar_rect, border_radius=4)
        draw_rect(surface, self.app.theme.colors["accent"], self.cursor_rect, border_radius=6)

        # draw value
        value_surf = self.app.theme.font.render(
            str(self.value),
            True,
            self.app.theme.colors["text"]
        )
        value_rect = value_surf.get_rect(midleft=self.bar_rect.move(10, 0).midright)
        surface.blit(value_surf, value_rect)


class Frame(UIWidget):
    """
    Simple scrollable Frame widget
    """
    def __init__(self,
                 parent: Optional[UIWidget],
                 rect: Rect,
                 width: Optional[int]=None,
                 height: Optional[int]=None) -> None:
        UIWidget.__init__(self, parent, rect)
        self.scroll: Vector2 = Vector2(0, 0)
        self._size: tuple[int, int] = (width or self.rect.width,
                                      height or self.rect.height)
        self.surface: Surface = Surface(self._size, SRCALPHA)

    def handle_event(self, event: Event) -> bool:
        if not self.displayed:
            return False
        if self.hover and event.type == MOUSEWHEEL:
            if not any(child.hover for child in self.children):
                if get_mods() & (KMOD_SHIFT | KMOD_RSHIFT):
                    self.scroll.x -= 48 * event.y
                    self.scroll.x = min(self.size[0]-self.rect.width, max(0, self.scroll.x))
                    return True
                else:
                    self.scroll.y -= 48 * event.y
                    self.scroll.y = min(self.size[1]-self.rect.height, max(0, self.scroll.y))
                    return True
        return UIWidget.handle_event(self, event)

    def draw_scrollbars(self, surface: Surface) -> None:
        """
        draw scrollbar of the frame
        """
        if self.size[1] > self.rect.height:
            visible_ratio = self.rect.height / self.size[1]
            bar_height = max(20, self.rect.height * visible_ratio)
            max_scroll_y = self.size[1] - self.rect.height
            scroll_ratio = self.scroll.y / max_scroll_y if max_scroll_y else 0
            bar_y = self.rect.y + scroll_ratio * (self.rect.height - bar_height)
            draw_rect(surface, (100, 100, 100),
                      (self.rect.right - 6, bar_y, 4, bar_height),
                      border_radius=2)

        if self.size[0] > self.rect.width:
            visible_ratio = self.rect.width / self.size[0]
            bar_width = max(20, self.rect.width * visible_ratio)
            max_scroll_x = self.size[0] - self.rect.width
            scroll_ratio = self.scroll.x / max_scroll_x if max_scroll_x else 0
            bar_x = self.rect.x + scroll_ratio * (self.rect.width - bar_width)
            draw_rect(surface, (100, 100, 100),
                      (bar_x, self.rect.bottom - 6, bar_width, 4),
                      border_radius=2)

    def render(self, surface: Surface) -> None:
        if not self.displayed:
            return

        self.surface.fill(self.app.theme.colors["bg"])

        for child in self.children:
            child.render(self.surface)

        surface_rect = Rect(self.scroll, self.rect.size)
        surface.blit(self.surface.subsurface(surface_rect), self.rect)

        self.draw_scrollbars(surface)
        draw_rect(surface, (0, 0, 0), self.rect.inflate(2, 2), 2)

    @property
    def size(self) -> tuple[int, int]:
        """
        Size of the Surface of the frame
        """
        return self._size

    @size.setter
    def size(self, size: tuple[int, int]) -> None:
        if size != self._size:
            self._size = size
            self.surface = Surface(size, SRCALPHA)
            max_scroll_x = max(0, self._size[0] - self.rect.width)
            max_scroll_y = max(0, self._size[1] - self.rect.height)
            self.scroll.x = min(max_scroll_x, max(0, self.scroll.x))
            self.scroll.y = min(max_scroll_y, max(0, self.scroll.y))


# ====================================================== #
##### ----- create frame widgets of the module ----- #####
# ====================================================== #
class DropdownList(Frame):
    """
    Simple dropdown TextList widget
    """
    def __init__(self,
                 parent: Optional[UIWidget],
                 pos: tuple[int, int],
                 items: list[str],
                 max_visible_items: int=8) -> None:
        Frame.__init__(self, parent, Rect(pos, (0, 0)))
        self.items = items
        self.selected_index: int = 0
        self.hover_index: int = -1
        self.max_visible_items = max_visible_items
        self.item_height: int = self.app.theme.font.get_linesize()+4

        width = max(self.app.theme.font.size(item)[0]+10 for item in items)
        height = self.item_height*len(items)
        self.size = (width, height) # update surface too
        self.rect.size = (width, self.item_height)

    def get_text(self) -> str:
        """
        Return the current selected text
        """
        return self.items[self.selected_index]

    def handle_event(self, event: Event) -> bool:
        if not self.displayed:
            return False

        if event.type == MOUSEMOTION:
            if self.hover:
                # Move to end of parent's children list (render last = on top)
                if self.parent and self in self.parent.children:
                    self.parent.children.remove(self)
                    self.parent.children.append(self)
                
                self.rect.height = min(len(self.items), self.max_visible_items)*self.item_height
                posy = event.pos[1]-self.global_rect.y + self.scroll.y
                self.hover_index = posy // self.item_height
            else:
                self.rect.height = self.item_height
                self.hover_index = -1
        if event.type == MOUSEBUTTONUP and event.button == 1 and self.focus:
            posy = event.pos[1]-self.global_rect.y + self.scroll.y
            idx = int(posy // self.item_height)
            if 0 <= idx < len(self.items):
                self.selected_index = idx
            return True

        return Frame.handle_event(self, event)

    def render(self, surface: Surface) -> None:
        if not self.displayed:
            return

        self.surface.fill(self.app.theme.colors["bg"])

        if self.hover:
            for i, text in enumerate(self.items):
                y = i * self.item_height
                rect = Rect(0, y, self.rect.width, self.item_height)
                color = (
                    self.app.theme.colors["accent"] if self.selected_index == i else
                    self.app.theme.colors["hover"] if self.hover_index == i else
                    self.app.theme.colors["bg"]
                )
                draw_rect(self.surface, color, rect)
                text_surf = self.app.theme.font.render(text, True, self.app.theme.colors["text"])
                text_rect = text_surf.get_rect(midleft=rect.move(5, 0).midleft)
                self.surface.blit(text_surf, text_rect)
        else:
            rect = Rect(0, 0, self.rect.width, self.rect.height)
            draw_rect(self.surface, self.app.theme.colors["accent"], rect)
            text_surf = self.app.theme.font.render(
                self.get_text(),
                True,
                self.app.theme.colors["text"]
            )
            text_rect = text_surf.get_rect(midleft=rect.move(5, 0).midleft)
            self.surface.blit(text_surf, text_rect)

        surface_rect = Rect((0, 0), self.rect.size)
        if self.hover:
            surface_rect.x = self.scroll.x
            surface_rect.y = self.scroll.y
        surface.blit(self.surface.subsurface(surface_rect), self.rect)

        if self.hover:
            self.draw_scrollbars(surface)
        draw_rect(surface, (0, 0, 0), self.rect.inflate(2, 2), 2)


class TextArea(Frame):
    """
    Multi-line text area with optional editing capabilities.
    """
    def __init__(self: TextArea,
                 parent: UIWidget,
                 rect: Rect,
                 text: str="",
                 width: Optional[int]=None,
                 height: Optional[int]=None,
                 padding: int=50) -> None:
        Frame.__init__(self, parent, rect, width, height)
        self.lines: list[str] = text.splitlines() or [""]
        self.editable: bool = True
        self.selection: tuple[int, int] = (0, 0)
        self.cursor_pos: int = len(text)
        self.padding: int = padding
        self._dragging: bool = False
        self._dragged_start_pos: Optional[int] = None

        # setup frame internal size
        height = len(self.lines) * self.app.theme.font.get_linesize()
        width = max(self.app.theme.font.size(line)[0] for line in self.lines) if self.lines else 0
        self.size = (max(width+self.padding, self.rect.width), max(height, self.rect.height))

    # useful methods
    def get_cursor_pos(self: TextArea, pos: Vector2) -> int:
        """
        Get the cursor position in text from pixel position.
        """
        line_height = self.app.theme.font.get_linesize()
        line_index = min(len(self.lines)-1, max(0, (pos.y + self.scroll.y) // line_height))
        line_text = self.lines[int(line_index)]
        x_offset = pos.x + self.scroll.x
        char_index = 0
        for i in range(len(line_text)+1):
            if x_offset < self.app.theme.font.size(line_text[:i])[0]+self.padding:
                break
            char_index = i
            
        # Calculate overall cursor position
        cursor_pos = sum(len(self.lines[i]) + 1 for i in range(int(line_index))) + char_index
        return cursor_pos

    # handle events
    def handle_event(self: TextArea, event: Event) -> bool:
        if not self.displayed:
            return False

        if self.editable:
            if event.type == KEYDOWN and self.focus:
                if event.key == K_BACKSPACE:
                    if self.selection != (0, 0):
                        start, end = self.selection
                        self.text = self.text[:start] + self.text[end:]
                        self.cursor_pos = start
                        self.selection = (0, 0)
                        return True
                    if self.cursor_pos > 0:
                        self.text = self.text[:self.cursor_pos-1] + self.text[self.cursor_pos:]
                        self.cursor_pos -= 1
                        self.selection = (0, 0)
                        return True
                elif event.key == K_DELETE:
                    if self.selection != (0, 0):
                        start, end = self.selection
                        self.text = self.text[:start] + self.text[end:]
                        self.cursor_pos = start
                        self.selection = (0, 0)
                        return True
                    if self.cursor_pos < len(self.text):
                        self.text = self.text[:self.cursor_pos] + self.text[self.cursor_pos+1:]
                        self.selection = (0, 0)
                        return True
                elif event.key == K_LEFT:
                    if self.selection != (0, 0):
                        start, end = self.selection
                        self.cursor_pos = start
                        self.selection = (0, 0)
                        return True
                    if self.cursor_pos > 0:
                        self.cursor_pos -= 1
                        self.selection = (0, 0)
                        return True
                elif event.key == K_RIGHT:
                    if self.selection != (0, 0):
                        start, end = self.selection
                        self.cursor_pos = end
                        self.selection = (0, 0)
                        return True
                    if self.cursor_pos < len(self.text):
                        self.cursor_pos += 1
                        self.selection = (0, 0)
                        return True
                elif event.unicode and event.unicode.isprintable():
                    if self.selection != (0, 0):
                        start, end = self.selection
                        self.text = self.text[:start] + event.unicode + self.text[end:]
                        self.cursor_pos = start + 1
                        self.selection = (0, 0)
                        return True
                    self.text = (self.text[:self.cursor_pos] +
                                 event.unicode +
                                 self.text[self.cursor_pos:])
                    self.cursor_pos += 1
                    self.selection = (0, 0)
                    return True
                elif event.key == K_RETURN:
                    if self.selection != (0, 0):
                        start, end = self.selection
                        self.text = self.text[:start] + "\n" + self.text[end:]
                        self.cursor_pos = start + 1
                        self.selection = (0, 0)
                        return True
                    self.text = (self.text[:self.cursor_pos] +
                                 "\n" +
                                 self.text[self.cursor_pos:])
                    self.cursor_pos += 1
                    self.selection = (0, 0)
                    return True
                elif event.key == K_v and KMOD_CTRL & get_mods():
                    if scrap.get(SCRAP_TEXT):
                        paste_text = scrap.get(SCRAP_TEXT).decode("utf-8")
                        paste_text = paste_text.replace('\x00', '').replace('\0', '')
                        if self.selection != (0, 0):
                            start, end = self.selection
                            self.text = self.text[:start] + paste_text + self.text[end:]
                            self.cursor_pos = start + len(paste_text)
                            self.selection = (0, 0)
                            return True
                        self.text = (self.text[:self.cursor_pos] +
                                     paste_text +
                                     self.text[self.cursor_pos:])
                        self.cursor_pos += len(paste_text)
                        self.selection = (0, 0)
                        return True
                elif event.key == K_x and KMOD_CTRL & get_mods():
                    selected_text = self.selected_text
                    if selected_text:
                        scrap.put(SCRAP_TEXT, selected_text.encode("utf-8"))
                        start, end = self.selection
                        self.text = self.text[:start] + self.text[end:]
                        self.cursor_pos = start
                        self.selection = (0, 0)
                        return True

        if event.type == KEYDOWN and self.focus:
            if event.key == K_a and KMOD_CTRL & get_mods():
                self.selection = (0, len(self.text))
                self.cursor_pos = len(self.text)
                return True
            if event.key == K_c and KMOD_CTRL & get_mods():
                selected_text = self.selected_text
                if selected_text:
                    scrap.put(SCRAP_TEXT, selected_text.encode("utf-8"))
                    return True

        if event.type == MOUSEBUTTONDOWN and event.button == 1 and self.focus:
            local_pos = Vector2(event.pos) - Vector2(self.global_rect.topleft)
            self.cursor_pos = self.get_cursor_pos(local_pos)
            self.selection = (0, 0)
            self._dragging = True
            self._dragged_start_pos = self.cursor_pos
            return True

        if event.type == MOUSEMOTION and self._dragging:
            local_pos = Vector2(event.pos) - Vector2(self.global_rect.topleft)
            current_pos = self.get_cursor_pos(local_pos)
            start = min(self._dragged_start_pos, current_pos)
            end = max(self._dragged_start_pos, current_pos)
            self.selection = (start, end)
            self.cursor_pos = current_pos
            return True

        if event.type == MOUSEBUTTONUP and event.button == 1 and self._dragging:
            self._dragging = False
            self._dragged_start_pos = None
            return True

        return Frame.handle_event(self, event)

    # rendering
    def render(self: TextArea, surface: Surface) -> None:
        if not self.displayed:
            return

        self.surface.fill(self.app.theme.colors["bg"])

        # draw text lines
        line_height = self.app.theme.font.get_linesize()
        y_offset = 0
        for i, line in enumerate(self.lines):
            for j, char in enumerate(line):
                # detect if part of selection
                char_index = sum(len(self.lines[i]) + 1 for i in range(i)) + j
                if self.selection[0] <= char_index < self.selection[1]:
                    # is part of selection
                    char_width = self.app.theme.font.size(char)[0]
                    draw_rect(self.surface, self.app.theme.colors["hover"],
                              (self.app.theme.font.size(line[:j])[0]+self.padding,
                               y_offset,
                               char_width,
                               line_height))
                    char_surf = self.app.theme.font.render(char, True, self.app.theme.colors["bg"])
                else:
                    #isn't part of selection
                    char_surf = self.app.theme.font.render(char, True, self.app.theme.colors["text"])
                self.surface.blit(char_surf,
                                  (self.app.theme.font.size(line[:j])[0]+self.padding,
                                   y_offset))
            y_offset += line_height

        # render cursor
        if self.focus:
            cursor_line = 0
            cursor_col = 0
            acc_len = 0
            for i, line in enumerate(self.lines):
                if acc_len + len(line) >= self.cursor_pos:
                    cursor_line = i
                    cursor_col = self.cursor_pos - acc_len
                    break
                acc_len += len(line) + 1  # +1 for newline
            cursor_x = self.app.theme.font.size(self.lines[cursor_line][:cursor_col])[0]+self.padding
            cursor_y = cursor_line * line_height
            draw_line(self.surface, self.app.theme.colors["text"],
                      (cursor_x, cursor_y), (cursor_x, cursor_y + line_height))
            
        # render line numeration
        numeration_surface = Surface((self.padding, self.size[1]), SRCALPHA)
        numeration_surface.fill(self.app.theme.colors["bg"])
        for i in range(len(self.lines)):
            line_num_surf = self.app.theme.font.render(str(i+1), True, self.app.theme.colors["hover"])
            line_num_rect = line_num_surf.get_rect(topright=(self.padding-10, i * line_height))
            numeration_surface.blit(line_num_surf, line_num_rect)
        render_rect = Rect(0, self.scroll.y, self.padding, self.rect.height)
        
            
        # blit scrollable content
        surface_rect = Rect(self.scroll, self.rect.size)
        surface.blit(self.surface.subsurface(surface_rect), self.rect)
        surface.blit(numeration_surface.subsurface(render_rect), (self.rect.left, self.rect.top))
        
        # draw scrollbars and border
        self.draw_scrollbars(surface)
        border_color = self.app.theme.colors["accent"] if self.focus else self.app.theme.colors["hover"]
        draw_rect(surface, border_color, self.rect.inflate(2, 2), 2)

    @property
    def selected_text(self: TextArea) -> str:
        """
        Get the currently selected text.
        """
        start, end = self.selection
        return self.text[start:end]

    @property
    def text(self: TextArea) -> str:
        """
        Get the full text content.
        """
        return "\n".join(self.lines)

    @text.setter
    def text(self: TextArea, text: str) -> None:
        """
        Set the full text content.
        """
        self.lines = text.splitlines() or [""]
        if text.endswith("\n"):
            self.lines.append("")

        # setup frame internal size
        height = len(self.lines) * self.app.theme.font.get_linesize()
        width = max(self.app.theme.font.size(line)[0] for line in self.lines) if self.lines else 0
        self.size = (max(width+self.padding, self.rect.width), max(height, self.rect.height))


class ListView(Frame):
    """
    Scrollable list of selectable labels.
    """
    def __init__(
        self,
        parent: Optional[UIWidget],
        rect: Rect,
        items: list[str]
    ) -> None:
        # Initialize Frame with default surface (will adjust size below)
        super().__init__(parent, rect)

        self.items = items
        self.selected_index: int = 0 if items else -1
        self.hover_index: int = -1

        # Font and colors from app theme
        self.font = self.app.theme.font
        self.text_color = self.app.theme.colors["text"]
        self.hover_color = self.app.theme.colors["hover"]
        self.active_color = self.app.theme.colors["accent"]

        # Item height
        self.item_height = self.font.get_linesize() + 4

        # Adjust surface size: ensure it's at least frame height
        content_height = max(len(items) * self.item_height, rect.height)
        self.size = (rect.width, content_height)

    @property
    def selected_text(self) -> Optional[str]:
        """
        Get the currently selected text, or None if no selection.
        """
        if 0 <= self.selected_index < len(self.items):
            return self.items[self.selected_index]
        return None

    def handle_event(self, event: Event) -> bool:
        if not self.displayed:
            return False

        # Mouse hovering
        if event.type == MOUSEMOTION and self.hover:
            posy = event.pos[1] - self.global_rect.y + self.scroll.y
            idx = int(posy // self.item_height)
            self.hover_index = idx if 0 <= idx < len(self.items) else -1
            return True

        # Mouse click selection
        if event.type == MOUSEBUTTONDOWN and event.button == 1 and self.hover:
            posy = event.pos[1] - self.global_rect.y + self.scroll.y
            idx = int(posy // self.item_height)
            if 0 <= idx < len(self.items):
                self.selected_index = idx
            return True

        return super().handle_event(event)

    def render(self, surface: Surface) -> None:
        if not self.displayed:
            return

        # Clear surface
        self.surface.fill(self.app.theme.colors["bg"])

        # Draw items
        for i, text in enumerate(self.items):
            y = i * self.item_height
            rect = Rect(0, y, self.rect.width, self.item_height)

            if i == self.selected_index:
                draw_rect(self.surface, self.active_color, rect)
            elif i == self.hover_index:
                draw_rect(self.surface, self.hover_color, rect)

            text_surf = self.font.render(text, True, self.text_color)
            self.surface.blit(text_surf, (5, y + 2))

        # Blit scrollable content (taking scroll position into account)
        surface_rect = Rect(self.scroll.x, self.scroll.y, self.rect.width, self.rect.height)
        surface.blit(self.surface.subsurface(surface_rect), self.rect)

        # Draw scrollbars
        self.draw_scrollbars(surface)

        # Draw border
        draw_rect(surface, self.app.theme.colors["accent"], self.rect, 2)


class DualListToggle(Frame):
    """
    A dual-panel toggle list.
    Left panel = disabled, Right panel = enabled.
    Preserves vertical order of items.
    """
    def __init__(
        self,
        parent: Optional[UIWidget],
        rect: Rect,
        items: list[str]
    ) -> None:
        super().__init__(parent, rect)

        self.items = items
        self.enabled: set[int] = set()   # indices of enabled items
        self.hover_index: int = -1

        self.font = self.app.theme.font
        self.text_color = self.app.theme.colors["text"]
        self.enabled_color = self.app.theme.colors["accent"]
        self.disabled_color = self.app.theme.colors["hover"]

        self.item_height = self.font.get_linesize() + 6

        # Adjust surface size: height must at least frame height
        content_height = max(len(items) * self.item_height, rect.height)
        self.size = (rect.width, content_height)
        
    def get(self) -> list[str]:
        """
        get Current enabled items
        """
        return [self.items[idx] for idx in self.enabled]

    def toggle(self, idx: int) -> None:
        """
        toggle an index to enabled / disabled
        """
        if idx in self.enabled:
            self.enabled.remove(idx)
        else:
            self.enabled.add(idx)

    def handle_event(self, event: Event) -> bool:
        if not self.displayed:
            return False

        if event.type == MOUSEMOTION and self.hover:
            posy = event.pos[1] - self.global_rect.y + self.scroll.y
            idx = int(posy // self.item_height)
            self.hover_index = idx if 0 <= idx < len(self.items) else -1
            return True

        if event.type == MOUSEBUTTONDOWN and event.button == 1 and self.hover:
            posy = event.pos[1] - self.global_rect.y + self.scroll.y
            idx = int(posy // self.item_height)
            if 0 <= idx < len(self.items):
                self.toggle(idx)
            return True

        return super().handle_event(event)

    def render(self, surface: Surface) -> None:
        if not self.displayed:
            return

        self.surface.fill(self.app.theme.colors["bg"])

        col_width = self.rect.width // 2

        for i, text in enumerate(self.items):
            y = i * self.item_height
            row_rect_left = Rect(0, y, col_width, self.item_height)
            row_rect_right = Rect(col_width, y, col_width, self.item_height)
            row_rect = Rect(0, y, self.rect.width, self.item_height)

            is_enabled = i in self.enabled
            is_hover = i == self.hover_index

            # pick target rect and background color
            target_rect = row_rect_left if is_enabled else row_rect_right
            bg_color = self.enabled_color if is_enabled else self.disabled_color
            draw_rect(self.surface, bg_color, target_rect)

            # draw text in its active slot
            text_surf = self.font.render(text, True, self.text_color)
            text_rect = text_surf.get_rect(midleft=target_rect.move(5, 0).midleft)
            self.surface.blit(text_surf, text_rect)

            # hover highlight and arrow
            if is_hover:
                arrow = ">" if is_enabled else "<"
                arrow_surf = self.font.render(arrow, True, (255, 200, 0))
                arrow_rect = arrow_surf.get_rect(
                    centery=target_rect.centery,
                    right=row_rect_left.right - 5 if not is_enabled else row_rect_right.left + 15
                )
                self.surface.blit(arrow_surf, arrow_rect)

                overlay = Surface(row_rect.size, SRCALPHA)
                overlay.fill((255, 255, 255, 40))
                self.surface.blit(overlay, row_rect)

        # Blit scrollable content
        surface_rect = Rect(self.scroll, self.rect.size)
        surface.blit(self.surface.subsurface(surface_rect), self.rect)

        # Scrollbars
        self.draw_scrollbars(surface)

        # Frame border
        draw_rect(surface, self.app.theme.colors["accent"], self.rect, 2)


class Selector(Frame):
    """
    Single-choice selector with multiple options represented by icons.
    Options are a dict[name -> icon].
    Highlights the currently selected option.
    """
    def __init__(
        self,
        parent: Optional[UIWidget],
        pos: tuple[int, int],
        options: dict[str, Surface],  # keys are names, values are icons
        default_name: str | None = None,
        spacing: int = 16
    ) -> None:
        # Initial dummy rect; frame will adapt size based on options
        super().__init__(parent, Rect(pos, (0, 0)))
        self.options = options

        self.selected_index = self.names.index(default_name) if default_name else None
        self.hover_index = -1
        self.spacing = spacing

        # Calculate total width and max height
        self.option_sizes = [icon.get_size() for icon in self.icons]
        if self.option_sizes:
            total_width = (sum(w for w, _ in self.option_sizes) +
                           spacing * (len(self.option_sizes) - 1)) + 16
            max_height = max(h for _, h in self.option_sizes)+16
        else:
            total_width, max_height = 0, 0
        self.rect.size = (total_width, max_height)
        self.size = self.rect.size

    @property
    def names(self) -> list[str]:
        """
        Names of the Options of the Selector
        """
        return list(self.options.keys())

    @property
    def icons(self) -> list[Surface]:
        """
        Icons of the Options of the Selector
        """
        return [self.options[name] for name in self.names]

    @property
    def selected_name(self) -> Optional[str]:
        """
        Current name selection
        Return None if no options are in the Selector
        """
        return self.names[self.selected_index] if self.selected_index is not None else None

    def handle_event(self, event: Event) -> bool:
        if not self.displayed:
            return False

        if not self.hover:
            self.hover_index = -1

        if event.type == MOUSEMOTION and self.hover:
            mx, _ = event.pos
            relative_x = mx - self.global_rect.x
            current_x = 0
            self.hover_index = -1
            for i, (w, _) in enumerate(self.option_sizes):
                if current_x <= relative_x < current_x + w:
                    self.hover_index = i
                    break
                current_x += w + self.spacing
            return True

        if event.type == MOUSEBUTTONDOWN and event.button == 1 and self.hover:
            if self.hover_index != -1:
                self.selected_index = self.hover_index
                return True

        return super().handle_event(event)

    def render(self, surface: Surface) -> None:
        if not self.displayed:
            return

        self.surface.fill(self.app.theme.colors["bg"])

        # Draw options
        current_x = 0
        for i, icon in enumerate(self.icons):
            w, h = self.option_sizes[i]
            option_rect = Rect(current_x, 0, w+16, h+16)

            # Highlight selected option
            if i == self.selected_index:
                draw_rect(
                    self.surface,
                    self.app.theme.colors["accent"],
                    option_rect,
                    border_radius=4
                )
            elif i == self.hover_index:
                draw_rect(
                    self.surface,
                    self.app.theme.colors["hover"],
                    option_rect,
                    border_radius=4
                )

            icon_rect = icon.get_rect(center=option_rect.center)
            self.surface.blit(icon, icon_rect)
            current_x += w + self.spacing

        surface.blit(self.surface, self.rect)


class TabbedFrame(Frame):
    """
    A selector of frames: only one frame is displayed at a time.
    """
    def __init__(self,
                 parent: Optional[UIWidget],
                 rect: Rect,
                 selector: Selector | ListView,
                 width: Optional[int]=None,
                 height: Optional[int]=None
                 ) -> None:
        Frame.__init__(self, parent, rect, width, height)
        self.selector = selector
        self.frames: dict[str, Frame] = {}

    def attach(self, name: str, frame: Frame) -> None:
        """
        Attach a frame to the selector by name.
        """
        self.frames[name] = frame
        frame.parent = self
        frame.displayed = False

    def update_frame(self) -> None:
        """
        Update which frame is displayed based on the selector's current selection.
        """
        if isinstance(self.selector, ListView) and self.selector.selected_text is None:
            for frame in self.frames.values():
                frame.displayed = False
            return
        if isinstance(self.selector, Selector) and self.selector.selected_name is None:
            for frame in self.frames.values():
                frame.displayed = False
            return
        if isinstance(self.selector, ListView):
            selected_name = self.selector.selected_text
        else:
            selected_name = self.selector.selected_name
        for name, frame in self.frames.items():
            frame.displayed = name == selected_name

    def handle_event(self, event: Event) -> bool:
        self.update_frame()
        return Frame.handle_event(self, event)

    def render(self, surface):
        self.update_frame()
        super().render(surface)


class Popup(Frame):
    """
    Virtual modal popup (blocks input to underlying app)
    """
    def __init__(self,
                 app: UIApp,
                 parent_surface: Surface,
                 rect: Rect,
                 title: str = "Popup",
                 width: Optional[int] = None,
                 height: Optional[int] = None) -> None:
        Frame.__init__(self, None, rect, width=width, height=height)
        self.parent_surface = parent_surface
        self.app_ref = app
        self.title = title
        self.running = True

        # darkened background
        self.bg = self.parent_surface.copy()
        overlay = Surface(self.bg.get_size(), SRCALPHA)
        overlay.fill((0, 0, 0, 128))
        self.bg.blit(overlay, (0, 0))

        # add close button as widget
        self.close_button = Button(
            parent=self,
            rect=Rect(rect.width - 30, -30, 30, 30),
            label="X",
            callback=self.close
        )

    def _get_widget_at(self, pos: tuple[int, int]) -> Optional[UIWidget]:
        """
        Get the topmost widget at the given position (descend recursively)
        """
        if self.close_button.rect.move(self.rect.topleft).collidepoint(pos):
            return self.close_button
        def find_deepest(widget):
            if not widget.displayed or not widget.global_rect.collidepoint(pos):
                return None
            for child in reversed(widget.children):
                hit = find_deepest(child)
                if hit:
                    return hit
            return widget
        return find_deepest(self)

    def handle_event(self, event):
        if event.type == MOUSEMOTION:
            self.app.hovered_widget = self._get_widget_at(event.pos)
        if event.type == MOUSEBUTTONDOWN and event.button in [1, 3]:
            if not self.rect.inflate(0, -30).collidepoint(event.pos):
                self.close()
                return True
            self.app.focused_widget = self.app.hovered_widget
        return Frame.handle_event(self, event)

    def close(self) -> None:
        """
        Close the popup
        """
        self.running = False

    def render(self, surface: Surface) -> None:
        Frame.render(self, surface)

        # header
        header_rect = Rect(self.rect.x, self.rect.y - 30, self.rect.width, 30)
        draw_rect(surface, self.app.theme.colors["hover"], header_rect,
                  border_top_left_radius=10, border_top_right_radius=10)

        # title
        text = self.app.theme.font.render(self.title, True, self.app.theme.colors["text"])
        surface.blit(text, (self.rect.x + 10, self.rect.y - 22))

        # close button
        old_rect = self.close_button.rect.copy()
        self.close_button.rect.topleft = Vector2(self.rect.topright) + Vector2(-30, -30)
        self.close_button.render(surface)
        self.close_button.rect = old_rect

        # border
        draw_rect(surface, self.app.theme.colors["accent"], self.rect, 2)

    def run(self) -> None:
        """
        Blocking popup loop
        """
        while self.running:
            for event in get_events():
                if event.type == QUIT:
                    quit_pygame()
                    return
                self.handle_event(event)

            self.parent_surface.blit(self.bg, (0, 0))
            self.render(self.parent_surface)
            flip_display()


class Menubar(Frame):
    """
    Top-level menubar containing multiple dropdowns.
    Only one dropdown can be open at a time.
    Auto-positions dropdowns horizontally.
    """
    def __init__(self, parent: Optional[UIWidget], width: Optional[int]=None) -> None:
        width = width or parent.rect.width
        Frame.__init__(self, parent, Rect(0, 0, width, 24))
        self._next_x: int = 0

    def add_dropdown(self, label: str) -> MenubarDropdown:
        """
        Add a dropdown menu to the Menubar
        """
        width = self.app.theme.font.size(label)[0] + 16
        dd = MenubarDropdown(self, Rect(self._next_x, 0, width, 24), label)
        self._next_x += width
        return dd

    def render(self, surface: Surface) -> None:
        draw_rect(surface, self.app.theme.colors["bg"], self.rect)
        for dd in self.children:
            dd.render(surface)
        draw_line(
            surface,
            self.app.theme.colors["accent"],
            self.rect.bottomleft,
            self.rect.bottomright,
            2
        )


class MenubarDropdown(Frame):
    """
    Simple Dropdown Menu of a Menubar
    """
    def __init__(self, parent: Menubar, rect: Rect, label: str) -> None:
        Frame.__init__(self, parent, rect)
        self.label = label

    @property
    def focused(self) -> bool:
        """
        Check if any Option of the Widget is focused or if the widget himself is focused
        """
        focus = self.focus or any(opt.focus for opt in self.children)
        if not focus:
            for opt in self.children:
                opt.displayed = False
        else:
            for opt in self.children:
                opt.displayed = True
        return focus

    def add_option(self, label: str, callback: Callable) -> MenubarOption:
        """
        Add an option to the dropdown
        """
        y = 24*(len(self.children)+1)
        height = 24
        previous_width = max(opt.rect.width for opt in self.children) if len(self.children) else 0
        width = self.app.theme.font.size(label)[0]+16
        if width > previous_width:
            for opt in self.children:
                opt.rect.width = width
        else:
            width = previous_width
        rect = Rect(0, y, width, height)
        opt = MenubarOption(self, rect, label, callback)
        return opt

    def render(self, surface: Surface) -> None:
        label_surf = self.app.theme.font.render(self.label, True, self.app.theme.colors["text"])
        label_rect = label_surf.get_rect(center=self.rect.center)
        bg_color = (
            self.app.theme.colors["accent"] if self.focused else
            self.app.theme.colors["hover"] if self.hover else
            self.app.theme.colors["bg"]
        )
        draw_rect(surface, bg_color, self.rect)
        surface.blit(label_surf, label_rect)

        if self.focused:
            for opt in self.children:
                opt.render(surface)


class MenubarOption(UIWidget):
    """
    Simple Option of a Menubar
    """
    def __init__(self,
                 parent: MenubarDropdown,
                 rect: Rect,
                 label: str,
                 callback: Callable) -> None:
        UIWidget.__init__(self, parent, rect)
        self.label = label
        self.callback = callback

    def handle_event(self, event: Event) -> bool:
        if self.focus and event.type == MOUSEBUTTONUP and event.button == 1:
            self.callback()
            self.app.focused_widget = None
            return True
        return UIWidget.handle_event(self, event)

    def render(self, surface: Surface) -> None:
        color = (
            self.app.theme.colors["accent"] if self.focus else
            self.app.theme.colors["hover"] if self.hover else
            self.app.theme.colors["bg"]
        )
        draw_rect(surface, color, self.global_rect)
        label_surf = self.app.theme.font.render(self.label, True, self.app.theme.colors["text"])
        label_rect = label_surf.get_rect(midleft=self.global_rect.move(8, 0).midleft)
        surface.blit(label_surf, label_rect)
