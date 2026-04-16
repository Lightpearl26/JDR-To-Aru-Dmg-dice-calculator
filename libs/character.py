#-*- coding: utf-8 -*-

"""
Character module.
"""

# import built-in modules
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from json import load
from os.path import join

# import local modules
from . import config
from .item import Inventory
from .dice import Dice, DiceRatio
from .spells.spell_def import Spell
from .spells.spell_event import SpellEvent
from .spells.spell_effect import SpellEffect
from .registry.entity import EntityRegistry
from .registry.spell import SpellRegistry


# ----- Stats definition ----- #
@dataclass
class Stats:
    """
    Class managing the stats of a character.
    """
    str: int = config.BASE_STATS
    dex: int = config.BASE_STATS
    int: int = config.BASE_STATS
    agi: int = config.BASE_STATS
    con: int = config.BASE_STATS
    wis: int = config.BASE_STATS
    cha: int = config.BASE_STATS
    per: int = config.BASE_STATS
    luc: int = config.BASE_STATS
    sur: int = config.BASE_STATS
    mental_health: int = 100
    drug_health: int = 100
    stamina: int = 100

    @property
    def hp(self: Stats) -> int:
        """
        Calculate the hp of the character based on constitution and wisdom.
        
        Formula: 10 + (con // 10) + (wis // 10)
        """
        return 10 + self.con // 10 + self.wis // 10

    @property
    def lvl(self: Stats) -> int:
        """
        Calculate the level of the character based on the sum of all stats.
        
        Formula: (total_stats - 500) // 5
        """
        total_stats = sum([
            self.str, self.dex, self.int, self.agi, self.con,
            self.wis, self.cha, self.per, self.luc, self.sur
        ])
        return (total_stats - 500) // 5

    @classmethod
    def from_dict(cls: type[Stats], data: dict[str, int]) -> Stats:
        """
        Create a Stats object from a dictionary.
        """
        return cls(
            str=data.get("str", config.BASE_STATS),
            dex=data.get("dex", config.BASE_STATS),
            int=data.get("int", config.BASE_STATS),
            agi=data.get("agi", config.BASE_STATS),
            con=data.get("con", config.BASE_STATS),
            wis=data.get("wis", config.BASE_STATS),
            cha=data.get("cha", config.BASE_STATS),
            per=data.get("per", config.BASE_STATS),
            luc=data.get("luc", config.BASE_STATS),
            sur=data.get("sur", config.BASE_STATS),
            mental_health=data.get("mental_health", 100),
            drug_health=data.get("drug_health", 100),
            stamina=data.get("stamina", 100),
        )


# ----- StatsModifier definition ----- #
@dataclass
class StatsModifier:
    """
    Class managing the stats modifiers of a character.
    
    A stat modifier is a bonus gave by the MJ that is not counted in the character base stats
    and that can be temporary or permanent.
    """
    hp: int = 0
    str: int = 0
    dex: int = 0
    int: int = 0
    agi: int = 0
    con: int = 0
    wis: int = 0
    cha: int = 0
    per: int = 0
    luc: int = 0
    sur: int = 0
    mental_health: int = 0
    drug_health: int = 0
    stamina: int = 0

    @classmethod
    def from_dict(cls: type[StatsModifier], data: dict[str, int]) -> StatsModifier:
        """
        Create a StatsModifier object from a dictionary.
        """
        return cls(
            hp=data.get("hp", 0),
            str=data.get("str", 0),
            dex=data.get("dex", 0),
            int=data.get("int", 0),
            agi=data.get("agi", 0),
            con=data.get("con", 0),
            wis=data.get("wis", 0),
            cha=data.get("cha", 0),
            per=data.get("per", 0),
            luc=data.get("luc", 0),
            sur=data.get("sur", 0),
            mental_health=data.get("mental_health", 0),
            drug_health=data.get("drug_health", 0),
            stamina=data.get("stamina", 0),
        )


