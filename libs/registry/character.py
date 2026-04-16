# -*- coding: utf-8 -*-

"""
Character registry module.
"""

from __future__ import annotations
from os import listdir
from os.path import isdir, isfile, join, splitext
from typing import Optional

from .. import config
from ..character import Character


class CharacterRegistry:
    """
    Runtime character registry with lazy loading.
    """
    _characters: dict[str, Character] = {}

    @classmethod
    def register(cls, character: Character) -> None:
        cls._characters[character.name] = character

    @classmethod
    def get(cls, character_id: str) -> Optional[Character]:
        character = cls._characters.get(character_id)
        if character is not None:
            return character

        character = Character.from_name(character_id)
        if character is not None:
            cls._characters[character.name] = character
        return character

    @classmethod
    def clear(cls) -> None:
        cls._characters.clear()

    @classmethod
    def load_all(cls, clear_before: bool = False) -> int:
        """
        Load all characters from config.CHARACTERS_FOLDER.
        """
        if clear_before:
            cls.clear()

        if not isdir(config.CHARACTERS_FOLDER):
            return 0

        loaded = 0
        for filename in listdir(config.CHARACTERS_FOLDER):
            path = join(config.CHARACTERS_FOLDER, filename)
            if not isfile(path):
                continue
            stem, ext = splitext(filename)
            if ext.lower() != ".json":
                continue
            character = Character.from_name(stem)
            if character is None:
                continue
            cls.register(character)
            loaded += 1
        return loaded
