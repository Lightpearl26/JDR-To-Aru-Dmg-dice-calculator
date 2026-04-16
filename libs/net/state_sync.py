# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import fields
from uuid import UUID, uuid4

from ..character import Entity
from ..spells.spell_def import Effect, Formula
from ..spells.spell_event import SpellEvent
from ..spells.spell_effect import SpellEffect


def serialize_entity_state(entity: Entity) -> dict[str, object]:
    """Construit un snapshot JSON-safe de l'etat utile a la fiche joueur."""
    stats_modifier = {
        f.name: int(getattr(entity.character.stats_modifier, f.name, 0))
        for f in fields(entity.character.stats_modifier)
    }

    inventory_items = {
        str(item_name): int(quantity)
        for item_name, quantity in entity.character.inventory.items.items()
    }

    spell_effects: list[dict[str, object]] = []
    for effect in entity.spell_effects:
        target_scope = "target"
        operator = "bonus" if effect.delta >= 0 else "malus"
        formula_expression = str(abs(effect.delta))
        try:
            target_scope = str(effect.effect_def.target[0])
            operator = str(effect.effect_def.operator)
            formula_expression = str(effect.effect_def.formula.expression)
        except Exception:
            pass

        spell_name = "UnknownSpell"
        caster_id = "UnknownCaster"
        if isinstance(effect.link_key, tuple) and len(effect.link_key) >= 2:
            spell_name = str(effect.link_key[0])
            caster_id = str(effect.link_key[1])

        spell_effects.append(
            {
                "uuid": str(effect.uuid),
                "target_id": str(effect.target_id),
                "target_stat": str(effect.target_stat),
                "delta": int(effect.delta),
                "spell_name": spell_name,
                "caster_id": caster_id,
                "target_scope": target_scope,
                "operator": operator,
                "formula": formula_expression,
            }
        )

    spell_events: list[dict[str, object]] = []
    for event in entity.spell_events:
        spell_events.append(
            {
                "spell_id": str(event.spell_id),
                "caster_id": str(event.caster_id),
                "targets_ids": [str(target_id) for target_id in event.targets_ids],
                "effects": [str(effect.uuid) for effect in event.effects],
                "runtime_policy": str(event.runtime_policy),
                "nb_cast": int(event.nb_cast),
                "finished": bool(event.finished),
            }
        )

    return {
        "entity_name": entity.name,
        "character_name": entity.character.name,
        "stats_modifier": stats_modifier,
        "inventory_items": inventory_items,
        "spell_effects": spell_effects,
        "spell_events": spell_events,
    }


def apply_entity_state(entity: Entity, payload: dict[str, object]) -> None:
    """Applique un snapshot de sync sur l'entite locale du joueur."""
    stats_modifier = payload.get("stats_modifier", {})
    if isinstance(stats_modifier, dict):
        for f in fields(entity.character.stats_modifier):
            try:
                setattr(entity.character.stats_modifier, f.name, int(stats_modifier.get(f.name, 0)))
            except (TypeError, ValueError):
                setattr(entity.character.stats_modifier, f.name, 0)

    inventory_items = payload.get("inventory_items", {})
    if isinstance(inventory_items, dict):
        entity.character.inventory.items = {
            str(item_name): int(quantity)
            for item_name, quantity in inventory_items.items()
            if isinstance(item_name, str)
        }
        entity.character.inventory._item_cache.clear()

    raw_effects = payload.get("spell_effects", [])
    new_effects: list[SpellEffect] = []
    if isinstance(raw_effects, list):
        for raw in raw_effects:
            if not isinstance(raw, dict):
                continue

            target_stat = str(raw.get("target_stat", "hp"))
            try:
                delta = int(raw.get("delta", 0))
            except (TypeError, ValueError):
                delta = 0

            target_scope = str(raw.get("target_scope", "target"))
            if target_scope not in {"target", "user"}:
                target_scope = "target"

            operator = str(raw.get("operator", "bonus" if delta >= 0 else "malus"))
            if operator not in {"bonus", "malus"}:
                operator = "bonus" if delta >= 0 else "malus"

            formula_expression = str(raw.get("formula", str(abs(delta))))
            formula = Formula(formula_expression)
            formula.compilate()
            effect_def = Effect(target=(target_scope, target_stat), operator=operator, formula=formula)

            raw_uuid = str(raw.get("uuid", ""))
            try:
                effect_uuid = UUID(raw_uuid)
            except (ValueError, TypeError):
                effect_uuid = uuid4()

            spell_name = str(raw.get("spell_name", "UnknownSpell"))
            caster_id = str(raw.get("caster_id", "UnknownCaster"))
            target_id = str(raw.get("target_id", entity.name))

            new_effects.append(
                SpellEffect(
                    uuid=effect_uuid,
                    effect_def=effect_def,
                    target_id=target_id,
                    target_stat=target_stat,
                    delta=delta,
                    link_key=(spell_name, caster_id),
                )
            )

    entity.spell_effects = new_effects

    # Reconstruit les SpellEvents apres les effets pour pouvoir relier les UUID.
    effect_by_uuid = {str(effect.uuid): effect for effect in new_effects}
    raw_events = payload.get("spell_events", [])
    new_events: list[SpellEvent] = []
    if isinstance(raw_events, list):
        for raw in raw_events:
            if not isinstance(raw, dict):
                continue

            spell_id = str(raw.get("spell_id", ""))
            caster_id = str(raw.get("caster_id", ""))
            targets_ids_raw = raw.get("targets_ids", [])
            effect_ids_raw = raw.get("effects", [])

            if not spell_id or not caster_id:
                continue

            targets_ids: list[str] = []
            if isinstance(targets_ids_raw, list):
                targets_ids = [str(target_id) for target_id in targets_ids_raw]

            effects: list[SpellEffect] = []
            if isinstance(effect_ids_raw, list):
                for effect_uuid in effect_ids_raw:
                    effect = effect_by_uuid.get(str(effect_uuid))
                    if effect is not None:
                        effects.append(effect)

            runtime_policy = str(raw.get("runtime_policy", "instant"))
            if runtime_policy not in {"instant", "maintain", "refresh", "delay"}:
                runtime_policy = "instant"

            try:
                nb_cast = int(raw.get("nb_cast", 0))
            except (TypeError, ValueError):
                nb_cast = 0

            finished_raw = raw.get("finished", False)
            if isinstance(finished_raw, bool):
                finished = finished_raw
            elif isinstance(finished_raw, str):
                finished = finished_raw.strip().lower() in {"1", "true", "yes", "on"}
            else:
                finished = bool(finished_raw)

            new_events.append(
                SpellEvent(
                    spell_id=spell_id,
                    caster_id=caster_id,
                    targets_ids=targets_ids,
                    effects=effects,
                    runtime_policy=runtime_policy,
                    nb_cast=nb_cast,
                    finished=finished,
                )
            )

    entity.spell_events = new_events
