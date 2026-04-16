# -*- coding: utf-8 -*-

"""
Registry package.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .entity import EntityRegistry
    from .character import CharacterRegistry
    from .spell import SpellRegistry
    from .item import ItemRegistry


def __getattr__(name: str):
    """
    Lazy-export registries to avoid import cycles during package initialization.
    """
    if name == "EntityRegistry":
        from .entity import EntityRegistry
        return EntityRegistry
    if name == "CharacterRegistry":
        from .character import CharacterRegistry
        return CharacterRegistry
    if name == "SpellRegistry":
        from .spell import SpellRegistry
        return SpellRegistry
    if name == "ItemRegistry":
        from .item import ItemRegistry
        return ItemRegistry
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def load_all() -> tuple[int, int, int]:
    """
    Load all static registries (characters, spells, items).
    """
    from .character import CharacterRegistry
    from .spell import SpellRegistry
    from .item import ItemRegistry

    c = CharacterRegistry.load_all()
    s = SpellRegistry.load_all()
    i = ItemRegistry.load_all()
    return c, s, i


__all__ = [
    "EntityRegistry",
    "CharacterRegistry",
    "SpellRegistry",
    "ItemRegistry",
    "load_all",
]
