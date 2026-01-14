# -*- coding: utf-8 -*-

"""
JDR dice libs
"""

# Import external libs
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from random import randint

# Import logger
from . import logger

if TYPE_CHECKING:
    from .character import Character


# ----- Dice class ----- #
class Dice:
    """
    Dice class
    
    This class represent a dice
    arguments:
        cmd: str
            The dice command
            for example 1d100 for one 100-sided dice
            or 2d6 for two 6-sided dices
        dices_values: list of int
            The list of the dice values
    """
    def __init__(self, cmd: str, dices_values: list[int]) -> None:
        self.cmd = cmd
        self.dices_values = dices_values

    # - Dice properties
    @property
    def critical_success(self) -> bool:
        """
        Check if the dice roll is a critical success
        
        returns:
            bool: True if the roll is a critical success, False otherwise
        """
        # get the dice type
        dice_type = int(self.cmd.split('d')[1])

        # check if any dice value is under or over 5% of the dice type
        for value in self.dices_values:
            if value-1 <= dice_type * 0.05:
                return True
        return False

    @property
    def critical_failure(self) -> bool:
        """
        Check if the dice roll is a critical failure
        
        returns:
            bool: True if the roll is a critical failure, False otherwise
        """
        # get the dice type
        dice_type = int(self.cmd.split('d')[1])

        # check if any dice value is over 95% of the dice type
        for value in self.dices_values:
            if value >= dice_type * 0.95:
                return True
        return False

    @property
    def total(self) -> int:
        """
        Get the total of the dice roll
        
        returns:
            int: The total of the dice roll
        """
        return sum(self.dices_values)

    # - Dice roller function
    @classmethod
    def roll(cls, cmd: str) -> Dice:
        """
        Roll a dice
        
        arguments:
            cmd: str
                The dice command
                for example 1d100 for one 100-sided dice
                or 2d6 for two 6-sided dices
        
        returns:
            Dice: The rolled dice object
        """
        # parse the command
        try:
            num_dices, dice_type = cmd.lower().split('d')
            num_dices = int(num_dices)
            dice_type = int(dice_type)
        except Exception as e:
            logger.error(f"Invalid dice command: {cmd} - {e}")
            raise ValueError(f"Invalid dice command: {cmd}") from e

        # roll the dices
        dices_values = [randint(1, dice_type) for _ in range(num_dices)]
        logger.debug(f"[Dice] Rolled dice '{cmd}': values={dices_values}")

        # create and return the Dice object
        return cls(cmd, dices_values)

    # - String representation
    def __str__(self) -> str:
        return f"[Dice] cmd: {self.cmd}, " \
               f"values: {self.dices_values}, " \
               f"total: {self.total}, " \
               f"critical success: {self.critical_success}, " \
               f"critical failure: {self.critical_failure}"


# ----- DiceCheck class ----- #
class DiceCheck:
    """
    Dice check linked to a character's stat
    """
    def __init__(self, dice: Dice, character: Character, stat: str) -> None:
        self.dice = dice
        self.character = character
        self.stat = stat
        logger.debug(f"[DiceCheck] Created for character '{character.name}' "
                     f"stat '{stat}': success={self.success}")

    @property
    def success(self) -> bool:
        """
        Check if the dice check is a success
        
        returns:
            bool: True if the check is a success, False otherwise
        """
        # get the character's stat value
        stat_value = self.character.get_current_stat(self.stat)

        # check if the dice total is under or equal to the stat value
        return self.dice.total <= stat_value and not self.dice.critical_failure

    @classmethod
    def resolve(cls, character: Character, stat: str) -> DiceCheck:
        """
        Resolve a dice check for a character's stat
        
        arguments:
            character: Character
                The character to check
            stat: str
                The stat to check
        returns:
            DiceCheck: The resolved dice check
        """
        # roll a d100 dice
        dice = Dice.roll("1d100")

        # create and return the DiceCheck object
        return cls(dice, character, stat)


# ----- DiceRatio class ----- #
class DiceRatio:
    """
    Dice ratio for damage calculation
    
    attributes:
        stat: str
            The stat linked to the ratio
        ratio: int
            The ratio value (in percentage)
    """
    def __init__(self, stat: str, ratio: int) -> None:
        self.stat = stat
        self.ratio = ratio

    def resolve(self, character: Character, dice: Optional[Dice]=None) -> int:
        """
        Resolve the dice ratio for a character
        
        arguments:
            character: Character
                The character to calculate the ratio for
            dice: Dice, optional
                The dice to use for the calculation (if needed)
                if no dice is given we roll a new one 1d100
        returns:
            int: The resolved ratio value
        """
        # get the character's stat value
        stat_value = character.get_current_stat(self.stat)

        # roll a d100 dice if no dice is given
        if dice is None:
            dice = Dice.roll("1d100")

        # calculate and return the ratio value
        result = (stat_value - dice.total) * self.ratio // 100
        logger.debug(f"[DiceRatio] Resolving ratio for stat '{self.stat}': "
                     f"stat_value={stat_value}, dice_total={dice.total}, "
                     f"ratio={self.ratio}, result={result}")
        return int(result)


# ----- DiceAttack class ----- #
class DiceAttack:
    """
    Dice attack for damage calculation
    
    attributes:
        user_ratio: DiceRatio
            The user's ratio
        target_ratio: DiceRatio
            The target's ratio
    """
    def __init__(self, user_ratio: DiceRatio, target_ratio: DiceRatio) -> None:
        self.user_ratio = user_ratio
        self.target_ratio = target_ratio
        logger.debug(f"[DiceAttack] Created with user_ratio '{user_ratio.stat}':"
                     f"{user_ratio.ratio}%, target_ratio '{target_ratio.stat}':"
                     f"{target_ratio.ratio}%")

    def resolve(self, user: Character,
                      target: Character,
                      user_dices: Optional[Dice]=None,
                      target_dices: Optional[Dice]=None) -> int:
        """
        Resolve the dice attack between a user and a target
        arguments:
            user: Character
                The character performing the attack
            target: Character
                The character being attacked
            user_dices: Dice, optional
                The dice to use for the user's ratio calculation (if needed)
                if no dice is given we roll a new one 1d100
            target_dices: Dice, optional
                The dice to use for the target's ratio calculation (if needed)
                if no dice is given we roll a new one 1d100
        returns:
            int: The resolved attack value
        """
        # resolve the user's ratio
        user_value = self.user_ratio.resolve(user, user_dices)
        # resolve the target's ratio
        target_value = self.target_ratio.resolve(target, target_dices)
        logger.debug(f"[DiceAttack] Resolving attack: user_value={user_value}, "
                     f"target_value={target_value}")
        return max(0, user_value - target_value)

    @classmethod
    def from_stats(cls, user_stat: str, user_ratio: int,
                        target_stat: str, target_ratio: int) -> DiceAttack:
        """
        Create a DiceAttack from stats and ratios
        
        arguments:
            user_stat: str
                The user's stat linked to the ratio
            user_ratio: int
                The user's ratio value (in percentage)
            target_stat: str
                The target's stat linked to the ratio
            target_ratio: int
                The target's ratio value (in percentage)
        
        returns:
            DiceAttack: The created DiceAttack object
        """
        user_dice_ratio = DiceRatio(user_stat, user_ratio)
        target_dice_ratio = DiceRatio(target_stat, target_ratio)
        return cls(user_dice_ratio, target_dice_ratio)
