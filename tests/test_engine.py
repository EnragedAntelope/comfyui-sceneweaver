"""Todo 16 -- ``generate_scene``, end to end.

The four gates the plan names for this todo, each with a test that would fail if
the behaviour regressed rather than one that merely exercises it:

* same seed + same data yields identical prose;
* ``Peaceful`` over 500 seeds yields zero conflict-tagged values;
* a constraint cycle terminates at the pass cap with no hang;
* ``prompt_text`` stays under each level's token ceiling over a 500-seed sweep.

Plus the precedence rules, which are behaviour a user meets and therefore
behaviour a test has to pin: a wired entity beats a locked widget, and a locked
value beats a constraint.
"""
from __future__ import annotations

import json
import unittest

from data.genre import (
    NONE,
    RANDOM,
    SET_ALL_CLEAR,
    SET_ALL_RANDOMIZE,
    ConstraintRule,
    FieldSpec,
    GenrePack,
    HeadPhrase,
    ProseSpec,
    affordances_of,
    spoken_value,
    tag_for,
)
from data.genre import TAG_CONFLICT_ONLY, TAG_PEACEFUL_ONLY
from data.scifi import SCIFI_PACK
from engine.budget import TOKEN_CEILING, count_tokens
from engine.grammar import pluralize
from engine.scene import (
    JSON_SCHEMA_VERSION,
    MAX_CONSTRAINT_PASSES,
    SOURCE_WIDGETS,
    SOURCE_WIRED,
    entity_payload,
    generate_entity,
    generate_scene,
    scene_json_text,
)

SWEEP_SEEDS = 500

#: Where the engine logs its precedence decisions. Tests that deliberately
#: trigger one capture it rather than letting it reach stderr -- which asserts
#: the logging actually happens, and keeps the gate output readable.
LOG = "sceneweaver"


def scene(seed: int, **kwargs):
    return generate_scene(seed, SCIFI_PACK, **kwargs)


class DeterminismTests(unittest.TestCase):
    def test_the_same_seed_reproduces_the_same_scene(self) -> None:
        for seed in (0, 1, 42, 99991):
            with self.subTest(seed=seed):
                first_text, first_json = scene(seed)
                second_text, second_json = scene(seed)
                self.assertEqual(first_text, second_text)
                self.assertEqual(first_json, second_json)

    def test_different_seeds_produce_different_scenes(self) -> None:
        """Guards the test above against passing because everything is constant."""
        texts = {scene(seed)[0] for seed in range(20)}
        self.assertGreater(len(texts), 15)

    def test_every_seed_in_a_sweep_produces_a_scene(self) -> None:
        for seed in range(SWEEP_SEEDS):
            text, document = scene(seed)
            with self.subTest(seed=seed):
                self.assertTrue(text)
                self.assertTrue(document["entities"])


class JsonSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text, self.document = scene(7, )

    def test_the_top_level_shape(self) -> None:
        self.assertEqual(
            set(self.document), {"environment", "context", "entities", "relations", "_meta"}
        )

    def test_the_meta_block(self) -> None:
        meta = self.document["_meta"]
        self.assertEqual(
            set(meta),
            {"seed", "genre", "schema_version", "filter_applied",
             "overridden_fields", "warnings", "context_sentence_index",
             "redrawn_fields"},
        )
        self.assertEqual(meta["seed"], 7)
        self.assertEqual(meta["genre"], "scifi")
        self.assertEqual(meta["schema_version"], JSON_SCHEMA_VERSION)
        self.assertEqual(meta["filter_applied"], "Any")

    def test_an_entity_carries_every_field_plus_its_provenance(self) -> None:
        expected = {"index", "source", "genre", "situation", "archetype", *SCIFI_PACK.entity_fields}
        for record in self.document["entities"]:
            with self.subTest(index=record["index"]):
                self.assertEqual(set(record), expected)
                self.assertIn(record["source"], (SOURCE_WIDGETS, SOURCE_WIRED))
                self.assertEqual(record["genre"], "scifi")

    def test_a_relation_names_its_endpoints(self) -> None:
        for record in self.document["relations"]:
            with self.subTest(record=record):
                self.assertEqual(set(record), {"endpoints", "value"})
                self.assertEqual(len(record["endpoints"]), 2)

    def test_the_document_serializes(self) -> None:
        self.assertEqual(json.loads(scene_json_text(self.document)), self.document)


