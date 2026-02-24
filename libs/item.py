# -*- coding: utf-8 -*-

"""
JDR item libs
"""

# Import external libs
from __future__ import annotations
from typing import Optional
from os.path import join
from json import load

# Import logger
from . import logger

# Import config
from . import config


# ----- Item class ----- #
class Item:
    """
    Item class
    
    arguments:
        name: str
            The name of the item
        description: str
            The description of the item
        modifier: list of tuple(str, int)
            The list of modifiers applied by the item
    """
    def __init__(self, name, description: str, modifier: list[tuple[str, int]]) -> None:
        self.name = name
        self.description = description
        self.modifier = modifier
        logger.debug(f"[Item] <'{self.name}'> Item loaded.")

    @classmethod
    def from_blueprint(cls, blueprint: dict) -> Item:
        """
        Create an Item object from a blueprint dictionary
        
        arguments:
            blueprint: dict
                The blueprint dictionary
        returns:
            Item: The created Item object
        """
        name = blueprint.get("name", "Unknown Item")
        description = blueprint.get("description", "")
        modifier = blueprint.get("modifier", [])
        return cls(name, description, modifier)

    @classmethod
    def from_name(cls, item_name: str) -> Optional[Item]:
        """
        Create an Item object from its name by loading its blueprint from a JSON file
        
        arguments:
            item_name: str
                The name of the item
        returns:
            Item: The created Item object
        """
        with open(join(config.ITEMS_FOLDER, f"{item_name.replace(' ', '_')}.json"), "r", encoding="utf-8") as file:
            blueprint = load(file)
        return cls.from_blueprint(blueprint)


# ----- Inventory class ----- #
class Inventory:
    """
    Inventory class
    """
    def __init__(self, items: dict[str, int]) -> None:
        self.items: dict[str, int] = items
        self._item_cache: dict[str, Item] = {}
        logger.debug(f"[Inventory] Inventory created with items: {self.items}")

    def add_item(self, item_name: str) -> None:
        """
        Add an item to the inventory
        
        arguments:
            item: Item
                The item to add
        """
        self.items[item_name] = self.items.get(item_name, 0) + 1

    def remove_item(self, item_name: str) -> None:
        """
        Remove an item from the inventory
        
        arguments:
            item: Item
                The item to remove
        """
        if item_name in self.items:
            if self.items[item_name] > 1:
                self.items[item_name] -= 1
            else:
                del self.items[item_name]
                self._item_cache.pop(item_name, None)

    def get_stat_modifier(self, stat: str) -> int:
        """
        Get the total modifier for a given stat from all items in the inventory
        
        arguments:
            stat: str
                The stat to get the modifier for
        returns:
            int: The total modifier for the stat
        """
        total_modifier = 0
        for item_name, quantity in self.items.items():
            item = self._item_cache.get(item_name)
            if item is None:
                try:
                    item = Item.from_name(item_name)
                    self._item_cache[item_name] = item
                except (FileNotFoundError, OSError, ValueError) as error:
                    logger.error(f"[Inventory] Failed to load item '{item_name}': {error}")
                    continue
            if item:
                for mod_stat, mod_value in item.modifier:
                    if mod_stat == stat:
                        total_modifier += mod_value * quantity
        return total_modifier

    def to_list(self) -> list[tuple[str, int]]:
        """
        Convert the inventory to a list of item names and their quantities
        
        returns:
            list of tuple[str, int]: The list of item names and their quantities
        """
        return [(item_name, quantity) for item_name, quantity in self.items.items()]

    @classmethod
    def from_list(cls, items_list: list[tuple[str, int]]) -> Inventory:
        """
        Create an Inventory object from a list of item names
        
        arguments:
            items_list: list of tuple[str, int]
                The list of item names and their quantities
        returns:
            Inventory: The created Inventory object
        """
        items_dict = {item_name: quantity for item_name, quantity in items_list}
        return cls(items_dict)
