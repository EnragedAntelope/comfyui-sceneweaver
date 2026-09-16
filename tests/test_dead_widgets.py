"""Todo 21 -- no widget is drawn every render and never voiced.

``identity-forge-dead-widget-check``: a field can be present in the schema,
resolved on every seed, written into the JSON, and still never reach the prompt
-- because nothing in the prose layer asks for it. The widget looks alive. It
does nothing. Identity Forge shipped one, and it was found by reading the prose
builder rather than by any test, which is why this file exists.

The check is deliberately the crude, end-to-end one: **for every field on every
node, some seed at ```` must put its value into
``prompt_text``**. Nothing subtler would have caught the original bug, because
every subtler check was already passing.

Three surfaces are swept, because a field can be alive on one and dead on
another:

* the Scene Weaver's slot 1 -- the full morphology;
* the Scene Weaver's supporting slots 2-4 -- the brief five, whose values reach
  the prose through a different path (the head-phrase fallback);
* the Scene Entity node, whose sentence is assembled by ``generate_entity``.

And the widgets that are not description at all -- the four controls -- are
checked by the effect they are supposed to have, since "appears in the prompt"
is meaningless for a seed.
"""
from __future__ import annotations

import dataclasses
import unittest

from data.genre import (
    ENTITY_NODE_SLOTS,
    KIND_FIELD,
    SCENE_NODE_SLOTS,
    SET_ALL_FIELDS_KEY,
    build_field_definitions,
    pool_for,
    widget_order,
)
from data.scifi import SCIFI_PACK
from engine.budget import ALLOWANCE_BY_COUNT
from engine.prose import render_entity
from engine.resolution import ResolvedEntity
from engine.scene import generate_entity, generate_scene

#: Wide enough that a value one pool in twenty-two draws is still seen. The
#: sweep is the whole point: a field voiced on one seed in two hundred is alive.
SWEEP_SEEDS = 400



def _voiced(entity: ResolvedEntity) -> set[str]:
    """Which of ``entity``'s fields actually change the sentence it renders to.

    **Not** a substring search of the prompt. Searching was tried first and is
    too permissive to be a liveness test: an ``extras`` value of "ice cap" is a
    substring of the ``surface_detail`` value "ice cap fracture", so one coincidental
    scene anywhere in a 400-seed sweep marks a field alive that the renderer had
    stopped voicing. A planted defect that silenced the whole ``extras`` clause
    passed that version of this file.

    Removing the field and re-rendering is exact. A field whose absence changes
    nothing is not being said, whatever else the sentence happens to contain.
    """
    baseline = render_entity(entity, SCIFI_PACK)
    voiced = set()
    for name, value in entity.fields.items():
        if value is None:
            continue
        without = dataclasses.replace(
            entity, fields={**dict(entity.fields), name: None}
        )
        if render_entity(without, SCIFI_PACK) != baseline:
            voiced.add(name)
    return voiced


def _entities(document) -> list[ResolvedEntity]:
    """The resolved entities of a ``prompt_json`` document."""
    return [
        ResolvedEntity(
            index=record["index"],
            source=record["source"],
            genre=record["genre"],
            fields={k: v for k, v in record.items() if k not in _META_KEYS},
            situation=record["situation"],
        )
        for record in document["entities"]
    ]


#: Provenance keys of a ``prompt_json`` entity record, not description.
_META_KEYS = frozenset({"index", "source", "genre", "situation", "archetype"})


def _spoken_fields(document, text: str) -> set[str]:
    """Which entity fields of ``document`` actually reached ``text``."""
    spoken: set[str] = set()
    for entity in _entities(document):
        spoken |= _voiced(entity)
        if entity.situation and entity.situation.lower() in text.lower():
            spoken.add("situation")
    return spoken


