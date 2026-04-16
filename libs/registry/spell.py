# -*- coding: utf-8 -*-

"""
Spell registry module.
"""

from __future__ import annotations
from os import listdir
from os.path import isdir, isfile, join, splitext
from typing import Optional

from .. import config
from ..spells.spell_def import Spell


class SpellRegistry:
    """
    Runtime spell registry with lazy loading.
    """
    _spells: dict[str, Spell] = {}

    @classmethod
    def register(cls, spell: Spell) -> None:
        cls._spells[spell.name] = spell

    @classmethod
    def get(cls, spell_id: str) -> Optional[Spell]:
        spell = cls._spells.get(spell_id)
        if spell is not None:
            return spell

        spell = Spell.from_name(spell_id)
        if spell is not None:
            cls._spells[spell.name] = spell
        return spell

    @classmethod
    def clear(cls) -> None:
        cls._spells.clear()

    @classmethod
    def load_all(cls, clear_before: bool = False) -> int:
        """
        Load all spells from config.SPELLS_FOLDER.
        """
        if clear_before:
            cls.clear()

        if not isdir(config.SPELLS_FOLDER):
            return 0

        loaded = 0
        for filename in listdir(config.SPELLS_FOLDER):
            path = join(config.SPELLS_FOLDER, filename)
            if not isfile(path):
                continue
            stem, ext = splitext(filename)
            if ext.lower() != ".json":
                continue
            spell = Spell.from_name(stem)
            if spell is None:
                continue
            cls.register(spell)
            loaded += 1
        return loaded
