"""Todo 26 -- structural proof that a second genre is a data module.

The claim the whole architecture rests on is that adding a genre costs **one
``data/<genre>.py`` and two registration lines**, with zero edits under
``nodes/`` or ``engine/``. That claim is cheap to make and easy to get wrong:
one hardcoded field name, one ``if kind == "starship"``, one clause order baked
into the renderer, and the second genre silently costs a refactor instead.

So this module builds a genre. Not sci-fi, and not fantasy either -- a
deliberately alien two-kind fixture whose field names, kinds, clause order and
count pairing share nothing with the shipped pack, constructed here in memory
and never written to ``data/``. Then it generates both node classes from it,
executes them, and runs the whole engine over it.

``tests/test_genre_contract.py`` asserts the *negative* half of the seam (the
engine imports without a pack; no genre slug appears under ``nodes/`` or
``engine/``). This module asserts the positive half: a pack the production code
has never seen actually works. Both are needed. A grep proves nobody wrote the
word "scifi"; only running a foreign pack proves nobody encoded sci-fi's
*shape*.

**The rule for maintaining this file:** if a change to ``nodes/`` or ``engine/``
is what makes it pass, the seam is not real. Widen the contract in
``data/genre.py`` instead -- that is the seam, and a genre-shaped hole in it is
the defect. This test failing is a design finding, not a test bug.

The last suite pins the cross-genre path, which is a documented feature rather
than an accident: ``SCENE_ENTITY`` is one socket type shared by every genre, so
a sci-fi entity wires into a fixture-genre scene. The scene's pack owns the
environment, the situations and the relations; the entity brings its own
description and carries its own ``genre`` tag into ``prompt_json``.
"""
from __future__ import annotations

import dataclasses
import json
import unittest

from data.genre import (
    CONTEXT_FIELD,
    NONE,
    POOL_DEFAULT_KEY,
    RANDOM,
    RELATION_ANY,
    RULE_EXCLUDE,
    SCENE_NODE_SLOTS,
    Archetype,
    ConstraintRule,
    FieldSpec,
    GenrePack,
    HeadPhrase,
    ProseSpec,
    Sentence,
    affordances_of,
    build_field_definitions,
    is_classified,
    kind_feasible,
    resolved_needs,
    spoken_value,
)
from data.scifi import SCIFI_PACK
from engine.budget import apply_budget
from engine.scene import SOURCE_WIDGETS, SOURCE_WIRED, generate_entity, generate_scene
from nodes.scene_entity import build_entity_node
from nodes.scene_weaver import build_scene_node, entity_socket_key
from scripts.sample_distribution import motif_hits

# ---------------------------------------------------------------------------
# The fixture genre
# ---------------------------------------------------------------------------
#
# Nothing here is sci-fi shaped on purpose:
#
# * two kinds, not nine, and neither is "starship";
# * field names the shipped pack does not have ("bearing", "chorus"), so a
#   production module that reached for a sci-fi field name by string would fail
#   here rather than quietly keep working;
# * a count pair on a field that is not one of sci-fi's four;
# * one kind that leads its sentence with its ``form`` and one that does not,
#   so the subject-leading path is exercised from pack data alone;
# * one kind with a deliberately absent pool, reached through ``_default``.

BEAST = "beast"
RELIC = "relic"

#: One motif, declared so the distribution instrument is exercised on a genre
#: the production code has never seen. The words are the fixture's own.
FIXTURE_MOTIFS = {"drowned": ("drowned", "sunken")}


