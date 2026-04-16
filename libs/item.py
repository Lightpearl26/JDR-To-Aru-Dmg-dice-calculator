# -*- coding: utf-8 -*-

"""
JDR item libs (V2)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from os.path import join
from json import load

from . import config


@dataclass
class Item:
    """
    Item definition.
    """
    name: str
    description: str
    modifier: list[tuple[str, int]]

    @classmethod
    def from_blueprint(cls, blueprint: dict) -> Item:
        return cls(
            name=blueprint.get("name", "Unknown Item"),
            description=blueprint.get("description", ""),
            modifier=blueprint.get("modifier", []),
        )

    @classmethod
    def from_name(cls, item_name: str) -> Optional[Item]:
        filename = join(config.ITEMS_FOLDER, f"{item_name.replace(' ', '_')}.json")
        try:
            with open(filename, "r", encoding="utf-8-sig") as file:
                return cls.from_blueprint(load(file))
        except FileNotFoundError:
            return None


@dataclass
class Inventory:
    """
    Inventory with lazy item loading and stat aggregation.
    """
    items: dict[str, int] = field(default_factory=dict)
    _item_cache: dict[str, Item] = field(default_factory=dict)

    def add_item(self, item_name: str) -> None:
        self.items[item_name] = self.items.get(item_name, 0) + 1

    def remove_item(self, item_name: str) -> None:
        if item_name not in self.items:
            return
        if self.items[item_name] > 1:
            self.items[item_name] -= 1
        else:
            del self.items[item_name]
            self._item_cache.pop(item_name, None)

    def get_stat_modifier(self, stat: str) -> int:
        total_modifier = 0
        for item_name, quantity in self.items.items():
            item = self._item_cache.get(item_name)
            if item is None:
                item = Item.from_name(item_name)
                if item is None:
                    continue
                self._item_cache[item_name] = item

            for mod_stat, mod_value in item.modifier:
                if mod_stat == stat:
                    total_modifier += mod_value * quantity
        return total_modifier

    def to_list(self) -> list[tuple[str, int]]:
        return [(item_name, quantity) for item_name, quantity in self.items.items()]

    @classmethod
    def from_list(cls, items_list: list[tuple[str, int]]) -> Inventory:
        return cls(items={item_name: quantity for item_name, quantity in items_list})
