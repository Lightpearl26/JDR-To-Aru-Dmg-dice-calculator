#-*-coding: utf-8-*-

"""
Components of the characters
"""

# Import external modules
from __future__ import annotations
from dataclasses import dataclass
from random import randint
from re import match
from json import load, dump
import pygame
from pygame import Surface, font, Rect
from pygame.image import save as png_save
import pygame.draw as draw

pygame.font.init()
pygame.display.init()

# ----- Create constants ----- #
STATS_DICES: dict[str, str] = {
    "str": "1d100",
    "dex": "1d100",
    "con": "1d100",
    "wis": "1d100",
    "int": "1d100",
    "cha": "1d100",
    "per": "1d100",
    "agi": "1d100",
    "luc": "1d100",
    "sur": "1d100"
}

# ----- Create helper functions ----- #
def smart_split(expr: str) -> list[str]:
    """
    Split an expression into parts, considering parentheses
    e.g. "10 + diceratio(user.int, 20) - (5 * 2)" -> ["10", "+", "diceratio(user.int, 20)", "-", "(5 * 2)"]
    1. Split the expression by operators (+, -, *, /) not inside parentheses
    2. Return the list of parts
    3. Keep the operators as separate parts
    4. Remove leading and trailing spaces from each part
    5. Ignore empty parts
    6. Handle nested parentheses correctly
    """
    parts = []
    buf = ''
    depth = 0
    for c in expr:
        if c == '(':
            depth += 1
            buf += c
        elif c == ')':
            depth -= 1
            buf += c
        elif c in '+-*/' and depth == 0:
            if buf.strip():
                parts.append(buf.strip())
            parts.append(c)
            buf = ''
        else:
            buf += c
    if buf.strip():
        parts.append(buf.strip())
    return parts