class OmissionTests(unittest.TestCase):
    def test_the_default_scene_is_one_entity(self) -> None:
        """Slots 2-4 default to None: an untouched node is one entity."""
        _, document = scene(3)
        self.assertEqual([e["index"] for e in document["entities"]], [1])

    def test_a_wired_entity_populates_a_slot_whose_kind_widget_is_none(self) -> None:
        """A wire supplies the slot's kind, so a Scene Entity wired into a
        slot whose own kind widget defaults to None still appears (todo 6)."""
        for slot in (2, 3, 4):
            _, payload = generate_entity(7 + slot, SCIFI_PACK)
            _, document = scene(7, wired_entities={slot: payload})
            record = next((e for e in document["entities"] if e["index"] == slot), None)
            with self.subTest(slot=slot):
                self.assertIsNotNone(record)
                self.assertEqual(record["source"], SOURCE_WIRED)
                self.assertIsNotNone(record["kind"])

    def test_zero_entities_still_renders_the_setting(self) -> None:
        widgets = {f"entity{slot}_kind": NONE for slot in range(1, 5)}
        text, document = scene(3, widgets=widgets)
        self.assertEqual(document["entities"], [])
        self.assertTrue(text.endswith("."))
        self.assertEqual(text.count("."), 1)

    def test_one_through_four_entities_all_compose(self) -> None:
        """The Entities control is what fills slots; the widgets only say what
        may go in them."""
        for count in (1, 2, 3, 4):
            _, document = scene(5, entity_count=count)
            with self.subTest(count=count):
                self.assertEqual(len(document["entities"]), count)
                self.assertEqual(
                    [e["index"] for e in document["entities"]],
                    list(range(1, count + 1)),
                )

    def test_a_slot_named_past_the_count_still_appears(self) -> None:
        """A locked kind is an explicit statement and outranks the count.

        Dropping it would be the same defect as a widget quietly overriding a
        wire -- naming a subject is more specific than saying how many there
        are, so the count clamps rather than commands.
        """
        _, document = scene(5, entity_count=1, widgets={"entity3_kind": "starship"})
        indexes = [e["index"] for e in document["entities"]]
        self.assertEqual(indexes, [1, 3])

    def test_a_relation_to_an_omitted_slot_is_dropped(self) -> None:
        _, document = scene(
            3,
            entity_count=1,
            widgets={"entity3_kind": "starship", "relation_1_2": "pursuing",
                     "relation_1_3": "observing"},
        )
        endpoints = [tuple(r["endpoints"]) for r in document["relations"]]
        self.assertNotIn((1, 2), endpoints)
        self.assertIn((1, 3), endpoints)

    def test_an_absent_field_is_null_and_never_negated(self) -> None:
        text, document = scene(4, widgets={"entity1_armament": NONE}, )
        self.assertIsNone(document["entities"][0]["armament"])
        for word in (" no ", "without", "lacking", "unarmed", "absent", "devoid"):
            with self.subTest(word=word):
                self.assertNotIn(word, f" {text.lower()} ")