def build_fixture_pack() -> GenrePack:
    """A complete, minimal genre built in memory. Never written to ``data/``."""
    entity_fields = {
        "kind": FieldSpec(
            group="identity", label="Kind", kind_scoped=False, brief=True,
        ),
        "lineage": FieldSpec(
            group="identity", label="Lineage", kind_scoped=True, tag_scoped=True,
            brief=True,
        ),
        "stature": FieldSpec(group="identity", label="Stature", brief=True),
        "form": FieldSpec(group="body", label="Form", kind_scoped=True),
        "hue": FieldSpec(group="body", label="Hue"),
        "chorus": FieldSpec(
            group="body", label="Chorus", kind_scoped=True,
            count_partner="chorus_count",
        ),
        "chorus_count": FieldSpec(
            group="body", label="Chorus count", count_partner="chorus",
            renders_with="chorus",
        ),
        "bearing": FieldSpec(
            group="body", label="Bearing", kind_scoped=True, tag_scoped=True,
        ),
    }
    scene_fields = {
        "environment": FieldSpec(group="scene", label="Setting"),
        "situation": FieldSpec(
            group="scene", label="Doing", kind_scoped=True, tag_scoped=True, brief=True,
        ),
        "relation": FieldSpec(group="scene", label="Relation", tag_scoped=True),
        "relation_position": FieldSpec(group="scene", label="Position"),
    }
    pools = {
        "environment": {POOL_DEFAULT_KEY: ("a sunken colonnade", "a salt plain")},
        "kind": {POOL_DEFAULT_KEY: (BEAST, RELIC)},
        "lineage": {BEAST: ("hollow-boned drake", "silt wyrm"), RELIC: ("oath stone",)},
        # No per-kind override: both kinds fall through to _default. The
        # fall-through is a documented pack decision, so the engine has to
        # resolve it without the pack restating it per kind.
        "stature": {POOL_DEFAULT_KEY: ("slight", "towering")},
        "form": {BEAST: ("coiled serpentine body",), RELIC: ("fluted monolith",)},
        "hue": {POOL_DEFAULT_KEY: ("verdigris", "bone white")},
        "chorus": {BEAST: ("throat sac",), RELIC: ("resonating flute",)},
        "chorus_count": {POOL_DEFAULT_KEY: ("a single", "a pair of", "six")},
        "bearing": {BEAST: ("bared fang ridge",), RELIC: ("worn petition step",)},
        "situation": {
            BEAST: ("circling the drowned steps",),
            RELIC: ("shedding flakes into the water",),
        },
        "relation": {POOL_DEFAULT_KEY: ("coiled around", "keeping vigil over")},
        "relation_position": {POOL_DEFAULT_KEY: ("the drowned steps", "the salt crust")},
    }
    return GenrePack(
        slug="fixture",
        display="Fixture",
        class_suffix="Fixture",
        kinds=(BEAST, RELIC),
        entity_fields=entity_fields,
        scene_fields=scene_fields,
        pools=pools,
        motifs=FIXTURE_MOTIFS,
        labels={"chorus_count": {BEAST: "Cry count", RELIC: "Tone count"}},
        counts={"chorus": "chorus_count"},
        tags={
            "lineage": {
                "hollow-boned drake": "conflict_only",
                "silt wyrm": "neutral",
                "oath stone": "peaceful_only",
            },
            "bearing": {
                "bared fang ridge": "conflict_only",
                "worn petition step": "peaceful_only",
            },
            "situation": {
                "circling the drowned steps": "neutral",
                "shedding flakes into the water": "neutral",
            },
            "relation": {"coiled around": "neutral", "keeping vigil over": "neutral"},
        },
        constraints=(
            ConstraintRule(
                type=RULE_EXCLUDE,
                field="entity1.kind",
                value=RELIC,
                excludes_field="entity1.stature",
                excludes_values=("slight",),
                reason="a relic in this genre is never slight",
            ),
        ),
        prose=ProseSpec(
            scene_order=("environment", "entities", "relations"),
            # Deliberately NOT the order `entity_fields` declares them in. A
            # renderer that walked the field declaration order instead of this
            # would produce a plausible sentence and pass any test that only
            # checked the words were present -- so the two orders are kept
            # different on purpose, and the clause-order test reads positions.
            entity_clause_order=("kind", "bearing", "chorus", "form", "hue", "stature", "lineage"),
            # The beast leads with its body; the relic leads with what it is.
            kind_clause_order={
                BEAST: ("form", "kind", "chorus", "bearing", "hue", "stature", "lineage"),
            },
            subject_leading_kinds=frozenset({BEAST}),
            # The fixture's own wording, deliberately unlike the shipped pack: a
            # fantasy copula ("looms"), a framing ("amid") and a relation-position
            # template all different from sci-fi's -- so a renderer that
            # hardcoded "is"/"Set in"/", from behind" fails here.
            environment_sentence="amid {a_value}",
            copula="looms",
            copula_plural="loom",
            relation_position_template=" from {value}",
            # The relation template earns its place: the shipped pack defaults
            # its relation widgets to None, so a default sci-fi scene rarely
            # renders one and the relation path is barely exercised end to end.
            # The fixture leaves them on Random, so this suite is where a
            # two-endpoint clause actually gets rendered.
            templates={
                "environment": "{a_value}",
                "relation": "{first} is {value} {second}",
                "kind": "{a_value}",
                "lineage": "{a_value}",
                "form": "{a_value}",
                "chorus": "{value}",
                "bearing": "{value}",
                "hue": "{value}",
                "stature": "{value}",
                "situation": "{value}",
            },
            head_phrase={
                POOL_DEFAULT_KEY: HeadPhrase(noun=("lineage", "kind"), modifiers=("stature",)),
                BEAST: HeadPhrase(
                    noun=("lineage", "kind"), modifiers=("stature",), subject="form"
                ),
            },
            adjective_of={"hue": ("form", "chorus")},
            detail_priority=("lineage", "form", "chorus", "hue", "bearing", "stature"),
        ),
    )


FIXTURE_PACK = build_fixture_pack()

#: The two lines a new genre costs in the repo-root ``__init__.py``. Building
#: them here is the whole registration story, which is the point.
FIXTURE_SCENE_NODE = build_scene_node(FIXTURE_PACK)
FIXTURE_ENTITY_NODE = build_entity_node(FIXTURE_PACK)


def _scene(seed: int, **kwargs: object) -> tuple[str, dict]:
    text, payload = FIXTURE_SCENE_NODE.execute(seed=seed, **kwargs).args
    return text, json.loads(payload)


# ---------------------------------------------------------------------------


