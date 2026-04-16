# -*- coding: utf-8 -*-

"""
Entity registry module.
"""

from __future__ import annotations
from typing import Any, Optional


class EntityRegistry:
    """
    Runtime entity registry.
    """
    _entities: dict[str, Any] = {}

    @classmethod
    def register(cls, entity_id: str, entity: Any) -> None:
        cls._entities[entity_id] = entity

    @classmethod
    def unregister(cls, entity_id: str) -> None:
        cls._entities.pop(entity_id, None)

    @classmethod
    def get(cls, entity_id: str) -> Optional[Any]:
        return cls._entities.get(entity_id)

    @classmethod
    def clear(cls) -> None:
        cls._entities.clear()
