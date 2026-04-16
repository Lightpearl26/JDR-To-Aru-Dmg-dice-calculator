#-*- coding: utf-8 -*-

"""
Spell effect module.
"""

# import built-in modules
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

# import local modules
from .spell_def import Effect, TargetStat


# ----- SpellEffect definition -----
@dataclass
class SpellEffect:
    """
    Class representing a spell effect.
    """
    uuid: UUID
    effect_def: Effect
    target_id: str
    target_stat: TargetStat
    delta: int
    link_key: tuple[str, str]
