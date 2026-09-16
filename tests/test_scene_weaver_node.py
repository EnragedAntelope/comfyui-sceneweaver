"""Todo 18 -- the ``Scene Weaver`` node class and its ``prompt_json`` contract.

``prompt_json`` is a published interface: the plan pins its exact shape, and
anything downstream of this node reads it. So the assertions here are
deliberately **exact** rather than "contains" -- an extra top-level key or a
renamed ``_meta`` entry is a breaking change that a subset check would wave
through, and the schema version would go on claiming 1.

The widget half is the same compatibility surface the Scene Entity suite
describes: 48 widgets in ``widget_order``, four link-only sockets appended after
them, and no reordering ever.
"""
from __future__ import annotations

import json
import unittest

from data import genre
from data.genre import NONE, RANDOM, SCENE_NODE_SLOTS, spoken_value
from data.scifi import SCIFI_PACK
from engine.scene import JSON_SCHEMA_VERSION
from nodes.scene_entity import SCENE_ENTITY_TYPE, build_entity_node
from nodes.scene_weaver import build_scene_node, entity_socket_key

NODE = build_scene_node(SCIFI_PACK)
ENTITY_NODE = build_entity_node(SCIFI_PACK)

#: Widget inputs carry a default; a link-only socket does not. Distinguishing
#: them structurally rather than by a name list means a widget added later is
#: counted as a widget without anyone remembering to update a list here.
def _is_widget(inp: object) -> bool:
    return hasattr(inp, "default")


def _run(**kwargs: object) -> tuple[str, dict]:
    text, payload = NODE.execute(**kwargs).args
    return text, json.loads(payload)


class SchemaShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = NODE.define_schema()
        self.widgets = [i for i in self.schema.inputs if _is_widget(i)]
        self.sockets = [i for i in self.schema.inputs if not _is_widget(i)]
        self.by_id = {i.id: i for i in self.schema.inputs}

    def test_input_counts(self) -> None:
        """55 widgets: 4 controls (seed, entity count, scene filter, bulk edit)
        + environment + slot 1's 21 + 3 brief slots of 5 + 4 situations
        + 6 relations + 6 positions + context. Plus four optional sockets."""
        self.assertEqual(len(self.widgets), 55)
        self.assertEqual(len(self.sockets), SCENE_NODE_SLOTS)
        self.assertEqual(len(self.schema.inputs), 59)

    def test_widget_order_matches_the_contract_exactly(self) -> None:
        self.assertEqual(
            [w.id for w in self.widgets],
            list(genre.widget_order(SCIFI_PACK, SCENE_NODE_SLOTS)),
        )

    def test_set_all_fields_sits_last_among_the_controls(self) -> None:
        """Its position is pinned even though it is not a FieldDef: it is a
        widget, so it occupies a ``widgets_values`` slot like any other and
        drifting one place would reassign every value after it."""
        ids = [w.id for w in self.widgets]
        self.assertEqual(
            ids[:5],
            ["seed", genre.ENTITY_COUNT_KEY, "scene_filter",
             genre.SET_ALL_FIELDS_KEY, genre.ENVIRONMENT_FIELD],
        )

    def test_slot_one_is_full_depth_and_the_others_are_brief(self) -> None:
        """The core node is never a stub, and supporting slots stay brief until
        something is wired into them."""
        for name in SCIFI_PACK.entity_fields:
            with self.subTest(field=name):
                self.assertIn(f"entity1_{name}", self.by_id)
        brief = {"kind", "subkind", "scale", "condition"}
        for slot in (2, 3, 4):
            present = {
                name
                for name in SCIFI_PACK.entity_fields
                if f"entity{slot}_{name}" in self.by_id
            }
            with self.subTest(slot=slot):
                self.assertEqual(present, brief)
                # Situation is scene-owned, so every slot carries one.
                self.assertIn(f"entity{slot}_situation", self.by_id)

    def test_six_relation_widgets_one_per_slot_pair(self) -> None:
        keys = [f"relation_{a}_{b}" for a, b in genre.relation_pairs(SCENE_NODE_SLOTS)]
        self.assertEqual(len(keys), 6)
        for key in keys:
            with self.subTest(relation=key):
                self.assertIn(key, self.by_id)
                # Session 3's closed decision: the widgets exist and are
                # full-random-capable, but six random relations between four
                # random entities reads as noise, so the user opts in.
                self.assertEqual(self.by_id[key].default, NONE)

    def test_the_sockets_are_optional_scene_entity_links(self) -> None:
        for slot in range(1, SCENE_NODE_SLOTS + 1):
            key = entity_socket_key(slot)
            with self.subTest(socket=key):
                socket = self.by_id[key]
                self.assertTrue(socket.optional)
                self.assertEqual(socket.io_type, SCENE_ENTITY_TYPE)
                # A link-only input has no widget, so it contributes nothing to
                # the positional widgets_values array.
                self.assertFalse(_is_widget(socket))

    def test_there_is_no_fifth_slot_anywhere(self) -> None:
        """Four slots is a structural fact, not a convention: no fifth socket,
        no fifth widget, and a constraint rule naming one is rejected."""
        self.assertNotIn(entity_socket_key(5), self.by_id)
        self.assertFalse([k for k in self.by_id if k.startswith("entity5")])
        self.assertNotIn(
            "entity5.kind", genre.constraint_address_space(SCIFI_PACK, SCENE_NODE_SLOTS)
        )

    def test_outputs(self) -> None:
        self.assertEqual(
            [o.display_name for o in self.schema.outputs], ["prompt_text", "prompt_json"]
        )