class SetAllFieldsTests(unittest.TestCase):
    def test_all_to_none_empties_the_scene(self) -> None:
        text, document = scene(9, set_all_fields=SET_ALL_CLEAR)
        self.assertEqual(text, "")
        self.assertEqual(document["entities"], [])
        self.assertIsNone(document["environment"])

    def test_all_to_random_fills_a_scene_that_was_all_none(self) -> None:
        definitions_none = {"environment": NONE, "entity1_kind": NONE}
        text, _ = scene(9, widgets=definitions_none, set_all_fields=SET_ALL_RANDOMIZE)
        self.assertTrue(text)

    def test_a_bulk_edit_never_touches_a_locked_field(self) -> None:
        """A lock is a deliberate choice; a bulk control that silently undid one
        would be the "widgets keep saying Random while the node behaves
        differently" failure the plan calls out."""
        _, document = scene(
            9,
            widgets={"entity1_kind": "starship", "entity1_subkind": "salvage tug"},
            set_all_fields=SET_ALL_CLEAR,
        )
        self.assertEqual(len(document["entities"]), 1)
        self.assertEqual(document["entities"][0]["kind"], "starship")
        self.assertEqual(document["entities"][0]["subkind"], "salvage tug")

    def test_an_unknown_bulk_option_is_rejected_by_name(self) -> None:
        with self.assertRaises(ValueError):
            scene(1, set_all_fields="All to Chaos")


