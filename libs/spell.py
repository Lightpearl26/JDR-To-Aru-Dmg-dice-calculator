# -*- coding: utf-8 -*-
# pylint: disable=eval-used, broad-except

"""
JDR spell libs
"""

# Import external libs
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from ast import Expression, BinOp, UnaryOp, Constant, Add, Sub, Mult, Div, USub, UAdd, parse
from re import match
from os.path import join
from json import load

# Import logger
from . import logger

# Import config
from . import config

from .dice import Dice, DiceRatio, DiceAttack

if TYPE_CHECKING:
    from .character import Character


def _safe_eval_expression(expr: str) -> int:
    """
    Evaluate a simple arithmetic expression safely.

    Allowed operations: +, -, *, /
    """
    tree = parse(expr, mode="eval")

    def _eval(node):
        if isinstance(node, Expression):
            return _eval(node.body)
        if isinstance(node, Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, UnaryOp) and isinstance(node.op, (USub, UAdd)):
            value = _eval(node.operand)
            return -value if isinstance(node.op, USub) else value
        if isinstance(node, BinOp) and isinstance(node.op, (Add, Sub, Mult, Div)):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, Add):
                return left + right
            if isinstance(node.op, Sub):
                return left - right
            if isinstance(node.op, Mult):
                return left * right
            if right == 0:
                raise ZeroDivisionError("division by zero")
            return left / right
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    return int(_eval(tree))

# - smart_split function
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


# ----- Formula class ----- #
class Formula:
    """
    Formula to parse and evaluate
    1. Compile the formula into a template and placeholders
    2. Evaluate the formula by resolving the placeholders and calculating the final result
    3. Return the final result as an integer
    """
    def __init__(self, cmd: str="", template: str="", placeholders: Optional[list]=None) -> None:
        self.cmd = cmd
        self.template = template
        self.placeholders = placeholders

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
        logger.debug(f"[Formula] Formula '{self.cmd}' compilated to template '{self.template}' with {len(self.placeholders)} placeholders.")

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
                    dice_value = user_dices.get(stat)
                elif who == "target" and target_dices:
                    dice_value = target_dices.get(stat)
                if who == "user":
                    value = DiceRatio(stat, ratio).resolve(user, dice_value)
                elif who == "target":
                    value = DiceRatio(stat, ratio).resolve(target, dice_value)
                else:
                    value = 0
                values.append(value)
            elif cls == DiceAttack:
                atk_who, atk_stat = args[0].split(".")
                def_who, def_stat = args[2].split(".")
                atk_ratio = DiceRatio(atk_stat, int(args[1]))
                def_ratio = DiceRatio(def_stat, int(args[3]))

                if atk_who == "user":
                    atk_char = user
                    atk_dice = user_dices.get(atk_stat) if user_dices else None
                elif atk_who == "target":
                    atk_char = target
                    atk_dice = target_dices.get(atk_stat) if target_dices else None
                else:
                    atk_char = None
                    atk_dice = None

                if def_who == "user":
                    def_char = user
                    def_dice = user_dices.get(def_stat) if user_dices else None
                elif def_who == "target":
                    def_char = target
                    def_dice = target_dices.get(def_stat) if target_dices else None
                else:
                    def_char = None
                    def_dice = None

                if atk_char is None or def_char is None:
                    value = 0
                else:
                    value = DiceAttack(atk_ratio, def_ratio).resolve(atk_char, def_char, atk_dice, def_dice)
                values.append(value)
            else:
                values.append(0)
        try:
            result = _safe_eval_expression(self.template.format(*values))
        except (ValueError, ZeroDivisionError, SyntaxError, TypeError) as error:
            logger.error(f"[Formula] Failed to evaluate formula '{self.cmd}': {error}")
            result = 0
        logger.debug(f"[Formula] Evaluated formula '{self.cmd}' with values {values} to result {result}.")
        return result


