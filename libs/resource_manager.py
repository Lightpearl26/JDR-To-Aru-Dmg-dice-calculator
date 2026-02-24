# -*- coding: utf-8 -*-

"""
Resource Manager - Manages all available game resources (characters, items, spells)
"""

from __future__ import annotations
from typing import Dict
from pathlib import Path

from libs.character import Character
from libs.item import Item
from libs.spell import Spell
from libs.config import CHARACTERS_FOLDER, ITEMS_FOLDER, SPELLS_FOLDER


class ResourceManager:
    """
    Manages all available resources in the game.
    
    Resources are loaded from JSON files in assets/ folders.
    Acts as a catalog/library of all available characters, items, and spells.
    """
    
    def __init__(self) -> None:
        # Dictionaries: name -> resource
        self.characters: Dict[str, str] = {}  # name -> json filename
        self.items: Dict[str, str] = {}       # name -> json filename
        self.spells: Dict[str, str] = {}      # name -> json filename
        
        # Load all resources
        self._load_resources()
    
    def _load_resources(self) -> None:
        """Scan assets folders and catalog all available resources."""
        # Load character names
        char_path = Path(CHARACTERS_FOLDER)
        if char_path.exists():
            for json_file in char_path.glob("*.json"):
                name = json_file.stem  # Filename without extension
                self.characters[name] = name
        
        # Load item names
        item_path = Path(ITEMS_FOLDER)
        if item_path.exists():
            for json_file in item_path.glob("*.json"):
                name = json_file.stem
                self.items[name] = name
        
        # Load spell names
        spell_path = Path(SPELLS_FOLDER)
        if spell_path.exists():
            for json_file in spell_path.glob("*.json"):
                name = json_file.stem
                self.spells[name] = name
    
    def get_character_names(self) -> list[str]:
        """Get list of all available character names."""
        return sorted(self.characters.keys())
    
    def get_item_names(self) -> list[str]:
        """Get list of all available item names."""
        return sorted(self.items.keys())
    
    def get_spell_names(self) -> list[str]:
        """Get list of all available spell names."""
        return sorted(self.spells.keys())
    
    def load_character(self, name: str) -> Character:
        """
        Load a character instance from its name.
        
        Args:
            name: Name of the character to load
            
        Returns:
            Character instance
        """
        if name not in self.characters:
            raise ValueError(f"Character '{name}' not found in resources")
        return Character.from_name(name)
    
    def load_item(self, name: str) -> Item:
        """
        Load an item instance from its name.
        
        Args:
            name: Name of the item to load
            
        Returns:
            Item instance
        """
        if name not in self.items:
            raise ValueError(f"Item '{name}' not found in resources")
        return Item.from_name(name)
    
    def load_spell(self, name: str) -> Spell:
        """
        Load a spell instance from its name.
        
        Args:
            name: Name of the spell to load
            
        Returns:
            Spell instance
        """
        if name not in self.spells:
            raise ValueError(f"Spell '{name}' not found in resources")
        return Spell.from_name(name)
    
    def reload(self) -> None:
        """Reload all resources from disk."""
        self.characters.clear()
        self.items.clear()
        self.spells.clear()
        self._load_resources()