class WiredEntityTests(unittest.TestCase):
    def _payload(self, **fields):
        base = {name: None for name in SCIFI_PACK.entity_fields}
        base.update(fields)
        # Every field supplied here stands for a value the user *chose* on the
        # Entity node, so it is marked locked. A drawn value is tested apart.
        return entity_payload("scifi", base, fields)

    def test_a_wired_entity_supplies_its_slot(self) -> None:
        payload = self._payload(kind="alien creature", subkind="insectoid",
                                form="hexapodal frame")
        text, document = scene(2, wired_entities={2: payload})
        record = next(e for e in document["entities"] if e["index"] == 2)
        self.assertEqual(record["source"], SOURCE_WIRED)
        self.assertEqual(record["form"], "hexapodal frame")
        self.assertIn("hexapodal frame", text)

    def test_a_wired_entity_beats_a_locked_slot_widget_and_says_so(self) -> None:
        """The documented precedence. A widget quietly overriding the node the
        user visibly connected would be the worse of the two surprises."""
        payload = self._payload(kind="alien creature", subkind="insectoid")
        with self.assertLogs(LOG, "WARNING") as captured:
            _, document = scene(
                2,
                widgets={"entity2_kind": "starship", "entity2_subkind": "courier"},
                wired_entities={2: payload},
            )
        self.assertTrue(any("wired Scene Entity" in m for m in captured.output))
        record = next(e for e in document["entities"] if e["index"] == 2)
        self.assertEqual(record["kind"], "alien creature")
        self.assertIn("entity2_kind", document["_meta"]["overridden_fields"])
        self.assertIn("entity2_subkind", document["_meta"]["overridden_fields"])
        self.assertTrue(
            any("wired Scene Entity replaced" in w for w in document["_meta"]["warnings"])
        )

    def test_the_scene_keeps_the_situation_of_a_wired_slot(self) -> None:
        """The entity node owns what a thing *is*; the scene node owns what it
        is *doing*."""
        payload = self._payload(kind="starship", subkind="courier")
        _, document = scene(2, wired_entities={2: payload})
        record = next(e for e in document["entities"] if e["index"] == 2)
        self.assertIsNotNone(record["situation"])

    def test_a_wired_slot_is_described_at_full_depth(self) -> None:
        payload = self._payload(
            kind="starship", subkind="courier", form="needle hull",
            material="titanium alloy", emitters="ion thruster", emitter_count="six",
        )
        _, document = scene(2, wired_entities={2: payload}, )
        record = next(e for e in document["entities"] if e["index"] == 2)
        self.assertEqual(record["form"], "needle hull")
        self.assertEqual(record["emitters"], "ion thruster")

    def test_a_foreign_genre_entity_keeps_its_own_tag(self) -> None:
        payload = entity_payload("fantasy", {"kind": "starship", "subkind": "courier"})
        _, document = scene(2, wired_entities={2: payload})
        record = next(e for e in document["entities"] if e["index"] == 2)
        self.assertEqual(record["genre"], "fantasy")

    def test_a_payload_field_this_pack_does_not_know_is_dropped(self) -> None:
        payload = entity_payload("fantasy", {"kind": "starship", "enchantment": "frost"})
        _, document = scene(2, wired_entities={2: payload})
        record = next(e for e in document["entities"] if e["index"] == 2)
        self.assertNotIn("enchantment", record)

    def test_a_fifth_slot_is_rejected_rather_than_silently_dropped(self) -> None:
        payload = self._payload(kind="starship")
        with self.assertLogs(LOG, "WARNING"):
            _, document = scene(2, wired_entities={5: payload})
        self.assertLessEqual(len(document["entities"]), 4)
        self.assertTrue(
            any("slot 5" in w for w in document["_meta"]["warnings"]),
            document["_meta"]["warnings"],
        )

    def test_a_drawn_wired_value_is_redrawn_to_fit_the_place(self) -> None:
        """A value the Entity node DREW is a draw, not a choice: the host
        re-draws it when the place cannot hold it. Before the fix every wired
        field was force-locked, so a walker was drawn in vacuum."""
        base = {name: None for name in SCIFI_PACK.entity_fields}
        base.update(kind="alien creature", form="hexapodal frame")
        payload = entity_payload("scifi", base)  # nothing chosen
        _, document = scene(
            2,
            widgets={"environment": "deep interstellar void"},
            wired_entities={1: payload},
            entity_count=1,
        )
        record = next(e for e in document["entities"] if e["index"] == 1)
        form = record["form"]
        self.assertNotEqual(form, "hexapodal frame")
        stances = SCIFI_PACK.value_stances["form"].get(form)
        if form is not None and stances:
            supported: set[str] = set()
            for affordance in affordances_of(SCIFI_PACK, "deep interstellar void"):
                supported |= set(SCIFI_PACK.place_stances.get(affordance, ()))
            self.assertTrue(stances & supported, form)

    def test_a_payload_with_no_locked_key_locks_nothing(self) -> None:
        """Back-compat: an older saved graph, or a foreign-genre node, has no
        ``locked`` key. Nothing is locked, so rules apply to all of it."""
        base = {name: None for name in SCIFI_PACK.entity_fields}
        base.update(kind="alien creature", form="hexapodal frame")
        payload = {"schema_version": 1, "genre": "scifi", "fields": base}
        _, document = scene(
            2,
            widgets={"environment": "deep interstellar void"},
            wired_entities={1: payload},
            entity_count=1,
        )
        record = next(e for e in document["entities"] if e["index"] == 1)
        self.assertNotEqual(record["form"], "hexapodal frame")

    def test_a_chosen_wired_value_is_kept_and_warns(self) -> None:
        """A field the user locked on the Entity node is a choice: it beats
        the rule and the rule's reason is reported."""
        base = {name: None for name in SCIFI_PACK.entity_fields}
        base.update(kind="alien creature", form="hexapodal frame")
        payload = entity_payload("scifi", base, ("form",))
        _, document = scene(
            2,
            widgets={"environment": "deep interstellar void"},
            wired_entities={1: payload},
            entity_count=1,
        )
        record = next(e for e in document["entities"] if e["index"] == 1)
        self.assertEqual(record["form"], "hexapodal frame")
        self.assertTrue(
            any(
                "entity1.form" in w and "kept the locked value" in w
                for w in document["_meta"]["warnings"]
            ),
            document["_meta"]["warnings"],
        )

    def test_entity_payload_records_only_the_chosen_fields(self) -> None:
        payload = entity_payload(
            "scifi", {"kind": "starship", "form": "needle hull"}, ("form",)
        )
        self.assertEqual(payload["locked"], ["form"])
        self.assertEqual(payload["fields"]["kind"], "starship")

    def test_entity_payload_locks_nothing_by_default(self) -> None:
        payload = entity_payload("scifi", {"kind": "starship", "form": "needle hull"})
        self.assertEqual(payload["locked"], [])