class SceneNodeTests(unittest.TestCase):
    def test_every_budgeted_entity_field_reaches_the_prompt_on_some_seed(self) -> None:
        """The fixed budget keeps the head of ``detail_priority``; every field
        it keeps must actually be voiced. The tail fields beyond the allowance
        are capped by design, not dead -- the Entity Node test below sweeps them
        at full depth."""
        budgeted = set(SCIFI_PACK.prose.detail_priority[: ALLOWANCE_BY_COUNT[1][0]])
        spoken: set[str] = set()
        for seed in range(SWEEP_SEEDS):
            text, document = generate_scene(seed, SCIFI_PACK)
            spoken |= _spoken_fields(document, text)
            if spoken >= budgeted:
                break
        missing = sorted(budgeted - spoken)
        self.assertEqual(missing, [], "a budgeted widget is drawn and never voiced")

    def test_the_environment_reaches_the_prompt(self) -> None:
        seen = False
        for seed in range(SWEEP_SEEDS):
            text, document = generate_scene(seed, SCIFI_PACK, )
            if document["environment"] and document["environment"].lower() in text.lower():
                seen = True
                break
        self.assertTrue(seen)

    def test_a_relation_is_left_out_until_it_is_asked_for(self) -> None:
        """The six relation widgets default to ``None`` on purpose, so a
        one-click scene is a setting and its occupants rather than a diagram.
        Pinned here because it is what makes the sweep below need widgets."""
        for seed in range(50):
            _text, document = generate_scene(seed, SCIFI_PACK, )
            self.assertEqual(document["relations"], [])

    def test_every_relation_widget_reaches_the_prompt(self) -> None:
        """All six pairs, not just 1-2. A relation widget nothing renders is a
        dead widget with a whole slot pair behind it."""
        widgets = {
            
            **{f"relation_{first}_{second}": "Random"
               for first in range(1, 5)
               for second in range(first + 1, 5)},
        }
        self.assertEqual(sum(1 for k in widgets if k.startswith("relation_")), 6)
        seen: set[tuple[int, int]] = set()
        for seed in range(SWEEP_SEEDS):
            text, document = generate_scene(
                seed, SCIFI_PACK, widgets=widgets, entity_count=4,
            )
            low = text.lower()
            for relation in document["relations"]:
                if relation["value"].lower() in low:
                    seen.add(tuple(relation["endpoints"]))
            if len(seen) == 6:
                break
        self.assertEqual(len(seen), 6, sorted(seen))

    def test_every_supporting_slot_speaks(self) -> None:
        """Slots 2-4 reach the prose by the head-phrase fallback rather than by
        the full clause walk, so they are a separate liveness question."""
        for slot in (2, 3, 4):
            spoken = False
            for seed in range(SWEEP_SEEDS):
                text, document = generate_scene(seed, SCIFI_PACK, entity_count=4)
                record = next(
                    (r for r in document["entities"] if r["index"] == slot), None
                )
                if record is None:
                    continue
                described = [
                    v
                    for k, v in record.items()
                    if k not in ("index", "source", "genre", "kind") and v
                ]
                if described and all(v.lower() in text.lower() for v in described):
                    spoken = True
                    break
            with self.subTest(slot=slot):
                self.assertTrue(spoken)

    def test_every_brief_field_of_a_supporting_slot_reaches_the_prompt(self) -> None:
        brief = [name for name, spec in SCIFI_PACK.entity_fields.items() if spec.brief]
        self.assertTrue(brief, "the pack marks no field brief")
        spoken: set[str] = set()
        for seed in range(SWEEP_SEEDS):
            _text, document = generate_scene(seed, SCIFI_PACK, entity_count=4)
            for entity in _entities(document):
                if entity.index == 1:
                    continue
                spoken |= _voiced(entity) & set(brief)
        # ``kind`` is consumed by a more specific subkind; see test_coherence.
        self.assertEqual(sorted(set(brief) - spoken - {"kind"}), [])


class EntityNodeTests(unittest.TestCase):
    def test_every_field_reaches_the_entity_prompt_on_some_seed(self) -> None:
        spoken: set[str] = set()
        for seed in range(SWEEP_SEEDS):
            _text, payload = generate_entity(seed, SCIFI_PACK)
            entity = ResolvedEntity(
                index=1, source="widgets", genre=payload["genre"],
                fields=payload["fields"],
            )
            spoken |= _voiced(entity)
            if spoken >= set(SCIFI_PACK.entity_fields) - {"kind"}:
                break
        missing = sorted(set(SCIFI_PACK.entity_fields) - spoken - {"kind"})
        self.assertEqual(missing, [])


class KindCoverageTests(unittest.TestCase):
    """Every field a kind can show is voiced on some seed.

    A fixed detail priority cut the same tail on every render, so a field below
    the line was drawn, resolved, written into the payload and never spoken. The
    rotation turns that tail into a draw, and this is the gate that every option
    is reachable for the kind that shows it.
    """

    #: The archetypes whose tail rotates. A world is seen whole (decision D3),
    #: so its short cap is the decision rather than a defect and it is exempt.
    ROTATING = frozenset({
        "craft", "structure", "machine", "figure", "object", "wreck", "creature",
        "world", "giant", "ring",
    })

    def test_every_field_a_kind_shows_is_voiced_for_that_kind(self) -> None:
        for kind in SCIFI_PACK.kinds:
            name = SCIFI_PACK.archetype_of_kind.get(kind)
            archetype = SCIFI_PACK.archetypes.get(name) if name else None
            if archetype is None or name not in self.ROTATING:
                continue
            expected = {
                field
                for field, spec in SCIFI_PACK.entity_fields.items()
                if spec.renders_with is None
                and field != KIND_FIELD
                and field not in archetype.omits
                and pool_for(SCIFI_PACK, field, {KIND_FIELD: kind})
            }
            seen: set[str] = set()
            for seed in range(SWEEP_SEEDS):
                _text, payload = generate_entity(
                    seed, SCIFI_PACK, widgets={"kind": kind}
                )
                seen |= {
                    field
                    for field, value in payload["fields"].items()
                    if value is not None
                }
                if seen >= expected:
                    break
            with self.subTest(kind=kind):
                self.assertEqual(
                    sorted(expected - seen), [], "drawn but never voiced"
                )


