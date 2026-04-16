#-*- coding: utf-8 -*-

"""
Spell event module.
"""

# import built-in modules
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

# import local modules
from .spell_effect import SpellEffect
from .spell_def import RuntimePolicy
from ..registry.spell import SpellRegistry
from ..registry.entity import EntityRegistry


# ----- SpellEvent definition -----
@dataclass
class SpellEvent:
    """
    Class representing a spell event, which is an instance of a spell being cast or maintained.
    """
    spell_id: str
    caster_id: str
    targets_ids: list[str]
    effects: list[SpellEffect]
    runtime_policy: RuntimePolicy
    nb_cast: int = 0
    finished: bool = False

    def apply(
                self,
                new_targets: list[str],
                user_dices: Optional[dict[str, int]]=None,
                targets_dices: Optional[dict[str, dict[str, int]]]=None
            ) -> None:
        """
        Apply the spell event effects to the targets.
        """
        if self.finished:
            return # Spell event is finished, do nothing
        spell = SpellRegistry.get(self.spell_id)
        if not spell:
            return # Spell not found, do nothing
        caster = EntityRegistry.get(self.caster_id)
        if not caster:
            return # Caster not found, do nothing
        self.targets_ids = new_targets

        self._purge_removed_targets()

        if self.runtime_policy == "instant":
            if self.nb_cast == 0:
                if not self._pay_cost(caster, spell.cost):
                    return
                self._create_effects_for_targets(caster, spell, user_dices, targets_dices)
            self.finished = True
            self.nb_cast += 1
        elif self.runtime_policy == "maintain":
            if self.nb_cast < spell.delay:
                if not self._pay_cost(caster, spell.cost):
                    return
                self._create_effects_for_targets(caster, spell, user_dices, targets_dices, only_new_targets=True)
            else:
                self.purge()
                self.finished = True
            self.nb_cast += 1
        elif self.runtime_policy == "refresh":
            if self.nb_cast < spell.delay:
                if not self._pay_cost(caster, spell.cost):
                    return
                self.purge()
                self._create_effects_for_targets(caster, spell, user_dices, targets_dices)
            else:
                self.purge()
                self.finished = True
            self.nb_cast += 1
        elif self.runtime_policy == "delay":
            if self.nb_cast == 0:
                if not self._pay_cost(caster, spell.cost):
                    return
            if self.nb_cast == spell.delay:
                self._create_effects_for_targets(caster, spell, user_dices, targets_dices)
                self.finished = True
            self.nb_cast += 1
        else:
            pass # Invalid runtime policy, do nothing

    def _pay_cost(self, caster, cost: int) -> bool:
        """
        Pay spell stamina cost once for the current apply call.
        """
        if caster.get_stat("stamina") < cost:
            return False
        caster.stats_modifiers.stamina -= cost
        return True

    def _purge_removed_targets(self) -> None:
        """
        Remove effects linked to targets that are no longer targeted.
        """
        for effect in self.effects[:]:
            if effect.link_key[1] in self.targets_ids:
                continue
            target = EntityRegistry.get(effect.target_id)
            if target:
                target.spell_effects = [e for e in target.spell_effects if e.uuid != effect.uuid]
            self.effects.remove(effect)

    def _create_effects_for_targets(
                self,
                caster,
                spell,
                user_dices: Optional[dict[str, int]]=None,
                targets_dices: Optional[dict[str, dict[str, int]]]=None,
                only_new_targets: bool=False
            ) -> None:
        """
        Create spell effects for current targets.
        """
        existing_target_ids = {effect.link_key[1] for effect in self.effects}
        for target_id in self.targets_ids:
            if only_new_targets and target_id in existing_target_ids:
                continue
            target = EntityRegistry.get(target_id)
            if not target:
                continue
            target_dice = targets_dices[target_id] if targets_dices and target_id in targets_dices else None
            for effect_def in spell.effects:
                delta = effect_def.formula.evaluate(caster, target, user_dices, target_dice)
                if delta < 0:
                    delta = 0
                op = -1 if effect_def.operator == "malus" else 1
                destination_id = self.caster_id if effect_def.target[0] == "user" else target_id
                destination = caster if effect_def.target[0] == "user" else target
                spell_effect = SpellEffect(
                    uuid=uuid4(),
                    effect_def=effect_def,
                    target_id=destination_id,
                    target_stat=effect_def.target[1],
                    delta=delta * op,
                    link_key=(self.caster_id, target_id)
                )
                self.effects.append(spell_effect)
                destination.spell_effects.append(spell_effect)

    def purge(self) -> None:
        """
        Purge the spell event effects from the targets.
        """
        for effect in self.effects:
            target = EntityRegistry.get(effect.target_id)
            if target:
                target.spell_effects = [e for e in target.spell_effects if e.uuid != effect.uuid]
        self.effects.clear()

    def stop(self) -> None:
        """
        Stop the spell event and purge its effects.
        """
        self.finished = True
        self.purge()