class NodeGenerationTests(unittest.TestCase):
    """Both node classes generate from a pack the production code never saw."""

    def test_both_classes_are_generated_and_named_from_the_pack(self) -> None:
        self.assertEqual(FIXTURE_SCENE_NODE.__name__, "SceneWeaverFixture")
        self.assertEqual(FIXTURE_ENTITY_NODE.__name__, "SceneEntityFixture")

    def test_schemas_define_and_are_labelled_from_the_pack(self) -> None:
        scene = FIXTURE_SCENE_NODE.define_schema()
        entity = FIXTURE_ENTITY_NODE.define_schema()
        self.assertEqual(scene.node_id, "SceneWeaverFixture")
        self.assertEqual(scene.display_name, "Scene Weaver - Fixture")
        self.assertEqual(entity.node_id, "SceneEntityFixture")
        self.assertEqual(entity.display_name, "Scene Entity - Fixture")
        self.assertEqual(scene.category, entity.category)

    def test_the_widget_set_is_the_fixture_morphology_not_the_shipped_one(self) -> None:
        """The decisive assertion of this suite. If the node classes carried any
        sci-fi shape, a pack with different fields could not produce a different
        widget set -- it would produce the sci-fi one, or fail."""
        ids = {i.id for i in FIXTURE_ENTITY_NODE.define_schema().inputs}
        self.assertIn("chorus_count", ids)
        self.assertIn("bearing", ids)
        self.assertNotIn("emitter_count", ids)
        self.assertNotIn("armament", ids)

    def test_slot_layout_follows_the_fixture_pack(self) -> None:
        definitions = build_field_definitions(FIXTURE_PACK, SCENE_NODE_SLOTS)
        self.assertIn("entity1_bearing", definitions)
        # Slot 2 is brief, so it carries the pack's `brief` fields and no more.
        self.assertIn("entity2_lineage", definitions)
        self.assertNotIn("entity2_bearing", definitions)

    def test_the_options_offered_are_the_fixture_pools(self) -> None:
        by_id = {i.id: i for i in FIXTURE_ENTITY_NODE.define_schema().inputs}
        options = list(by_id["kind"].options)
        self.assertEqual(options, [RANDOM, BEAST, RELIC, NONE])