class SceneFilterTests(unittest.TestCase):
    TAGGED = tuple(
        name
        for name, spec in SCIFI_PACK.entity_fields.items()
        if spec.tag_scoped
    ) + ("situation",)

    def _offenders(self, document: dict, banned: str) -> list[str]:
        found = []
        for record in document["entities"]:
            for field in self.TAGGED:
                value = record.get(field)
                if value is not None and tag_for(SCIFI_PACK, field, value) == banned:
                    found.append(f"entity{record['index']}.{field}={value!r}")
        for record in document["relations"]:
            if tag_for(SCIFI_PACK, "relation", record["value"]) == banned:
                found.append(f"relation={record['value']!r}")
        return found

    def test_peaceful_draws_no_conflict_value_across_the_sweep(self) -> None:
        offenders: list[str] = []
        for seed in range(SWEEP_SEEDS):
            _, document = generate_scene(
                seed, SCIFI_PACK, scene_filter="Peaceful", 
                widgets={f"relation_{a}_{b}": RANDOM
                         for a, b in ((1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4))},
            )
            offenders.extend(self._offenders(document, TAG_CONFLICT_ONLY))
        self.assertEqual(offenders[:10], [])

    def test_conflict_draws_no_peaceful_only_value_across_the_sweep(self) -> None:
        offenders: list[str] = []
        for seed in range(SWEEP_SEEDS):
            _, document = generate_scene(
                seed, SCIFI_PACK, scene_filter="Conflict",             )
            offenders.extend(self._offenders(document, TAG_PEACEFUL_ONLY))
        self.assertEqual(offenders[:10], [])

    def test_peaceful_omits_weapons_rather_than_denying_them(self) -> None:
        for seed in range(50):
            text, document = generate_scene(
                seed, SCIFI_PACK, scene_filter="Peaceful",             )
            with self.subTest(seed=seed):
                for record in document["entities"]:
                    self.assertIsNone(record["armament"])
                    self.assertIsNone(record["armament_count"])
                self.assertNotIn("unarmed", text)
                self.assertNotIn(" no weapon", text)

    def test_a_locked_conflict_value_survives_peaceful_with_a_warning(self) -> None:
        """The filter masks pools; it never overrules a value the user named."""
        with self.assertLogs(LOG, "WARNING"):
            _, document = scene(
                1,
                widgets={"entity1_kind": "starship", "entity1_armament": "spinal railgun"},
                scene_filter="Peaceful",
            )
        self.assertEqual(document["entities"][0]["armament"], "spinal railgun")
        self.assertTrue(
            any("would otherwise have masked" in w for w in document["_meta"]["warnings"]),
            document["_meta"]["warnings"],
        )

    def test_an_unknown_filter_is_rejected_by_name(self) -> None:
        with self.assertRaises(ValueError):
            scene(1, scene_filter="Tense")


