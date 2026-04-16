#-*- coding: utf-8 -*-

"""
Spell definition module.
"""

# import built-in modules
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Literal, Any
from ast import Expression, BinOp, UnaryOp, Constant, Add, Sub, Mult, Div, USub, UAdd, parse
from re import match
from os.path import join
from json import load

# import local modules
from ..dice import DiceRatio, DiceAttack, Dice
from .. import config


# define types and constants
TargetScope = Literal["user", "target"]
TargetStat = Literal["hp",
                      "stamina",
                      "str",
                      "con",
                      "dex",
                      "int",
                      "wis",
                      "cha",
                      "per",
                      "luc",
                      "sur",
                      "agi",
                      "mental_health",
                      "drug_health"]
Targeting = Literal["single", "multi"]
RuntimePolicy = Literal["instant", "maintain", "refresh", "delay"]
Operator = Literal["bonus", "malus"]

# define helper functions
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
            if isinstance(node.op, Div):
                if right == 0:
                    raise ZeroDivisionError("division by zero")
                return left / right
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    return int(_eval(tree))


# ----- Formula definition ----- #
@dataclass
class Formula:
    """
    Represents a formula for calculating spell effects.
    """
    expression: str
    template: str = ""
    placeholders: list[Any] = field(default_factory=list)
    compilated: bool = False

    def compilate(self) -> None:
        """
        Compiles the expression to create the template and placeholders.
        """
        self.template = ""
        self.placeholders = []
        count = 0
        parts = smart_split(self.expression)
        for part in parts:
            if part in "+-*/":
                self.template += f" {part} "
            else:
                if part.startswith("(") and part.endswith(")"):
                    sub_formula = Formula(part[1:-1])
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
        self.compilated = True

    def evaluate(
                    self,
                    user,
                    target,
                    user_dices: Optional[dict[str, int]]=None,
                    target_dices: Optional[dict[str, int]]=None
            ) -> int:
        """
        Evaluates the formula by replacing the placeholders with their actual values.
        """
        if not self.compilated:
            self.compilate()
        values = []
        for cls, args in self.placeholders:
            if cls == str:
                try:
                    value = int(args)
                except ValueError:
                    try:
                        value = float(args)
                    except ValueError:
                        if "." in args:
                            who, stat = args.split(".")
                            if who == "user":
                                value = user.get_stat(stat)
                            elif who == "target":
                                value = target.get_stat(stat)
                            else:
                                value = 0
                        else:
                            value = 0
                values.append(value)
            elif cls == Formula:
                value = args.evaluate(user, target, user_dices, target_dices)
                values.append(value)
            elif cls == DiceRatio:
                who, stat = args[0].split(".")
                ratio = int(args[1])
                dice_value = None
                dice = None
                if who == "user" and user_dices:
                    dice_value = user_dices.get(stat)
                    dice = Dice("1d100", [dice_value]) if dice_value else None
                elif who == "target" and target_dices:
                    dice_value = target_dices.get(stat)
                    dice = Dice("1d100", [dice_value]) if dice_value else None
                if who == "user":
                    value = DiceRatio(stat, ratio).resolve(user, dice)
                elif who == "target":
                    value = DiceRatio(stat, ratio).resolve(target, dice)
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
                if atk_dice is not None:
                    atk_dice = Dice("1d100", [atk_dice])
                if def_dice is not None:
                    def_dice = Dice("1d100", [def_dice])

                if atk_char and def_char:
                    value = DiceAttack(atk_ratio, def_ratio).resolve(
                        atk_char,
                        def_char,
                        atk_dice,
                        def_dice
                    )
                else:
                    value = 0
                values.append(value)
            else:
                values.append(0)
        try:
            result = _safe_eval_expression(self.template.format(*values))
        except (ValueError, ZeroDivisionError, SyntaxError, TypeError):
            result = 0
        return result


# ----- Effect definition ----- #
@dataclass
class Effect:
    """
    Represents an effect of a spell.
    """
    target: tuple[TargetScope, TargetStat]
    operator: Operator
    formula: Formula


# ----- Spell definition ----- #
@dataclass
class Spell:
    """
    Represents a spell definition.
    """
    name: str
    description: str
    cost: int
    targeting: Targeting
    runtime_policy: RuntimePolicy
    effects: list[Effect]
    delay: float | int = float("inf")

    @classmethod
    def from_name(cls, name: str) -> Optional[Spell]:
        """
        Load a spell definition from json file by name.
        
        1. Look for a file named "{name}.json" in the "assets/spells" directory
        2. If found, load the JSON content and parse it into a Spell object
        3. If not found, return None
        """
        filename = join(config.SPELLS_FOLDER, f"{name.replace(' ', '_').lower()}.json")
        try:
            with open(filename, "r", encoding="utf-8-sig") as f:
                data = load(f)
                effects = []
                delay = data.get("delay", float("inf"))
                for effect_data in data.get("effects", []):
                    target_scope, target_stat = effect_data["target"].split(".")
                    formula = Formula(effect_data["formula"])
                    formula.compilate()
                    effect = Effect(
                        target=(target_scope, target_stat),
                        operator=effect_data["operator"],
                        formula=formula
                    )
                    effects.append(effect)
                return cls(
                    name=data["name"],
                    description=data["description"],
                    cost=data["cost"],
                    targeting=data["targeting"],
                    runtime_policy=data["runtime_policy"],
                    effects=effects,
                    delay=delay
                )
        except FileNotFoundError:
            return None