class PromptJsonSchemaTests(unittest.TestCase):
    """The exact document shape, asserted key-for-key."""

    def setUp(self) -> None:
        self.text, self.document = _run(seed=42)

    def test_top_level_keys_exactly(self) -> None:
        self.assertEqual(
            set(self.document), {"environment", "context", "entities", "relations", "_meta"}
        )

    def test_meta_keys_exactly_and_carries_the_seed(self) -> None:
        """The seed belongs here. Without it the document is not round-trippable
        and a scene cannot be reproduced from its own output."""
        meta = self.document["_meta"]
        self.assertEqual(
            set(meta),
            {
                "seed", "genre", "schema_version", "filter_applied",
                "overridden_fields", "warnings", "context_sentence_index",
                "redrawn_fields",
            },
        )
        self.assertEqual(meta["seed"], 42)
        self.assertEqual(meta["genre"], "scifi")
        self.assertEqual(meta["schema_version"], JSON_SCHEMA_VERSION)
        self.assertEqual(meta["filter_applied"], genre.DEFAULT_SCENE_FILTER)
        self.assertEqual(meta["overridden_fields"], [])

    def test_every_entity_record_carries_every_field_of_the_pack(self) -> None:
        expected = {"index", "source", "genre", "situation", "archetype", *SCIFI_PACK.entity_fields}
        for record in self.document["entities"]:
            with self.subTest(index=record.get("index")):
                self.assertEqual(set(record), expected)
                self.assertIn(record["source"], ("widgets", "wired"))
                self.assertEqual(record["genre"], "scifi")

    def test_relation_records(self) -> None:
        _, document = _run(seed=42, entity_count="2", entity1_kind=RANDOM, entity2_kind=RANDOM,
                            relation_1_2=RANDOM)
        self.assertTrue(document["relations"])
        for record in document["relations"]:
            self.assertEqual(set(record), {"endpoints", "value", "position"})
            self.assertEqual(len(record["endpoints"]), 2)
            self.assertIsInstance(record["value"], str)

    def test_the_document_is_json_and_the_text_is_prose(self) -> None:
        self.assertIsInstance(NODE.execute(seed=1).args[1], str)
        self.assertTrue(self.text.endswith("."))
        self.assertNotIn("{", self.text)


class GenerationTests(unittest.TestCase):
    def test_a_default_node_produces_a_full_random_scene_in_one_click(self) -> None:
        """The headline behaviour: no configuration, one entity, an
        environment, and no relations unless the user asks for one."""
        text, document = _run(seed=8)
        self.assertIsNotNone(document["environment"])
        self.assertEqual(len(document["entities"]), 1)
        self.assertEqual(document["relations"], [])
        self.assertTrue(text)

    def test_same_seed_reproduces(self) -> None:
        self.assertEqual(_run(seed=77)[0], _run(seed=77)[0])
        self.assertNotEqual(_run(seed=77)[0], _run(seed=78)[0])

    def test_a_slot_set_to_none_is_omitted_entirely(self) -> None:
        """Entity slots are 0-4: a pure-setting scene and a single-subject scene
        are both things a user can ask for."""
        _, document = _run(seed=8, entity2_kind=NONE, entity3_kind=NONE, entity4_kind=NONE)
        self.assertEqual([e["index"] for e in document["entities"]], [1])
        _, empty = _run(seed=8, **{f"entity{n}_kind": NONE for n in range(1, 5)})
        self.assertEqual(empty["entities"], [])
        self.assertIsNotNone(empty["environment"])

    def test_a_relation_needs_both_of_its_endpoints(self) -> None:
        _, document = _run(seed=8, relation_1_2="pursuing", entity2_kind=NONE)
        self.assertEqual(document["relations"], [])

    def test_peaceful_leaves_weapons_out_rather_than_negating_them(self) -> None:
        for seed in range(15):
            with self.subTest(seed=seed):
                text, document = _run(seed=seed, scene_filter="Peaceful")
                self.assertEqual(document["_meta"]["filter_applied"], "Peaceful")
                for record in document["entities"]:
                    self.assertIsNone(record["armament"])
                    self.assertIsNone(record["armament_count"])
                for word in (" no ", "without", "unarmed", "lacking"):
                    self.assertNotIn(word, text.lower())


    def test_a_budget_cut_field_is_null_in_the_json_too(self) -> None:
        """Never "resolved but not voiced": prompt_json and prompt_text can only
        ever agree about what the scene contains."""
        text, document = _run(seed=8, )
        for record in document["entities"]:
            for name, value in record.items():
                if name in ("index", "source", "genre", "archetype") or value is None:
                    continue
                if name == "kind" and record["subkind"] is not None:
                    # The one field the pack deliberately does not voice
                    # literally: the head-phrase ladder runs subkind then kind
                    # and consumes the loser unspoken, because "a strike
                    # carrier" already says "starship". It is still the control
                    # token every pool and label on the slot is scoped by, so it
                    # belongs in the JSON. With no subkind it *is* spoken --
                    # asserted below rather than skipped, so this exception
                    # cannot quietly widen.
                    continue
                with self.subTest(index=record["index"], field=name):
                    self.assertIn(spoken_value(SCIFI_PACK, name, value), text)

    def test_kind_is_spoken_when_no_subkind_outranks_it(self) -> None:
        text, document = _run(seed=8, entity1_subkind=NONE, entity1_kind="starship")
        self.assertIsNone(document["entities"][0]["subkind"])
        self.assertIn("starship", text)

    def test_a_locked_field_survives_the_tightest_budget(self) -> None:
        text, document = _run(
            seed=8,  entity1_markings="hazard chevrons"
        )
        slot1 = document["entities"][0]
        self.assertEqual(slot1["markings"], "hazard chevrons")
        self.assertIn("hazard chevrons", text)

    def test_set_all_fields_never_touches_a_locked_widget(self) -> None:
        _, document = _run(
            seed=8,
            set_all_fields="Clear all",
            entity1_kind="starship",
            entity1_form="needle hull",
        )
        self.assertEqual(len(document["entities"]), 1)
        slot1 = document["entities"][0]
        self.assertEqual(slot1["kind"], "starship")
        self.assertEqual(slot1["form"], "needle hull")
        self.assertIsNone(slot1["material"])

    def test_set_all_to_random_undoes_a_node_of_nones(self) -> None:
        """The bulk edit rewrites *fields*, never the generation controls.

        ``entity_count`` is passed explicitly here because it is a control:
        "Randomize all" must not silently decide how many subjects the scene
        has, any more than it may reroll the seed.
        """
        nones = {d.key: NONE for d in _descriptive_defs()}
        _, document = _run(
            seed=8, set_all_fields="Randomize all",
            entity_count=str(SCENE_NODE_SLOTS), **nones,
        )
        self.assertEqual(len(document["entities"]), SCENE_NODE_SLOTS)


