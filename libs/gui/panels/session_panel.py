# -*- coding: utf-8 -*-

"""
Session Panel - Active game session screen
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from pygame import Rect

from ..pygame_ui import Frame, UIWidget, Label, Button, TextArea
from ..character_card_widget import CharacterCardWidget
from ... import logger

if TYPE_CHECKING:
    from ...session_manager import SessionManager
    from ...resource_manager import ResourceManager
    


class SessionPanel(Frame):
    """
    Main panel for managing active game sessions.
    
    Features:
    - Display party (GROUP) members with CharacterCards
    - Add/Remove characters from party
    - List of all loaded characters
    - Search functionality for characters
    """

    def __init__(
        self,
        parent: Optional[UIWidget], 
        rect: Rect,
    ) -> None:
        Frame.__init__(self, parent, rect)
        
        # UI elements
        self.party_frame: Optional[Frame] = None
        self.all_chars_frame: Optional[Frame] = None
        self.party_search_input: Optional[TextArea] = None
        self.search_input: Optional[TextArea] = None
        
        self._build_ui()
        self._refresh_party()
        self._refresh_all_characters()

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
        margin = 15
        
        # Left side - Current Party
        party_width = (self.rect.width - margin * 3) // 2
        
        Label(self, (margin, margin), "Groupe Actuel")
        
        # Party search bar
        party_search_y = margin + 30
        Label(self, (margin, party_search_y), "Recherche:")
        
        self.party_search_input = TextArea(
            self,
            Rect(margin + 80, party_search_y, party_width - 80, 30),
            text="",
            padding=5
        )
        self.party_search_input.editable = True
        
        # Party frame
        party_frame_y = party_search_y + 40
        party_frame_height = self.rect.height - party_frame_y - margin
        
        self.party_frame = Frame(
            self,
            Rect(margin, party_frame_y, party_width, party_frame_height)
        )
        
        # Right side - All Loaded Characters
        all_chars_x = margin * 2 + party_width
        all_chars_width = self.rect.width - all_chars_x - margin
        
        Label(self, (all_chars_x, margin), "Tous les Personnages")
        
        # Search bar
        search_y = margin + 30
        Label(self, (all_chars_x, search_y), "Recherche:")
        
        self.search_input = TextArea(
            self,
            Rect(all_chars_x + 80, search_y, all_chars_width - 80, 30),
            text="",
            padding=5
        )
        self.search_input.editable = True
        
        # All characters frame
        all_chars_frame_y = search_y + 40
        all_chars_frame_height = self.rect.height - all_chars_frame_y - margin
        
        self.all_chars_frame = Frame(
            self,
            Rect(all_chars_x, all_chars_frame_y, all_chars_width, all_chars_frame_height)
        )
    
    def _refresh_party(self, search_filter: str = "") -> None:
        """Refresh the party display with CharacterCards."""
        if not self.party_frame:
            return
        
        # Clear existing cards
        self.party_frame.children.clear()
        
        party_chars = self.session_manager.get_party_characters()
        
        # Apply search filter
        if search_filter:
            filtered_chars = [c for c in party_chars if search_filter.lower() in c.name.lower()]
        else:
            filtered_chars = party_chars
        
        if not filtered_chars:
            Label(self.party_frame, (10, 10), "Aucun personnage trouvé" if search_filter else "Aucun personnage dans le groupe")
            return
        
        card_width = self.party_frame.rect.width - 20
        card_height = 180
        y_offset = 10
        
        for char in filtered_chars:
            CharacterCardWidget(
                self.party_frame,
                Rect(10, y_offset, card_width, card_height),
                character=char
            )
            
            # Add Remove button
            Button(
                self.party_frame,
                Rect(card_width - 80, y_offset + card_height + 5, 70, 30),
                "Retirer",
                lambda name=char.name: self._remove_from_party(name)
            )
            
            y_offset += card_height + 45
        
        # Update frame size for scroll
        content_height = max(y_offset + 10, self.party_frame.rect.height)
        self.party_frame.size = (self.party_frame.rect.width, content_height)
    
    def _refresh_all_characters(self, search_filter: str = "") -> None:
        """Refresh the list of all loaded characters."""
        if not self.all_chars_frame:
            return
        
        # Clear existing cards
        self.all_chars_frame.children.clear()
        
        all_chars = self.session_manager.get_all_loaded()
        party_names = [c.name for c in self.session_manager.get_party_characters()]
        
        # Apply search filter
        if search_filter:
            filtered_chars = [c for c in all_chars if search_filter.lower() in c.name.lower()]
        else:
            filtered_chars = all_chars
        
        if not filtered_chars:
            Label(self.all_chars_frame, (10, 10), "Aucun personnage trouvé" if search_filter else "Aucun personnage chargé")
            return
        
        card_width = self.all_chars_frame.rect.width - 20
        card_height = 180
        y_offset = 10
        
        for char in filtered_chars:
            CharacterCardWidget(
                self.all_chars_frame,
                Rect(10, y_offset, card_width, card_height),
                character=char
            )
            
            # Add "Add to Party" button if not already in party
            if char.name not in party_names:
                Button(
                    self.all_chars_frame,
                    Rect(card_width - 80, y_offset + card_height + 5, 70, 30),
                    "Ajouter",
                    lambda name=char.name: self._add_to_party(name)
                )
            else:
                # Show "In Party" label
                Label(self.all_chars_frame, (card_width - 80, y_offset + card_height + 10), "Dans groupe")
            
            y_offset += card_height + 45
        
        # Update frame size for scroll
        content_height = max(y_offset + 10, self.all_chars_frame.rect.height)
        self.all_chars_frame.size = (self.all_chars_frame.rect.width, content_height)
    
    def _add_to_party(self, char_name: str) -> None:
        """Add a character to the party."""
        try:
            self.session_manager.add_to_party(char_name)
            logger.info(f"Added {char_name} to party")
            self._refresh_party(self.party_search_input.text if self.party_search_input else "")
            self._refresh_all_characters(self.search_input.text if self.search_input else "")
        except (ValueError, KeyError, RuntimeError, OSError) as error:
            logger.error(f"Error adding character to party '{char_name}': {error}")
    
    def _remove_from_party(self, char_name: str) -> None:
        """Remove a character from the party."""
        try:
            self.session_manager.remove_from_party(char_name)
            logger.info(f"Removed {char_name} from party")
            self._refresh_party(self.party_search_input.text if self.party_search_input else "")
            self._refresh_all_characters(self.search_input.text if self.search_input else "")
        except (ValueError, KeyError, RuntimeError, OSError) as error:
            logger.error(f"Error removing character from party '{char_name}': {error}")
    
    def handle_event(self, event) -> bool:
        if not self.displayed:
            return False
        
        # Check if search inputs changed
        party_old_text = self.party_search_input.text if self.party_search_input else ""
        all_old_text = self.search_input.text if self.search_input else ""
        
        result = super().handle_event(event)
        
        # Refresh party if party search changed
        if self.party_search_input and self.party_search_input.text != party_old_text:
            self._refresh_party(self.party_search_input.text)
        
        # Refresh all characters if all chars search changed
        if self.search_input and self.search_input.text != all_old_text:
            self._refresh_all_characters(self.search_input.text)
        
        return result
