# -*- coding: utf-8 -*-

"""
Session Manager - Manages loaded character instances for the active session
"""

from __future__ import annotations
from typing import Dict, Optional

from libs.character import Character


class SessionManager:
    """
    Manages loaded character instances during an active game session.
    
    Characters are loaded into memory and can be accessed by name.
    Tracks which characters are currently in use (party, enemies, etc.)
    """

    def __init__(self) -> None:
        # Dictionary of loaded characters: name -> Character instance
        self.loaded_characters: Dict[str, Character] = {}

        # Optional: track which characters are in the active party
        self.party: list[str] = []  # List of character names in party

    def load_character(self, character: Character) -> None:
        """
        Load a character instance into the session.
        
        Args:
            character: Character instance to load
        """
        self.loaded_characters[character.name] = character
    
    def unload_character(self, name: str) -> None:
        """
        Remove a character from the session.
        
        Args:
            name: Name of the character to unload
        """
        if name in self.loaded_characters:
            del self.loaded_characters[name]
        if name in self.party:
            self.party.remove(name)

    def get_character(self, name: str) -> Optional[Character]:
        """
        Get a loaded character by name.
        
        Args:
            name: Name of the character
            
        Returns:
            Character instance or None if not loaded
        """
        return self.loaded_characters.get(name)

    def get_party_characters(self) -> list[Character]:
        """
        Get all characters in the active party.
        
        Returns:
            List of Character instances in the party
        """
        return [self.loaded_characters[name] for name in self.party 
                if name in self.loaded_characters]

    def add_to_party(self, name: str) -> None:
        """
        Add a loaded character to the active party.
        
        Args:
            name: Name of the character to add
        """
        if name in self.loaded_characters and name not in self.party:
            self.party.append(name)

    def remove_from_party(self, name: str) -> None:
        """
        Remove a character from the active party.
        
        Args:
            name: Name of the character to remove
        """
        if name in self.party:
            self.party.remove(name)

    def load_default_party(self) -> None:
        """
        Load the default party from setup.py (GROUP).
        """
        group = ["Alistair", "Heilari", "Hella", "Saru", "Dexter"]
        characters = [Character.from_name(name) for name in group]
        for character in characters:
            self.load_character(character)
            self.add_to_party(character.name)

    def clear(self) -> None:
        """Clear all loaded characters and party."""
        self.loaded_characters.clear()
        self.party.clear()

    def get_all_loaded(self) -> list[Character]:
        """
        Get all loaded characters (party + others).
        
        Returns:
            List of all loaded Character instances
        """
        return list(self.loaded_characters.values())