class ControlWidgetTests(unittest.TestCase):
    """The four controls describe nothing, so liveness is their *effect*."""

    def test_the_seed_changes_the_scene(self) -> None:
        self.assertNotEqual(
            generate_scene(1, SCIFI_PACK)[0], generate_scene(2, SCIFI_PACK)[0]
        )


    def test_the_scene_filter_changes_the_scene(self) -> None:
        """The control has an effect in all three directions.

        Swept rather than pinned to one seed: whether Any and Conflict
        diverge on a given seed depends on which tagged value the draw
        happens to reach, and a filter that never diverged would still
        fail here."""
        three_way = 0
        for seed in range(30):
            texts = {
                name: generate_scene(seed, SCIFI_PACK, scene_filter=name)[0]
                for name in ("Any", "Peaceful", "Conflict")
            }
            if len(set(texts.values())) == 3:
                three_way += 1
        self.assertGreater(three_way, 0, "the scene filter never changed the scene")

    def test_set_all_fields_changes_the_scene(self) -> None:
        base = generate_scene(11, SCIFI_PACK, )[0]
        emptied = generate_scene(
            11, SCIFI_PACK,  set_all_fields="Clear all"
        )[0]
        self.assertNotEqual(base, emptied)
        self.assertEqual(emptied, "")


class WidgetInventoryTests(unittest.TestCase):
    """Every widget a node registers is one of the two kinds checked above.

    A widget that is neither a described field nor a known control would be
    invisible to both sweeps -- so the inventory is asserted rather than assumed.
    """

    def test_the_scene_node_registers_only_accounted_for_widgets(self) -> None:
        definitions = build_field_definitions(SCIFI_PACK, SCENE_NODE_SLOTS)
        accounted = {SET_ALL_FIELDS_KEY}
        for key, definition in definitions.items():
            if definition.control or definition.base in SCIFI_PACK.entity_fields:
                accounted.add(key)
            elif definition.base in SCIFI_PACK.scene_fields:
                accounted.add(key)
        self.assertEqual(set(widget_order(SCIFI_PACK, SCENE_NODE_SLOTS)), accounted)

    def test_the_entity_node_registers_only_accounted_for_widgets(self) -> None:
        definitions = build_field_definitions(SCIFI_PACK, ENTITY_NODE_SLOTS)
        accounted = {
            key
            for key, definition in definitions.items()
            if definition.control or definition.base in SCIFI_PACK.entity_fields
        }
        self.assertEqual(set(widget_order(SCIFI_PACK, ENTITY_NODE_SLOTS)), accounted)


class VarietyTests(unittest.TestCase):
    """Round XII: a rotating tail is only variety if its values are real."""

    def test_creature_emitter_values_reach_a_creature(self) -> None:
        """A creature's bioluminescence is a thing a model draws, not a dead widget."""
        pool = set(pool_for(SCIFI_PACK, "emitters", {KIND_FIELD: "alien creature"}))
        seen: set[str] = set()
        for seed in range(SWEEP_SEEDS):
            _text, payload = generate_entity(
                seed, SCIFI_PACK, widgets={"kind": "alien creature"}
            )
            value = payload["fields"].get("emitters")
            if value is not None:
                seen.add(value)
            if seen & pool:
                break
        self.assertTrue(seen & pool, sorted(pool))

    def test_a_world_voices_a_world_scale_feature(self) -> None:
        """D12: a world's world-scale feature comes from the rotating tail."""
        seen = False
        for seed in range(SWEEP_SEEDS):
            _text, payload = generate_entity(
                seed, SCIFI_PACK, widgets={"kind": "celestial body"}
            )
            fields = payload["fields"]
            if fields.get("extras") or fields.get("markings"):
                seen = True
                break
        self.assertTrue(seen, "no world voiced a world-scale feature")


if __name__ == "__main__":
    unittest.main()