class EngineOverAForeignPackTests(unittest.TestCase):
    """The whole pipeline, driven only by fixture data."""

    def test_a_scene_generates_and_reads_as_prose(self) -> None:
        text, document = generate_scene(seed=11, pack=FIXTURE_PACK)
        self.assertTrue(text.strip())
        self.assertEqual(document["_meta"]["genre"], "fixture")
        self.assertEqual(len(document["entities"]), 1)

    def test_the_same_seed_reproduces_the_same_scene(self) -> None:
        first, _ = generate_scene(seed=99, pack=FIXTURE_PACK)
        second, _ = generate_scene(seed=99, pack=FIXTURE_PACK)
        self.assertEqual(first, second)

    def test_only_fixture_vocabulary_ever_appears(self) -> None:
        """A leak of the shipped pack into a foreign scene would be the loudest
        possible seam failure, so it is asserted rather than assumed."""
        legal = {v for kinds in FIXTURE_PACK.pools.values() for vs in kinds.values() for v in vs}
        for seed in range(120):
            _, document = generate_scene(
                seed=seed, pack=FIXTURE_PACK,             )
            for entity in document["entities"]:
                for key, value in entity.items():
                    if key in ("index", "source", "genre") or value is None:
                        continue
                    self.assertIn(value, legal, f"seed {seed}: {key}={value!r} is not fixture data")

    def test_the_pack_supplies_clause_order_not_the_engine(self) -> None:
        """Read by **position**, against an order the pack declares and the field
        declaration order does not match.

        Checking only that the words are present, or checking an order that
        happens to equal ``entity_fields``' own order, both pass against a
        renderer that ignores ``pack.prose`` entirely. The fixture's
        ``entity_clause_order`` is deliberately not its declaration order, so
        these positions can only come from the pack.
        """
        text, _ = generate_scene(
            seed=3,
            pack=FIXTURE_PACK,
            widgets={
                "entity1_kind": RELIC,
                "entity1_lineage": "oath stone",
                "entity1_stature": "towering",
                "entity1_form": "fluted monolith",
                "entity1_chorus": "resonating flute",
                "entity1_chorus_count": "a pair of",
                "entity1_bearing": "worn petition step",
                **{f"entity{n}_kind": NONE for n in (2, 3, 4)},
            },
        )
        # Declared: kind, bearing, chorus, form, ... -- the head phrase consumes
        # `lineage` and `stature`, so the three that stand as clauses are these.
        self.assertLess(text.index("worn petition step"), text.index("resonating flute"), text)
        self.assertLess(text.index("resonating flute"), text.index("fluted monolith"), text)

    def test_a_subject_leading_kind_puts_its_body_first(self) -> None:
        """The beast's ``form`` is the *subject* of its sentence, not a trailing
        modifier -- declared by the pack in ``subject_leading_kinds`` and its
        ``HeadPhrase.subject``, and obeyed by the renderer for a genre it has
        never seen."""
        text, _ = generate_scene(
            seed=3,
            pack=FIXTURE_PACK,
            widgets={
                "entity1_kind": BEAST,
                "entity1_form": "coiled serpentine body",
                "entity1_lineage": "silt wyrm",
                **{f"entity{n}_kind": NONE for n in (2, 3, 4)},
            },
        )
        self.assertLess(text.index("coiled serpentine body"), text.index("silt wyrm"), text)

    def test_a_relation_names_both_of_its_endpoints(self) -> None:
        """A two-endpoint clause, rendered from the pack's own template."""
        widgets = {"entity1_kind": RELIC, "entity2_kind": BEAST}
        _, document = generate_scene(seed=11, pack=FIXTURE_PACK, widgets=widgets)
        self.assertTrue(document["relations"])
        text, _ = generate_scene(seed=11, pack=FIXTURE_PACK, widgets=widgets)
        for relation in document["relations"]:
            self.assertIn(relation["value"], text)

    def test_an_entity_uses_the_fixture_copula_not_the_default(self) -> None:
        """The copula is pack data: the fixture declares "looms", so a renderer
        that hardcoded "is" would fail here."""
        text, _ = generate_scene(
            seed=3,
            pack=FIXTURE_PACK,
            widgets={"entity1_kind": RELIC, **{f"entity{n}_kind": NONE for n in (2, 3, 4)}},
        )
        self.assertIn("looms", text.lower())
        self.assertNotIn(" is ", text.lower())

    def test_the_environment_uses_the_fixture_framing(self) -> None:
        text, _ = generate_scene(
            seed=3,
            pack=FIXTURE_PACK,
            widgets={"entity1_kind": RELIC, **{f"entity{n}_kind": NONE for n in (2, 3, 4)}},
        )
        self.assertTrue(text.lower().startswith("amid "), text)

    def test_a_relation_uses_the_fixture_position_vocabulary(self) -> None:
        """The position pool and template are the fixture's, not sci-fi's."""
        text, _ = generate_scene(
            seed=11,
            pack=FIXTURE_PACK,
            widgets={
                "entity1_kind": RELIC,
                "entity2_kind": BEAST,
                "relation_1_2": "coiled around",
                **{f"entity{n}_kind": NONE for n in (3, 4)},
            },
        )
        self.assertTrue(
            "from the drowned steps" in text.lower() or "from the salt crust" in text.lower(),
            text,
        )

    def test_a_count_pair_the_shipped_pack_does_not_have_pluralizes(self) -> None:
        text, _ = generate_scene(
            seed=5,
            pack=FIXTURE_PACK,
            widgets={
                "entity1_kind": RELIC,
                "entity1_chorus": "resonating flute",
                "entity1_chorus_count": "six",
                **{f"entity{n}_kind": NONE for n in (2, 3, 4)},
            },
        )
        self.assertIn("six resonating flutes", text)

    def test_a_fixture_constraint_rule_fires(self) -> None:
        for seed in range(60):
            _, document = generate_scene(
                seed=seed,
                pack=FIXTURE_PACK,
                widgets={"entity1_kind": RELIC},
            )
            self.assertNotEqual(document["entities"][0]["stature"], "slight")

    def test_the_content_filter_masks_fixture_tags(self) -> None:
        for seed in range(60):
            _, document = generate_scene(
                seed=seed, pack=FIXTURE_PACK, scene_filter="Peaceful",
            )
            for entity in document["entities"]:
                self.assertNotEqual(entity["lineage"], "hollow-boned drake")
                self.assertNotEqual(entity["bearing"], "bared fang ridge")

    def test_the_fixed_budget_leaves_a_small_pack_intact(self) -> None:
        """The fixed allowance is larger than the fixture's whole morphology,
        so nothing is cut -- a small genre renders fully at the default budget.
        """
        expected = {
            name
            for name, spec in FIXTURE_PACK.entity_fields.items()
            if spec.renders_with is None and name != "kind"
        }
        for seed in range(40):
            _, document = generate_scene(
                seed=seed,
                pack=FIXTURE_PACK,
                widgets={
                    "entity1_kind": RELIC,
                    **{f"entity{n}_kind": NONE for n in (2, 3, 4)},
                },
            )
            voiced = {
                name
                for name, value in document["entities"][0].items()
                if value is not None
                and name in FIXTURE_PACK.entity_fields
                and name != "kind"
                and FIXTURE_PACK.entity_fields[name].renders_with is None
            }
            self.assertEqual(voiced, expected, f"seed {seed}")


    def test_a_none_kind_omits_the_slot(self) -> None:
        """An omitted slot leaves the document entirely; ``index`` is what says
        which slot a record came from, so a single-subject scene is one entry."""
        _, document = generate_scene(
            seed=4,
            pack=FIXTURE_PACK,
            widgets={f"entity{n}_kind": NONE for n in (2, 3, 4)},
        )
        self.assertEqual([e["index"] for e in document["entities"]], [1])

    def test_a_scene_with_no_entities_at_all_still_renders(self) -> None:
        """Pure setting: every slot switched off. The environment carries it."""
        text, document = generate_scene(
            seed=4,
            pack=FIXTURE_PACK,
            widgets={f"entity{n}_kind": NONE for n in (1, 2, 3, 4)},
        )
        self.assertEqual(document["entities"], [])
        self.assertTrue(text.strip())

    def test_both_node_classes_execute(self) -> None:
        text, document = _scene(21)
        self.assertTrue(text.strip())
        self.assertEqual(document["_meta"]["genre"], "fixture")
        entity_text, payload = FIXTURE_ENTITY_NODE.execute(
            seed=21, **{name: RANDOM for name in FIXTURE_PACK.entity_fields}
        ).args
        self.assertTrue(entity_text.strip())
        self.assertEqual(payload["genre"], "fixture")


