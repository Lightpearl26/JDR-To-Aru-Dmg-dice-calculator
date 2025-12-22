# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin

"""
JDR character libs
"""

# Import external libs
from __future__ import annotations
from typing import Optional
from os.path import join
from json import load, dump
from pygame import Surface, font, Rect, display
from pygame.image import save as png_save
import pygame.draw as draw


# Import logger
from . import logger

# import config
from . import config

# import components
from .dice import Dice, DiceRatio
from .spell import Spell
from .item import Inventory


# ----- Stats class ----- #
class Stats:
    """
    Stats class
    
    This class represent the stats of a character
    
    arguments:
        str: int
            The strength stat value of the character
        dex: int
            The dexterity stat value of the character
        con: int
            The constitution stat value of the character
        int: int
            The intelligence stat value of the character
        wis: int
            The wisdom stat value of the character
        cha: int
            The charisma stat value of the character
        per: int
            The perception stat value of the character
        agi: int
            The agility stat value of the character
        luc: int
            The luck stat value of the character
        sur: int
            The survivability stat value of the character
        stamina: int
            The stamina stat value of the character
        mental_health: int
            The mental health stat value of the character
        drug_health: int
            The drug health stat value of the character
    """
    def __init__(self,
                 str: int=config.BASE_STATS,
                 dex: int=config.BASE_STATS,
                 con: int=config.BASE_STATS,
                 int: int=config.BASE_STATS,
                 wis: int=config.BASE_STATS,
                 cha: int=config.BASE_STATS,
                 per: int=config.BASE_STATS,
                 agi: int=config.BASE_STATS,
                 luc: int=config.BASE_STATS,
                 sur: int=config.BASE_STATS,
                 stamina: int=100,
                 mental_health: int=100,
                 drug_health: int=100) -> None:
        self.str = str
        self.dex = dex
        self.con = con
        self.int = int
        self.wis = wis
        self.cha = cha
        self.per = per
        self.agi = agi
        self.luc = luc
        self.sur = sur
        self.stamina = stamina
        self.mental_health = mental_health
        self.drug_health = drug_health
        logger.debug(f"[Stats] Created with values: str={str}, dex={dex}, "
                     f"con={con}, int={int}, wis={wis}, cha={cha}, per={per}, "
                     f"agi={agi}, luc={luc}, sur={sur}, stamina={stamina}, "
                     f"mental_health={mental_health}, drug_health={drug_health}")

    # - Properties
    @property
    def dict(self) -> dict[str, int]:
        """
        Get the stats as a dictionary
        
        returns:
            dict[str, int]: The stats as a dictionary
        """
        return {
            "str": self.str,
            "dex": self.dex,
            "con": self.con,
            "int": self.int,
            "wis": self.wis,
            "cha": self.cha,
            "per": self.per,
            "agi": self.agi,
            "luc": self.luc,
            "sur": self.sur,
            "stamina": self.stamina,
            "mental_health": self.mental_health,
            "drug_health": self.drug_health
        }

    @property
    def hp(self) -> int:
        """
        Get the character's HP based on constitution and Wisdom stat
        
        returns:
            int: The character's HP
        """
        return 10 + self.con // 10 + self.wis // 10

    @property
    def lvl(self) -> int:
        """
        Get the character's level based on average of stats
        
        returns:
            int: The character's level
        """
        total_stats = (self.str + self.dex + self.con +
                       self.int + self.wis + self.cha +
                       self.per + self.agi + self.luc +
                       self.sur)
        return (total_stats - 500) // 5

    # - dict importation
    @classmethod
    def from_dict(cls, stats_dict: dict[str, int]) -> Stats:
        """
        Create a Stats object from a dictionary
        
        arguments:
            stats_dict: dict[str, int]
                The stats dictionary
        returns:
            Stats: The created Stats object
        """
        return cls(
            str=stats_dict.get("str", config.BASE_STATS),
            dex=stats_dict.get("dex", config.BASE_STATS),
            con=stats_dict.get("con", config.BASE_STATS),
            int=stats_dict.get("int", config.BASE_STATS),
            wis=stats_dict.get("wis", config.BASE_STATS),
            cha=stats_dict.get("cha", config.BASE_STATS),
            per=stats_dict.get("per", config.BASE_STATS),
            agi=stats_dict.get("agi", config.BASE_STATS),
            luc=stats_dict.get("luc", config.BASE_STATS),
            sur=stats_dict.get("sur", config.BASE_STATS),
            stamina=stats_dict.get("stamina", 100),
            mental_health=stats_dict.get("mental_health", 100),
            drug_health=stats_dict.get("drug_health", 100)
        )


