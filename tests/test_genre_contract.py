"""Todo 3 -- the GenrePack contract and the genre seam.

The seam claim is "a second genre costs one data module and two registration
lines". Nothing about the code's *appearance* proves that; only two things do:

1. The contract module imports with no pack in ``sys.modules`` (a subprocess,
   so an earlier test's imports cannot make this pass by accident).
2. No genre name appears anywhere under ``nodes/`` or ``engine/``.

Todo 26 finishes the proof by running a throwaway fixture pack end to end. These
tests are what stop the seam from being quietly broken before then -- by which
point unpicking it would mean rewriting the node classes.
"""
from __future__ import annotations

import dataclasses
import re
import subprocess
import sys
import textwrap
import unittest

from data import genre
from data.genre import (
    ENTITY_COUNT_KEY,
    ENTITY_NODE_SLOTS,
    NONE,
    RANDOM,
    SCENE_NODE_SLOTS,
    SET_ALL_FIELDS_KEY,
    ConstraintRule,
    FieldDef,
    FieldSpec,
    GenrePack,
    ProseSpec,
    address_matches,
    build_field_definitions,
    field_def_required_keys,
    label_for,
    pool_for,
    pool_options,
    relation_pairs,
    widget_choices,
    widget_order,
)
from data.scifi import SCIFI_PACK
from data.user_options import apply_user_options
from tests._loader import REPO_ROOT

#: The widget count, pinned because it is a compatibility surface: three
#: generation controls (seed, entity count, scene filter) + set_all_fields,
#: which is not a field -- see genre.py -- + environment + slot 1's 21
#: morphology fields and its situation + three brief slots of five + six
#: relations + six positions.
EXPECTED_SCENE_KEYS = 54
EXPECTED_ENTITY_KEYS = 22
EXPECTED_ENTITY_FIELDS = 21

#: Directories that must never name a genre.
GENRE_FREE_DIRS = ("nodes", "engine")