class CrossGenreWiringTests(unittest.TestCase):
    """A sci-fi entity in a fixture-genre scene -- the documented feature."""

    def setUp(self) -> None:
        _, self.scifi_entity = generate_entity(
            seed=8, pack=SCIFI_PACK, widgets={"kind": "starship"}
        )

    def test_the_payload_crosses_the_socket_unchanged(self) -> None:
        text, document = _scene(8, **{entity_socket_key(1): self.scifi_entity})
        self.assertTrue(text.strip())
        slot = document["entities"][0]
        self.assertEqual(slot["source"], SOURCE_WIRED)
        self.assertEqual(slot["kind"], "starship")

    def test_the_entity_keeps_its_own_genre_tag(self) -> None:
        """Provenance is the whole reason the tag is per-entity rather than
        per-scene: a foreign entity stays traceable in the JSON."""
        _, document = _scene(8, entity2_kind=RELIC, **{entity_socket_key(1): self.scifi_entity})
        self.assertEqual(document["entities"][0]["genre"], "scifi")
        self.assertEqual(document["_meta"]["genre"], "fixture")
        self.assertEqual(document["entities"][1]["genre"], "fixture")

    def test_the_scene_still_owns_what_is_happening(self) -> None:
        """The entity node describes what a thing *is*; the situation and the
        relations belong to the scene whatever genre the entity came from."""
        _, document = _scene(8, **{entity_socket_key(1): self.scifi_entity})
        situation = document["entities"][0]["situation"]
        if situation is not None:
            fixture_situations = {
                v for vs in FIXTURE_PACK.pools["situation"].values() for v in vs
            }
            self.assertIn(situation, fixture_situations)

    def test_a_foreign_entity_does_not_derange_the_native_slots(self) -> None:
        _, document = _scene(8, **{entity_socket_key(1): self.scifi_entity})
        legal = {v for kinds in FIXTURE_PACK.pools.values() for vs in kinds.values() for v in vs}
        for slot in document["entities"][1:]:
            self.assertEqual(slot["source"], SOURCE_WIDGETS)
            for key, value in slot.items():
                if key in ("index", "source", "genre") or value is None:
                    continue
                self.assertIn(value, legal)

    def test_a_rule_keyed_on_a_kind_this_pack_lacks_never_fires(self) -> None:
        """The fixture's one rule is keyed on ``relic``. A wired sci-fi vessel is
        not a relic, so the rule has nothing to say about it -- rather than
        fighting it, or crashing on a kind it does not know."""
        _, document = _scene(8, **{entity_socket_key(1): self.scifi_entity})
        self.assertEqual(document["entities"][0]["kind"], "starship")

    def test_the_wire_still_beats_a_locked_widget_across_genres(self) -> None:
        _, document = _scene(
            8,
            entity1_kind=RELIC,
            **{entity_socket_key(1): self.scifi_entity},
        )
        self.assertEqual(document["entities"][0]["kind"], "starship")
        self.assertTrue(document["_meta"]["overridden_fields"])


class ArchetypeContractTests(unittest.TestCase):
    """The archetype's detail shape is genre-blind, not sci-fi-only."""

    def setUp(self) -> None:
        # Two archetypes with deliberately different caps and priorities, so a
        # test that only worked for the shipped pack's numbers would fail here.
        self.pack = dataclasses.replace(
            FIXTURE_PACK,
            archetypes={
                "spare": Archetype(
                    head_phrase=None, detail_cap=2, detail_priority=("hue",)
                ),
                "full": Archetype(
                    head_phrase=None, detail_cap=6, detail_priority=("bearing",)
                ),
            },
            archetype_of_kind={BEAST: "full", RELIC: "spare"},
        )
        self.heads = tuple(
            name
            for name, spec in self.pack.entity_fields.items()
            if spec.renders_with is None and name != "kind"
        )

    def test_each_archetypes_cap_is_honoured(self) -> None:
        for seed in range(40):
            _, document = generate_scene(seed, self.pack, entity_count=1)
            for record in document["entities"]:
                name = record["archetype"]
                spoken = [n for n in self.heads if record.get(n) is not None]
                cap = self.pack.archetypes[name].detail_cap
                with self.subTest(seed=seed, archetype=name):
                    self.assertLessEqual(len(spoken), cap)

    def test_each_archetypes_priority_leads(self) -> None:
        values = {name: "value" for name in self.pack.entity_fields}
        for name, promoted in (("spare", "hue"), ("full", "bearing")):
            kept = apply_budget(
                self.pack, values, budget=1, archetype=self.pack.archetypes[name]
            )
            spoken = {n for n in self.heads if kept.get(n) is not None}
            with self.subTest(archetype=name):
                self.assertEqual(spoken - {"stature"}, {promoted})


class ForeignEntityIntoShippedSceneTests(unittest.TestCase):
    """The reverse seam: a fixture entity in the sci-fi Scene Weaver."""

    def setUp(self) -> None:
        _, self.fixture_entity = FIXTURE_ENTITY_NODE.execute(seed=5).args

    def _scene(self, seed: int):
        return generate_scene(
            seed, SCIFI_PACK, wired_entities={1: self.fixture_entity}, entity_count=1
        )

    def test_the_scene_renders(self) -> None:
        for seed in range(20):
            text, _ = self._scene(seed)
            with self.subTest(seed=seed):
                self.assertTrue(text.strip())

    def test_the_environment_is_not_narrowed_to_nothing(self) -> None:
        seen = {self._scene(seed)[1]["environment"] for seed in range(30)}
        self.assertGreater(len(seen), 1)

    def test_the_entity_uses_the_packs_stranger_grammar(self) -> None:
        """Without a ``_default`` archetype it would fall through to the bare
        ProseSpec and be \"clad in\" its own hide; with one it is spoken
        through the pack's declared stranger grammar."""
        _, document = self._scene(3)
        self.assertEqual(document["entities"][0]["archetype"], POOL_DEFAULT_KEY)

    def test_the_entity_keeps_its_own_genre_tag(self) -> None:
        _, document = self._scene(3)
        self.assertEqual(document["entities"][0]["genre"], "fixture")