# ----- StatsModifiers class ----- #
class StatsModifiers:
    """
    Stats modifiers class
    
    This class represent the modifiers of a character's stats
    
    arguments:
        hp: int
            The HP modifier
        str: int
            The strength stat modifier
        dex: int
            The dexterity stat modifier
        con: int
            The constitution stat modifier
        int: int
            The intelligence stat modifier
        wis: int
            The wisdom stat modifier
        cha: int
            The charisma stat modifier
        per: int
            The perception stat modifier
        agi: int
            The agility stat modifier
        luc: int
            The luck stat modifier
        sur: int
            The survivability stat modifier
        stamina: int
            The stamina stat modifier
        mental_health: int
            The mental health stat modifier
        drug_health: int
            The drug health stat modifier
    """
    def __init__(self, hp: int=0,
                       str: int=0,
                       dex: int=0,
                       con: int=0,
                       int: int=0,
                       wis: int=0,
                       cha: int=0,
                       per: int=0,
                       agi: int=0,
                       luc: int=0,
                       sur: int=0,
                       stamina: int=0,
                       mental_health: int=0,
                       drug_health: int=0) -> None:
        self.hp = hp
        self.str = str
        self.dex = dex
        self.con = con
        self.int = int
        self.wis = wis
        self.cha = cha
        self.per = per
        self.agi = agi
        self.luc = luc
        self.sur = sur
        self.stamina = stamina
        self.mental_health = mental_health
        self.drug_health = drug_health
        logger.debug(f"[StatsModifiers] Created with values: hp={hp}, str={str}, "
                     f"dex={dex}, con={con}, int={int}, wis={wis}, cha={cha}, "
                     f"per={per}, agi={agi}, luc={luc}, sur={sur}, stamina={stamina}, "
                     f"mental_health={mental_health}, drug_health={drug_health}")

    # - Properties
    @property
    def dict(self) -> dict[str, int]:
        """
        Get the stats modifiers as a dictionary
        
        returns:
            dict[str, int]: The stats modifiers as a dictionary
        """
        return {
            "hp": self.hp,
            "str": self.str,
            "dex": self.dex,
            "con": self.con,
            "int": self.int,
            "wis": self.wis,
            "cha": self.cha,
            "per": self.per,
            "agi": self.agi,
            "luc": self.luc,
            "sur": self.sur,
            "stamina": self.stamina,
            "mental_health": self.mental_health,
            "drug_health": self.drug_health
        }

    # - dict importation
    @classmethod
    def from_dict(cls, modifiers_dict: dict[str, int]) -> StatsModifiers:
        """
        Create a StatsModifiers object from a dictionary
        
        arguments:
            modifiers_dict: dict[str, int]
                The stats modifiers dictionary
        returns:
            StatsModifiers: The created StatsModifiers object
        """
        return cls(
            hp=modifiers_dict.get("hp", 0),
            str=modifiers_dict.get("str", 0),
            dex=modifiers_dict.get("dex", 0),
            con=modifiers_dict.get("con", 0),
            int=modifiers_dict.get("int", 0),
            wis=modifiers_dict.get("wis", 0),
            cha=modifiers_dict.get("cha", 0),
            per=modifiers_dict.get("per", 0),
            agi=modifiers_dict.get("agi", 0),
            luc=modifiers_dict.get("luc", 0),
            sur=modifiers_dict.get("sur", 0),
            stamina=modifiers_dict.get("stamina", 0),
            mental_health=modifiers_dict.get("mental_health", 0),
            drug_health=modifiers_dict.get("drug_health", 0)
        )

    # - Reset method
    def reset(self) -> None:
        """
        Reset all modifiers to 0
        """
        self.hp = 0
        self.str = 0
        self.dex = 0
        self.con = 0
        self.int = 0
        self.wis = 0
        self.cha = 0
        self.per = 0
        self.agi = 0
        self.luc = 0
        self.sur = 0
        self.stamina = 0
        self.mental_health = 0
        self.drug_health = 0
        logger.debug("[StatsModifiers] All modifiers have been reset to 0")


