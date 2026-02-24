# -*- coding: utf-8 -*-

"""
Main Application.
"""

# import built-in modules
from __future__ import annotations
from typing import Optional, TYPE_CHECKING, Callable

# import third-party modules
from pygame import init, Rect
from pygame import display
from pygame.event import get as get_events
from pygame import (
    QUIT,
)

# import libs
from libs.gui.pygame_ui import Popup, Label, Button, InvisibleButton, DropdownList, TextArea
from libs.gui.pygame_ui import UIApp, Frame, TabbedFrame
from libs.gui.text_tab_selector import TextTabSelector
from libs.gui.character_card_widget import CharacterCardWidget
from libs.gui.panels import SessionPanel, CombatPanel, ResourcePanel
from libs.resource_manager import ResourceManager
from libs.session_manager import SessionManager
from libs.dice import Dice
from libs import logger

if TYPE_CHECKING:
    from libs.character import Character


class SearchablePopup(Popup):
    """
    Custom Popup that tracks TextArea search changes and calls callbacks.
    """
    def __init__(self, app, surface, rect, title: str = ""):
        super().__init__(app, surface, rect, title)
        self.search_callbacks: dict[TextArea, Callable[[], None]] = {}
        self.search_texts: dict[TextArea, str] = {}
    
    def add_search_handler(self, text_area: TextArea, callback: Callable[[], None]) -> None:
        """Register a TextArea and callback for search changes."""
        self.search_callbacks[text_area] = callback
        self.search_texts[text_area] = text_area.text
    
    def handle_event(self, event) -> bool:
        """Handle events and check for search text changes."""
        result = super().handle_event(event)
        
        # Check if any search text has changed
        for text_area, callback in self.search_callbacks.items():
            if text_area.text != self.search_texts.get(text_area, ""):
                self.search_texts[text_area] = text_area.text
                callback()
        
        return result