class ForeignPayloadLockTests(unittest.TestCase):
    """A foreign payload is placed by the host's rules unless it declares locks.

    The `locked` key is genre-blind: any genre's node may carry it, and a
    payload that omits it -- an older saved graph, a node that does not know
    about locks -- is treated as fully unlocked. A fantasy beast wired into a
    sci-fi scene is then placed by the host's rules rather than dropped into a
    place that cannot hold it."""

    def _payload(self, locked):
        base = {name: None for name in SCIFI_PACK.entity_fields}
        base.update(kind="alien creature", form="hexapodal frame")
        payload = {"schema_version": 1, "genre": "fixture", "fields": base}
        if locked is not None:
            payload["locked"] = locked
        return payload

    def _scene(self, payload):
        return generate_scene(
            2,
            SCIFI_PACK,
            widgets={"environment": "deep interstellar void"},
            wired_entities={1: payload},
            entity_count=1,
        )

    def test_an_undeclared_lock_is_treated_as_fully_unlocked(self) -> None:
        _, document = self._scene(self._payload(None))
        record = document["entities"][0]
        self.assertEqual(record["genre"], "fixture")
        self.assertNotEqual(record["form"], "hexapodal frame")

    def test_a_declared_lock_is_kept_and_warns(self) -> None:
        _, document = self._scene(self._payload(["form"]))
        record = document["entities"][0]
        self.assertEqual(record["genre"], "fixture")
        self.assertEqual(record["form"], "hexapodal frame")
        self.assertTrue(
            any("entity1.form" in w for w in document["_meta"]["warnings"]),
            document["_meta"]["warnings"],
        )

class MotifInstrumentTests(unittest.TestCase):
    """The motif instrument is genre-blind.

    ``GenrePack.motifs`` is a contract field: any genre declares its own word
    families and the distribution sweep reports their share. The fixture
    declares one, and the helper reports it for a fixture scene -- with no
    sci-fi vocabulary involved anywhere."""

    def test_the_fixture_declares_a_motif(self) -> None:
        self.assertEqual(set(FIXTURE_PACK.motifs), {"drowned"})

    def test_the_sweep_helper_reports_the_fixture_motif(self) -> None:
        found: set[str] = set()
        for seed in range(40):
            text, _ = generate_scene(seed, FIXTURE_PACK)
            found |= motif_hits(text, FIXTURE_PACK.motifs)
        self.assertIn("drowned", found)


class DramaticWeightTests(unittest.TestCase):
    """W1/W5 -- ``value_tiers``/``tier_weights`` and ``omission_weight``.

    Both are genre-blind contract: a genre declares which end of its own
    vocabulary is worth spending draws on, and how often a head-phrase
    modifier should say nothing at all. The fixture states both, and each is
    asserted to reach the renderer rather than merely construct."""

    def _tiered(self) -> GenrePack:
        return dataclasses.replace(
            FIXTURE_PACK,
            value_tiers={"stature": {"slight": "common", "towering": "rare"}},
            tier_weights={"common": 1.0, "rare": 9.0},
        )

    def test_weights_for_returns_the_effective_map(self) -> None:
        weights = self._tiered().weights_for("stature")
        self.assertIsNotNone(weights)
        self.assertEqual(dict(weights), {"slight": 1.0, "towering": 9.0})
        # A field with neither tiers nor weights has no effective map.
        self.assertIsNone(FIXTURE_PACK.weights_for("hue"))

    def test_a_tiered_value_is_drawn_more_often(self) -> None:
        """The derived weights reach ``_draw``, not just the accessor."""
        pack = self._tiered()
        counts = {"slight": 0, "towering": 0}
        for seed in range(200):
            _, document = generate_scene(seed, pack, entity_count=1)
            value = document["entities"][0]["stature"]
            if value in counts:
                counts[value] += 1
        self.assertGreater(counts["towering"], counts["slight"], counts)

    def test_an_unclassified_value_draws_at_neutral_weight(self) -> None:
        """A value with no tier is neutral, so a merged user value never crashes.

        The completeness rule -- every value carries a tier -- is a content
        check in ``tests/validate_data.py``; construction only rejects a tier
        *name* that has no weight."""
        pack = dataclasses.replace(
            FIXTURE_PACK,
            value_tiers={"stature": {"slight": "common"}},
            tier_weights={"common": 1.0},
        )
        weights = pack.weights_for("stature")
        self.assertEqual(weights["slight"], 1.0)
        self.assertEqual(weights["towering"], 1.0)  # untiered -> neutral
        with self.assertRaises(ValueError):
            dataclasses.replace(
                FIXTURE_PACK,
                value_tiers={"stature": {"slight": "common", "towering": "rare"}},
                tier_weights={"common": 1.0},
            )

    def test_omission_weight_can_draw_nothing(self) -> None:
        """A field with ``omission_weight`` draws ``None`` on some seeds."""
        specs = dict(FIXTURE_PACK.entity_fields)
        specs["hue"] = dataclasses.replace(specs["hue"], omission_weight=3.0)
        pack = dataclasses.replace(FIXTURE_PACK, entity_fields=specs)
        drawn = {"value": 0, "none": 0}
        for seed in range(120):
            hue = generate_scene(seed, pack, entity_count=1)[1]["entities"][0]["hue"]
            drawn["none" if hue is None else "value"] += 1
        self.assertGreater(drawn["none"], 0, drawn)
        self.assertGreater(drawn["value"], 0, drawn)