def _descriptive_defs() -> list:
    return [
        d
        for d in genre.build_field_definitions(SCIFI_PACK, SCENE_NODE_SLOTS).values()
        if not d.control
    ]


class WiredEntityTests(unittest.TestCase):
    def test_a_wire_promotes_a_brief_slot_to_full_depth(self) -> None:
        _, payload = ENTITY_NODE.execute(seed=3, kind="alien creature").args
        _, document = _run(seed=8, **{entity_socket_key(3): payload})
        slot3 = next(e for e in document["entities"] if e["index"] == 3)
        self.assertEqual(slot3["source"], "wired")
        self.assertEqual(slot3["kind"], "alien creature")
        # Slot 3 carries no `form` widget at all; the wire supplied one.
        self.assertIsNotNone(slot3["form"])

    def test_the_scene_still_owns_what_a_wired_entity_is_doing(self) -> None:
        _, payload = ENTITY_NODE.execute(seed=3, kind="starship").args
        _, document = _run(
            seed=8,
            entity2_situation="running silent with every system dark",
            **{entity_socket_key(2): payload},
        )
        slot2 = next(e for e in document["entities"] if e["index"] == 2)
        self.assertEqual(
            slot2["situation"], "running silent with every system dark"
        )

    def test_a_wire_beats_a_locked_widget_and_says_so(self) -> None:
        _, payload = ENTITY_NODE.execute(seed=3, kind="starship").args
        with self.assertLogs("sceneweaver", level="WARNING"):
            _, document = _run(
                seed=8,
                entity2_kind="alien creature",
                **{entity_socket_key(2): payload},
            )
        slot2 = next(e for e in document["entities"] if e["index"] == 2)
        self.assertEqual(slot2["kind"], "starship")
        self.assertIn("entity2_kind", document["_meta"]["overridden_fields"])
        self.assertTrue(document["_meta"]["warnings"])

    def test_a_foreign_genre_entity_keeps_its_own_tag(self) -> None:
        """A crashed starship in an enchanted forest is a supported feature. The
        scene supplies environment, situation and relations; the entity brings
        its own description and its own genre tag."""
        payload = {
            "schema_version": 1,
            "genre": "fantasy",
            "fields": {"kind": "starship", "form": "needle hull"},
        }
        _, document = _run(seed=8, **{entity_socket_key(1): payload})
        slot1 = document["entities"][0]
        self.assertEqual(slot1["genre"], "fantasy")
        self.assertEqual(slot1["form"], "needle hull")

    def test_an_unwired_socket_changes_nothing(self) -> None:
        self.assertEqual(_run(seed=8)[0], _run(seed=8, entity_1_in=None)[0])

    def test_a_payload_of_the_wrong_shape_is_loud(self) -> None:
        with self.assertRaises(ValueError):
            NODE.execute(seed=8, entity_1_in="not a payload")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