class ConstraintTests(unittest.TestCase):
    def _cyclic_pack(self) -> GenrePack:
        """Two fields that forbid each other's every value, in a closed loop.

        There is no fixed point, so the pass cap is the only thing that ends it.
        A rule set like this is a data defect -- the point of the test is that it
        is a *reported* defect and not a hung queue.
        """
        return GenrePack(
            slug="cycle",
            display="Cycle",
            class_suffix="Cycle",
            kinds=("thing",),
            entity_fields={
                "kind": FieldSpec(group="I", label="Kind"),
                "alpha": FieldSpec(group="I", label="Alpha"),
                "beta": FieldSpec(group="I", label="Beta"),
            },
            scene_fields={
                "environment": FieldSpec(group="S", label="E"),
                "situation": FieldSpec(group="S", label="S"),
                "relation": FieldSpec(group="R", label="R"),
                "relation_position": FieldSpec(group="R", label="Position"),
            },
            pools={
                "kind": {"_default": ("thing",)},
                "alpha": {"_default": ("a1", "a2")},
                "beta": {"_default": ("b1", "b2")},
                "environment": {"_default": ("nowhere",)},
                "situation": {"_default": ("waiting",)},
                "relation": {"_default": ("beside",)},
            },
            constraints=(
                ConstraintRule(type="exclude", field="entity*.alpha", value="a1",
                               excludes_field="entity*.beta", excludes_values=("b1",),
                               reason="a1 forbids b1"),
                ConstraintRule(type="exclude", field="entity*.beta", value="b2",
                               excludes_field="entity*.alpha", excludes_values=("a1",),
                               reason="b2 forbids a1"),
                ConstraintRule(type="exclude", field="entity*.alpha", value="a2",
                               excludes_field="entity*.beta", excludes_values=("b2",),
                               reason="a2 forbids b2"),
                ConstraintRule(type="exclude", field="entity*.beta", value="b1",
                               excludes_field="entity*.alpha", excludes_values=("a2",),
                               reason="b1 forbids a2"),
            ),
            prose=ProseSpec(
                scene_order=("environment", "entities", "relations"),
                entity_clause_order=("kind", "alpha", "beta"),
            ),
        )

    def test_a_cycle_terminates_at_the_cap_and_reports_itself(self) -> None:
        with self.assertLogs(LOG, "WARNING"):
            _, document = generate_scene(1, self._cyclic_pack(), )
        self.assertTrue(
            any(f"within {MAX_CONSTRAINT_PASSES} passes" in w
                for w in document["_meta"]["warnings"]),
            document["_meta"]["warnings"],
        )

    def test_a_cycle_still_produces_a_usable_scene(self) -> None:
        with self.assertLogs(LOG, "WARNING"):
            text, document = generate_scene(1, self._cyclic_pack(), )
        self.assertTrue(text)
        self.assertTrue(document["entities"])

    def test_the_shipped_rule_set_settles_well_inside_the_cap(self) -> None:
        for seed in range(200):
            _, document = scene(seed, )
            with self.subTest(seed=seed):
                self.assertFalse(
                    [w for w in document["_meta"]["warnings"] if "passes" in w],
                    document["_meta"]["warnings"],
                )

    def test_a_constraint_moves_an_unlocked_field(self) -> None:
        """An interior cannot hold a colossal thing: the scale rule re-draws it."""
        from data.scifi import ENVIRONMENT_BANDS

        interior = ENVIRONMENT_BANDS["interior"][0]
        seen = 0
        for seed in range(120):
            _, document = scene(
                seed,
                widgets={"environment": interior, "entity1_scale": RANDOM},
            )
            for entity in document["entities"]:
                seen += 1
                with self.subTest(seed=seed):
                    self.assertNotIn(entity["scale"], ("colossal", "planetary"))
        self.assertGreater(seen, 0, "no entity was ever generated")

    def test_a_locked_value_beats_a_constraint_and_reports_the_reason(self) -> None:
        from data.scifi import ENVIRONMENT_BANDS

        with self.assertLogs(LOG, "WARNING"):
            _, document = scene(
                1,
                widgets={"entity1_scale": "colossal",
                         "environment": ENVIRONMENT_BANDS["interior"][0]},
            )
        self.assertEqual(document["environment"], ENVIRONMENT_BANDS["interior"][0])
        self.assertTrue(
            any("kept the locked value" in w for w in document["_meta"]["warnings"]),
            document["_meta"]["warnings"],
        )

    def test_a_constraint_reason_never_reaches_the_prompt(self) -> None:
        """A reason is the one deliberate exemption from never-negate. It is
        warning text; letting it into prompt_text would put "cannot contain"
        in front of the model."""
        from data.scifi import ENVIRONMENT_BANDS

        with self.assertLogs(LOG, "WARNING"):
            text, document = scene(
                1,
                widgets={"entity1_scale": "colossal",
                         "environment": ENVIRONMENT_BANDS["interior"][0]},
            )
        for warning in document["_meta"]["warnings"]:
            for fragment in ("is not", "no ", "cannot"):
                if fragment in warning:
                    self.assertNotIn(warning, text)