# ----- Create Dice components ----- #
@dataclass
class Dice:
    """
    Dice component attached to a stat
    """
    critical: bool
    value: int
    dices: list[int]

    @classmethod
    def roll(cls, cmd: str) -> Dice:
        """
        Roll a dice and return the dice object of the result
        cmd must be of the following form:
        XdY
            - X is the number of dices rolled
            - Y is the number of face per dice
        """
        x, y = (int(v) for v in cmd.split("d"))
        crit_percentage = max(1, y // 20)
        results = [randint(1, y) for _ in range(x)]
        crit = any(result <= crit_percentage or result >= y - crit_percentage for result in results)
        return cls(crit, sum(results), results)


@dataclass
class DiceCheck:
    """
    Dice check component attached to a stat
    """

    @classmethod
    def resolve(cls, character: Character, stat_name: str) -> tuple[Dice, bool]:
        """
        Resolve the dice check
        """
        stat_value = getattr(character.stats, stat_name)
        stat_modifier = getattr(character.stats_modifiers, stat_name)
        total_value = stat_value + stat_modifier
        dice = Dice.roll("1d100")
        print(f"DiceCheck: {total_value} vs {dice.value} ({'Success' if dice.value <= total_value else 'Fail'})")
        return dice, dice.value <= total_value


@dataclass
class DiceRatio:
    """
    Dice ratio component attached to a stat
    """
    stat: str
    ratio: int

    def resolve(self, character: Character, dice: Dice=None) -> int:
        """
        Resolve Dice Ratio
        """
        if dice is None:
            dice = Dice.roll("1d100")
        stat_value = getattr(character.stats, self.stat)
        stat_modifier = getattr(character.stats_modifiers, self.stat)
        total_value = stat_value + stat_modifier
        result = (total_value - dice.value) * self.ratio / 100
        print(f"DiceRatio ({self.stat}): ({total_value} - {dice.value}) * {self.ratio} / 100 = {result}")
        return int(result)


@dataclass
class DiceAttack:
    """
    Dice attack component attached to a stat
    """
    user_ratio: DiceRatio
    target_ratio: DiceRatio

    def resolve(self, user: Character, target: Character, user_dices: Dice=None, target_dices: Dice=None) -> int:
        """
        Resolve the dice attack
        """
        user_stats = self.user_ratio.resolve(user, dice=user_dices)
        target_stats = self.target_ratio.resolve(target, dice=target_dices)
        print(f"DiceAttack: max(0, {user_stats} - {target_stats}) = {max(0, user_stats - target_stats)}")
        return max(0, user_stats - target_stats)


# ----- Create Stats components ----- #
@dataclass
class Stats:
    """
    Stats of the Character
    """
    str: int = 50 # Strength
    dex: int = 50 # Dexterity
    con: int = 50 # Constitution
    wis: int = 50 # Wisdom
    int: int = 50 # Intelligence
    cha: int = 50 # Charism
    per: int = 50 # Perception
    agi: int = 50 # Agility
    luc: int = 50 # Luck
    sur: int = 50 # Survivability
    stamina: int = 100
    mental_health: int = 100
    drug_health: int = 100

    @property
    def dict(self) -> dict[str, int]:
        """
        Save the stats to a dict
        """
        return {
            "str": self.str,
            "dex": self.dex,
            "con": self.con,
            "wis": self.wis,
            "int": self.int,
            "cha": self.cha,
            "per": self.per,
            "agi": self.agi,
            "luc": self.luc,
            "sur": self.sur,
            "stamina": self.stamina,
            "mental_health": self.mental_health,
            "drug_health": self.drug_health
        }

    @classmethod
    def from_dict(cls, stats: dict) -> Stats:
        """
        Generate Stats instance from stats dict
        """
        return cls(
            stats.get("str", 50),
            stats.get("dex", 50),
            stats.get("con", 50),
            stats.get("wis", 50),
            stats.get("int", 50),
            stats.get("cha", 50),
            stats.get("per", 50),
            stats.get("agi", 50),
            stats.get("luc", 50),
            stats.get("sur", 50),
            stats.get("stamina", 100),
            stats.get("mental_health", 100),
            stats.get("drug_health", 100)
        )

    @property
    def hp(self) -> int:
        """
        Max Hp stat of the character
        """
        return 10 + self.con // 10 + self.wis // 10

    @property
    def lvl(self) -> int:
        """
        Current level of the character
        """
        total_stats = (
            self.str +
            self.dex +
            self.con +
            self.wis +
            self.int +
            self.cha +
            self.per +
            self.agi +
            self.luc +
            self.sur
        )
        return (total_stats - 500) // 5


@dataclass
class StatsModifiers:
    """
    Modifier applied to character stats
    """
    hp: int = 0 # Health points
    str: int = 0 # Strength
    dex: int = 0 # Dexterity
    con: int = 0 # Constitution
    wis: int = 0 # Wisdom
    int: int = 0 # Intelligence
    cha: int = 0 # Charism
    per: int = 0 # Perception
    agi: int = 0 # Agility
    luc: int = 0 # Luck
    sur: int = 0 # Survivability
    stamina: int = 0
    mental_health: int = 0
    drug_health: int = 0

    @classmethod
    def from_dict(cls, modifiers: dict) -> StatsModifiers:
        """
        Generate StatsModifiers instance from stats dict
        """
        return cls(
            modifiers.get("hp", 0),
            modifiers.get("str", 0),
            modifiers.get("dex", 0),
            modifiers.get("con", 0),
            modifiers.get("wis", 0),
            modifiers.get("int", 0),
            modifiers.get("cha", 0),
            modifiers.get("per", 0),
            modifiers.get("agi", 0),
            modifiers.get("luc", 0),
            modifiers.get("sur", 0),
            modifiers.get("stamina", 0),
            modifiers.get("mental_health", 0),
            modifiers.get("drug_health", 0)
        )

    def reset(self) -> None:
        """
        reset all modifiers
        """
        self.hp = 0
        self.str = 0
        self.dex = 0
        self.con = 0
        self.wis = 0
        self.int = 0
        self.cha = 0
        self.per = 0
        self.agi = 0
        self.luc = 0
        self.sur = 0
        self.stamina = 0
        self.mental_health = 0
        self.drug_health = 0

    @property
    def dict(self) -> dict[str, int]:
        """
        Save the stats modifiers to a dict
        """
        return {
            "hp": self.hp,
            "str": self.str,
            "dex": self.dex,
            "con": self.con,
            "wis": self.wis,
            "int": self.int,
            "cha": self.cha,
            "per": self.per,
            "agi": self.agi,
            "luc": self.luc,
            "sur": self.sur,
            "stamina": self.stamina,
            "mental_health": self.mental_health,
            "drug_health": self.drug_health
        }


# ----- Create spells components ----- #
@dataclass
class Formula:
    """
    Formula to parse and evaluate
    1. Compile the formula into a template and placeholders
    2. Evaluate the formula by resolving the placeholders and calculating the final result
    3. Return the final result as an integer
    """
    cmd: str = ""
    template: str = ""
    placeholders: list = None

    def compilate(self) -> None:
        """
        Compile la formule en template et placeholders
        """
        self.template = ""
        self.placeholders = []
        count = 0
        parts = smart_split(self.cmd)
        for part in parts:
            if part in ("+", "-", "*", "/"):
                self.template += f" {part} "
            else:
                # Expression entre parenthèses = sous-formule
                if part.startswith("(") and part.endswith(")"):
                    sub_formula = Formula(cmd=part[1:-1])
                    sub_formula.compilate()
                    self.placeholders.append((Formula, sub_formula))
                else:
                    m = match(r"(\w+)\s*\(([^)]*)\)", part)
                    if m:
                        func_name = m.group(1)
                        args = [arg.strip() for arg in m.group(2).split(",")]
                        if func_name == "diceratio" and len(args) == 2:
                            self.placeholders.append((DiceRatio, args))
                        elif func_name == "diceattack" and len(args) == 4:
                            self.placeholders.append((DiceAttack, args))
                        else:
                            self.placeholders.append((str, part))
                    else:
                        self.placeholders.append((str, part))
                self.template += f"{{{count}}}"
                count += 1

    def eval(self, user, target, user_dices: dict[str, Dice]=None, target_dices: dict[str, Dice]=None) -> int:
        """
        Résout la formule en évaluant les placeholders et en calculant le résultat final
        """
        if not self.template or self.placeholders is None:
            self.compilate()
        values = []
        for placeholder in self.placeholders:
            cls, args = placeholder
            if cls == str:
                try:
                    value = int(args)
                except ValueError:
                    # Accès à une stat, ex: user.int ou target.wis
                    if "." in args:
                        who, stat = args.split(".")
                        if who == "user":
                            value = getattr(user.stats, stat)
                        elif who == "target":
                            value = getattr(target.stats, stat)
                        else:
                            value = 0
                    else:
                        value = 0
                values.append(value)
            elif cls == Formula:
                # Sous-formule
                value = args.eval(user, target)
                values.append(value)
            elif cls == DiceRatio:
                who, stat = args[0].split(".")
                ratio = int(args[1])
                dice_value = None
                if who == "user" and user_dices:
                    dice_value = Dice(False, user_dices.get(stat), [])
                elif who == "target" and target_dices:
                    dice_value = Dice(False, target_dices.get(stat), [])
                if who == "user":
                    value = DiceRatio(stat, ratio).resolve(user, dice_value)
                elif who == "target":
                    value = DiceRatio(stat, ratio).resolve(target, dice_value)
                else:
                    value = 0
                values.append(value)
            elif cls == DiceAttack:
                # À adapter selon ton implémentation de DiceAttack
                atk_ratio = DiceRatio(args[0].split(".")[1], int(args[1]))
                def_ratio = DiceRatio(args[2].split(".")[1], int(args[3]))
                value = DiceAttack(atk_ratio, def_ratio).resolve(user, target, user_dices, target_dices)
                values.append(value)
            else:
                values.append(0)
        try:
            result = eval(self.template.format(*values), {"__builtins__": None})
        except Exception as e:
            print(e)
            result = 0
        return result


@dataclass
class Effect:
    """
    Effect of a spell
    """
    target: str
    target_stat: str
    effect: str  # "bonus" or "malus"
    formula: Formula

    @classmethod
    def from_blueprint(cls, blueprint: dict) -> Effect:
        """
        Generate Effect instance from an effect blueprint
        """
        formula = Formula(blueprint.get("formula", ""))
        formula.compilate()
        return cls(
            blueprint.get("target", "target"),
            blueprint.get("target_stat", "hp"),
            blueprint.get("effect", "malus"),
            formula
        )

    def resolve(self, user: Character, target: Character, user_dices: dict[str, Dice] = None, target_dices: dict[str, Dice] = None) -> None:
        """
        Resolve the effect from user to target
        """
        value = self.formula.eval(user, target, user_dices, target_dices)
        if self.target == "user":
            if self.effect == "bonus":
                setattr(user.stats_modifiers, self.target_stat,
                        getattr(user.stats_modifiers, self.target_stat) + value)
                print(f"{user.name} gains {value} {self.target_stat} (current: {user.get_current_stat(self.target_stat)})")
            else:
                setattr(user.stats_modifiers, self.target_stat,
                        getattr(user.stats_modifiers, self.target_stat) - value)
                print(f"{user.name} loses {value} {self.target_stat} (current: {user.get_current_stat(self.target_stat)})")
        elif self.target == "target":
            if self.effect == "bonus":
                setattr(target.stats_modifiers, self.target_stat,
                        getattr(target.stats_modifiers, self.target_stat) + value)
                print(f"{target.name} gains {value} {self.target_stat} (current: {target.get_current_stat(self.target_stat)})")
            else:
                setattr(target.stats_modifiers, self.target_stat,
                        getattr(target.stats_modifiers, self.target_stat) - value)
                print(f"{target.name} loses {value} {self.target_stat} (current: {target.get_current_stat(self.target_stat)})")


@dataclass
class Spell:
    """
    Spell entity
    """
    name: str
    cost: int
    description: str
    effects: list[Effect]

    @classmethod
    def from_blueprint(cls, blueprint: dict) -> Spell:
        """
        Generate Spell instance from a spell blueprint
        """
        effects = [
            Effect.from_blueprint(effect)
            for effect in blueprint.get("effects", [])
        ]
        return cls(
            blueprint.get("name", "Unnamed Spell"),
            blueprint.get("cost", 0),
            blueprint.get("description", ""),
            effects
        )

    @classmethod
    def from_name(cls, name: str) -> Spell:
        """
        Load a spell by its name
        """
        with open(f"spells/{name.replace(' ', '_')}.json", "r", encoding="utf-8") as f:
            blueprint = load(f)
        return cls.from_blueprint(blueprint)

    def cast(self, user: Character, target: Character, user_dices: dict[str, Dice] = None, target_dices: dict[str, Dice] = None) -> None:
        """
        Cast the spell from user to target
        """
        user.stats_modifiers.stamina -= self.cost
        for effect in self.effects:
            effect.resolve(user, target, user_dices, target_dices)


# ----- Create inventory components ----- #
@dataclass
class Item:
    """
    Instance of an item
    """
    name: str
    description: str


@dataclass
class Inventory:
    """
    Inventory of the character
    """
    items: list[Item]
    funds: int


# ----- Create character components ----- #
@dataclass
class Character:
    """
    Character entity
    """
    name: str
    stats: Stats
    stats_modifiers: StatsModifiers
    spells: dict[str, Spell]

    def get_current_stat(self, stat_name: str) -> int:
        """
        Get the current value of a stat, including modifiers
        """
        base_value = getattr(self.stats, stat_name)
        modifier_value = getattr(self.stats_modifiers, stat_name)
        return base_value + modifier_value

    def cast_spell(self, spell_name: str, target: Character, user_dices: dict[str, Dice] = None, target_dices: dict[str, Dice] = None) -> None:
        """
        Cast a spell on a target character
        """
        spell = self.spells.get(spell_name)
        if spell:
            spell.cast(self, target, user_dices, target_dices)
        else:
            print(f"{self.name} does not know the spell '{spell_name}'")

    def save(self) -> None:
        """
        Save the character to a JSON file
        """
        blueprint = {
            "name": self.name,
            "stats": self.stats.dict,
            "modifiers": self.stats_modifiers.dict,
            "spells": list(self.spells.keys())
        }
        with open(f"characters/{self.name.replace(' ', '_')}.json", "w", encoding="utf-8") as f:
            dump(blueprint, f, ensure_ascii=False, indent=4)

    def create_sheet(self) -> None:
        """
        Create a character sheet Image
        """
        image = Surface((600, 400))
        image.fill((0, 0, 10))
        title_font = font.Font(None, 50)
        text_font = font.Font(None, 24)
        name = title_font.render(self.name, True, (255, 255, 255))
        image.blit(name, (20, 15))
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

        png_save(image, f"Sheets/{self.name.replace(' ', '_')}.png")

    @classmethod
    def from_blueprint(cls, blueprint: dict) -> Character:
        """
        Generate Character instance from a character blueprint
        """
        stats = Stats.from_dict(blueprint.get("stats", {}))
        stats_modifiers = StatsModifiers.from_dict(blueprint.get("modifiers", {}))
        spells = {
            spell_name: Spell.from_name(spell_name)
            for spell_name in blueprint.get("spells", [])
        }
        return cls(
            blueprint.get("name", "Unnamed Character"),
            stats,
            stats_modifiers,
            spells
        )

    @classmethod
    def from_name(cls, name: str) -> Character:
        """
        Load a character by its name
        """
        with open(f"characters/{name.replace(' ', '_')}.json", "r", encoding="utf-8") as f:
            blueprint = load(f)
        return cls.from_blueprint(blueprint)