# Create App
class App(UIApp):
    """
    Main Application Class.
    """
    def __init__(self, size: tuple[int, int] = (1280, 720)) -> None:
        self.screen = display.set_mode(size)
        UIApp.__init__(self, size)

        # Initialize managers
        self.resource_manager = ResourceManager()
        self.session_manager = SessionManager()
        self.session_manager.load_default_party()

        # Setup App main frame
        self.main_layer = self.add_layer()
        self.main_frame = Frame(None, Rect(0, 0, *self.size))
        self.main_layer.add(self.main_frame)

        # Create tab selector (text-based buttons)
        tab_selector_height = 30
        self.tab_selector = TextTabSelector(
            self.main_frame,
            Rect(0, 0, self.size[0], tab_selector_height),
            tabs=["Session", "Combat", "Ressources"],
            default_tab="Session"
        )

        # Create tabbed frame for the panels
        content_rect = Rect(0, tab_selector_height, self.size[0], self.size[1]-tab_selector_height)
        self.tabbed_frame = TabbedFrame(
            self.main_frame,
            content_rect,
            self.tab_selector
        )

        # Create panels for each tab
        session_panel = SessionPanel(
            self.tabbed_frame,
            content_rect.move(0,-tab_selector_height),
        )
        combat_panel = CombatPanel(
            self.tabbed_frame,
            content_rect.move(0,-tab_selector_height),
        )
        resource_panel = ResourcePanel(
            self.tabbed_frame,
            content_rect.move(0,-tab_selector_height),
        )

        # Attach panels to tabbed frame
        self.tabbed_frame.attach("Session", session_panel)
        self.tabbed_frame.attach("Combat", combat_panel)
        self.tabbed_frame.attach("Ressources", resource_panel)
        
        # Save button
        Button(self.main_frame, Rect(self.size[0] - 150, 0, 150, 30), "Sauvegarder", self.save_session)

        logger.info("App initialized")
        
    def save_session(self):
        """Convenience method to save the current session."""
        for character in self.session_manager.loaded_characters.values():
            character.save()
            character.create_sheet()
            logger.info(f"Saved character: {character.name}")
        logger.info("Session saved successfully.")

    def open_strike_form(self, attacker: Optional['Character'] = None) -> None:
        """
        Open a form popup to configure strike action with dice rolls and character selection.
        
        Args:
            attacker: Optional pre-selected attacker character
        """
        
        surface = display.get_surface()
        if not surface:
            return
        
        popup_w, popup_h = 900, 550
        rect = Rect(
            (surface.get_width() - popup_w) // 2,
            (surface.get_height() - popup_h) // 2,
            popup_w,
            popup_h,
        )
        popup = SearchablePopup(self, surface, rect, title="Strike Action")
        
        # Selection tracking
        selected_attacker: list[Optional[str]] = [attacker.name if attacker else None]
        selected_target: list[Optional[str]] = [None]
        
        # ===== LEFT PANEL: ATTACKERS =====
        Label(popup, (20, 20), "Attaquants:")
        
        attacker_search = TextArea(
            popup,
            Rect(20, 45, 140, 30),
            text="",
            padding=5
        )
        attacker_search.editable = True
        
        party_chars = self.session_manager.get_party_characters()
        if not party_chars:
            Label(popup, (20, 85), "Aucun personnage")
            popup.run()
            return
        
        # ===== CENTER PANEL: PARAMETERS =====
        Label(popup, (200, 20), "Paramètres:")
        
        # Selected attacker display
        selected_attacker_label = Label(popup, (200, 45), "Attaquant: Non sélectionné")
        
        # Selected target display
        selected_target_label = Label(popup, (200, 300), "Cible: Non sélectionnée")
        
        # Now create the attacker list frame AFTER labels are created
        attacker_list_frame = Frame(
            parent=popup,
            rect=Rect(20, 85, 160, 400)
        )
        
        def refresh_attacker_list(search_filter=""):
            attacker_list_frame.children.clear()
            
            matched_chars = [c for c in party_chars if search_filter.lower() in c.name.lower()]
            
            if not matched_chars:
                Label(attacker_list_frame, (10, 10), "Aucun match")
                return
            
            y = 10
            for char in matched_chars:
                # Create card with proper sizing
                card_width = 140
                card = CharacterCardWidget(
                    attacker_list_frame,
                    Rect(10, y, card_width, 100),
                    character=char,
                    show_action_buttons=False
                )
                
                # Add clickable overlay button
                def make_select_attacker(char_name):
                    def select_attacker():
                        selected_attacker[0] = char_name
                        selected_attacker_label.text = f"Attaquant: {char_name}"
                    return select_attacker
                
                InvisibleButton(
                    attacker_list_frame,
                    Rect(10, y, card_width, 100),
                    make_select_attacker(char.name)
                )
                y += 120
            
            # Update frame size for scroll
            content_height = max(y + 10, 400)
            attacker_list_frame.size = (160, content_height)
        
        # Initialize with all characters
        refresh_attacker_list()
        
        # Connect search callback
        def on_attacker_search_changed():
            refresh_attacker_list(attacker_search.text)
        
        popup.add_search_handler(attacker_search, on_attacker_search_changed)
        
        # ===== RIGHT PANEL: TARGETS =====
        Label(popup, (200, 85), "Dé Attaquant (d100):")
        attacker_dice_input = TextArea(
            popup,
            Rect(200, 110, 80, 30),
            text="",
            padding=5
        )
        attacker_dice_input.editable = True
        
        def roll_attacker_dice():
            dice = Dice.roll("1d100")
            attacker_dice_input.text = str(dice.dices_values[0])
        
        Button(
            popup,
            Rect(290, 110, 80, 30),
            "Lancer",
            roll_attacker_dice
        )
        
        # Dé Cible (CON)
        Label(popup, (200, 160), "Dé Cible (d100):")
        target_dice_input = TextArea(
            popup,
            Rect(200, 185, 80, 30),
            text="",
            padding=5
        )
        target_dice_input.editable = True
        
        def roll_target_dice():
            dice = Dice.roll("1d100")
            target_dice_input.text = str(dice.dices_values[0])
        
        Button(
            popup,
            Rect(290, 185, 80, 30),
            "Lancer",
            roll_target_dice
        )
        
        # ===== RIGHT PANEL: TARGETS =====
        Label(popup, (700, 20), "Cibles:")
        
        target_search = TextArea(
            popup,
            Rect(700, 45, 140, 30),
            text="",
            padding=5
        )
        target_search.editable = True
        
        all_chars = self.session_manager.get_all_loaded()
        if not all_chars:
            Label(popup, (700, 85), "Aucune cible")
            popup.run()
            return
        
        target_list_frame = Frame(
            parent=popup,
            rect=Rect(700, 85, 160, 400)
        )
        
        def refresh_target_list(search_filter=""):
            target_list_frame.children.clear()
            y = 10
            matched_chars = [c for c in all_chars if search_filter.lower() in c.name.lower()]
            
            for char in matched_chars:
                card = CharacterCardWidget(
                    target_list_frame,
                    Rect(0, y, 160, 110),
                    character=char,
                    show_action_buttons=False
                )
                
                # Add clickable overlay
                def make_select_target(char_name):
                    def select_target():
                        selected_target[0] = char_name
                        selected_target_label.text = f"Cible: {char_name}"
                    return select_target
                
                InvisibleButton(
                    target_list_frame,
                    Rect(0, y, 160, 110),
                    make_select_target(char.name)
                )
                y += 120
            
            # Update frame size for scroll
            content_height = max(y + 10, 400)
            target_list_frame.size = (160, content_height)
        
        refresh_target_list()
        
        # Connect search callback
        def on_target_search_changed():
            refresh_target_list(target_search.text)
        
        popup.add_search_handler(target_search, on_target_search_changed)
        
        # Validate button
        def on_validate():
            # Get dice values
            try:
                attacker_dice_val = int(attacker_dice_input.text) if attacker_dice_input.text else None
            except ValueError:
                attacker_dice_val = None
            
            try:
                target_dice_val = int(target_dice_input.text) if target_dice_input.text else None
            except ValueError:
                target_dice_val = None
            
            if not selected_attacker[0] or not selected_target[0]:
                return
            
            popup.close()
            self._resolve_strike(selected_attacker[0], selected_target[0], attacker_dice_val, target_dice_val)
        
        Button(
            popup,
            Rect(popup_w - 120, popup_h - 60, 100, 35),
            "Valider",
            on_validate
        )
        
        popup.run()
    
    def open_shoot_form(self, shooter: Optional['Character'] = None) -> None:
        """
        Open a form popup to configure shoot action with dice rolls and character selection.
        
        Args:
            shooter: Optional pre-selected shooter character
        """
        
        surface = display.get_surface()
        if not surface:
            return
        
        popup_w, popup_h = 900, 550
        rect = Rect(
            (surface.get_width() - popup_w) // 2,
            (surface.get_height() - popup_h) // 2,
            popup_w,
            popup_h,
        )
        popup = SearchablePopup(self, surface, rect, title="Shoot Action")
        
        # Selection tracking
        selected_shooter: list[Optional[str]] = [shooter.name if shooter else None]
        selected_target: list[Optional[str]] = [None]
        
        # ===== LEFT PANEL: SHOOTERS =====
        Label(popup, (20, 20), "Tireurs:")
        
        shooter_search = TextArea(
            popup,
            Rect(20, 45, 140, 30),
            text="",
            padding=5
        )
        shooter_search.editable = True
        
        party_chars = self.session_manager.get_party_characters()
        if not party_chars:
            Label(popup, (20, 85), "Aucun personnage")
            popup.run()
            return
        
        # ===== CENTER PANEL: PARAMETERS =====
        Label(popup, (200, 20), "Paramètres:")
        
        # Selected shooter display
        selected_shooter_label = Label(popup, (200, 45), "Tireur: Non sélectionné")
        
        # Selected target display
        selected_target_label = Label(popup, (200, 300), "Cible: Non sélectionnée")
        
        # Now create the shooter list frame AFTER labels are created
        shooter_list_frame = Frame(
            parent=popup,
            rect=Rect(20, 85, 160, 400)
        )
        
        def refresh_shooter_list(search_filter=""):
            shooter_list_frame.children.clear()
            
            matched_chars = [c for c in party_chars if search_filter.lower() in c.name.lower()]
            
            if not matched_chars:
                Label(shooter_list_frame, (10, 10), "Aucun personnage")
                return
            
            y = 10
            card_width = 140
            for char in matched_chars:
                card = CharacterCardWidget(
                    shooter_list_frame,
                    Rect(10, y, card_width, 100),
                    character=char,
                    show_action_buttons=False
                )
                
                # Add clickable overlay
                def make_select_shooter(char_name):
                    def select_shooter():
                        selected_shooter[0] = char_name
                        selected_shooter_label.text = f"Tireur: {char_name}"
                    return select_shooter
                
                InvisibleButton(
                    shooter_list_frame,
                    Rect(10, y, card_width, 100),
                    make_select_shooter(char.name)
                )
                y += 120
            
            # Update frame size for scroll
            content_height = max(y + 10, 400)
            shooter_list_frame.size = (160, content_height)
        
        refresh_shooter_list()
        
        # Connect search callback
        def on_shooter_search_changed():
            refresh_shooter_list(shooter_search.text)
        
        popup.add_search_handler(shooter_search, on_shooter_search_changed)
        
        # Dé Tireur (DEX)
        Label(popup, (200, 85), "Dé Tireur (d100):")
        shooter_dice_input = TextArea(
            popup,
            Rect(200, 110, 80, 30),
            text="",
            padding=5
        )
        shooter_dice_input.editable = True
        
        def roll_shooter_dice():
            dice = Dice.roll("1d100")
            shooter_dice_input.text = str(dice.dices_values[0])
        
        Button(
            popup,
            Rect(290, 110, 80, 30),
            "Lancer",
            roll_shooter_dice
        )
        
        # Dé Cible (AGI)
        Label(popup, (200, 160), "Dé Cible (d100):")
        target_dice_input = TextArea(
            popup,
            Rect(200, 185, 80, 30),
            text="",
            padding=5
        )
        target_dice_input.editable = True
        
        def roll_target_dice():
            dice = Dice.roll("1d100")
            target_dice_input.text = str(dice.dices_values[0])
        
        Button(
            popup,
            Rect(290, 185, 80, 30),
            "Lancer",
            roll_target_dice
        )
        
        # ===== RIGHT PANEL: TARGETS =====
        Label(popup, (700, 20), "Cibles:")
        
        target_search = TextArea(
            popup,
            Rect(700, 45, 140, 30),
            text="",
            padding=5
        )
        target_search.editable = True
        
        all_chars = self.session_manager.get_all_loaded()
        if not all_chars:
            Label(popup, (700, 85), "Aucune cible")
            popup.run()
            return
        
        target_list_frame = Frame(
            parent=popup,
            rect=Rect(700, 85, 160, 400)
        )
        
        def refresh_target_list_shoot(search_filter=""):
            target_list_frame.children.clear()
            
            matched_chars = [c for c in all_chars if search_filter.lower() in c.name.lower()]
            
            if not matched_chars:
                Label(target_list_frame, (10, 10), "Aucune cible")
                return
            
            y = 10
            card_width = 140
            for char in matched_chars:
                card = CharacterCardWidget(
                    target_list_frame,
                    Rect(10, y, card_width, 100),
                    character=char,
                    show_action_buttons=False
                )
                
                # Add clickable overlay
                def make_select_target(char_name):
                    def select_target():
                        selected_target[0] = char_name
                        selected_target_label.text = f"Cible: {char_name}"
                    return select_target
                
                InvisibleButton(
                    target_list_frame,
                    Rect(10, y, card_width, 100),
                    make_select_target(char.name)
                )
                y += 120
            
            # Update frame size for scroll
            content_height = max(y + 10, 400)
            target_list_frame.size = (160, content_height)
        
        refresh_target_list_shoot()
        
        # Connect search callback
        def on_target_search_changed_shoot():
            refresh_target_list_shoot(target_search.text)
        
        popup.add_search_handler(target_search, on_target_search_changed_shoot)
        
        # Validate button
        def on_validate():
            # Get dice values
            try:
                shooter_dice_val = int(shooter_dice_input.text) if shooter_dice_input.text else None
            except ValueError:
                shooter_dice_val = None
            
            try:
                target_dice_val = int(target_dice_input.text) if target_dice_input.text else None
            except ValueError:
                target_dice_val = None
            
            if not selected_shooter[0] or not selected_target[0]:
                return
            
            popup.close()
            self._resolve_shoot(selected_shooter[0], selected_target[0], shooter_dice_val, target_dice_val)
        
        Button(
            popup,
            Rect(popup_w - 120, popup_h - 60, 100, 35),
            "Valider",
            on_validate
        )
        
        popup.run()
    
    def open_cast_spell_form(self, caster: Optional['Character'] = None, spell_key: Optional[str] = None) -> None:
        """
        Open a form popup to configure cast spell action with SearchablePopup.
        Shows casters on left, spell/dices in center, targets on right.
        """
        surface = display.get_surface()
        if not surface:
            return
        
        popup_w, popup_h = 980, 550
        rect = Rect(
            (surface.get_width() - popup_w) // 2,
            (surface.get_height() - popup_h) // 2,
            popup_w,
            popup_h,
        )
        popup = SearchablePopup(self, surface, rect, title="Cast Spell")
        
        # Selection state
        selected_caster = [caster.name if caster else None]
        selected_target = [None]
        selected_spell = [spell_key]
        
        # Dices storage
        user_dices: dict[str, int] = {}
        target_dices: dict[str, int] = {}
        
        # Get all party characters and loaded characters
        party_chars = self.session_manager.get_party_characters()
        all_chars = self.session_manager.get_all_loaded()
        
        if not party_chars or not all_chars:
            Label(popup, (20, 20), "Pas assez de personnages disponibles")
            popup.run()
            return
        
        # Find initial caster
        initial_caster_name = caster.name if caster and caster in party_chars else party_chars[0].name
        initial_caster = self.session_manager.loaded_characters.get(initial_caster_name)
        selected_caster[0] = initial_caster_name
        
        # --- LEFT PANEL: Casters list ---
        Label(popup, (20, 20), "Lanceur:")
        caster_search = TextArea(popup, Rect(20, 45, 160, 30), text="", padding=5)
        caster_search.editable = True
        
        caster_list_frame = Frame(popup, Rect(20, 80, 160, 350))
        caster_search_text = [""]
        
        selected_caster_label = Label(popup, (20, 440), f"Lanceur: {selected_caster[0]}")
        
        def refresh_caster_list():
            search_filter = caster_search.text
            caster_list_frame.children.clear()
            
            matched_casters = [c for c in party_chars if search_filter.lower() in c.name.lower()]
            
            y = 10
            card_width = 140
            for char in matched_casters:
                card = CharacterCardWidget(
                    caster_list_frame,
                    Rect(10, y, card_width, 100),
                    character=char,
                    show_action_buttons=False
                )
                
                def make_select_caster(char_name):
                    def select_caster():
                        selected_caster[0] = char_name
                        selected_caster_label.text = f"Lanceur: {char_name}"
                        # Update spells for new caster
                        update_spell_list()
                    return select_caster
                
                InvisibleButton(
                    caster_list_frame,
                    Rect(10, y, card_width, 100),
                    make_select_caster(char.name)
                )
                
                y += 110
            
            caster_list_frame.size = (160, max(350, y))
        
        def update_spell_list():
            """Update spell dropdown when caster changes."""
            caster = self.session_manager.loaded_characters.get(selected_caster[0])
            spell_names = list(caster.spells.keys()) if caster else []
            spell_dropdown.options = spell_names
            spell_dropdown.selected_index = 0
            selected_spell[0] = spell_names[0] if spell_names else None
        
        popup.add_search_handler(caster_search, refresh_caster_list)
        refresh_caster_list()
        
        # --- CENTER PANEL: Spell, dices ---
        center_x = 210
        Label(popup, (center_x, 20), "Sort:")
        spell_names = list(initial_caster.spells.keys()) if initial_caster else []
        spell_dropdown = DropdownList(popup, (center_x, 45), spell_names)
        if spell_key and spell_key in spell_names:
            spell_dropdown.selected_index = spell_names.index(spell_key)
            selected_spell[0] = spell_key
        
        # User dices labels
        user_dice_labels: list[Label] = []
        user_dice_display_y = 135
        
        def refresh_user_dice_display():
            nonlocal user_dice_labels
            for label in user_dice_labels:
                popup.children.remove(label)
            user_dice_labels.clear()
            
            y = user_dice_display_y
            for stat, value in user_dices.items():
                label = Label(popup, (center_x + 10, y), f"{stat}: {value}")
                user_dice_labels.append(label)
                y += 20
        
        Label(popup, (center_x, 85), "Dés Lanceur:")
        
        def add_user_dice():
            sub_w, sub_h = 350, 250
            sub_rect = Rect(
                (surface.get_width() - sub_w) // 2,
                (surface.get_height() - sub_h) // 2,
                sub_w,
                sub_h,
            )
            sub_popup = Popup(self, surface, sub_rect, title="Add User Dice")
            
            Label(sub_popup, (20, 20), "Stat:")
            stat_names = ["str", "dex", "con", "int", "wis", "cha", "per", "agi", "luc", "sur"]
            stat_dropdown = DropdownList(sub_popup, (20, 45), stat_names)
            
            Label(sub_popup, (20, 90), "Valeur (d100):")
            value_input = TextArea(sub_popup, Rect(20, 115, 80, 30), text="", padding=5)
            value_input.editable = True
            
            def roll_dice():
                dice = Dice.roll("1d100")
                value_input.text = str(dice.dices_values[0])
            
            Button(sub_popup, Rect(110, 115, 80, 30), "Lancer", roll_dice)
            
            def validate_dice():
                stat = stat_dropdown.get_text()
                try:
                    value = int(value_input.text) if value_input.text else None
                except ValueError:
                    value = None
                
                if stat and value is not None:
                    user_dices[stat] = value
                    refresh_user_dice_display()
                
                sub_popup.close()
            
            Button(sub_popup, Rect(sub_w - 120, sub_h - 60, 100, 35), "Valider", validate_dice)
            sub_popup.run()
        
        Button(popup, Rect(center_x, 105, 200, 30), "Ajouter dé Lanceur", add_user_dice)
        
        # Target dices labels
        target_dice_labels: list[Label] = []
        target_dice_display_y = 135
        
        def refresh_target_dice_display():
            nonlocal target_dice_labels
            for label in target_dice_labels:
                popup.children.remove(label)
            target_dice_labels.clear()
            
            y = target_dice_display_y
            for stat, value in target_dices.items():
                label = Label(popup, (center_x + 260, y), f"{stat}: {value}")
                target_dice_labels.append(label)
                y += 20
        
        Label(popup, (center_x+250, 85), "Dés Cible:")
        
        def add_target_dice():
            sub_w, sub_h = 350, 250
            sub_rect = Rect(
                (surface.get_width() - sub_w) // 2,
                (surface.get_height() - sub_h) // 2,
                sub_w,
                sub_h,
            )
            sub_popup = Popup(self, surface, sub_rect, title="Add Target Dice")
            
            Label(sub_popup, (20, 20), "Stat:")
            stat_names = ["str", "dex", "con", "int", "wis", "cha", "per", "agi", "luc", "sur"]
            stat_dropdown = DropdownList(sub_popup, (20, 45), stat_names)
            
            Label(sub_popup, (20, 90), "Valeur (d100):")
            value_input = TextArea(sub_popup, Rect(20, 115, 80, 30), text="", padding=5)
            value_input.editable = True
            
            def roll_dice():
                dice = Dice.roll("1d100")
                value_input.text = str(dice.dices_values[0])
            
            Button(sub_popup, Rect(110, 115, 80, 30), "Lancer", roll_dice)
            
            def validate_dice():
                stat = stat_dropdown.get_text()
                try:
                    value = int(value_input.text) if value_input.text else None
                except ValueError:
                    value = None
                
                if stat and value is not None:
                    target_dices[stat] = value
                    refresh_target_dice_display()
                
                sub_popup.close()
            
            Button(sub_popup, Rect(sub_w - 120, sub_h - 60, 100, 35), "Valider", validate_dice)
            sub_popup.run()
        
        Button(popup, Rect(center_x+250, 105, 200, 30), "Ajouter dé Cible", add_target_dice)
        
        refresh_user_dice_display()
        refresh_target_dice_display()
        
        # --- RIGHT PANEL: Targets list ---
        right_x = 780
        Label(popup, (right_x, 20), "Cible:")
        target_search = TextArea(popup, Rect(right_x, 45, 160, 30), text="", padding=5)
        target_search.editable = True
        
        target_list_frame = Frame(popup, Rect(right_x, 80, 160, 350))
        
        selected_target_label = Label(popup, (right_x, 440), "Cible: Non sélectionnée")
        
        def refresh_target_list():
            search_filter = target_search.text
            target_list_frame.children.clear()
            
            matched_targets = [c for c in all_chars if search_filter.lower() in c.name.lower()]
            
            y = 10
            card_width = 140
            for char in matched_targets:
                card = CharacterCardWidget(
                    target_list_frame,
                    Rect(10, y, card_width, 100),
                    character=char,
                    show_action_buttons=False
                )
                
                def make_select_target(char_name):
                    def select_target():
                        selected_target[0] = char_name
                        selected_target_label.text = f"Cible: {char_name}"
                    return select_target
                
                InvisibleButton(
                    target_list_frame,
                    Rect(10, y, card_width, 100),
                    make_select_target(char.name)
                )
                
                y += 110
            
            target_list_frame.size = (160, max(350, y))
        
        popup.add_search_handler(target_search, refresh_target_list)
        refresh_target_list()
        
        # Validate button
        def on_validate():
            caster_name = selected_caster[0]
            spell_name = spell_dropdown.get_text()
            target_name = selected_target[0]
            
            if not caster_name or not spell_name or not target_name:
                return
            
            popup.close()
            self._resolve_cast_spell(caster_name, spell_name, target_name, user_dices if user_dices else None, target_dices if target_dices else None)
        
        Button(
            popup,
            Rect(popup_w - 120, popup_h - 60, 100, 35),
            "Valider",
            on_validate
        )
        
        popup.run()
    
    def _resolve_strike(self, attacker_name: str, target_name: str, 
                       attacker_dice_val: Optional[int], target_dice_val: Optional[int]) -> None:
        """
        Resolve strike action and show result popup.
        """
        
        surface = display.get_surface()
        if not surface:
            return
        
        # Get characters
        attacker = self.session_manager.loaded_characters.get(attacker_name)
        target = self.session_manager.loaded_characters.get(target_name)
        
        if not attacker or not target:
            return
        
        # Create dice objects
        attacker_dice = Dice("1d100", [attacker_dice_val]) if attacker_dice_val is not None else None
        target_dice = Dice("1d100", [target_dice_val]) if target_dice_val is not None else None
        
        # Perform strike
        damage_dice = attacker.strike(target, attacker_dice, target_dice)
        
        # Show result
        popup_w, popup_h = 450, 250
        rect = Rect(
            (surface.get_width() - popup_w) // 2,
            (surface.get_height() - popup_h) // 2,
            popup_w,
            popup_h,
        )
        popup = Popup(self, surface, rect, title="Résolution Strike")
        Label(popup, (20, 20), f"{attacker_name} attaque {target_name}")
        Label(popup, (20, 50), f"Attaquant: {attacker_dice.dices_values[0] if attacker_dice else 'Auto'}")
        Label(popup, (20, 75), f"Cible: {target_dice.dices_values[0] if target_dice else 'Auto'}")
        Label(popup, (20, 110), f"Dégâts: {damage_dice}")
        
        # Roll damage button
        def roll_damage():
            if damage_dice and damage_dice != "0d0":
                dmg = Dice.roll(damage_dice)
                Label(popup, (20, 145), f"Total dégâts: {sum(dmg.dices_values)}")
        
        Button(
            popup,
            Rect(20, 180, 120, 35),
            "Lancer dégâts",
            roll_damage
        )
        
        popup.run()
    
    def _resolve_shoot(self, shooter_name: str, target_name: str, 
                      shooter_dice_val: Optional[int], target_dice_val: Optional[int]) -> None:
        """
        Resolve shoot action and show result popup.
        """
        
        surface = display.get_surface()
        if not surface:
            return
        
        # Get characters
        shooter = self.session_manager.loaded_characters.get(shooter_name)
        target = self.session_manager.loaded_characters.get(target_name)
        
        if not shooter or not target:
            return
        
        # Create dice objects
        shooter_dice = Dice("1d100", [shooter_dice_val]) if shooter_dice_val is not None else None
        target_dice = Dice("1d100", [target_dice_val]) if target_dice_val is not None else None
        
        # Perform shoot
        damage_dice = shooter.shoot(target, shooter_dice, target_dice)
        
        # Show result
        popup_w, popup_h = 450, 250
        rect = Rect(
            (surface.get_width() - popup_w) // 2,
            (surface.get_height() - popup_h) // 2,
            popup_w,
            popup_h,
        )
        popup = Popup(self, surface, rect, title="Résolution Shoot")
        Label(popup, (20, 20), f"{shooter_name} tire sur {target_name}")
        Label(popup, (20, 50), f"Tireur: {shooter_dice.dices_values[0] if shooter_dice else 'Auto'}")
        Label(popup, (20, 75), f"Cible: {target_dice.dices_values[0] if target_dice else 'Auto'}")
        Label(popup, (20, 110), f"Dégâts: {damage_dice}")
        
        # Roll damage button
        def roll_damage():
            if damage_dice and damage_dice != "0d0":
                dmg = Dice.roll(damage_dice)
                Label(popup, (20, 145), f"Total dégâts: {sum(dmg.dices_values)}")
        
        Button(
            popup,
            Rect(20, 180, 120, 35),
            "Lancer dégâts",
            roll_damage
        )
        
        popup.run()
    
    def _resolve_cast_spell(self, caster_name: str, spell_name: str, target_name: str, 
                           user_dices: Optional[dict[str, int]] = None,
                           target_dices: Optional[dict[str, int]] = None) -> None:
        """
        Resolve cast spell action and show result popup.
        """
        
        surface = display.get_surface()
        if not surface:
            return
        
        # Get characters
        caster = self.session_manager.loaded_characters.get(caster_name)
        target = self.session_manager.loaded_characters.get(target_name)
        
        if not caster or not target:
            return
        
        # Cast spell with dice values
        effect_log = caster.cast_spell(spell_name, target, user_dices, target_dices)
        
        # Show result
        popup_w, popup_h = 450, 300
        rect = Rect(
            (surface.get_width() - popup_w) // 2,
            (surface.get_height() - popup_h) // 2,
            popup_w,
            popup_h,
        )
        popup = Popup(self, surface, rect, title="Résolution Cast Spell")
        Label(popup, (20, 20), f"{caster_name} lance {spell_name}")
        Label(popup, (20, 50), f"sur {target_name}")
        Label(popup, (20, 90), "Effets appliqués:")
        
        # Display effect logs with word wrap
        y = 120
        for line in effect_log.split("\n"):
            # Simple word wrapping
            words = line.split()
            current_line = ""
            for word in words:
                if len(current_line) + len(word) + 1 > 40:  # Rough estimate based on character count
                    if current_line:
                        Label(popup, (30, y), current_line)
                        y += 20
                    current_line = word
                else:
                    current_line += (" " if current_line else "") + word
            if current_line:
                Label(popup, (30, y), current_line)
                y += 20
        
        popup.run()

    def run(self) -> None:
        """
        Launch mainloop of the app.
        """
        running = True
        while running:
            for event in get_events():
                if event.type == QUIT:
                    running = False
                else:
                    self.handle_events(event)

            self.render(self.screen)
            display.flip()

        display.quit()

if __name__ == "__main__":
    init()
    app = App()
    app.run()