# ----- Character class ----- #
class Character:
    """
    Character class
    
    This class represent a character in the game
    arguments:
        name: str
            The name of the character
        stats: Stats
            The stats of the character
        stats_modifiers: StatsModifiers
            The stats modifiers of the character
        spells: dict[str, Spell]
            The spells known by the character
        inventory: Inventory
            The items owned by the character
    """
    def __init__(self,
                 name: str,
                 stats: Stats,
                 stats_modifiers: StatsModifiers,
                 spells: dict[str, Spell],
                 inventory: Inventory) -> None:
        self.name = name
        self.stats = stats
        self.stats_modifiers = stats_modifiers
        self.spells = spells
        self.inventory = inventory
        logger.debug(f"[Character] Created character '{name}' with stats: "
                     f"{stats.dict} and modifiers: {stats_modifiers.dict}")

    # - Methods
    def get_current_stat(self, stat: str) -> int:
        """
        Get the current value of a stat, including modifiers
        
        arguments:
            stat: str
                The stat to get
        returns:
            int: The current value of the stat
        """
        base_value = getattr(self.stats, stat, 0)
        modifier_value = getattr(self.stats_modifiers, stat, 0)
        inventory_value = self.inventory.get_stat_modifier(stat)
        current_value = base_value + modifier_value + inventory_value
        logger.debug(f"[Character] <'{self.name}'> Current value of stat '{stat}': {current_value}")
        return current_value

    def save(self) -> None:
        """
        Save the character data to a file
        """
        with open(join(config.CHARACTERS_FOLDER, f"{self.name.replace(' ', '_')}.json"),
                  "w",
                  encoding="utf-8") as file:
            dump({
                "name": self.name,
                "stats": self.stats.dict,
                "modifiers": self.stats_modifiers.dict,
                "spells": list(self.spells.keys()),
                "inventory": self.inventory.to_list()
            }, file, indent=4)
        logger.debug(f"[Character] <'{self.name}'> Character data saved.")

    def create_sheet(self) -> None:
        """
        Create a character sheet Image
        """
        display.init()
        font.init()
        image = Surface((600, 400))
        image.fill((0, 0, 10))
        title_font = font.Font(None, 50)
        text_font = font.Font(None, 24)
        name = title_font.render(self.name, True, (255, 255, 255))
        image.blit(name, (20, 15))
        lvl = text_font.render(f"Level: {self.stats.lvl}", True, (255, 255, 255))
        rect = lvl.get_rect(bottomright=(535, 395))
        image.blit(lvl, rect)
        draw.line(image, (255, 255, 255), (0, 60), (600, 60), 2)
        draw.rect(image, (255, 255, 255), Rect(200, 15, 200, 10))
        draw.rect(image, (255, 255, 255), Rect(200, 35, 200, 10))
        hp = text_font.render(f"HP: {self.get_current_stat('hp')} / {self.stats.hp}", True, (255, 255, 255))
        image.blit(hp, (410, 12))
        stamina = text_font.render(f"Stamina: {self.get_current_stat('stamina')} / {self.stats.stamina}", True, (255, 255, 255))
        image.blit(stamina, (410, 32))
        hp_ratio = self.get_current_stat('hp') / self.stats.hp if self.stats.hp > 0 else 0
        stamina_ratio = self.get_current_stat('stamina') / self.stats.stamina if self.stats.stamina > 0 else 0
        draw.rect(image, (155, 255, 55), Rect(200, 15, 200 * hp_ratio, 10))
        draw.rect(image, (255, 155, 55), Rect(200, 35, 200 * stamina_ratio, 10))
        draw.line(image, (255, 255, 255), (60, 60), (60, 400), 2)
        draw.line(image, (255, 255, 255), (540, 60), (540, 400), 2)
        for i, stat_name in enumerate(["str", "dex", "con", "wis", "int", "cha", "per", "agi", "luc", "sur"]):
            stat_value = int(self.get_current_stat(stat_name))
            base_stat_value = getattr(self.stats, stat_name)
            modifier_value = getattr(self.stats_modifiers, stat_name)
            stat_color = (255, 0, 0) if base_stat_value <= 30 else (255, 155, 0) if base_stat_value <= 50 else (155, 255, 55) if base_stat_value <= 100 else (55, 155, 255)
            stat_text = text_font.render(f"{stat_name.upper()}", True, (255, 255, 255))
            stat_text_rect = stat_text.get_rect(center=(30, 80 + i * 30))
            stat_value_text = text_font.render(f"{stat_value}", True, (255, 255, 255))
            stat_value_text_rect = stat_value_text.get_rect(center=(570, 80 + i * 30))
            image.blit(stat_value_text, stat_value_text_rect)
            image.blit(stat_text, stat_text_rect)
            draw.rect(image, stat_color, Rect(70, 75 + i * 30, 200 * (base_stat_value / 100), 10))
            draw.rect(image, (255, 55, 155), Rect(70 + (200 * (base_stat_value / 100)), 77 + i * 30, 200 * (modifier_value / 100), 6))

        png_save(image, join(config.SHEETS_FOLDER, f"{self.name.replace(' ', '_')}.png"))
        logger.debug(f"[Character] <'{self.name}'> Character sheet created.")

    # - Character actions
    def cast_spell(self, spell_name: str,
                         target: Character,
                         user_dices: Optional[dict[str, int]]=None,
                         target_dices: Optional[dict[str, int]]=None) -> None:
        """
        Cast a spell on a target character
        
        arguments:
            spell_name: str
                The name of the spell to cast
            target: Character
                The target character
            user_dices: Optional[dict[str, int]]
                The dice rolls of the user casting the spell
                if None, new dice rolls will be generated
            target_dices: Optional[dict[str, int]]
                The dice rolls of the target character
                if None, new dice rolls will be generated
        """
        spell: Spell = self.spells.get(spell_name)
        if not spell:
            logger.debug(f"[Character] <'{self.name}'> Spell '{spell_name}' not known.")
            return
        
        spell.cast(self, target, user_dices, target_dices)

    def learn_spell(self, spell_name: Spell) -> None:
        """
        Learn a new spell
        
        arguments:
            spell_name: str
                The name of the spell to learn
        """
        self.spells[spell_name] = Spell.from_name(spell_name)
        logger.debug(f"[Character] <'{self.name}'> Learned new spell '{spell_name}'.")

    def strike(self, target: Character,
                     user_dices: Optional[Dice]=None,
                     target_dices: Optional[Dice]=None) -> str:
        """
        Perform a strike attack on a target character
        
        arguments:
            target: Character
                The target character
            user_dices: Optional[Dice]
                The dice rolls of the user performing the strike
                if None, new dice rolls will be generated
            target_dices: Optional[Dice]
                The dice rolls of the target character
                if None, new dice rolls will be generated
        
        returns:
            str: The dice command used for the strike damages
        """
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
            8 if user_dices.critical_success else
            4
        )
        logger.debug(f"[Character] <'{self.name}'> Strike on <'{target.name}'>: " \
                     f"{'Success' if nb_dice > 0 else 'Failure'}, {nb_dice}d{dice_value}")
        return f"{nb_dice}d{dice_value}"

    def shoot(self, target: Character,
                    user_dices: Optional[Dice]=None,
                    target_dices: Optional[Dice]=None) -> str:
        """
        Perform a shoot attack on a target character
        
        arguments:
            target: Character
                The target character
            user_dices: Optional[Dice]
                The dice rolls of the user performing the shoot
                if None, new dice rolls will be generated
            target_dices: Optional[Dice]
                The dice rolls of the target character
                if None, new dice rolls will be generated
        
        returns:
            str: The dice command used for the shoot damages
        """
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
            8 if user_dices.critical_success else
            4
        )
        logger.debug(f"[Character] <'{self.name}'> Shoot on <'{target.name}'>: " \
                     f"{'Success' if nb_dice > 0 else 'Failure'}, {nb_dice}d{dice_value}")
        return f"{nb_dice}d{dice_value}"

    # - Class methods
    @classmethod
    def from_blueprint(cls, blueprint: dict) -> Character:
        """
        Create a Character from a blueprint dictionary
        
        arguments:
            blueprint: dict
                The character blueprint dictionary
        returns:
            Character: The created Character object
        """
        stats = Stats.from_dict(blueprint.get("stats", {}))
        stats_modifiers = StatsModifiers.from_dict(blueprint.get("modifiers", {}))
        spells = {
            spell_name: Spell.from_name(spell_name)
            for spell_name in blueprint.get("spells", [])
        }
        inventory = Inventory.from_list(blueprint.get("inventory", []))
        return cls(
            name=blueprint.get("name", "Unnamed"),
            stats=stats,
            stats_modifiers=stats_modifiers,
            spells=spells,
            inventory=inventory
        )

    @classmethod
    def from_name(cls, name: str) -> Character:
        """
        Create a Character from a name (loads from file)
        
        arguments:
            name: str
                The name of the character
        returns:
            Character: The created Character object
        """
        with open(join(config.CHARACTERS_FOLDER, f"{name.replace(' ', '_')}.json"),
                  "r",
                  encoding="utf-8") as file:
            blueprint = load(file)
        return cls.from_blueprint(blueprint)