class TokenCeilingTests(unittest.TestCase):
    def test_the_scene_stays_under_the_ceiling_across_the_sweep(self) -> None:
        worst = 0
        for seed in range(1000):
            text, _ = scene(seed)
            worst = max(worst, count_tokens(text))
        self.assertLess(worst, TOKEN_CEILING, f"peaked at {worst}")

    def test_four_wired_entities_stay_under_the_ceiling_too(self) -> None:
        """The worst case a user can actually build, and the one the ceiling
        was measured against.

        Each slot is wired with a **real, fully-populated** entity from
        ``generate_entity``. An earlier version of this test wired an all-``None``
        payload, which describes nothing: it measured 54 tokens and so never
        noticed that ``generate_scene`` was marking wired fields budget-locked
        and letting four wired entities render at full depth. A worst-case test
        that is not the worst case is not a test.
        """
        worst = 0
        for seed in range(100):
            wired = {
                slot: generate_entity(seed * 10 + slot, SCIFI_PACK)[1]
                for slot in range(1, 5)
            }
            text, _ = scene(seed, wired_entities=wired)
            worst = max(worst, count_tokens(text))
        self.assertLess(worst, TOKEN_CEILING, f"peaked at {worst}")

    def test_a_wired_slot_is_richer_than_an_unwired_one(self) -> None:
        """The promotion, end to end: slot 3 wired reads as fully as slot 1."""
        spoken = 0
        tapered = 0
        for seed in range(60):
            payload = generate_entity(seed, SCIFI_PACK)[1]
            _, wired_doc = scene(seed, wired_entities={3: payload})
            _, plain_doc = scene(seed)
            for document, bucket in ((wired_doc, "wired"), (plain_doc, "plain")):
                record = next(
                    (r for r in document["entities"] if r["index"] == 3), None
                )
                if record is None:
                    continue
                described = sum(
                    1 for name in SCIFI_PACK.entity_fields if record.get(name)
                )
                if bucket == "wired":
                    spoken += described
                else:
                    tapered += described
        self.assertGreater(spoken, tapered)


class BudgetHonestyTests(unittest.TestCase):
    """A budget-cut field is ``None`` in ``prompt_json`` too -- across a sweep,
    because "resolved but not voiced" is the kind of bug that hides in one seed.
    """

    def test_every_json_value_appears_in_the_prose(self) -> None:
        skip = {"kind"}  # the head noun gives way to a more specific subkind
        for seed in range(200):
            text, document = scene(seed, )
            lowered = text.lower()
            for record in document["entities"]:
                for name in SCIFI_PACK.entity_fields:
                    value = record.get(name)
                    if value is None or name in skip:
                        continue
                    # A count-partnered noun with no count is voiced as a bare
                    # plural ("missile batteries"), so the inflected form counts
                    # as spoken. The engine's own pluralizer is the authority,
                    # rather than a second copy of the rule living here.
                    candidates = (value, spoken_value(SCIFI_PACK, name, value))
                    spoken = any(
                        c.lower() in lowered or pluralize(c).lower() in lowered
                        for c in candidates
                    )
                    with self.subTest(seed=seed, name=name):
                        self.assertTrue(spoken, f"{value!r} in {text!r}")

    def test_a_companion_never_outlives_its_host(self) -> None:
        for seed in range(200):
            _, document = scene(seed, )
            for record in document["entities"]:
                for name, spec in SCIFI_PACK.entity_fields.items():
                    if spec.renders_with is None:
                        continue
                    with self.subTest(seed=seed, name=name):
                        if record[spec.renders_with] is None:
                            self.assertIsNone(record[name])


