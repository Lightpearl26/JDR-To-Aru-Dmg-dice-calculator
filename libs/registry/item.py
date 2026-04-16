# -*- coding: utf-8 -*-

"""
Item registry module.
"""

from __future__ import annotations
from os import listdir
from os.path import isdir, isfile, join, splitext
from typing import Optional

from .. import config
from ..item import Item


class ItemRegistry:
    """
    Runtime item registry with lazy loading.
    """
    _items: dict[str, Item] = {}

    @classmethod
    def register(cls, item: Item) -> None:
        cls._items[item.name] = item

    @classmethod
    def get(cls, item_id: str) -> Optional[Item]:
        item = cls._items.get(item_id)
        if item is not None:
            return item

        item = Item.from_name(item_id)
        if item is not None:
            cls._items[item.name] = item
        return item

    @classmethod
    def clear(cls) -> None:
        cls._items.clear()

    @classmethod
    def load_all(cls, clear_before: bool = False) -> int:
        """
        Load all items from config.ITEMS_FOLDER.
        """
        if clear_before:
            cls.clear()

        if not isdir(config.ITEMS_FOLDER):
            return 0

        loaded = 0
        for filename in listdir(config.ITEMS_FOLDER):
            path = join(config.ITEMS_FOLDER, filename)
            if not isfile(path):
                continue
            stem, ext = splitext(filename)
            if ext.lower() != ".json":
                continue
            item = Item.from_name(stem)
            if item is None:
                continue
            cls.register(item)
            loaded += 1
        return loaded