def build_declared_fixture_pack() -> GenrePack:
    """The fixture plus one of each new vocabulary, so each expander fires."""
    scene_fields = dict(FIXTURE_PACK.scene_fields)
    scene_fields[CONTEXT_FIELD] = FieldSpec(group="scene", label="Context")
    pools = {name: dict(by_key) for name, by_key in FIXTURE_PACK.pools.items()}
    pools[CONTEXT_FIELD] = {POOL_DEFAULT_KEY: ("lone beacon",)}
    # One beast situation is authored under the defaulted key but left out of
    # ``value_needs``, so it inherits the key's need; another declares an empty
    # entry, which suppresses that default. Both are named by the tests.
    pools["situation"][BEAST] = (
        *pools["situation"][BEAST],
        "wading the drowned shallows",
    )
    return dataclasses.replace(
        FIXTURE_PACK,
        scene_fields=scene_fields,
        pools=pools,
        prose=dataclasses.replace(
            FIXTURE_PACK.prose,
            context_sentences=(
                Sentence(
                    text="Beyond {pronoun_object}, {a_context} stands in the "
                    "middle distance."
                ),
            ),
        ),
        place_affordances={
            "a sunken colonnade": frozenset({"water"}),
            "a salt plain": frozenset({"ground"}),
        },
        value_needs={
            "situation": {
                "shedding flakes into the water": frozenset({"water"}),
                "wading the drowned shallows": frozenset(),
            },
        },
        default_needs={"situation": {BEAST: frozenset({"water"})}},
        value_traits={
            "bearing": {"bared fang ridge": frozenset({"aggressive"})},
            "situation": {"circling the drowned steps": frozenset({"peaceful"})},
        },
        trait_conflicts=(("aggressive", "peaceful"),),
        trait_reasons={"aggressive|peaceful": "a display of threat is not a calm vigil"},
        kind_capabilities={BEAST: frozenset({"mobile"}), RELIC: frozenset()},
        relation_roles={"coiled around": (frozenset({"mobile"}), frozenset())},
        place_stances={
            "water": frozenset({"swims"}),
            "ground": frozenset({"rests"}),
        },
        value_stances={"form": {"coiled serpentine body": frozenset({"swims"})}},
        spoken={"bearing": {"bared fang ridge": "displayed fang ridge"}},
    )


DECLARED_PACK = build_declared_fixture_pack()