# ----- Character definition ----- #
@dataclass
class Character:
    """
    Class storing the data of a given Character. it is not an Entity but
    the metadata of an Entity that can be used to create it.
    """
    name: str
    stats: Stats = field(default_factory=Stats)
    stats_modifier: StatsModifier = field(default_factory=StatsModifier)
    inventory: Inventory = field(default_factory=Inventory)
    spells: dict[str, Spell] = field(default_factory=dict)

    @property
    def hp(self: Character) -> int:
        """
        Calculate the current hp of the character based on base hp and modifiers.
        """
        item_hp_modifier = self.inventory.get_stat_modifier("hp")
        return self.stats.hp + self.stats_modifier.hp + item_hp_modifier

    @property
    def str(self: Character) -> int:
        """
        Calculate the current strength of the character based on base strength and modifiers.
        """
        item_str_modifier = self.inventory.get_stat_modifier("str")
        return self.stats.str + self.stats_modifier.str + item_str_modifier

    @property
    def dex(self: Character) -> int:
        """
        Calculate the current dexterity of the character based on base dexterity and modifiers.
        """
        item_dex_modifier = self.inventory.get_stat_modifier("dex")
        return self.stats.dex + self.stats_modifier.dex + item_dex_modifier

    @property
    def int(self: Character) -> int:
        """
        Calculate the current intelligence of the character based on base
        intelligence and modifiers.
        """
        item_int_modifier = self.inventory.get_stat_modifier("int")
        return self.stats.int + self.stats_modifier.int + item_int_modifier

    @property
    def agi(self: Character) -> int:
        """
        Calculate the current agility of the character based on base agility and modifiers.
        """
        item_agi_modifier = self.inventory.get_stat_modifier("agi")
        return self.stats.agi + self.stats_modifier.agi + item_agi_modifier

    @property
    def con(self: Character) -> int:
        """
        Calculate the current constitution of the character based on base
        constitution and modifiers.
        """
        item_con_modifier = self.inventory.get_stat_modifier("con")
        return self.stats.con + self.stats_modifier.con + item_con_modifier

    @property
    def wis(self: Character) -> int:
        """
        Calculate the current wisdom of the character based on base wisdom and modifiers.
        """
        item_wis_modifier = self.inventory.get_stat_modifier("wis")
        return self.stats.wis + self.stats_modifier.wis + item_wis_modifier

    @property
    def cha(self: Character) -> int:
        """
        Calculate the current charisma of the character based on base charisma and modifiers.
        """
        item_cha_modifier = self.inventory.get_stat_modifier("cha")
        return self.stats.cha + self.stats_modifier.cha + item_cha_modifier

    @property
    def per(self: Character) -> int:
        """
        Calculate the current perception of the character based on base perception and modifiers.
        """
        item_per_modifier = self.inventory.get_stat_modifier("per")
        return self.stats.per + self.stats_modifier.per + item_per_modifier

    @property
    def luc(self: Character) -> int:
        """
        Calculate the current luck of the character based on base luck and modifiers.
        """
        item_luc_modifier = self.inventory.get_stat_modifier("luc")
        return self.stats.luc + self.stats_modifier.luc + item_luc_modifier

    @property
    def sur(self: Character) -> int:   
        """
        Calculate the current survival of the character based on base survival and modifiers.
        """
        item_sur_modifier = self.inventory.get_stat_modifier("sur")
        return self.stats.sur + self.stats_modifier.sur + item_sur_modifier

    @property
    def mental_health(self: Character) -> int:
        """
        Calculate the current mental health of the character based on base mental health
        and modifiers.
        """
        item_mental_health_modifier = self.inventory.get_stat_modifier("mental_health")
        return (
            self.stats.mental_health +
            self.stats_modifier.mental_health +
            item_mental_health_modifier
        )

    @property
    def drug_health(self: Character) -> int:
        """
        Calculate the current drug health of the character based on base drug health and modifiers.
        """
        item_drug_health_modifier = self.inventory.get_stat_modifier("drug_health")
        return self.stats.drug_health + self.stats_modifier.drug_health + item_drug_health_modifier

    @property
    def stamina(self: Character) -> int:
        """
        Calculate the current stamina of the character based on base stamina and modifiers.
        """
        item_stamina_modifier = self.inventory.get_stat_modifier("stamina")
        return self.stats.stamina + self.stats_modifier.stamina + item_stamina_modifier

    def get_spell(self: Character, spell_name: str) -> Optional[Spell]:
        """
        Get a spell from the character's spell list by name.
        
        arguments:
            spell_name: str
                The name of the spell to get
        returns:
            Optional[Spell]: The spell if found, None otherwise
        """
        return self.spells.get(spell_name)

    def get_current_stat(self: Character, stat_name: str) -> int:
        """
        Compatibility helper used by dice module.
        """
        value = getattr(self, stat_name, 0)
        return int(value)

    @classmethod
    def from_dict(cls: type[Character], data: dict) -> Character:
        """
        Create a Character object from a dictionary.
        """
        stats = Stats.from_dict(data.get("stats", {}))
        stats_modifier = StatsModifier.from_dict(data.get("stats_modifier", {}))
        inventory = Inventory(items=dict(data.get("inventory", [])))
        spells_names: list[str] = data.get("spells", [])
        spells_inst: dict[str, Optional[Spell]] = {
            name: Spell.from_name(name) for name in spells_names
        }
        spells: dict[str, Spell] = {
            name: spell for name, spell in spells_inst.items() if spell is not None
        }
        return cls(
            name=data.get("name", "Dummy"),
            stats=stats,
            stats_modifier=stats_modifier,
            inventory=inventory,
            spells=spells,
        )

    @classmethod
    def from_name(cls: type[Character], character_name: str) -> Optional[Character]:
        """
        Create a Character object from a character name by loading its blueprint.
        
        arguments:
            character_name: str
                The name of the character to load
        returns:
            Optional[Character]: The character if found, None otherwise
        """
        filename = join(
            config.CHARACTERS_FOLDER,
            f"{character_name.replace(' ', '_').lower()}.json"
        )
        try:
            with open(filename, "r", encoding="utf-8-sig") as file:
                return cls.from_dict(load(file))
        except FileNotFoundError:
            return None