class SeamIsolationTests(unittest.TestCase):
    """The contract must not reach a pack, even transitively."""

    def _run(self, body: str) -> str:
        script = textwrap.dedent(body)
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_contract_imports_without_any_pack(self) -> None:
        """A subprocess, not an in-process check: by the time this file runs,
        ``data.scifi`` is already imported, so an in-process assertion would be
        vacuous -- exactly the kind of test that looks green and proves nothing.
        """
        leaked = self._run(
            """
            import sys
            sys.path.insert(0, '.')
            import data.genre  # noqa: F401
            packs = [m for m in sys.modules if m.endswith('.scifi') or m == 'scifi']
            print(','.join(sorted(packs)))
            """
        )
        self.assertEqual(leaked, "")

    def test_node_factories_import_without_any_pack(self) -> None:
        """The factories take a pack as an argument. If one ever imports a pack
        instead, a second genre stops being free and this catches it."""
        leaked = self._run(
            """
            import sys
            sys.path.insert(0, '.')
            sys.path.insert(0, 'tests/comfy_stub')
            import nodes.scene_weaver  # noqa: F401
            import nodes.scene_entity  # noqa: F401
            packs = [m for m in sys.modules if m.endswith('.scifi') or m == 'scifi']
            print(','.join(sorted(packs)))
            """
        )
        self.assertEqual(leaked, "")

    def test_no_genre_name_under_nodes_or_engine(self) -> None:
        """``grep -r "scifi" nodes/ engine/`` returns nothing -- and would keep
        returning nothing for a fantasy pack, because the check is built from
        the pack's own slug rather than a hardcoded word."""
        needle = re.compile(
            rf"{re.escape(SCIFI_PACK.slug)}|{re.escape(SCIFI_PACK.class_suffix)}"
            rf"|{re.escape(SCIFI_PACK.display)}",
            re.IGNORECASE,
        )
        offenders = []
        for directory in GENRE_FREE_DIRS:
            for path in sorted((REPO_ROOT / directory).rglob("*.py")):
                for number, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), start=1
                ):
                    if needle.search(line):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}: {line.strip()}")
        self.assertEqual(offenders, [], "genre name leaked into genre-agnostic code")

    def test_the_entrypoint_is_where_the_genre_lives(self) -> None:
        """The counterpart to the test above: the seam is only meaningful if the
        genre is named *somewhere*, and that somewhere is the two registration
        lines in the repo-root ``__init__.py``."""
        source = (REPO_ROOT / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("from .data.scifi import SCIFI_PACK", source)
        self.assertIn("build_entity_node(SCIFI_PACK)", source)
        self.assertIn("build_scene_node(SCIFI_PACK)", source)

    def test_the_docs_do_not_reference_the_removed_detail_level(self) -> None:
        """The detail-level dial is gone; a stale doc reference to the removed
        ``detail_level`` identifier or the old relation set is a regression."""
        doc_paths = [
            REPO_ROOT / "README.md",
            REPO_ROOT / "AGENTS.md",
            REPO_ROOT / "docs" / "architecture.md",
        ]
        stale = ("detail_level", "towed by", "merged with")
        for path in doc_paths:
            text = path.read_text(encoding="utf-8")
            for term in stale:
                with self.subTest(path=path.name, term=term):
                    self.assertNotIn(term, text)


class FieldDefContractTests(unittest.TestCase):
    def _complete_kwargs(self) -> dict:
        return {
            "key": "entity1_kind",
            "path": "entity1.kind",
            "base": "kind",
            "slot": 1,
            "endpoints": None,
            "group": "Identity",
            "label": "Kind",
            "tooltip": "",
            "options": ("starship",),
            "optional": True,
            "control": False,
            "kind_scoped": False,
            "tag_scoped": False,
            "count_partner": None,
            "weights": None,
            "omission_weight": 0.0,
            "widget": "combo",
            "default": RANDOM,
        }

    def test_the_plan_named_keys_are_all_required(self) -> None:
        self.assertTrue(genre.REQUIRED_FIELD_DEF_KEYS <= field_def_required_keys())

    def test_every_declared_attribute_is_required(self) -> None:
        """A FieldDef is machine-built, so a silently-defaulted key would be a
        hole nothing notices until render time."""
        declared = {f.name for f in dataclasses.fields(FieldDef)}
        self.assertEqual(declared, field_def_required_keys())

    def test_a_missing_required_key_raises(self) -> None:
        for missing in sorted(genre.REQUIRED_FIELD_DEF_KEYS):
            with self.subTest(missing=missing):
                kwargs = self._complete_kwargs()
                del kwargs[missing]
                with self.assertRaises(TypeError):
                    FieldDef(**kwargs)

    def test_every_built_definition_is_complete(self) -> None:
        for slots in (ENTITY_NODE_SLOTS, SCENE_NODE_SLOTS):
            for key, definition in build_field_definitions(SCIFI_PACK, slots).items():
                with self.subTest(slots=slots, key=key):
                    for attribute in field_def_required_keys():
                        self.assertTrue(hasattr(definition, attribute))
                    self.assertEqual(definition.key, key)


class BuildFieldDefinitionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scene = build_field_definitions(SCIFI_PACK, SCENE_NODE_SLOTS)
        self.entity = build_field_definitions(SCIFI_PACK, ENTITY_NODE_SLOTS)

    def test_key_counts(self) -> None:
        self.assertEqual(len(self.scene), EXPECTED_SCENE_KEYS)
        self.assertEqual(len(self.entity), EXPECTED_ENTITY_KEYS)

    def test_the_pack_declares_the_whole_morphology(self) -> None:
        self.assertEqual(len(SCIFI_PACK.entity_fields), EXPECTED_ENTITY_FIELDS)

    def test_every_kind_widget_defaults_to_random(self) -> None:
        """An untouched node still generates exactly one entity, but the
        ``Entities`` control is what says so, not the widget defaults.

        The defaults used to be None on slots 2-4, which made that control a lie
        the moment it was raised: the slot appeared and stayed empty, because
        the hidden widget it revealed still said None.
        """
        for slot in (1, 2, 3, 4):
            with self.subTest(slot=slot):
                self.assertEqual(self.scene[f"entity{slot}_kind"].default, RANDOM)

    def test_the_entity_count_control_defaults_to_one(self) -> None:
        self.assertEqual(self.scene[ENTITY_COUNT_KEY].default, "1")
        self.assertEqual(
            self.scene[ENTITY_COUNT_KEY].options, ("1", "2", "3", "4")
        )

    def test_entity_node_is_a_seed_plus_the_morphology(self) -> None:
        self.assertEqual(list(self.entity), ["seed", *SCIFI_PACK.entity_fields])

    def test_slot_one_is_full_depth_and_the_rest_are_brief(self) -> None:
        slot_one = [d.base for d in self.scene.values() if d.slot == 1]
        self.assertEqual(slot_one, [*SCIFI_PACK.entity_fields, "situation"])
        brief = [name for name, s in SCIFI_PACK.entity_fields.items() if s.brief]
        for slot in (2, 3, 4):
            with self.subTest(slot=slot):
                self.assertEqual(
                    [d.base for d in self.scene.values() if d.slot == slot],
                    [*brief, "situation"],
                )

    def test_relations_and_positions_over_four_slots(self) -> None:
        self.assertEqual(
            [d.key for d in self.scene.values() if d.endpoints],
            ["relation_1_2", "relation_1_3", "relation_1_4",
             "relation_2_3", "relation_2_4", "relation_3_4",
             "relation_1_2_position", "relation_1_3_position", "relation_1_4_position",
             "relation_2_3_position", "relation_2_4_position", "relation_3_4_position"],
        )
        self.assertEqual(len(relation_pairs(SCENE_NODE_SLOTS)), 6)

    def test_the_lone_entity_borrows_slot_one_addresses(self) -> None:
        """One constraint rule set governs both nodes, so a rule written for
        ``entity1.kind`` fires on the Scene Entity node too."""
        self.assertEqual(self.entity["kind"].path, "entity1.kind")
        self.assertEqual(self.entity["kind"].key, "kind")

    def test_widget_keys_are_legal_identifiers(self) -> None:
        """They arrive at ``execute`` as keyword arguments, so a dot would be
        fatal -- which is why the constraint address is a separate key space."""
        for key in (*self.scene, *self.entity):
            with self.subTest(key=key):
                self.assertTrue(key.isidentifier())

    def test_negative_slots_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_field_definitions(SCIFI_PACK, -1)


class WidgetOrderTests(unittest.TestCase):
    """``widgets_values`` is positional, so this order is a compatibility
    surface: appending is safe, reordering silently rewrites saved workflows."""

    def test_set_all_fields_sits_last_among_the_controls(self) -> None:
        order = widget_order(SCIFI_PACK, SCENE_NODE_SLOTS)
        self.assertEqual(
            order[:5],
            ("seed", ENTITY_COUNT_KEY, "scene_filter", SET_ALL_FIELDS_KEY, "environment"),
        )
        self.assertEqual(len(order), EXPECTED_SCENE_KEYS + 1)

    def test_the_entity_node_has_no_bulk_control(self) -> None:
        order = widget_order(SCIFI_PACK, ENTITY_NODE_SLOTS)
        self.assertNotIn(SET_ALL_FIELDS_KEY, order)
        self.assertEqual(len(order), EXPECTED_ENTITY_KEYS)

    def test_order_matches_the_definitions_apart_from_bulk_control(self) -> None:
        order = [
            k for k in widget_order(SCIFI_PACK, SCENE_NODE_SLOTS)
            if k != SET_ALL_FIELDS_KEY
        ]
        self.assertEqual(order, list(build_field_definitions(SCIFI_PACK, SCENE_NODE_SLOTS)))

class WidgetChoiceTests(unittest.TestCase):
    def test_descriptive_fields_offer_random_then_options_then_none(self) -> None:
        definition = build_field_definitions(SCIFI_PACK, SCENE_NODE_SLOTS)["entity1_kind"]
        choices = widget_choices(definition)
        self.assertEqual(choices[0], RANDOM)
        self.assertEqual(choices[-1], NONE)
        self.assertEqual(choices[1:-1], SCIFI_PACK.kinds)

    def test_controls_offer_exactly_their_own_options(self) -> None:
        scene = build_field_definitions(SCIFI_PACK, SCENE_NODE_SLOTS)
        self.assertEqual(widget_choices(scene["scene_filter"]), genre.SCENE_FILTERS)
        self.assertNotIn(RANDOM, widget_choices(scene["scene_filter"]))

    def test_the_relation_position_combo_offers_random_and_none(self) -> None:
        definition = build_field_definitions(SCIFI_PACK, SCENE_NODE_SLOTS)["relation_1_2_position"]
        choices = widget_choices(definition)
        self.assertEqual(choices[0], RANDOM)
        self.assertEqual(choices[-1], NONE)

    def test_a_control_may_not_be_optional(self) -> None:
        with self.assertRaises(ValueError):
            FieldSpec(group="Controls", label="X", control=True, optional=True)

    def test_relations_default_to_none(self) -> None:
        scene = build_field_definitions(SCIFI_PACK, SCENE_NODE_SLOTS)
        self.assertEqual(scene["relation_1_2"].default, NONE)
        self.assertEqual(scene["entity1_kind"].default, RANDOM)

    def test_the_mechanic_line_is_on_every_descriptive_widget(self) -> None:
        scene = build_field_definitions(SCIFI_PACK, SCENE_NODE_SLOTS)
        tip = genre.field_tooltip(scene["entity1_emitter_count"])
        self.assertIn("Random=randomize, value=lock, None=omit", tip)
        self.assertNotIn("=randomize", genre.field_tooltip(scene["seed"]))


class PackStructureTests(unittest.TestCase):
    def test_count_pairs_point_at_each_other(self) -> None:
        for noun, counter in SCIFI_PACK.counts.items():
            with self.subTest(pair=(noun, counter)):
                self.assertEqual(SCIFI_PACK.entity_fields[noun].count_partner, counter)
                self.assertEqual(SCIFI_PACK.entity_fields[counter].count_partner, noun)
                self.assertEqual(SCIFI_PACK.entity_fields[counter].renders_with, noun)

    def test_clause_order_covers_exactly_the_clause_heads(self) -> None:
        heads = {n for n, s in SCIFI_PACK.entity_fields.items() if s.renders_with is None}
        self.assertEqual(set(SCIFI_PACK.prose.entity_clause_order), heads)

    def test_a_field_that_heads_no_clause_is_rejected(self) -> None:
        """The dead-widget guard, at construction time: a field that heads no
        clause and is composed into none would be drawn every render and never
        voiced."""
        fields = dict(SCIFI_PACK.entity_fields)
        fields["orphan"] = FieldSpec(group="Components", label="Orphan")
        with self.assertRaises(ValueError):
            dataclasses.replace(SCIFI_PACK, entity_fields=fields)

    def test_the_pack_is_not_mutable_in_place(self) -> None:
        """User options merge into a *new* pack. Appending to a shared pool
        would leak one caller's private entries into every other reader."""
        with self.assertRaises(TypeError):
            SCIFI_PACK.pools["environment"] = ()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            SCIFI_PACK.slug = "fantasy"

    def test_scene_fields_are_declared(self) -> None:
        self.assertEqual(
            list(SCIFI_PACK.scene_fields),
            ["environment", "situation", "relation", "relation_position", "context"],
        )

    #: Pool fields no todo has authored yet, and the todo that owns each. Todo 3
    #: pinned "every pool is empty"; that assertion retires field by field as the
    #: data lands, and this map is what keeps the emptiness a *recorded stage*
    #: rather than an unnoticed omission. Empty it and delete this test.
    PENDING_POOLS: dict[str, int] = {}

    def test_pool_authoring_progress_matches_the_recorded_stage(self) -> None:
        """Every field either has a pool or is on the pending list -- never both,
        and never neither."""
        expected = set(SCIFI_PACK.entity_fields) | set(SCIFI_PACK.scene_fields)
        authored = set(SCIFI_PACK.pools)
        self.assertEqual(
            expected - authored,
            set(self.PENDING_POOLS),
            "a pool was authored (or lost) without retiring its pending entry",
        )
        self.assertFalse(
            authored & set(self.PENDING_POOLS),
            "a field is both authored and listed as pending",
        )

    def test_every_empty_pool_is_a_declared_omission(self) -> None:
        """An empty pool under a kind is legal -- it says "this kind has no such
        feature", which is omission, not negation -- but it must be registered in
        ``OMITTED_POOLS`` so it reads as a decision rather than as a hole."""
        from data.scifi import OMITTED_POOLS

        empty = {
            (field, key)
            for field, by_kind in SCIFI_PACK.pools.items()
            for key, values in by_kind.items()
            if not values
        }
        self.assertEqual(
            empty,
            set(OMITTED_POOLS),
            "an empty pool is not declared in OMITTED_POOLS (or a declared "
            "omission has quietly gained values)",
        )


class PackValidationTests(unittest.TestCase):
    """Structural rules a genre author can get wrong, and the errors they get."""

    def _pack(self, **overrides) -> GenrePack:
        base = {
            "slug": "fixture",
            "display": "Fixture",
            "class_suffix": "Fixture",
            "kinds": ("thing",),
            "entity_fields": {"kind": FieldSpec(group="Identity", label="Kind")},
            "scene_fields": {
                "environment": FieldSpec(group="Scene", label="Environment"),
                "situation": FieldSpec(group="Scene", label="Situation"),
                "relation": FieldSpec(group="Relations", label="Relation"),
                "relation_position": FieldSpec(group="Relations", label="Position"),
            },
            "prose": ProseSpec(scene_order=(), entity_clause_order=("kind",)),
        }
        base.update(overrides)
        return GenrePack(**base)

    def test_a_minimal_pack_builds(self) -> None:
        self.assertEqual(len(build_field_definitions(self._pack(), ENTITY_NODE_SLOTS)), 2)

    def test_a_pack_without_a_kind_field_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._pack(
                entity_fields={"form": FieldSpec(group="Identity", label="Form")},
                prose=ProseSpec(scene_order=(), entity_clause_order=("form",)),
            )

    def test_a_pack_missing_a_scene_field_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._pack(scene_fields={"environment": FieldSpec(group="Scene", label="E")})

    def test_a_bad_slug_or_suffix_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._pack(slug="Sci-Fi")
        with self.assertRaises(ValueError):
            self._pack(class_suffix="sciFi")

    def test_a_half_declared_count_pair_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._pack(
                entity_fields={
                    "kind": FieldSpec(group="Identity", label="Kind"),
                    "sensors": FieldSpec(group="C", label="S", count_partner="sensor_count"),
                    "sensor_count": FieldSpec(group="C", label="N", renders_with="sensors"),
                },
                counts={"sensors": "sensor_count"},
                prose=ProseSpec(scene_order=(), entity_clause_order=("kind", "sensors")),
            )

    def test_a_staging_pair_naming_an_unknown_affordance_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._pack(
                prose=ProseSpec(
                    scene_order=(), entity_clause_order=("kind",),
                    environment_staging=(("open-space", ", out in open space"),),
                ),
            )

    def test_a_staging_suffix_without_a_leading_comma_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._pack(
                pools={"environment": {"void": ("void",)}},
                place_affordances={"void": frozenset({"open-space"})},
                prose=ProseSpec(
                    scene_order=(), entity_clause_order=("kind",),
                    environment_staging=(("open-space", " out in open space"),),
                ),
            )


class UserOptionsSeamTests(unittest.TestCase):
    """The merge hook exists and is not wired to an import.

    Todo 23 implements it. The rule pinned here is the one that is easy to break
    later: importing a pack must never run the merge, or a check script that
    reads the data layer bakes the maintainer's private entries into a committed
    file.
    """

    def test_importing_a_pack_does_not_merge(self) -> None:
        source = (REPO_ROOT / "data" / "scifi.py").read_text(encoding="utf-8")
        self.assertNotIn("user_options", source)
        self.assertNotIn("apply_user_options", (REPO_ROOT / "data" / "genre.py").read_text(
            encoding="utf-8"))

    def test_the_hook_returns_a_pack_rather_than_mutating_one(self) -> None:
        self.assertIs(apply_user_options(SCIFI_PACK), SCIFI_PACK)


class ConstraintRuleTests(unittest.TestCase):
    """Shape only. Todo 12 authors the rules; Todo 21 resolves them against the
    real pools."""

    def test_an_exclude_rule_builds(self) -> None:
        rule = ConstraintRule(
            type=genre.RULE_EXCLUDE,
            field="entity1.kind",
            value="celestial body",
            excludes_field="entity1.armament",
            excludes_values=("spinal railgun",),
            reason="a moon carries no guns",
        )
        self.assertEqual(rule.excludes_values, ("spinal railgun",))

    def test_a_require_rule_builds(self) -> None:
        rule = ConstraintRule(
            type=genre.RULE_REQUIRE,
            field="entity*.kind",
            value="celestial body",
            requires_field="environment",
            requires_value="deep space",
            reason="a planet is not indoors",
        )
        self.assertEqual(rule.field, "entity*.kind")

    def test_a_rule_of_neither_shape_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ConstraintRule(type=genre.RULE_EXCLUDE, field="environment", value="orbit")
        with self.assertRaises(ValueError):
            ConstraintRule(type="forbid", field="environment", value="orbit",
                           excludes_field="entity1.kind", excludes_values=("x",))

    def test_a_rule_against_absence_is_rejected(self) -> None:
        """A rule keyed on ``None`` would fire on every unfilled field, and the
        pack expresses absence by omission rather than as a value."""
        with self.assertRaises(ValueError):
            ConstraintRule(type=genre.RULE_EXCLUDE, field="entity1.kind", value=NONE,
                           excludes_field="entity1.form", excludes_values=("saucer",))

    def test_a_rule_naming_a_fifth_slot_is_still_syntactically_addressable(self) -> None:
        """Address *syntax* allows any slot number; whether slot 5 exists is a
        resolution question, and Todo 21's validate_data is what rejects it. The
        assertion here is only that the two checks stay separate concerns."""
        rule = ConstraintRule(type=genre.RULE_EXCLUDE, field="entity5.kind", value="starship",
                              excludes_field="entity5.form", excludes_values=("saucer",))
        scene_paths = {d.path for d in build_field_definitions(SCIFI_PACK, SCENE_NODE_SLOTS).values()}
        self.assertNotIn(rule.field, scene_paths)

    def test_a_malformed_address_is_rejected(self) -> None:
        for bad in ("Entity1.kind", "entity1.", "entity0.kind", "entity1.KIND", "1entity.kind"):
            with self.subTest(address=bad):
                with self.assertRaises(ValueError):
                    ConstraintRule(type=genre.RULE_EXCLUDE, field=bad, value="x",
                                   excludes_field="environment", excludes_values=("y",))

    def test_the_slot_wildcard_selects_every_slot(self) -> None:
        self.assertTrue(address_matches("entity*.kind", "entity3.kind"))
        self.assertFalse(address_matches("entity*.kind", "entity3.form"))
        self.assertFalse(address_matches("entity*.kind", "environment"))
        self.assertTrue(address_matches("environment", "environment"))
        self.assertTrue(address_matches("entity2.kind", "entity2.kind"))
        self.assertFalse(address_matches("entity2.kind", "entity3.kind"))


class PoolAccessTests(unittest.TestCase):
    """The fallback chain, exercised against a fixture pack because the sci-fi
    pools are empty until Todo 4."""

    def setUp(self) -> None:
        self.pack = GenrePack(
            slug="fixture",
            display="Fixture",
            class_suffix="Fixture",
            kinds=("starship", "creature"),
            entity_fields={
                "kind": FieldSpec(group="Identity", label="Kind"),
                "form": FieldSpec(group="Form", label="Form", kind_scoped=True),
            },
            scene_fields={
                "environment": FieldSpec(group="Scene", label="Environment"),
                "situation": FieldSpec(group="Scene", label="Situation"),
                "relation": FieldSpec(group="Relations", label="Relation"),
                "relation_position": FieldSpec(group="Relations", label="Position"),
            },
            pools={
                "kind": {"_default": ("starship", "creature")},
                "form": {"starship": ("needle hull", "saucer"), "_default": ("amorphous",)},
            },
            labels={"form": {"starship": "Hull silhouette", "creature": "Body plan"}},
            prose=ProseSpec(scene_order=(), entity_clause_order=("kind", "form")),
        )

    def test_a_kind_override_wins(self) -> None:
        self.assertEqual(pool_for(self.pack, "form", "starship"), ("needle hull", "saucer"))

    def test_an_unlisted_kind_falls_through_to_the_default(self) -> None:
        self.assertEqual(pool_for(self.pack, "form", "creature"), ("amorphous",))

    def test_a_missing_pool_returns_empty_rather_than_raising(self) -> None:
        """A data hole is reported by name by ``validate_data``; it must not be
        an exception the user meets mid-render."""
        self.assertEqual(pool_for(self.pack, "material", "starship"), ())

    def test_widget_options_are_the_union_across_kinds(self) -> None:
        """ComfyUI fixes a combo's options at registration, so a value legal
        under *some* kind must stay selectable -- otherwise locking it and then
        switching kind would silently drop it."""
        self.assertEqual(pool_options(self.pack, "form"), ("amorphous", "needle hull", "saucer"))

    def test_labels_fall_back_to_the_generic_name(self) -> None:
        self.assertEqual(label_for(self.pack, "form", "starship"), "Hull silhouette")
        self.assertEqual(label_for(self.pack, "form", "creature"), "Body plan")
        self.assertEqual(label_for(self.pack, "form", "station"), "Form")
        self.assertEqual(label_for(self.pack, "form"), "Form")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