class VocabularyExpansionTests(unittest.TestCase):
    """Each vocabulary the contract declares expands into a real rule."""

    def test_a_spoken_form_is_said_instead_of_the_token(self) -> None:
        self.assertEqual(
            spoken_value(DECLARED_PACK, "bearing", "bared fang ridge"),
            "displayed fang ridge",
        )
        self.assertEqual(
            spoken_value(DECLARED_PACK, "bearing", "worn petition step"),
            "worn petition step",
        )

    def test_an_affordance_need_excludes_a_value_from_a_place(self) -> None:
        self.assertEqual(
            affordances_of(DECLARED_PACK, "a sunken colonnade"),
            frozenset({"water"}),
        )
        rule = next(
            rule
            for rule in DECLARED_PACK.all_constraints
            if rule.excludes_field == "entity*.situation"
            and "shedding flakes into the water" in rule.excludes_values
        )
        self.assertEqual(rule.field, "environment")
        self.assertEqual(rule.triggers, ("a salt plain",))

    def test_a_default_need_excludes_a_value_the_key_classifies(self) -> None:
        self.assertEqual(
            resolved_needs(DECLARED_PACK, "situation", "circling the drowned steps"),
            frozenset({"water"}),
        )
        self.assertTrue(
            is_classified(DECLARED_PACK, "situation", "circling the drowned steps")
        )
        rule = next(
            rule
            for rule in DECLARED_PACK.all_constraints
            if rule.field == "environment"
            and rule.excludes_field == "entity*.situation"
            and "circling the drowned steps" in rule.excludes_values
        )
        self.assertEqual(rule.field, "environment")
        self.assertEqual(rule.triggers, ("a salt plain",))

    def test_an_explicit_empty_need_suppresses_the_key_default(self) -> None:
        """An empty ``value_needs`` entry is a declaration, not a hole.

        The value is authored under the defaulted key, so only the explicit
        entry keeps it out of the rule the key's need would build.
        """
        self.assertEqual(
            resolved_needs(DECLARED_PACK, "situation", "wading the drowned shallows"),
            frozenset(),
        )
        self.assertTrue(
            is_classified(DECLARED_PACK, "situation", "wading the drowned shallows")
        )
        self.assertFalse(
            any(
                "wading the drowned shallows" in rule.excludes_values
                for rule in DECLARED_PACK.all_constraints
                if rule.field == "environment"
                and rule.excludes_field == "entity*.situation"
            )
        )

    def test_a_form_stance_is_excluded_from_a_place_that_cannot_hold_it(self) -> None:
        self.assertEqual(
            DECLARED_PACK.value_stances["form"]["coiled serpentine body"],
            frozenset({"swims"}),
        )
        self.assertEqual(DECLARED_PACK.place_stances["water"], frozenset({"swims"}))
        rule = next(
            rule
            for rule in DECLARED_PACK.all_constraints
            if rule.excludes_field == "entity*.form"
        )
        self.assertEqual(rule.field, "environment")
        self.assertEqual(rule.triggers, ("a salt plain",))
        self.assertEqual(rule.excludes_values, ("coiled serpentine body",))

    def test_the_declared_place_stance_pair_is_the_named_one(self) -> None:
        """A vacuity guard: the rule above must fire from these exact pairings."""
        self.assertEqual(
            DECLARED_PACK.place_stances,
            {"water": frozenset({"swims"}), "ground": frozenset({"rests"})},
        )

    def test_a_context_sentence_reaches_the_renderer(self) -> None:
        text, document = generate_scene(seed=2, pack=DECLARED_PACK)
        self.assertEqual(document["context"], "lone beacon")
        self.assertEqual(document["_meta"]["context_sentence_index"], 0)
        self.assertIn("lone beacon", text)
        self.assertIn("middle distance", text)

    def test_a_trait_conflict_expands_to_an_exclusion(self) -> None:
        rule = next(
            rule
            for rule in DECLARED_PACK.all_constraints
            if rule.field == "entity*.bearing"
        )
        self.assertEqual(rule.triggers, ("bared fang ridge",))
        self.assertEqual(rule.excludes_field, "entity*.situation")
        self.assertEqual(rule.excludes_values, ("circling the drowned steps",))

    def test_a_relation_role_expands_to_an_exclusion(self) -> None:
        rule = next(
            rule
            for rule in DECLARED_PACK.all_constraints
            if rule.excludes_field == RELATION_ANY
        )
        self.assertEqual(rule.field, "first.kind")
        self.assertEqual(rule.triggers, (RELIC,))
        self.assertEqual(rule.excludes_values, ("coiled around",))

    def test_a_relation_that_does_not_fit_is_dropped(self) -> None:
        # entity1's kind is locked to the immobile relic and the relation is
        # left Random: "coiled around" cannot hold, so it is never drawn.
        for seed in range(40):
            _, document = generate_scene(
                seed, DECLARED_PACK,
                widgets={
                    "entity1_kind": RELIC,
                    "entity2_kind": BEAST,
                    "relation_1_2": RANDOM,
                    **{f"entity{n}_kind": NONE for n in (3, 4)},
                },
            )
            for relation in document["relations"]:
                self.assertNotEqual(relation["value"], "coiled around", seed)

    def test_a_trait_conflict_is_honoured_in_a_scene(self) -> None:
        for seed in range(40):
            _, document = generate_scene(
                seed, DECLARED_PACK,
                widgets={
                    "entity1_kind": BEAST,
                    "entity1_bearing": "bared fang ridge",
                    **{f"entity{n}_kind": NONE for n in (2, 3, 4)},
                },
            )
            self.assertNotEqual(
                document["entities"][0]["situation"], "circling the drowned steps"
            )

    def test_a_pack_declaring_none_of_them_still_constructs_and_renders(self) -> None:
        self.assertEqual(FIXTURE_PACK.spoken, {})
        self.assertEqual(FIXTURE_PACK.place_affordances, {})
        self.assertEqual(FIXTURE_PACK.value_needs, {})
        self.assertEqual(FIXTURE_PACK.value_traits, {})
        self.assertEqual(FIXTURE_PACK.relation_roles, {})
        text, document = generate_scene(seed=2, pack=FIXTURE_PACK)
        self.assertTrue(text.strip())
        self.assertEqual(len(document["entities"]), 1)


class FeasibilitySeamTests(unittest.TestCase):
    """The derived feasibility rules read only the contract: a fixture kind whose every
    form cannot stand in a place is re-drawn there, with no type level at all."""

    def _pack(self) -> GenrePack:
        return dataclasses.replace(
            FIXTURE_PACK,
            place_affordances={
                "a sunken colonnade": frozenset({"flooded"}),
                "a salt plain": frozenset({"dry-ground"}),
            },
            place_stances={
                "flooded": frozenset({"swims", "rests"}),
                "dry-ground": frozenset({"rests"}),
            },
            value_stances={"form": {
                "coiled serpentine body": frozenset({"swims"}),
                "fluted monolith": frozenset({"rests"}),
            }},
        )

    def test_a_kind_that_cannot_stand_is_ruled_out_of_the_place(self) -> None:
        pack = self._pack()
        self.assertFalse(kind_feasible(pack, "a salt plain", BEAST))
        self.assertTrue(kind_feasible(pack, "a sunken colonnade", BEAST))
        for seed in range(60):
            _text, document = generate_scene(
                seed, pack, widgets={"environment": "a salt plain"}, entity_count=1
            )
            for record in document["entities"]:
                with self.subTest(seed=seed):
                    self.assertNotEqual(record["kind"], BEAST)


if __name__ == "__main__":
    unittest.main()