# ----- Entity definition ----- #
@dataclass
class Entity:
    """
    Class representing an entity in the game.
    It is created from a character and can be affected by spells and items.
    """
    name: str
    character: Character
    spell_events: list[SpellEvent] = field(default_factory=list)
    spell_effects: list[SpellEffect] = field(default_factory=list)

    @property
    def stats_modifiers(self) -> StatsModifier:
        """
        Compatibility alias used by SpellEvent runtime.
        """
        return self.character.stats_modifier

    @classmethod
    def from_character(
                cls: type[Entity],
                entity_name: str,
                character_name: str
            ) -> Optional[Entity]:
        """
        Create an Entity object from a character name by loading its blueprint.
        
        arguments:
            entity_name: str
                The name of the entity to create
            character_name: str
                The name of the character to load as base for the entity
        returns:
            Optional[Entity]: The entity if the character is found, None otherwise
        """
        character = Character.from_name(character_name)
        if character is None:
            return None
        return cls(
            name=entity_name,
            character=character
        )

    def get_stat(self, stat_name: str) -> int:
        """
        Get the current value of a stat by name.
        
        arguments:
            stat_name: str
                The name of the stat to get
        returns:
            int: The current value of the stat if found, 0 otherwise
        """
        base_stat = getattr(self.character, stat_name, 0)
        spell_modifier = sum(
            effect.delta for effect in self.spell_effects if effect.target_stat == stat_name
        )
        return base_stat + spell_modifier

    def get_current_stat(self, stat_name: str) -> int:
        """
        Compatibility helper used by dice module.
        """
        return self.get_stat(stat_name)

    def strike(
            self,
            target: Entity,
            user_dices: Optional[Dice]=None,
            target_dices: Optional[Dice]=None,
        ) -> str:
        """Resolve a strike attack (user.str vs target.con) and return damage dice cmd."""
        if not user_dices:
            user_dices = Dice.roll("1d100")
        if not target_dices:
            target_dices = Dice.roll("1d100")

        user_value = DiceRatio("str", 100).resolve(self, user_dices)
        target_value = DiceRatio("con", 100).resolve(target, target_dices)
        nb_dice = max(0, (user_value - target_value) // 10)

        dice_value = (
            0 if not user_dices.critical_success and target_dices.critical_success else
            0 if user_dices.critical_failure and not target_dices.critical_failure else
            6 if user_dices.critical_success and target_dices.critical_success else
            12 if user_dices.critical_success and target_dices.critical_failure else
            8 if user_dices.critical_success or target_dices.critical_failure else
            4
        )
        return f"{nb_dice}d{dice_value}"

    def shoot(
            self,
            target: Entity,
            user_dices: Optional[Dice]=None,
            target_dices: Optional[Dice]=None,
        ) -> str:
        """Resolve a shoot attack (user.dex vs target.agi) and return damage dice cmd."""
        if not user_dices:
            user_dices = Dice.roll("1d100")
        if not target_dices:
            target_dices = Dice.roll("1d100")

        user_value = DiceRatio("dex", 100).resolve(self, user_dices)
        target_value = DiceRatio("agi", 100).resolve(target, target_dices)
        nb_dice = max(0, (user_value - target_value) // 10)

        dice_value = (
            0 if not user_dices.critical_success and target_dices.critical_success else
            0 if user_dices.critical_failure and not target_dices.critical_failure else
            6 if user_dices.critical_success and target_dices.critical_success else
            12 if user_dices.critical_success and target_dices.critical_failure else
            8 if user_dices.critical_success or target_dices.critical_failure else
            4
        )
        return f"{nb_dice}d{dice_value}"

    def cast_spell(
            self,
            spell_name: str,
            targets: list[Entity],
            user_dices: Optional[dict[str, int]]=None,
            targets_dices: Optional[dict[str, dict[str, int]]]=None
        ) -> bool:
        """
        Cast a spell from the character's spell list on the given targets.
        
        arguments:
            spell_name: str
                The name of the spell to cast
            targets: list[Entity]
                The list of targets to cast the spell on
        returns:
            bool: True if the spell was successfully cast, False otherwise
        """
        spell = self.character.get_spell(spell_name)
        if spell is None:
            return False

        SpellRegistry.register(spell)
        EntityRegistry.register(self.name, self)
        for target in targets:
            EntityRegistry.register(target.name, target)

        # Create the spell event linked to this spell
        spell_event = SpellEvent(
            spell_id=spell.name,
            caster_id=self.name,
            targets_ids=[target.name for target in targets],
            effects=[],
            runtime_policy=spell.runtime_policy
        )

        # apply the SpellEvent once for this turn
        spell_event.apply(
            [target.name for target in targets],
            user_dices=user_dices,
            targets_dices=targets_dices
        )

        # add the spell event to the entity's list of spell events
        self.spell_events.append(spell_event)
        return True
