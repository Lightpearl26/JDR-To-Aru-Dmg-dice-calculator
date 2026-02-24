# -*- coding: utf-8 -*-

"""
Resource Panel - Management of characters, items, and spells
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
from pathlib import Path
import json

from pygame import Rect, KEYDOWN, K_RETURN, K_ESCAPE

from ..pygame_ui import Frame, UIWidget, Button, ListView, Label, Popup, TextArea, DropdownList
from ..text_tab_selector import TextTabSelector
from ..item_card_widget import ItemCardWidget
from ..spell_card_widget import SpellCardWidget
from ..character_summary_widget import CharacterSummaryWidget
from ...config import CHARACTERS_FOLDER, ITEMS_FOLDER, SPELLS_FOLDER

if TYPE_CHECKING:
    from libs.session_manager import SessionManager
    from libs.resource_manager import ResourceManager


class ResourcePanel(Frame):
    """
    Panel for managing game resources.
    
    Features:
    - Sub-tabs for Characters / Items / Spells
    - List of existing resources
    - Create/Edit/Delete functionality
    - Save to JSON in assets/
    """

    def __init__(
        self,
        parent: Optional[UIWidget], 
        rect: Rect,
    ) -> None:
        Frame.__init__(self, parent, rect)
        
        # Current resource type
        self.current_type = "Characters"
        
        # UI widgets
        self.type_selector: Optional[TextTabSelector] = None
        self.resource_list: Optional[ListView] = None
        self.create_button: Optional[Button] = None
        self.load_button: Optional[Button] = None
        self.modify_button: Optional[Button] = None
        self.remove_button: Optional[Button] = None
        self.character_summary: Optional[CharacterSummaryWidget] = None
        self.item_card: Optional[ItemCardWidget] = None
        self.spell_card: Optional[SpellCardWidget] = None

        self._build_ui()

    @property
    def session_manager(self) -> SessionManager:
        """Convenience property to access the session manager from the app."""
        return self.app.session_manager
    
    @property
    def resource_manager(self) -> ResourceManager:
        """Convenience property to access the resource manager from the app."""
        return self.app.resource_manager
    
    def _build_ui(self) -> None:
        """Initialize UI"""
        # Layout constants
        margin = 15
        spacing = 10
        
        # Sub-tab selector for resource types (bigger and clearer)
        selector_height = 50
        self.type_selector = TextTabSelector(
            self,
            Rect(margin, margin, self.rect.width - 2*margin, selector_height),
            tabs=["Characters", "Items", "Spells"],
            default_tab="Characters",
            font_size=18
        )
        
        # Instructions (compact, right after selector)
        inst_y = margin + selector_height + spacing
        Label(self, (margin, inst_y), "Create: new | Load: to session | Modify: edit | Remove: delete")
        
        # Action buttons (horizontal layout, larger and better spaced - now 4 buttons)
        button_y = inst_y + 25
        button_width = 100
        button_height = 40
        button_start_x = margin
        
        self.create_button = Button(
            self,
            Rect(button_start_x, button_y, button_width, button_height),
            "Create",
            self._on_create
        )
        
        self.load_button = Button(
            self,
            Rect(button_start_x + button_width + spacing, button_y, button_width, button_height),
            "Load",
            self._on_load
        )
        
        self.modify_button = Button(
            self,
            Rect(button_start_x + 2*(button_width + spacing), button_y, button_width, button_height),
            "Modify",
            self._on_modify
        )
        
        self.remove_button = Button(
            self,
            Rect(button_start_x + 3*(button_width + spacing), button_y, button_width, button_height),
            "Remove",
            self._on_remove
        )
        
        # Resource list (left side)
        list_y = button_y + button_height + spacing
        list_width = 350
        list_height = self.rect.height - list_y - margin
        
        self.resource_list = ListView(
            self,
            Rect(margin, list_y, list_width, list_height),
            items=self._get_current_resources()
        )
        
        # Cards (right side - shows details of selected resource)
        card_x = margin + list_width + spacing
        card_width = self.rect.width - card_x - margin
        card_height = 500  # Will adjust dynamically
        
        # CharacterSummary (for Characters tab)
        self.character_summary = CharacterSummaryWidget(
            self,
            Rect(card_x, list_y, card_width, card_height),
            character_data=None
        )
        self.character_summary.displayed = False  # Hide until a character is selected
        
        # ItemCard (for Items tab)
        self.item_card = ItemCardWidget(
            self,
            Rect(card_x, list_y, card_width, card_height),
            item=None
        )
        self.item_card.displayed = False  # Hide until an item is selected
        
        # SpellCard (for Spells tab) - with cast button disabled for ResourcePanel
        self.spell_card = SpellCardWidget(
            self,
            Rect(card_x, list_y, card_width, card_height),
            spell=None,
            enable_cast_button=False
        )
        self.spell_card.displayed = False  # Hide until a spell is selected
    
    def _get_current_resources(self) -> list[str]:
        """Get list of resources for the current type."""
        if self.current_type == "Characters":
            return self.resource_manager.get_character_names()
        elif self.current_type == "Items":
            return self.resource_manager.get_item_names()
        elif self.current_type == "Spells":
            return self.resource_manager.get_spell_names()
        return []
    
    def _refresh_resource_list(self) -> None:
        """Refresh the resource list display."""
        if self.resource_list:
            self.resource_list.items = self._get_current_resources()
            # Adjust content height
            self.resource_list.size = (
                self.resource_list.rect.width,
                max(len(self.resource_list.items) * self.resource_list.item_height, 
                    self.resource_list.rect.height)
            )
        # Hide cards when list changes
        if self.item_card:
            self.item_card.displayed = False
        if self.spell_card:
            self.spell_card.displayed = False
    
    def _update_resource_card(self) -> None:
        """Update the resource card with the currently selected resource."""
        if not self.resource_list:
            return
        
        selected_name = self.resource_list.selected_text
        
        # Hide all cards first
        if self.character_summary:
            self.character_summary.displayed = False
        if self.item_card:
            self.item_card.displayed = False
        if self.spell_card:
            self.spell_card.displayed = False
        
        if not selected_name:
            return
        
        # Show CharacterSummary for Characters
        if self.current_type == "Characters" and self.character_summary:
            try:
                # Load character JSON data
                char_path = Path(CHARACTERS_FOLDER) / f"{selected_name}.json"
                if char_path.exists():
                    with open(char_path, 'r', encoding='utf-8') as f:
                        char_data = json.load(f)
                    self.character_summary.set_character_data(char_data)
                    self.character_summary.displayed = True
            except Exception as e:
                print(f"Error loading character {selected_name}: {e}")
        
        # Show ItemCard for Items
        elif self.current_type == "Items" and self.item_card:
            try:
                item = self.resource_manager.load_item(selected_name)
                if item:
                    self.item_card.set_item(item, selected_name, quantity=1)
                    card_height = self.item_card.get_required_height(self.item_card.rect.width)
                    self.item_card.rect.height = card_height
                    self.item_card.displayed = True
            except Exception as e:
                print(f"Error loading item {selected_name}: {e}")
        
        # Show SpellCard for Spells
        elif self.current_type == "Spells" and self.spell_card:
            try:
                spell = self.resource_manager.load_spell(selected_name)
                if spell:
                    self.spell_card.set_spell(spell, selected_name)
                    card_height = self.spell_card.get_required_height(self.spell_card.rect.width)
                    self.spell_card.rect.height = card_height
                    self.spell_card.displayed = True
            except Exception as e:
                print(f"Error loading spell {selected_name}: {e}")
    
    def handle_event(self, event) -> bool:
        if not self.displayed:
            return False
        
        # Store old selection to detect changes
        old_selection = self.resource_list.selected_text if self.resource_list else None
        
        # Check if type selector changed
        if self.type_selector:
            old_type = self.current_type
            result = super().handle_event(event)
            new_type = self.type_selector.selected_name
            if new_type != old_type:
                self.current_type = new_type
                self._refresh_resource_list()
                self._update_resource_card()
            
            # Check if selection changed in list
            new_selection = self.resource_list.selected_text if self.resource_list else None
            if new_selection != old_selection:
                self._update_resource_card()
            
            return result
        
        return super().handle_event(event)
    
    def _on_create(self) -> None:
        """Handle Create button click."""
        if self.current_type == "Items":
            self._create_item_form()
        elif self.current_type == "Characters":
            self._create_character_form()
        elif self.current_type == "Spells":
            self._create_spell_form()
    
    def _on_modify(self) -> None:
        """Handle Modify button click."""
        if not self.resource_list or not self.resource_list.selected_text:
            print("No resource selected")
            return
        
        if self.current_type == "Items":
            self._modify_item_form()
        elif self.current_type == "Characters":
            self._modify_character_form()
        elif self.current_type == "Spells":
            self._modify_spell_form()
    
    def _modify_item_form(self) -> None:
        """
        Show a form to modify an existing item.
        """
        # Get selected item name
        selected_name = self.resource_list.selected_text
        if not selected_name:
            return
        
        # Load existing item data
        try:
            item = self.resource_manager.load_item(selected_name)
            if not item:
                print(f"Error: Could not load item {selected_name}")
                return
        except Exception as e:
            print(f"Error loading item {selected_name}: {e}")
            return
        
        # Available stats for modifiers
        STATS = ["str", "dex", "con", "int", "wis", "cha", "per", "agi", "luc", "sur", 
                 "stamina", "mental_health", "drug_health"]
        
        # Create popup (larger to fit modifiers section)
        popup_width = 600
        popup_height = 550
        popup_x = (self.app.size[0] - popup_width) // 2
        popup_y = (self.app.size[1] - popup_height) // 2
        
        popup = Popup(
            self.app,
            self.app.screen,
            Rect(popup_x, popup_y, popup_width, popup_height),
            title=f"Modify Item: {selected_name}"
        )
        
        # Name field (pre-filled)
        Label(popup, (20, 20), "Item Name:")
        name_input = TextArea(
            popup,
            Rect(20, 45, popup_width - 40, 30),
            text=item.name,
            padding=5
        )
        name_input.editable = True
        
        # Description field (pre-filled)
        Label(popup, (20, 85), "Description:")
        desc_input = TextArea(
            popup,
            Rect(20, 110, popup_width - 40, 80),
            text=item.description,
            padding=5
        )
        desc_input.editable = True
        
        # Modifiers section
        Label(popup, (20, 200), "Modifiers:")
        
        # List to store modifiers [["stat", value], ...] (pre-filled with existing)
        modifiers = [list(mod) for mod in item.modifier] if item.modifier else []
        modifier_labels = []  # Store Label widgets to update display
        
        # Dropdown for stat selection
        Label(popup, (20, 230), "Stat:")
        stat_dropdown = DropdownList(
            popup,
            (70, 230),
            items=STATS,
            max_visible_items=8
        )
        
        # Value input
        Label(popup, (200, 230), "Value:")
        value_input = TextArea(
            popup,
            Rect(260, 230, 80, 30),
            text="",
            padding=5
        )
        value_input.editable = True
        
        def refresh_modifier_display():
            """Refresh the display of modifiers list."""
            # Clear old labels
            for lbl in modifier_labels:
                if lbl in popup.children:
                    popup.children.remove(lbl)
            modifier_labels.clear()
            
            # Create new labels
            y_offset = 330
            for i, (stat, val) in enumerate(modifiers):
                # Modifier display
                mod_text = f"{i+1}. {stat}: {val:+d}"
                lbl = Label(popup, (40, y_offset), mod_text)
                modifier_labels.append(lbl)
                
                # Delete button
                def make_delete_handler(index):
                    def delete_handler():
                        modifiers.pop(index)
                        refresh_modifier_display()
                    return delete_handler
                
                del_btn = Button(
                    popup,
                    Rect(200, y_offset - 2, 60, 25),
                    "Delete",
                    make_delete_handler(i)
                )
                modifier_labels.append(del_btn)
                
                y_offset += 30
        
        def on_add_modifier():
            """Add a modifier to the list."""
            try:
                val_text = value_input.text.strip()
                if not val_text:
                    print("Error: Value is required")
                    return
                
                value = int(val_text)
                stat = stat_dropdown.get_text()
                
                modifiers.append([stat, value])
                value_input.text = ""  # Clear input
                refresh_modifier_display()
                print(f"Added modifier: {stat} {value:+d}")
                
            except ValueError:
                print("Error: Value must be a number")
        
        # Add Modifier button
        Button(
            popup,
            Rect(360, 230, 120, 30),
            "Add Modifier",
            on_add_modifier
        )
        
        # Modifiers display area
        Label(popup, (20, 300), "Current Modifiers:")
        
        # Refresh display with existing modifiers
        refresh_modifier_display()
        
        # Set focus on name input
        self.app.focused_widget = name_input
        
        def on_save():
            new_name = name_input.text.strip().replace(" ", "_")
            description = desc_input.text.strip()
            
            if not new_name:
                print("Error: Item name is required")
                return
            
            # Get old and new file paths
            old_file = Path(ITEMS_FOLDER) / f"{selected_name}.json"
            new_file = Path(ITEMS_FOLDER) / f"{new_name}.json"
            
            # Check if new name conflicts with another item
            if new_name != selected_name and new_file.exists():
                print(f"Error: Item '{new_name}' already exists")
                return
            
            # Create item data
            item_data = {
                "name": new_name,
                "description": description
            }
            
            # Add modifiers if any
            if modifiers:
                item_data["modifier"] = modifiers
            
            try:
                # Delete old file if name changed
                if new_name != selected_name and old_file.exists():
                    old_file.unlink()
                
                # Save to JSON file
                with open(new_file, "w", encoding="utf-8") as f:
                    json.dump(item_data, f, indent=4, ensure_ascii=False)
                
                print(f"Item modified: {new_name}")
                if modifiers:
                    print(f"  with {len(modifiers)} modifier(s)")
                
                # Reload resources and refresh list
                self.resource_manager.reload()
                self._refresh_resource_list()
                
                popup.close()
            except Exception as e:
                print(f"Error saving item: {e}")
        
        def on_cancel():
            popup.close()
        
        # Add buttons
        Button(
            popup,
            Rect(popup_width - 180, popup_height - 50, 80, 30),
            "Save",
            on_save
        )
        Button(
            popup,
            Rect(popup_width - 90, popup_height - 50, 80, 30),
            "Cancel",
            on_cancel
        )
        
        # Handle Escape key
        original_handle = popup.handle_event
        def handle_with_keys(event):
            if event.type == KEYDOWN and event.key == K_ESCAPE:
                on_cancel()
                return True
            return original_handle(event)
        
        popup.handle_event = handle_with_keys
        
        # Run popup
        popup.run()

    def _create_item_form(self) -> None:
        """
        Show a form to create a new item with modifiers support.
        """
        # Available stats for modifiers
        STATS = ["str", "dex", "con", "int", "wis", "cha", "per", "agi", "luc", "sur", 
                 "stamina", "mental_health", "drug_health"]
        
        # Create popup (larger to fit modifiers section)
        popup_width = 600
        popup_height = 550
        popup_x = (self.app.size[0] - popup_width) // 2
        popup_y = (self.app.size[1] - popup_height) // 2
        
        popup = Popup(
            self.app,
            self.app.screen,
            Rect(popup_x, popup_y, popup_width, popup_height),
            title="Create New Item"
        )
        
        # Name field
        Label(popup, (20, 20), "Item Name:")
        name_input = TextArea(
            popup,
            Rect(20, 45, popup_width - 40, 30),
            text="",
            padding=5
        )
        name_input.editable = True
        
        # Description field
        Label(popup, (20, 85), "Description:")
        desc_input = TextArea(
            popup,
            Rect(20, 110, popup_width - 40, 80),
            text="",
            padding=5
        )
        desc_input.editable = True
        
        # Modifiers section
        Label(popup, (20, 200), "Modifiers:")
        
        # List to store modifiers [["stat", value], ...]
        modifiers = []
        modifier_labels = []  # Store Label widgets to update display
        
        # Dropdown for stat selection
        Label(popup, (20, 230), "Stat:")
        stat_dropdown = DropdownList(
            popup,
            (70, 230),
            items=STATS,
            max_visible_items=8
        )
        
        # Value input
        Label(popup, (200, 230), "Value:")
        value_input = TextArea(
            popup,
            Rect(260, 230, 80, 30),
            text="",
            padding=5
        )
        value_input.editable = True
        
        def refresh_modifier_display():
            """Refresh the display of modifiers list."""
            # Clear old labels
            for lbl in modifier_labels:
                if lbl in popup.children:
                    popup.children.remove(lbl)
            modifier_labels.clear()
            
            # Create new labels
            y_offset = 330
            for i, (stat, val) in enumerate(modifiers):
                # Modifier display
                mod_text = f"{i+1}. {stat}: {val:+d}"
                lbl = Label(popup, (40, y_offset), mod_text)
                modifier_labels.append(lbl)
                
                # Delete button
                def make_delete_handler(index):
                    def delete_handler():
                        modifiers.pop(index)
                        refresh_modifier_display()
                    return delete_handler
                
                del_btn = Button(
                    popup,
                    Rect(200, y_offset - 2, 60, 25),
                    "Delete",
                    make_delete_handler(i)
                )
                modifier_labels.append(del_btn)  # Track for cleanup
                
                y_offset += 30
        
        def on_add_modifier():
            """Add a modifier to the list."""
            try:
                val_text = value_input.text.strip()
                if not val_text:
                    print("Error: Value is required")
                    return
                
                value = int(val_text)
                stat = stat_dropdown.get_text()
                
                modifiers.append([stat, value])
                value_input.text = ""  # Clear input
                refresh_modifier_display()
                print(f"Added modifier: {stat} {value:+d}")
                
            except ValueError:
                print("Error: Value must be a number")
        
        # Add Modifier button
        Button(
            popup,
            Rect(360, 230, 120, 30),
            "Add Modifier",
            on_add_modifier
        )
        
        # Modifiers display area
        Label(popup, (20, 300), "Current Modifiers:")
        
        # Set focus on name input
        self.app.focused_widget = name_input
        
        def on_save():
            name = name_input.text.strip().replace(" ", "_")
            description = desc_input.text.strip()
            
            if not name:
                print("Error: Item name is required")
                return
            
            # Check if item already exists
            item_file = Path(ITEMS_FOLDER) / f"{name}.json"
            if item_file.exists():
                print(f"Error: Item '{name}' already exists")
                return
            
            # Create item data
            item_data = {
                "name": name,
                "description": description
            }
            
            # Add modifiers if any
            if modifiers:
                item_data["modifier"] = modifiers
            
            try:
                # Save to JSON file
                with open(item_file, "w", encoding="utf-8") as f:
                    json.dump(item_data, f, indent=4, ensure_ascii=False)
                
                print(f"Item created: {name}")
                if modifiers:
                    print(f"  with {len(modifiers)} modifier(s)")
                
                # Reload resources and refresh list
                self.resource_manager.reload()
                self._refresh_resource_list()
                
                popup.close()
            except Exception as e:
                print(f"Error saving item: {e}")
        
        def on_cancel():
            popup.close()
        
        # Add buttons
        Button(
            popup,
            Rect(popup_width - 180, popup_height - 50, 80, 30),
            "Save",
            on_save
        )
        Button(
            popup,
            Rect(popup_width - 90, popup_height - 50, 80, 30),
            "Cancel",
            on_cancel
        )
        
        # Handle Escape key
        original_handle = popup.handle_event
        def handle_with_keys(event):
            if event.type == KEYDOWN and event.key == K_ESCAPE:
                on_cancel()
                return True
            return original_handle(event)
        
        popup.handle_event = handle_with_keys
        
        # Run popup
        popup.run()
    
    def _on_load(self) -> None:
        """Handle Load button click. Only works for Characters."""
        # Only allow loading characters
        if self.current_type != "Characters":
            print("Load only works for Characters")
            return
        
        if not self.resource_list or not self.resource_list.selected_text:
            print("No character selected")
            return
        
        selected_name = self.resource_list.selected_text
        
        # Ask for new character name
        new_name = self._ask_for_name(f"Load copy of {selected_name}")
        if not new_name:
            return
        
        # Check if name already exists in session
        if self.session_manager.get_character(new_name):
            print(f"Character '{new_name}' already loaded in session, update it instead")
            self._update_character(new_name)
            return
        
        try:
            # Load the character
            character = self.resource_manager.load_character(selected_name)
            # Change the name
            character.name = new_name
            # Add to session
            self.session_manager.load_character(character)
            print(f"Loaded character copy: {new_name} (from {selected_name})")
        except Exception as e:
            print(f"Error loading {selected_name}: {e}")

    def _update_character(self, name: str) -> None:
        """
        Update an already loaded character with the data from the resource.
        
        Args:
            name: Name of the character to update (must be loaded in session)
        """
        try:
            # Load character data from resource
            char_path = Path(CHARACTERS_FOLDER) / f"{name}.json"
            if not char_path.exists():
                print(f"Character file not found: {char_path}")
                return
            
            with open(char_path, 'r', encoding='utf-8') as f:
                char_data = json.load(f)
            
            # Create Character object from data
            character = self.session_manager.get_character(name)
            if not character:
                print(f"Character '{name}' not found in session")
                return
            
            # Update character attributes (this is a simple example, you may want to be more selective)
            for key, value in char_data.items():
                setattr(character, key, value)
            
            print(f"Updated character '{name}' with latest resource data")
        
        except Exception as e:
            print(f"Error updating character '{name}': {e}")
    
    def _ask_for_name(self, title: str) -> str:
        """
        Show a popup to ask for a name.
        
        Args:
            title: Title of the popup
            
        Returns:
            The entered name, or empty string if cancelled
        """
        # Create popup
        popup_width = 400
        popup_height = 150
        popup_x = (self.app.size[0] - popup_width) // 2
        popup_y = (self.app.size[1] - popup_height) // 2
        
        popup = Popup(
            self.app,
            self.app.screen,
            Rect(popup_x, popup_y, popup_width, popup_height),
            title=title
        )
        
        # Add label
        Label(popup, (20, 20), "Enter character name:")
        
        # Add text input
        text_input = TextArea(
            popup,
            Rect(20, 60, popup_width - 40, 30),
            text="",
            padding=5
        )
        text_input.editable = True
        self.app.focused_widget = text_input
        
        # Result holder
        result = {"name": ""}
        
        def on_ok():
            result["name"] = text_input.text.strip()
            popup.close()
        
        def on_cancel():
            popup.close()
        
        # Add buttons
        Button(
            popup,
            Rect(popup_width - 180, popup_height - 50, 80, 30),
            "OK",
            on_ok
        )
        Button(
            popup,
            Rect(popup_width - 90, popup_height - 50, 80, 30),
            "Cancel",
            on_cancel
        )
        
        # Handle Enter/Escape keys
        original_handle = popup.handle_event
        def handle_with_keys(event):
            if event.type == KEYDOWN:
                if event.key == K_RETURN and text_input.focus:
                    on_ok()
                    return True
                elif event.key == K_ESCAPE:
                    on_cancel()
                    return True
            return original_handle(event)
        
        popup.handle_event = handle_with_keys
        
        # Run popup
        popup.run()
        
        return result["name"]
    
    def _on_remove(self) -> None:
        """Handle Remove button click."""
        if not self.resource_list or not self.resource_list.selected_text:
            print("No resource selected")
            return
        
        selected_name = self.resource_list.selected_text
        
        # Show confirmation dialog
        if not self._confirm_remove(selected_name):
            return
        
        # Get the file path
        file_path = self._get_resource_file_path(selected_name)
        if not file_path or not file_path.exists():
            print(f"File not found: {file_path}")
            return
        
        try:
            # Delete the file
            file_path.unlink()
            print(f"Deleted {self.current_type}: {selected_name}")
            
            # Reload resource manager and refresh list
            self.resource_manager.reload()
            self._refresh_resource_list()
            
        except Exception as e:
            print(f"Error deleting {selected_name}: {e}")
    
    def _get_resource_file_path(self, name: str) -> Path:
        """
        Get the file path for a resource.
        
        Args:
            name: Name of the resource
            
        Returns:
            Path to the JSON file
        """
        if self.current_type == "Characters":
            return Path(CHARACTERS_FOLDER) / f"{name}.json"
        elif self.current_type == "Items":
            return Path(ITEMS_FOLDER) / f"{name}.json"
        elif self.current_type == "Spells":
            return Path(SPELLS_FOLDER) / f"{name}.json"
        return Path()
    
    def _confirm_remove(self, name: str) -> bool:
        """
        Show a confirmation dialog for removing a resource.
        
        Args:
            name: Name of the resource to remove
            
        Returns:
            True if confirmed, False otherwise
        """
        # Create popup
        popup_width = 450
        popup_height = 120
        popup_x = (self.app.size[0] - popup_width) // 2
        popup_y = (self.app.size[1] - popup_height) // 2
        
        popup = Popup(
            self.app,
            self.app.screen,
            Rect(popup_x, popup_y, popup_width, popup_height),
            title="Confirm Deletion"
        )
        
        # Add warning label
        warning_text = f"Are you sure you want to delete '{name}'?"
        Label(popup, (20, 20), warning_text)
        Label(popup, (20, 45), "This action cannot be undone!")
        
        # Result holder
        result = {"confirmed": False}
        
        def on_yes():
            result["confirmed"] = True
            popup.close()
        
        def on_no():
            popup.close()
        
        # Add buttons
        Button(
            popup,
            Rect(popup_width - 180, popup_height - 50, 80, 30),
            "Yes",
            on_yes
        )
        Button(
            popup,
            Rect(popup_width - 90, popup_height - 50, 80, 30),
            "No",
            on_no
        )
        
        # Handle Escape key
        original_handle = popup.handle_event
        def handle_with_keys(event):
            if event.type == KEYDOWN and event.key == K_ESCAPE:
                on_no()
                return True
            return original_handle(event)
        
        popup.handle_event = handle_with_keys
        
        # Run popup
        popup.run()
        
        return result["confirmed"]
    
    def _create_spell_form(self) -> None:
        """
        Show a form to create a new spell with effects support.
        """
        # Available stats and targets
        STATS = ["hp", "str", "dex", "con", "int", "wis", "cha", "per", "agi", "luc", "sur",
                 "stamina", "mental_health", "drug_health"]
        TARGETS = ["user", "target"]
        EFFECT_TYPES = ["bonus", "malus"]
        
        # Create popup (larger to fit effects section)
        popup_width = 700
        popup_height = 650
        popup_x = (self.app.size[0] - popup_width) // 2
        popup_y = (self.app.size[1] - popup_height) // 2
        
        popup = Popup(
            self.app,
            self.app.screen,
            Rect(popup_x, popup_y, popup_width, popup_height),
            title="Create New Spell"
        )
        
        # Name field
        Label(popup, (20, 20), "Spell Name:")
        name_input = TextArea(
            popup,
            Rect(20, 45, popup_width - 40, 30),
            text="",
            padding=5
        )
        name_input.editable = True
        
        # Description field
        Label(popup, (20, 85), "Description:")
        desc_input = TextArea(
            popup,
            Rect(20, 110, popup_width - 40, 60),
            text="",
            padding=5
        )
        desc_input.editable = True
        
        # Cost field
        Label(popup, (20, 180), "Cost:")
        cost_input = TextArea(
            popup,
            Rect(80, 180, 80, 30),
            text="",
            padding=5
        )
        cost_input.editable = True
        
        # Effects section
        Label(popup, (20, 220), "Effects:")
        
        # List to store effects
        effects = []
        effect_labels = []
        
        # New effect fields
        Label(popup, (20, 250), "Target:")
        target_dropdown = DropdownList(
            popup,
            (90, 250),
            items=TARGETS,
            max_visible_items=2
        )
        
        Label(popup, (20, 290), "Stat:")
        stat_dropdown = DropdownList(
            popup,
            (90, 290),
            items=STATS,
            max_visible_items=8
        )
        
        Label(popup, (220, 290), "Type:")
        effect_dropdown = DropdownList(
            popup,
            (280, 290),
            items=EFFECT_TYPES,
            max_visible_items=2
        )
        
        Label(popup, (20, 330), "Formula:")
        formula_input = TextArea(
            popup,
            Rect(90, 330, popup_width - 110, 30),
            text="",
            padding=5
        )
        formula_input.editable = True
        
        def refresh_effects_display():
            """Refresh the display of effects list."""
            for lbl in effect_labels:
                if lbl in popup.children:
                    popup.children.remove(lbl)
            effect_labels.clear()
            
            y_offset = 430
            for i, eff in enumerate(effects):
                effect_text = f"{i+1}. {eff['target']}.{eff['target_stat']} {eff['effect']}: {eff['formula']}"
                lbl = Label(popup, (40, y_offset), effect_text)
                effect_labels.append(lbl)
                
                def make_delete_handler(index):
                    def delete_handler():
                        effects.pop(index)
                        refresh_effects_display()
                    return delete_handler
                
                del_btn = Button(
                    popup,
                    Rect(popup_width - 100, y_offset - 2, 60, 25),
                    "Delete",
                    make_delete_handler(i)
                )
                effect_labels.append(del_btn)
                
                y_offset += 30
        
        def on_add_effect():
            """Add an effect to the list."""
            formula = formula_input.text.strip()
            if not formula:
                print("Error: Formula is required")
                return
            
            effect_data = {
                "target": target_dropdown.get_text(),
                "target_stat": stat_dropdown.get_text(),
                "effect": effect_dropdown.get_text(),
                "formula": formula
            }
            
            effects.append(effect_data)
            formula_input.text = ""
            refresh_effects_display()
            print(f"Added effect: {effect_data['target']}.{effect_data['target_stat']} {effect_data['effect']}")
        
        Button(
            popup,
            Rect(popup_width - 160, 330, 120, 30),
            "Add Effect",
            on_add_effect
        )
        
        Label(popup, (20, 400), "Current Effects:")
        
        self.app.focused_widget = name_input
        
        def on_save():
            name = name_input.text.strip().replace(" ", "_")
            description = desc_input.text.strip()
            cost_text = cost_input.text.strip()
            
            if not name:
                print("Error: Spell name is required")
                return
            
            try:
                cost = int(cost_text) if cost_text else 0
            except ValueError:
                print("Error: Cost must be a number")
                return
            
            if not effects:
                print("Error: At least one effect is required")
                return
            
            spell_file = Path(SPELLS_FOLDER) / f"{name}.json"
            if spell_file.exists():
                print(f"Error: Spell '{name}' already exists")
                return
            
            spell_data = {
                "name": name,
                "description": description,
                "cost": cost,
                "effects": effects
            }
            
            try:
                with open(spell_file, "w", encoding="utf-8") as f:
                    json.dump(spell_data, f, indent=4, ensure_ascii=False)
                
                print(f"Spell created: {name}")
                print(f"  with {len(effects)} effect(s)")
                
                self.resource_manager.reload()
                self._refresh_resource_list()
                
                popup.close()
            except Exception as e:
                print(f"Error saving spell: {e}")
        
        def on_cancel():
            popup.close()
        
        Button(
            popup,
            Rect(popup_width - 180, popup_height - 50, 80, 30),
            "Save",
            on_save
        )
        Button(
            popup,
            Rect(popup_width - 90, popup_height - 50, 80, 30),
            "Cancel",
            on_cancel
        )
        
        original_handle = popup.handle_event
        def handle_with_keys(event):
            if event.type == KEYDOWN and event.key == K_ESCAPE:
                on_cancel()
                return True
            return original_handle(event)
        
        popup.handle_event = handle_with_keys
        
        popup.run()
    
    def _modify_spell_form(self) -> None:
        """
        Show a form to modify an existing spell.
        """
        selected_name = self.resource_list.selected_text
        if not selected_name:
            return
        
        try:
            spell = self.resource_manager.load_spell(selected_name)
            if not spell:
                print(f"Error: Could not load spell {selected_name}")
                return
        except Exception as e:
            print(f"Error loading spell {selected_name}: {e}")
            return
        
        # Available stats and targets
        STATS = ["hp", "str", "dex", "con", "int", "wis", "cha", "per", "agi", "luc", "sur",
                 "stamina", "mental_health", "drug_health"]
        TARGETS = ["user", "target"]
        EFFECT_TYPES = ["bonus", "malus"]
        
        popup_width = 700
        popup_height = 650
        popup_x = (self.app.size[0] - popup_width) // 2
        popup_y = (self.app.size[1] - popup_height) // 2
        
        popup = Popup(
            self.app,
            self.app.screen,
            Rect(popup_x, popup_y, popup_width, popup_height),
            title=f"Modify Spell: {selected_name}"
        )
        
        Label(popup, (20, 20), "Spell Name:")
        name_input = TextArea(
            popup,
            Rect(20, 45, popup_width - 40, 30),
            text=spell.name,
            padding=5
        )
        name_input.editable = True
        
        Label(popup, (20, 85), "Description:")
        desc_input = TextArea(
            popup,
            Rect(20, 110, popup_width - 40, 60),
            text=spell.description,
            padding=5
        )
        desc_input.editable = True
        
        Label(popup, (20, 180), "Cost:")
        cost_input = TextArea(
            popup,
            Rect(80, 180, 80, 30),
            text=str(spell.cost),
            padding=5
        )
        cost_input.editable = True
        
        Label(popup, (20, 220), "Effects:")
        
        # Pre-fill effects
        effects = []
        if spell.effects:
            for eff in spell.effects:
                effects.append({
                    "target": eff.target,
                    "target_stat": eff.target_stat,
                    "effect": eff.effect,
                    "formula": eff.formula.cmd
                })
        
        effect_labels = []
        
        Label(popup, (20, 250), "Target:")
        target_dropdown = DropdownList(
            popup,
            (90, 250),
            items=TARGETS,
            max_visible_items=2
        )
        
        Label(popup, (20, 290), "Stat:")
        stat_dropdown = DropdownList(
            popup,
            (90, 290),
            items=STATS,
            max_visible_items=8
        )
        
        Label(popup, (220, 290), "Type:")
        effect_dropdown = DropdownList(
            popup,
            (280, 290),
            items=EFFECT_TYPES,
            max_visible_items=2
        )
        
        Label(popup, (20, 330), "Formula:")
        formula_input = TextArea(
            popup,
            Rect(90, 330, popup_width - 110, 30),
            text="",
            padding=5
        )
        formula_input.editable = True
        
        def refresh_effects_display():
            for lbl in effect_labels:
                if lbl in popup.children:
                    popup.children.remove(lbl)
            effect_labels.clear()
            
            y_offset = 430
            for i, eff in enumerate(effects):
                effect_text = f"{i+1}. {eff['target']}.{eff['target_stat']} {eff['effect']}: {eff['formula']}"
                lbl = Label(popup, (40, y_offset), effect_text)
                effect_labels.append(lbl)
               
                def make_delete_handler(index):
                    def delete_handler():
                        effects.pop(index)
                        refresh_effects_display()
                    return delete_handler
                
                del_btn = Button(
                    popup,
                    Rect(popup_width - 100, y_offset - 2, 60, 25),
                    "Delete",
                    make_delete_handler(i)
                )
                effect_labels.append(del_btn)
                
                y_offset += 30
        
        def on_add_effect():
            formula = formula_input.text.strip()
            if not formula:
                print("Error: Formula is required")
                return
            
            effect_data = {
                "target": target_dropdown.get_text(),
                "target_stat": stat_dropdown.get_text(),
                "effect": effect_dropdown.get_text(),
                "formula": formula
            }
            
            effects.append(effect_data)
            formula_input.text = ""
            refresh_effects_display()
            print(f"Added effect: {effect_data['target']}.{effect_data['target_stat']} {effect_data['effect']}")
        
        Button(
            popup,
            Rect(popup_width - 160, 330, 120, 30),
            "Add Effect",
            on_add_effect
        )
        
        Label(popup, (20, 400), "Current Effects:")
        refresh_effects_display()
        
        self.app.focused_widget = name_input
        
        def on_save():
            new_name = name_input.text.strip().replace(" ", "_")
            description = desc_input.text.strip()
            cost_text = cost_input.text.strip()
            
            if not new_name:
                print("Error: Spell name is required")
                return
            
            try:
                cost = int(cost_text) if cost_text else 0
            except ValueError:
                print("Error: Cost must be a number")
                return
            
            if not effects:
                print("Error: At least one effect is required")
                return
            
            old_file = Path(SPELLS_FOLDER) / f"{selected_name}.json"
            new_file = Path(SPELLS_FOLDER) / f"{new_name}.json"
            
            if new_name != selected_name and new_file.exists():
                print(f"Error: Spell '{new_name}' already exists")
                return
            
            spell_data = {
                "name": new_name,
                "description": description,
                "cost": cost,
                "effects": effects
            }
            
            try:
                if new_name != selected_name and old_file.exists():
                    old_file.unlink()
                
                with open(new_file, "w", encoding="utf-8") as f:
                    json.dump(spell_data, f, indent=4, ensure_ascii=False)
                
                print(f"Spell modified: {new_name}")
                print(f"  with {len(effects)} effect(s)")
                
                self.resource_manager.reload()
                self._refresh_resource_list()
                
                popup.close()
            except Exception as e:
                print(f"Error saving spell: {e}")
        
        def on_cancel():
            popup.close()
        
        Button(
            popup,
            Rect(popup_width - 180, popup_height - 50, 80, 30),
            "Save",
            on_save
        )
        Button(
            popup,
            Rect(popup_width - 90, popup_height - 50, 80, 30),
            "Cancel",
            on_cancel
        )
        
        original_handle = popup.handle_event
        def handle_with_keys(event):
            if event.type == KEYDOWN and event.key == K_ESCAPE:
                on_cancel()
                return True
            return original_handle(event)
        
        popup.handle_event = handle_with_keys
        
        popup.run()
    
    # ===== Character Management Forms =====
    
    def _create_character_form(self) -> None:
        """
        Show a form to create a new character with stats, spells, and inventory.
        """
        # Editable stats list (stamina, mental_health, drug_health auto = 100)
        STATS = ["str", "dex", "con", "int", "wis", "cha", "per", "agi", "luc", "sur"]
        
        # Base value for stats
        BASE_STAT = 50
        
        # Create popup (large to fit all fields)
        popup_width = 700
        popup_height = 680
        popup_x = (self.app.size[0] - popup_width) // 2
        popup_y = (self.app.size[1] - popup_height) // 2
        
        popup = Popup(
            self.app,
            self.app.screen,
            Rect(popup_x, popup_y, popup_width, popup_height),
            title="Create New Character"
        )
        
        y = 20
        
        # Name field
        Label(popup, (20, y), "Character Name:")
        name_input = TextArea(popup, Rect(20, y + 25, 300, 30), text="", padding=5)
        name_input.editable = True
        y += 65
        
        # Stats section
        Label(popup, (20, y), "Base Stats:")
        y += 25
        
        # Create TextArea for each stat in a 3-column grid
        stat_inputs = {}
        col_width = 220
        for i, stat in enumerate(STATS):
            col = i % 3
            row = i // 3
            x = 20 + col * col_width
            stat_y = y + row * 35
            
            label_text = stat.replace("_", " ").upper()
            Label(popup, (x, stat_y), f"{label_text}:")
            stat_input = TextArea(
                popup,
                Rect(x + 80, stat_y, 60, 25),
                text=str(BASE_STAT),
                padding=3
            )
            stat_input.editable = True
            stat_inputs[stat] = stat_input
        
        y += (len(STATS) // 3 + 1) * 35 + 10
        
        # Spells section
        Label(popup, (20, y), "Spells:")
        y += 25
        
        # List to store selected spells
        selected_spells = []
        spell_labels = []
        
        # Dropdown for spell selection
        available_spells = self.resource_manager.get_spell_names()
        Label(popup, (20, y), "Add Spell:")
        spell_dropdown = DropdownList(
            popup,
            (100, y),
            items=available_spells if available_spells else ["No spells available"],
            max_visible_items=6
        )
        
        def refresh_spell_display():
            """Refresh the display of spells list."""
            for lbl in spell_labels:
                if lbl in popup.children:
                    popup.children.remove(lbl)
            spell_labels.clear()
            
            y_offset = y + 100
            for i, spell_name in enumerate(selected_spells):
                spell_text = f"• {spell_name}"
                lbl = Label(popup, (40, y_offset), spell_text)
                spell_labels.append(lbl)
                
                def make_delete_handler(index):
                    def delete_handler():
                        selected_spells.pop(index)
                        refresh_spell_display()
                    return delete_handler
                
                del_btn = Button(
                    popup,
                    Rect(320, y_offset - 2, 60, 22),
                    "Delete",
                    make_delete_handler(i)
                )
                spell_labels.append(del_btn)
                y_offset += 25
        
        def on_add_spell():
            """Add selected spell to character."""
            spell_name = spell_dropdown.get_text()
            if spell_name and spell_name != "No spells available" and spell_name not in selected_spells:
                selected_spells.append(spell_name)
                refresh_spell_display()
        
        Button(popup, Rect(280, y, 100, 25), "Add Spell", on_add_spell)
        
        y += 35
        Label(popup, (20, y), "Selected Spells:")
        
        y += 220  # Space for spells list
        
        # Inventory section
        Label(popup, (400, y - 220 + 25), "Inventory:")
        inventory_y = y - 195 + 25
        
        # List to store inventory items
        inventory_items = []
        inventory_labels = []
        
        # Dropdown for item selection
        available_items = self.resource_manager.get_item_names()
        Label(popup, (400, inventory_y), "Add Item:")
        item_dropdown = DropdownList(
            popup,
            (470, inventory_y),
            items=available_items if available_items else ["No items available"],
            max_visible_items=6
        )
        
        Label(popup, (400, inventory_y + 35), "Quantity:")
        quantity_input = TextArea(
            popup,
            Rect(470, inventory_y + 35, 60, 25),
            text="1",
            padding=3
        )
        quantity_input.editable = True
        
        def refresh_inventory_display():
            """Refresh the display of inventory list."""
            for lbl in inventory_labels:
                if lbl in popup.children:
                    popup.children.remove(lbl)
            inventory_labels.clear()
            
            y_offset = inventory_y + 100
            for i, (item_name, qty) in enumerate(inventory_items):
                item_text = f"• {item_name} x{qty}"
                lbl = Label(popup, (420, y_offset), item_text)
                inventory_labels.append(lbl)
                
                def make_delete_handler(index):
                    def delete_handler():
                        inventory_items.pop(index)
                        refresh_inventory_display()
                    return delete_handler
                
                del_btn = Button(
                    popup,
                    Rect(620, y_offset - 2, 60, 22),
                    "Delete",
                    make_delete_handler(i)
                )
                inventory_labels.append(del_btn)
                y_offset += 25
        
        def on_add_item():
            """Add selected item to inventory."""
            item_name = item_dropdown.get_text()
            try:
                qty = int(quantity_input.text.strip())
                if item_name and item_name != "No items available" and qty > 0:
                    inventory_items.append([item_name, qty])
                    quantity_input.text = "1"
                    refresh_inventory_display()
            except ValueError:
                print("Error: Quantity must be a valid number")
        
        Button(popup, Rect(550, inventory_y + 35, 90, 25), "Add Item", on_add_item)
        
        Label(popup, (400, inventory_y + 70), "Inventory Items:")
        
        # Set focus on name input
        self.app.focused_widget = name_input
        
        def on_save():
            name = name_input.text.strip().replace(" ", "_")
            
            if not name:
                print("Error: Character name is required")
                return
            
            # Check if character already exists
            char_file = Path(CHARACTERS_FOLDER) / f"{name}.json"
            if char_file.exists():
                print(f"Error: Character '{name}' already exists")
                return
            
            # Collect stats
            stats = {}
            for stat, input_field in stat_inputs.items():
                try:
                    stats[stat] = int(input_field.text.strip())
                except ValueError:
                    print(f"Error: {stat} must be a valid number")
                    return
            
            # Add auto-initialized stats
            stats["stamina"] = 100
            stats["mental_health"] = 100
            stats["drug_health"] = 100
            
            # Create character data
            char_data = {
                "name": name,
                "stats": stats,
                "modifiers": {
                    "hp": 0,
                    "str": 0,
                    "dex": 0,
                    "con": 0,
                    "int": 0,
                    "wis": 0,
                    "cha": 0,
                    "per": 0,
                    "agi": 0,
                    "luc": 0,
                    "sur": 0,
                    "stamina": 0,
                    "mental_health": 0,
                    "drug_health": 0
                }
            }
            
            # Add spells if any
            if selected_spells:
                char_data["spells"] = selected_spells
            
            # Add inventory if any
            if inventory_items:
                char_data["inventory"] = inventory_items
            
            try:
                # Save to JSON file
                with open(char_file, "w", encoding="utf-8") as f:
                    json.dump(char_data, f, indent=4, ensure_ascii=False)
                
                print(f"Character created: {name}")
                
                # Reload resources and refresh list
                self.resource_manager.reload()
                self._refresh_resource_list()
                
                popup.close()
            except Exception as e:
                print(f"Error saving character: {e}")
        
        def on_cancel():
            popup.close()
        
        # Save/Cancel buttons
        Button(
            popup,
            Rect(popup_width - 180, popup_height - 50, 80, 30),
            "Save",
            on_save
        )
        Button(
            popup,
            Rect(popup_width - 90, popup_height - 50, 80, 30),
            "Cancel",
            on_cancel
        )
        
        # Handle Escape key
        original_handle = popup.handle_event
        def handle_with_keys(event):
            if event.type == KEYDOWN and event.key == K_ESCAPE:
                on_cancel()
                return True
            return original_handle(event)
        
        popup.handle_event = handle_with_keys
        
        popup.run()
    
    def _modify_character_form(self) -> None:
        """
        Show a form to modify an existing character.
        """
        # Get selected character name
        selected_name = self.resource_list.selected_text
        if not selected_name:
            return
        
        # Load existing character data
        try:
            char_path = Path(CHARACTERS_FOLDER) / f"{selected_name}.json"
            if not char_path.exists():
                print(f"Error: Character file not found: {selected_name}")
                return
            
            with open(char_path, 'r', encoding='utf-8') as f:
                char_data = json.load(f)
        except Exception as e:
            print(f"Error loading character {selected_name}: {e}")
            return
        
        # Editable stats list (stamina, mental_health, drug_health auto = 100)
        STATS = ["str", "dex", "con", "int", "wis", "cha", "per", "agi", "luc", "sur"]
        
        # Create popup (large to fit all fields)
        popup_width = 700
        popup_height = 680
        popup_x = (self.app.size[0] - popup_width) // 2
        popup_y = (self.app.size[1] - popup_height) // 2
        
        popup = Popup(
            self.app,
            self.app.screen,
            Rect(popup_x, popup_y, popup_width, popup_height),
            title=f"Modify Character: {selected_name}"
        )
        
        y = 20
        
        # Name field (pre-filled)
        Label(popup, (20, y), "Character Name:")
        name_input = TextArea(popup, Rect(20, y + 25, 300, 30), text=char_data.get("name", ""), padding=5)
        name_input.editable = True
        y += 65
        
        # Stats section (pre-filled)
        Label(popup, (20, y), "Base Stats:")
        y += 25
        
        stats_data = char_data.get("stats", {})
        stat_inputs = {}
        col_width = 220
        for i, stat in enumerate(STATS):
            col = i % 3
            row = i // 3
            x = 20 + col * col_width
            stat_y = y + row * 35
            
            label_text = stat.replace("_", " ").upper()
            Label(popup, (x, stat_y), f"{label_text}:")
            stat_input = TextArea(
                popup,
                Rect(x + 80, stat_y, 60, 25),
                text=str(stats_data.get(stat, 50)),
                padding=3
            )
            stat_input.editable = True
            stat_inputs[stat] = stat_input
        
        y += (len(STATS) // 3 + 1) * 35 + 10
        
        # Spells section (pre-filled)
        Label(popup, (20, y), "Spells:")
        y += 25
        
        selected_spells = list(char_data.get("spells", []))
        spell_labels = []
        
        available_spells = self.resource_manager.get_spell_names()
        Label(popup, (20, y), "Add Spell:")
        spell_dropdown = DropdownList(
            popup,
            (100, y),
            items=available_spells if available_spells else ["No spells available"],
            max_visible_items=6
        )
        
        def refresh_spell_display():
            for lbl in spell_labels:
                if lbl in popup.children:
                    popup.children.remove(lbl)
            spell_labels.clear()
            
            y_offset = y + 100
            for i, spell_name in enumerate(selected_spells):
                spell_text = f"• {spell_name}"
                lbl = Label(popup, (40, y_offset), spell_text)
                spell_labels.append(lbl)
                
                def make_delete_handler(index):
                    def delete_handler():
                        selected_spells.pop(index)
                        refresh_spell_display()
                    return delete_handler
                
                del_btn = Button(
                    popup,
                    Rect(320, y_offset - 2, 60, 22),
                    "Delete",
                    make_delete_handler(i)
                )
                spell_labels.append(del_btn)
                y_offset += 25
        
        def on_add_spell():
            spell_name = spell_dropdown.get_text()
            if spell_name and spell_name != "No spells available" and spell_name not in selected_spells:
                selected_spells.append(spell_name)
                refresh_spell_display()
        
        Button(popup, Rect(280, y, 100, 25), "Add Spell", on_add_spell)
        
        y += 35
        Label(popup, (20, y), "Selected Spells:")
        refresh_spell_display()  # Initial display
        
        y += 220
        
        # Inventory section (pre-filled)
        Label(popup, (400, y - 220 + 25), "Inventory:")
        inventory_y = y - 195 + 25
        
        inventory_items = list(char_data.get("inventory", []))
        inventory_labels = []
        
        available_items = self.resource_manager.get_item_names()
        Label(popup, (400, inventory_y), "Add Item:")
        item_dropdown = DropdownList(
            popup,
            (470, inventory_y),
            items=available_items if available_items else ["No items available"],
            max_visible_items=6
        )
        
        Label(popup, (400, inventory_y + 35), "Quantity:")
        quantity_input = TextArea(
            popup,
            Rect(470, inventory_y + 35, 60, 25),
            text="1",
            padding=3
        )
        quantity_input.editable = True
        
        def refresh_inventory_display():
            for lbl in inventory_labels:
                if lbl in popup.children:
                    popup.children.remove(lbl)
            inventory_labels.clear()
            
            y_offset = inventory_y + 100
            for i, (item_name, qty) in enumerate(inventory_items):
                item_text = f"• {item_name} x{qty}"
                lbl = Label(popup, (420, y_offset), item_text)
                inventory_labels.append(lbl)
                
                def make_delete_handler(index):
                    def delete_handler():
                        inventory_items.pop(index)
                        refresh_inventory_display()
                    return delete_handler
                
                del_btn = Button(
                    popup,
                    Rect(620, y_offset - 2, 60, 22),
                    "Delete",
                    make_delete_handler(i)
                )
                inventory_labels.append(del_btn)
                y_offset += 25
        
        def on_add_item():
            item_name = item_dropdown.get_text()
            try:
                qty = int(quantity_input.text.strip())
                if item_name and item_name != "No items available" and qty > 0:
                    inventory_items.append([item_name, qty])
                    quantity_input.text = "1"
                    refresh_inventory_display()
            except ValueError:
                print("Error: Quantity must be a valid number")
        
        Button(popup, Rect(550, inventory_y + 35, 90, 25), "Add Item", on_add_item)
        
        Label(popup, (400, inventory_y + 70), "Inventory Items:")
        refresh_inventory_display()  # Initial display
        
        # Set focus on name input
        self.app.focused_widget = name_input
        
        def on_save():
            name = name_input.text.strip().replace(" ", "_")
            
            if not name:
                print("Error: Character name is required")
                return
            
            # Collect stats
            stats = {}
            for stat, input_field in stat_inputs.items():
                try:
                    stats[stat] = int(input_field.text.strip())
                except ValueError:
                    print(f"Error: {stat} must be a valid number")
                    return
            
            # Preserve or use default for auto-initialized stats
            stats_data_existing = char_data.get("stats", {})
            stats["stamina"] = stats_data_existing.get("stamina", 100)
            stats["mental_health"] = stats_data_existing.get("mental_health", 100)
            stats["drug_health"] = stats_data_existing.get("drug_health", 100)
            
            # Create character data
            char_data_updated = {
                "name": name,
                "stats": stats,
                "modifiers": char_data.get("modifiers", {
                    "hp": 0,
                    "str": 0,
                    "dex": 0,
                    "con": 0,
                    "int": 0,
                    "wis": 0,
                    "cha": 0,
                    "per": 0,
                    "agi": 0,
                    "luc": 0,
                    "sur": 0,
                    "stamina": 0,
                    "mental_health": 0,
                    "drug_health": 0
                })
            }
            
            # Add spells if any
            if selected_spells:
                char_data_updated["spells"] = selected_spells
            
            # Add inventory if any
            if inventory_items:
                char_data_updated["inventory"] = inventory_items
            
            try:
                # Delete old file if name changed
                if name != selected_name:
                    old_file = Path(CHARACTERS_FOLDER) / f"{selected_name}.json"
                    if old_file.exists():
                        old_file.unlink()
                
                # Save to JSON file
                char_file = Path(CHARACTERS_FOLDER) / f"{name}.json"
                with open(char_file, "w", encoding="utf-8") as f:
                    json.dump(char_data_updated, f, indent=4, ensure_ascii=False)
                
                print(f"Character modified: {name}")
                
                # Reload resources and refresh list
                self.resource_manager.reload()
                self._refresh_resource_list()
                
                popup.close()
            except Exception as e:
                print(f"Error saving character: {e}")
        
        def on_cancel():
            popup.close()
        
        # Save/Cancel buttons
        Button(
            popup,
            Rect(popup_width - 180, popup_height - 50, 80, 30),
            "Save",
            on_save
        )
        Button(
            popup,
            Rect(popup_width - 90, popup_height - 50, 80, 30),
            "Cancel",
            on_cancel
        )
        
        # Handle Escape key
        original_handle = popup.handle_event
        def handle_with_keys(event):
            if event.type == KEYDOWN and event.key == K_ESCAPE:
                on_cancel()
                return True
            return original_handle(event)
        
        popup.handle_event = handle_with_keys
        
        popup.run()