# ----- Effect class ----- #
class Effect:
    """
    Effect of a spell
    attributes:
        target: str
            The target of the effect ("user" or "target")
        target_stat: str
            The stat to affect (e.g. "hp", "mp", "str", etc.)
        effect: str
            The type of effect ("bonus" or "malus")
        formula: Formula
            The formula to calculate the effect value
    """
    def __init__(self, target: str, target_stat: str, effect: str, formula: Formula) -> None:
        self.target = target  # "user" or "target"
        self.target_stat = target_stat  # e.g. "hp", "mp", "str", etc.
        self.effect = effect  # "bonus" or "malus"
        self.formula = formula

    # - loading from blueprint
    @classmethod
    def from_blueprint(cls, blueprint: dict) -> Effect:
        """
        Create an Effect from a blueprint dictionary
        """
        # Support both "formula" and "formule" keys for compatibility
        formula_cmd = blueprint.get("formula") or blueprint.get("formule", "")
        formula = Formula(cmd=formula_cmd)
        formula.compilate()
        return cls(
            target=blueprint.get("target", "target"),
            target_stat=blueprint.get("target_stat", "hp"),
            effect=blueprint.get("effect", "malus"),
            formula=formula
        )

    # - resolving effect
    def resolve(self, user: Character,
                      target: Character,
                      user_dices: dict[str, Dice]=None,
                      target_dices: dict[str, Dice]=None) -> str:
        """
        Resolve the effect of the spell
        arguments:
            user: Character
                The character casting the spell
            target: Character
                The character receiving the spell
            user_dices: dict[str, Dice], optional
                The dices to use for the user (if needed)
            target_dices: dict[str, Dice], optional
                The dices to use for the target (if needed)
        
        returns:
            str: A description of the effect applied
        """
        value = self.formula.eval(user, target, user_dices, target_dices)
        target_char = user if self.target == "user" else target
        target_char_name = target_char.name
        effect_symbol = "+" if self.effect == "bonus" else "-"
        
        if self.target == "user":
            if self.effect == "bonus":
                setattr(user.stats_modifiers, self.target_stat,
                        getattr(user.stats_modifiers, self.target_stat) + value)
                logger.debug(f"[Effect] Applied bonus effect to user: {self.target_stat} += {value} (total={user.get_current_stat(self.target_stat)})")
                return f"{target_char_name}: {self.target_stat} {effect_symbol} {value}"
            elif self.effect == "malus":
                setattr(user.stats_modifiers, self.target_stat,
                        getattr(user.stats_modifiers, self.target_stat) - value)
                logger.debug(f"[Effect] Applied malus effect to user: {self.target_stat} -= {value} (total={user.get_current_stat(self.target_stat)})")
                return f"{target_char_name}: {self.target_stat} {effect_symbol} {value}"
        elif self.target == "target":
            if self.effect == "bonus":
                setattr(target.stats_modifiers, self.target_stat,
                        getattr(target.stats_modifiers, self.target_stat) + value)
                logger.debug(f"[Effect] Applied bonus effect to target: {self.target_stat} += {value} (total={target.get_current_stat(self.target_stat)})")
                return f"{target_char_name}: {self.target_stat} {effect_symbol} {value}"
            elif self.effect == "malus":
                setattr(target.stats_modifiers, self.target_stat,
                        getattr(target.stats_modifiers, self.target_stat) - value)
                logger.debug(f"[Effect] Applied malus effect to target: {self.target_stat} -= {value} (total={target.get_current_stat(self.target_stat)})")
                return f"{target_char_name}: {self.target_stat} {effect_symbol} {value}"
        
        return ""


# ----- Spell class ----- #
class Spell:
    """
    Spell class
    attributes:
        name: str
            The name of the spell
        cost: int
            The cost of the spell (e.g. mana cost)
        description: str
            The description of the spell
        effects: list[Effect]
            The list of effects of the spell
    """
    def __init__(self, name: str, cost: int, description: str, effects: list[Effect]) -> None:
        self.name = name
        self.cost = cost
        self.description = description
        self.effects = effects
    
    # - loading from blueprint
    @classmethod
    def from_blueprint(cls, blueprint: dict) -> Spell:
        """
        Create a Spell from a blueprint dictionary
        """
        effects = [Effect.from_blueprint(effect_bp) for effect_bp in blueprint.get("effects", [])]
        return cls(
            name=blueprint.get("name", "Unnamed Spell"),
            cost=blueprint.get("cost", 0),
            description=blueprint.get("description", ""),
            effects=effects
        )

    # - loading from name
    @classmethod
    def from_name(cls, name: str) -> Optional[Spell]:
        """
        Load a Spell by its name from the config spell blueprints
        """
        with open(join(config.SPELLS_FOLDER, f"{name.replace(' ', '_')}.json"), "r", encoding="utf-8") as spell_file:
            blueprint = load(spell_file)
        return cls.from_blueprint(blueprint)

    # - casting spell
    def cast(self, user: Character,
                   target: Character,
                   user_dices: dict[str, Dice]=None,
                   target_dices: dict[str, Dice]=None) -> str:
        """
        Cast the spell from user to target
        arguments:
            user: Character
                The character casting the spell
            target: Character
                The character receiving the spell
            user_dices: dict[str, Dice], optional
                The dices to use for the user (if needed)
            target_dices: dict[str, Dice], optional
                The dices to use for the target (if needed)
        
        returns:
            str: A description of all effects applied
        """
        logger.debug(f"[Spell] Casting spell '{self.name}' from '{user.name}' to '{target.name}'.")
        user.stats_modifiers.stamina -= self.cost
        logger.debug(f"[Spell] '{user.name}' pays {self.cost} stamina for casting spell '{self.name}' (remaining stamina={user.get_current_stat('stamina')}).")
        
        effect_logs = []
        for effect in self.effects:
            effect_log = effect.resolve(user, target, user_dices, target_dices)
            if effect_log:
                effect_logs.append(effect_log)
        
        return "\n".join(effect_logs) if effect_logs else "Aucun effet"