class HeadPhraseFallbackTests(unittest.TestCase):
    """A supporting slot never draws a ``form``, so a subject-leading kind has to
    fall back to its noun ladder or it loses its name to the generic kind."""

    def test_a_supporting_creature_slot_is_still_described(self) -> None:
        """A supporting slot has fewer *widgets*, not fewer fields.

        It used to have both: every field without a widget resolved to None, so
        an unwired slot 2 read "A large arachnoid." and nothing else, and wiring
        a Scene Entity was the only way to get a second described subject. A
        supporting slot now draws its whole morphology and the detail budget --
        not the widget list -- decides how much of it is spoken.
        """
        payload_free = {f"entity{slot}_kind": NONE for slot in (1, 3, 4)}
        described = 0
        for seed in range(60):
            text, document = scene(
                seed, widgets={**payload_free, "entity2_kind": "alien creature"}
            )
            record = document["entities"][0]
            with self.subTest(seed=seed):
                # Never the bare generic kind: the head phrase falls through to
                # the body plan or the creature type, never to "alien creature".
                self.assertNotIn("A creature or being,", text)
                if record["form"] is not None:
                    described += 1
        self.assertGreater(
            described, 0, "no supporting creature slot ever drew a body plan"
        )

    def test_a_full_creature_slot_leads_with_its_body_plan(self) -> None:
        text, document = scene(
            11, widgets={"entity1_kind": "alien creature"},         )
        record = document["entities"][0]
        self.assertIsNotNone(record["form"])
        # The body plan is the head noun of the creature's sentence. Scale and
        # condition now fold onto it as leading adjectives (A5), so it need not
        # be the first word -- but it must precede the creature type.
        self.assertIn(record["form"], text)
        if record["subkind"] is not None:
            self.assertLess(text.index(record["form"]), text.index(record["subkind"]), text)


class SeamTests(unittest.TestCase):
    def test_a_minimal_fixture_pack_runs_the_whole_pipeline(self) -> None:
        """Zero prose authoring, zero constraints, two fields -- the cheapest
        pack a genre can be. If this needs an engine change, the seam is not
        real (Todo 26 makes this a first-class proof)."""
        pack = GenrePack(
            slug="fixture",
            display="Fixture",
            class_suffix="Fixture",
            kinds=("thing", "other"),
            entity_fields={
                "kind": FieldSpec(group="I", label="Kind"),
                "shape": FieldSpec(group="F", label="Shape", kind_scoped=True),
            },
            scene_fields={
                "environment": FieldSpec(group="S", label="E"),
                "situation": FieldSpec(group="S", label="S", kind_scoped=True),
                "relation": FieldSpec(group="R", label="R", default=NONE),
                "relation_position": FieldSpec(group="R", label="Position", default=NONE),
            },
            pools={
                "kind": {"_default": ("thing", "other")},
                "shape": {"thing": ("wedge", "sphere"), "_default": ("blob",)},
                "environment": {"_default": ("a void", "a plain")},
                "situation": {"_default": ("turning slowly",)},
                "relation": {"_default": ("beside",)},
            },
            prose=ProseSpec(
                scene_order=("environment", "entities", "relations"),
                entity_clause_order=("kind", "shape"),
                head_phrase={"_default": HeadPhrase(noun=("shape", "kind"))},
                templates={"relation": "{first} sits beside {second}"},
            ),
        )
        text, document = generate_scene(1, pack, )
        self.assertTrue(text)
        self.assertEqual(document["_meta"]["genre"], "fixture")
        self.assertTrue(document["entities"])


class EmptyEntityTests(unittest.TestCase):
    """``entity_count=1`` must always yield one entity.

    The defect this guards: two locked fields whose scoped pools do not
    overlap used to union their complements and ban every kind, so the slot
    vanished and the prompt was a bare setting sentence."""

    def test_a_default_scene_always_has_its_entity(self) -> None:
        for seed in range(50):
            with self.subTest(seed=seed):
                _text, document = generate_scene(seed, SCIFI_PACK, entity_count=1)
                self.assertEqual(len(document["entities"]), 1)

    def test_contradictory_locks_still_produce_an_entity(self) -> None:
        widgets = {
            "entity1_subkind": "salvager",
            "entity1_form": "six-wheeled rover chassis",
        }
        for seed in range(50):
            with self.subTest(seed=seed):
                _text, document = generate_scene(
                    seed, SCIFI_PACK, widgets=widgets, entity_count=1
                )
                self.assertEqual(len(document["entities"]), 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
