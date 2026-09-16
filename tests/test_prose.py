"""Todo 14 -- the prose renderer.

The assertions that matter most are the two that pin the *seam*:

* clause order comes out of ``pack.prose``, proven by rendering a fixture pack
  whose order is deliberately different and watching the output follow it;
* a creature's body plan is the subject of its sentence, proven on position
  rather than on presence.

Everything else is composition: articles, counts, gating and the never-negate
rule that a field with no value produces no clause at all.
"""
from __future__ import annotations

import unittest

from data.genre import FieldSpec, GenrePack, HeadPhrase, ProseSpec, archetype_for
from data.scifi import SCIFI_PACK
from engine.prose import entity_reference, render_entity, render_prose
from engine.resolution import ResolvedEntity, ResolvedRelation, ResolvedScene

VESSEL_FIELDS = {
    "kind": "starship",
    "subkind": "heavy freighter",
    "scale": "large",
    "condition": "battle-scarred",
    "form": "needle hull",
    "material": "titanium alloy",
    "primary_color": "gunmetal grey",
    "accent_color": "oxide red",
    "markings": "hazard chevrons",
    "surface_detail": "pitted and scarred",
    "appendages": "docking spar",
    "appendage_count": "four",
    "emitters": "ion thruster",
    "emitter_count": "six",
    "emitter_color": "cyan",
    "armament": "point-defence turret",
    "armament_count": "a pair of",
    "sensors": "phased array panel",
    "sensor_count": "three",
    "aperture": "launch bay",
    "extras": "cargo pod",
}

CREATURE_FIELDS = {
    "kind": "alien creature",
    "subkind": "insectoid",
    "scale": "massive",
    "condition": "pristine",
    "form": "hexapodal frame",
    "material": "chitinous carapace",
    "primary_color": "ochre yellow",
    "sensors": "stalked eye",
    "sensor_count": "a crown of",
    "aperture": "circular toothed maw",
}


def entity(index: int = 1, *, fields: dict, situation: str | None = None,
           source: str = "widgets") -> ResolvedEntity:
    return ResolvedEntity(
        index=index, source=source, genre="scifi", fields=fields, situation=situation
    )


class EntityCompositionTests(unittest.TestCase):
    def test_the_head_phrase_consumes_its_fields(self) -> None:
        """"a large battle-scarred heavy freighter" -- and no trailing repeat of
        the scale or the condition it already spoke."""
        text = render_entity(entity(fields=VESSEL_FIELDS), SCIFI_PACK)
        self.assertTrue(text.startswith("A large battle-scarred heavy cargo starship"), text)
        self.assertEqual(text.count("large"), 1)
        self.assertEqual(text.count("battle-scarred"), 1)

    def test_the_generic_kind_is_voiced_once_as_an_apposition(self) -> None:
        """The one field the ladder deliberately does *not* silence.

        A specific subkind suppressing its generic kind is right nearly
        everywhere and was catastrophic here: "warship", "prow", "hull" and
        "mast" are all naval words, and with nothing saying "starship" the
        prompt got drawn as a ship at sea. It is voiced exactly once -- an
        apposition, not a second head noun.
        """
        text = render_entity(entity(fields=VESSEL_FIELDS), SCIFI_PACK)
        self.assertIn("heavy cargo starship", text)
        self.assertEqual(text.count("starship"), 1)

    def test_a_count_and_a_colour_compose_into_their_noun(self) -> None:
        text = render_entity(entity(fields=VESSEL_FIELDS), SCIFI_PACK)
        self.assertIn("six cyan ion thrusters", text)
        self.assertIn("four docking spars", text)
        self.assertIn("a pair of point-defence turrets", text)
        self.assertIn("three phased array panels", text)

    def test_the_material_reads_as_a_clad_phrase(self) -> None:
        """form + material compose into the single with-clause: "with a needle hull, clad in ..."."""
        text = render_entity(entity(fields=VESSEL_FIELDS), SCIFI_PACK)
        self.assertIn("a needle hull", text)
        self.assertIn("clad in gunmetal-grey titanium alloy", text)

    def test_markings_read_as_a_plain_noun_phrase(self) -> None:
        """markings is a bare noun phrase; the livery sentence supplies the verb.

        The pool value itself must stay article-less and verb-less -- "hazard
        chevrons", never "marked with hazard chevrons" -- because the sentence
        plan is what decides how it is introduced. A value carrying its own
        verb would read as "It is marked with marked with ...".
        """
        text = render_entity(entity(fields=VESSEL_FIELDS), SCIFI_PACK)
        self.assertIn("marked with hazard chevrons", text)
        self.assertNotIn("with marked with", text)

    def test_surface_detail_reads_as_a_plain_noun_phrase(self) -> None:
        """surface_detail no longer carries a possessive subject; it is a noun
        phrase grouped under the single ``with`` clause."""
        text = render_entity(entity(fields=VESSEL_FIELDS), SCIFI_PACK)
        self.assertIn("pitted and scarred", text)
        self.assertNotIn("Its hull is", text)

    def test_a_soft_adjective_folds_onto_its_first_standing_anchor(self) -> None:
        text = render_entity(entity(fields=VESSEL_FIELDS), SCIFI_PACK)
        self.assertIn("clad in gunmetal-grey titanium alloy", text)

    def test_a_soft_adjective_falls_through_to_the_next_anchor(self) -> None:
        fields = dict(VESSEL_FIELDS, material=None)
        self.assertIn(
            "a gunmetal-grey needle hull", render_entity(entity(fields=fields), SCIFI_PACK)
        )

    def test_a_soft_adjective_stands_alone_when_no_anchor_survives(self) -> None:
        fields = {"kind": "starship", "subkind": "courier", "primary_color": "off-white"}
        self.assertEqual(
            render_entity(entity(fields=fields), SCIFI_PACK),
            "A courier starship. It is off-white.",
        )

    def test_a_field_with_no_value_produces_no_clause(self) -> None:
        """Never negate: absence is silence, not "with no weapons"."""
        fields = dict(VESSEL_FIELDS, armament=None, armament_count=None, aperture=None)
        text = render_entity(entity(fields=fields), SCIFI_PACK)
        self.assertNotIn("turret", text)
        self.assertNotIn("launch bay", text)
        for word in (" no ", "without", "lacking", "unarmed", "absent", "devoid"):
            with self.subTest(word=word):
                self.assertNotIn(word, f" {text} ")

    def test_a_count_with_no_noun_is_never_voiced(self) -> None:
        """The count rides its noun. A count left standing alone would be a
        quantity of nothing -- the "resolved but not voiced" bug in reverse."""
        fields = dict(VESSEL_FIELDS, emitters=None)
        text = render_entity(entity(fields=fields), SCIFI_PACK)
        self.assertNotIn("six", text)
        self.assertNotIn("cyan", text)

    def test_a_noun_with_no_count_voices_the_bare_plural(self) -> None:
        fields = dict(VESSEL_FIELDS, emitter_count=None)
        self.assertIn("cyan ion thrusters", render_entity(entity(fields=fields), SCIFI_PACK))

    def test_the_situation_is_the_entitys_first_predicate(self) -> None:
        text = render_entity(
            entity(fields=VESSEL_FIELDS, situation="docking at a damaged station"), SCIFI_PACK
        )
        self.assertTrue(
            text.startswith("A large battle-scarred heavy cargo starship is docking"),
            text,
        )
        self.assertIn("is docking at a damaged station.", text)

    def test_an_entity_with_nothing_to_say_renders_empty(self) -> None:
        self.assertEqual(render_entity(entity(fields={}), SCIFI_PACK), "")


class CreatureSubjectTests(unittest.TestCase):
    """A non-human body must be the *subject*, not a trailing modifier.

    "a creature with a segmented worm body" draws a human holding a worm; four
    Identity Forge render bugs traced to exactly this. Asserted on position.
    """

    def test_the_body_plan_is_the_first_thing_said(self) -> None:
        """A5: scale and condition now fold onto the promoted body plan, so the
        plan leads with its own adjectives and is still the head noun."""
        text = render_entity(entity(fields=CREATURE_FIELDS), SCIFI_PACK)
        self.assertTrue(text.startswith("A massive pristine hexapodal frame"), text)
        self.assertLess(text.index("hexapodal frame"), text.index("insectoid"), text)

    def test_every_other_descriptor_follows_the_body_plan(self) -> None:
        text = render_entity(entity(fields=CREATURE_FIELDS), SCIFI_PACK)
        form_at = text.index("hexapodal frame")
        for later in ("insectoid", "chitinous carapace"):
            with self.subTest(later=later):
                self.assertGreater(text.index(later), form_at)

    def test_a_promoted_subject_carries_its_modifiers(self) -> None:
        """A5: the modifiers ride with the promoted subject, so the creature
        never emits the bare "It is massive." filler it used to."""
        text = render_entity(entity(fields=CREATURE_FIELDS), SCIFI_PACK)
        self.assertIn("A massive pristine hexapodal frame", text)
        self.assertNotIn("It is massive.", text)
        self.assertNotIn("It is pristine.", text)

    def test_the_creature_type_is_still_said(self) -> None:
        """Leading with the body plan must not cost the subkind its voice."""
        self.assertIn("an insectoid", render_entity(entity(fields=CREATURE_FIELDS), SCIFI_PACK))

    def test_a_vessel_leads_with_its_class_instead(self) -> None:
        text = render_entity(entity(fields=VESSEL_FIELDS), SCIFI_PACK)
        self.assertLess(text.index("heavy cargo starship"), text.index("needle hull"))

    def test_every_declared_subject_leading_kind_actually_leads(self) -> None:
        for kind in SCIFI_PACK.prose.subject_leading_kinds:
            archetype = archetype_for(SCIFI_PACK, {"kind": kind})
            self.assertIsNotNone(archetype, kind)
            head = archetype.head_phrase
            self.assertIsNotNone(head.subject, kind)
            plan = archetype.sentences or SCIFI_PACK.prose.entity_sentences
            self.assertTrue(plan[0].text.startswith("{subject}"), plan[0].text)
            fields = {"kind": kind, head.subject: "marker phrase"}
            with self.subTest(kind=kind):
                self.assertTrue(
                    render_entity(entity(fields=fields), SCIFI_PACK).startswith("A marker phrase")
                )


class ArticleTests(unittest.TestCase):
    def test_a_and_an_follow_the_phrase(self) -> None:
        self.assertTrue(
            render_entity(
                entity(fields={"kind": "starship", "form": "arrowhead hull"}), SCIFI_PACK
            ).endswith("an arrowhead hull.")
        )
        self.assertTrue(
            render_entity(
                entity(fields={"kind": "starship", "form": "saucer hull"}), SCIFI_PACK
            ).endswith("a saucer hull.")
        )

    def test_a_plural_head_noun_takes_no_article(self) -> None:
        text = render_entity(
            entity(fields={"kind": "space station", "form": "stacked ring tiers"}),
            SCIFI_PACK,
        )
        self.assertIn("stacked ring tiers", text)
        self.assertNotIn("a stacked ring tiers", text)


class SceneCompositionTests(unittest.TestCase):
    def _scene(self, count: int, **kwargs) -> ResolvedScene:
        entities = tuple(
            entity(i, fields=dict(VESSEL_FIELDS, subkind=f"class {i}"))
            for i in range(1, count + 1)
        )
        return ResolvedScene(entities=entities, **kwargs)

    def test_zero_entities_renders_the_setting_alone(self) -> None:
        text = render_prose(ResolvedScene(environment="asteroid field"), SCIFI_PACK)
        self.assertEqual(
            text, "A science fiction scene set in an asteroid field, out in open space."
        )

    def test_an_empty_scene_renders_nothing_rather_than_punctuation(self) -> None:
        self.assertEqual(render_prose(ResolvedScene(), SCIFI_PACK), "")

    def test_one_to_four_entities_each_get_a_sentence(self) -> None:
        """The setting is its own sentence;
        each entity appears exactly once."""
        for count in (1, 2, 3, 4):
            with self.subTest(count=count):
                text = render_prose(
                    self._scene(count, environment="deep interstellar void"), SCIFI_PACK
                )
                self.assertTrue(text.startswith("A science fiction scene set in a deep interstellar void"), text)
                self.assertEqual(text.count("deep interstellar void"), 1)
                for i in range(1, count + 1):
                    self.assertIn(f"class {i}", text)
                    self.assertEqual(text.count(f"class {i}"), 1)

    def test_an_omitted_slot_never_appears(self) -> None:
        """Slots 2 and 4 are set to None; only 1 and 3 exist, and the prose
        must not leave a gap where the others were."""
        scene = ResolvedScene(entities=(
            entity(1, fields=dict(VESSEL_FIELDS, subkind="courier")),
            entity(3, fields=dict(VESSEL_FIELDS, subkind="ore hauler")),
        ))
        text = render_prose(scene, SCIFI_PACK)
        self.assertIn("courier", text)
        self.assertIn("ore-hauling starship", text)
        self.assertNotIn("class", text)

    def test_sentences_are_capitalized_and_closed(self) -> None:
        text = render_prose(self._scene(2, environment="asteroid field"), SCIFI_PACK)
        for sentence in text.split(". "):
            with self.subTest(sentence=sentence):
                self.assertTrue(sentence[0].isupper())
        self.assertTrue(text.endswith("."))

    def test_the_environment_and_the_relation_compose_into_the_scene(self) -> None:
        """The setting is its own sentence; a relation is a standalone sentence
        naming both endpoints and its spatial position."""
        scene = ResolvedScene(
            environment="asteroid field",
            entities=(entity(1, fields=dict(VESSEL_FIELDS, subkind="courier")),
                      entity(2, fields=dict(VESSEL_FIELDS, subkind="ore hauler"))),
            relations=(ResolvedRelation(endpoints=(1, 2), value="attacking", position="from behind"),),
        )
        text = render_prose(scene, SCIFI_PACK)
        self.assertTrue(text.startswith("A science fiction scene set in an asteroid field"), text)
        self.assertIn("The courier starship is attacking the ore-hauling starship, from behind.", text)

    def test_a_place_that_floats_says_so(self) -> None:
        """A model grounds whatever it is not told floats."""
        open_space = render_prose(ResolvedScene(environment="asteroid field"), SCIFI_PACK)
        self.assertIn("out in open space", open_space)
        underwater = render_prose(
            ResolvedScene(environment="deep ocean trench of a water world"), SCIFI_PACK
        )
        self.assertIn("deep underwater", underwater)
        interior = render_prose(ResolvedScene(environment="cargo hold"), SCIFI_PACK)
        self.assertNotIn("out in open space", interior)
        self.assertNotIn("deep underwater", interior)
        self.assertNotIn("far above the planet's surface", interior)


class RelationTests(unittest.TestCase):
    def _two(self) -> tuple[ResolvedEntity, ResolvedEntity]:
        return (
            entity(1, fields=dict(VESSEL_FIELDS, subkind="salvage hauler")),
            entity(2, fields=dict(VESSEL_FIELDS, subkind="ore hauler")),
        )

    def test_a_relation_names_both_endpoints(self) -> None:
        """A relation is a standalone sentence naming both endpoints."""
        scene = ResolvedScene(
            entities=self._two(),
            relations=(ResolvedRelation(endpoints=(1, 2), value="attacking"),),
        )
        self.assertIn(
            "The salvage starship is attacking the ore-hauling starship.",
            render_prose(scene, SCIFI_PACK),
        )

    def test_a_relation_with_a_position_reads_action_then_position(self) -> None:
        """A relation voices its action, then its spatial position."""
        scene = ResolvedScene(
            entities=self._two(),
            relations=(ResolvedRelation(endpoints=(1, 2), value="attacking", position="from behind"),),
        )
        text = render_prose(scene, SCIFI_PACK)
        self.assertIn("The salvage starship is attacking the ore-hauling starship, from behind.", text)

    def test_a_relation_with_no_position_renders_the_action_alone(self) -> None:
        scene = ResolvedScene(
            entities=self._two(),
            relations=(ResolvedRelation(endpoints=(1, 2), value="attacking"),),
        )
        text = render_prose(scene, SCIFI_PACK)
        self.assertIn("The salvage starship is attacking the ore-hauling starship.", text)
        self.assertNotIn(", from behind", text)

    def test_a_relation_to_an_empty_slot_is_dropped(self) -> None:
        """Half a relation is not a relation. Dropping it is the never-negate
        rule again: the scene says nothing rather than inventing a partner."""
        scene = ResolvedScene(
            entities=(self._two()[0],),
            relations=(ResolvedRelation(endpoints=(1, 3), value="pursuing"),),
        )
        self.assertNotIn("pursuing", render_prose(scene, SCIFI_PACK))

    def test_two_entities_with_the_same_name_are_told_apart(self) -> None:
        scene = ResolvedScene(
            entities=(entity(1, fields=dict(VESSEL_FIELDS, subkind="courier")),
                      entity(2, fields=dict(VESSEL_FIELDS, subkind="courier"))),
            relations=(ResolvedRelation(endpoints=(1, 2), value="merged with"),),
        )
        self.assertIn(
            "The first courier starship is merged with the second courier starship.",
            render_prose(scene, SCIFI_PACK),
        )

    def test_an_entity_is_referred_to_by_the_name_it_was_introduced_with(self) -> None:
        self.assertEqual(
            entity_reference(entity(fields=CREATURE_FIELDS), SCIFI_PACK), "the hexapodal frame"
        )
        self.assertEqual(
            entity_reference(entity(fields=VESSEL_FIELDS), SCIFI_PACK), "the heavy cargo starship"
        )

    def test_an_entity_with_only_a_kind_still_has_a_reference(self) -> None:
        self.assertEqual(
            entity_reference(entity(fields={"kind": "starship"}), SCIFI_PACK), "the starship"
        )


class CopulaTests(unittest.TestCase):
    """The entity sentence is a subject + conjugated predicate, not a catalog."""

    def _pack(self) -> GenrePack:
        return GenrePack(
            slug="fixture",
            display="Fixture",
            class_suffix="Fixture",
            kinds=("thing",),
            entity_fields={
                "kind": FieldSpec(group="Identity", label="Kind"),
                "form": FieldSpec(group="Form", label="Form"),
            },
            scene_fields={
                "environment": FieldSpec(group="Scene", label="Environment"),
                "situation": FieldSpec(group="Scene", label="Situation"),
                "relation": FieldSpec(group="Relations", label="Relation"),
                "relation_position": FieldSpec(group="Relations", label="Position"),
            },
            prose=ProseSpec(
                scene_order=("environment", "entities", "relations"),
                entity_clause_order=("kind", "form"),
                head_phrase={"_default": HeadPhrase(noun=("form", "kind"))},
            ),
        )

    def test_a_singular_subject_takes_is(self) -> None:
        text = render_entity(
            entity(fields={"kind": "thing", "form": "fluted monolith"}, situation="drifting"),
            self._pack(),
        )
        self.assertTrue(text.endswith("."), text)
        self.assertIn("A fluted monolith is drifting", text)

    def test_a_plural_subject_takes_are(self) -> None:
        text = render_entity(
            entity(fields={"kind": "thing", "form": "stacked ring tiers"}, situation="drifting"),
            self._pack(),
        )
        self.assertIn("Stacked ring tiers are drifting", text)
        self.assertNotIn(" is ", text)

    def test_no_situation_emits_no_copula(self) -> None:
        """A missing situation leaves no dangling copula.

        The situation sentence's lead is "{pronoun} {copula}", so an entity
        with no situation must drop that sentence entirely rather than emit a
        bare "It is." -- the never-negate rule's grammatical cousin.
        """
        text = render_entity(entity(fields=VESSEL_FIELDS), SCIFI_PACK)
        self.assertTrue(text.endswith("."), text)
        self.assertNotIn("It is.", text)
        self.assertFalse(text.rstrip().endswith(" is."), text)

    def test_trailing_descriptors_group_under_one_with_clause(self) -> None:
        text = render_entity(
            entity(fields=VESSEL_FIELDS, situation="docking at a damaged station"), SCIFI_PACK
        )
        self.assertIn(" is docking at a damaged station", text)
        self.assertEqual(text.count(" with "), 1)


class SeamTests(unittest.TestCase):
    """Clause order and wording live in the pack, not in the renderer.

    Proven the only way that counts: a second pack with a different order and
    different templates renders differently, through the same engine code.
    """

    def _fixture(self, **prose_overrides) -> GenrePack:
        prose = dict(
            scene_order=("environment", "entities", "relations"),
            entity_clause_order=("kind", "hue", "shape"),
            templates={"environment": "{a_value}", "relation": "{first} beside {second}"},
        )
        prose.update(prose_overrides)
        return GenrePack(
            slug="fixture",
            display="Fixture",
            class_suffix="Fixture",
            kinds=("thing",),
            entity_fields={
                "kind": FieldSpec(group="Identity", label="Kind"),
                "hue": FieldSpec(group="Surface", label="Hue"),
                "shape": FieldSpec(group="Form", label="Shape"),
            },
            scene_fields={
                "environment": FieldSpec(group="Scene", label="Environment"),
                "situation": FieldSpec(group="Scene", label="Situation"),
                "relation": FieldSpec(group="Relations", label="Relation"),
                "relation_position": FieldSpec(group="Relations", label="Position"),
            },
            prose=ProseSpec(**prose),
        )

    def _render(self, pack: GenrePack) -> str:
        return render_entity(
            entity(fields={"kind": "thing", "hue": "amber", "shape": "wedge"}), pack
        )

    def test_a_pack_with_no_head_phrase_renders_every_field_as_a_clause(self) -> None:
        self.assertEqual(self._render(self._fixture()), "Thing, amber, wedge.")

    def test_reordering_the_pack_reorders_the_prose(self) -> None:
        reordered = self._fixture(entity_clause_order=("shape", "hue", "kind"))
        self.assertEqual(self._render(reordered), "Wedge, amber, thing.")

    def test_a_pack_head_phrase_changes_the_opening(self) -> None:
        headed = self._fixture(
            head_phrase={"_default": HeadPhrase(noun=("shape",), modifiers=("hue",))}
        )
        self.assertEqual(self._render(headed), "An amber wedge with thing.")

    def test_a_pack_template_changes_the_wording(self) -> None:
        worded = self._fixture(
            templates={"hue": "finished in {value}", "environment": "{a_value}"}
        )
        self.assertEqual(self._render(worded), "Thing, finished in amber, wedge.")

    def test_a_pack_relation_template_changes_the_relation_wording(self) -> None:
        scene = ResolvedScene(
            entities=(entity(1, fields={"kind": "thing"}), entity(2, fields={"kind": "thing"})),
            relations=(ResolvedRelation(endpoints=(1, 2), value="ignored"),),
        )
        text = render_prose(scene, self._fixture())
        self.assertIn("The first thing beside the second thing.", text)


class TemplateValidationTests(unittest.TestCase):
    """A malformed template fails at pack construction, not at render time."""

    def _prose(self, templates: dict) -> ProseSpec:
        return ProseSpec(
            scene_order=(), entity_clause_order=("kind",), templates=templates
        )

    def test_an_unknown_placeholder_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._prose({"kind": "{colour}"})

    def test_a_positional_placeholder_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._prose({"kind": "{}"})

    def test_the_known_placeholders_are_accepted(self) -> None:
        self._prose({"kind": "{a_value}", "relation": "{first} is {value} {second}"})


class AppositionTests(unittest.TestCase):
    """A1 -- the apposition is set off on both sides.

    It used to open with a comma and never close it, so every pattern that put
    text after ``{subject}`` read "A large weathered ghost liner, a wreck is
    venting..." -- the readability defect this round closes.
    """

    def test_a_made_subject_names_its_category_in_the_head_noun(self) -> None:
        text = render_entity(
            entity(fields=VESSEL_FIELDS, situation="docking at a damaged station"),
            SCIFI_PACK,
        )
        self.assertTrue(
            text.startswith("A large battle-scarred heavy cargo starship is docking"), text
        )
        self.assertNotIn(", a starship", text)

    def test_a_creature_apposition_closes_against_the_stop(self) -> None:
        text = render_entity(entity(fields=CREATURE_FIELDS), SCIFI_PACK)
        self.assertIn("an alien creature", text)
        self.assertNotIn(",,", text)
        self.assertNotIn(", .", text)


class TidyTests(unittest.TestCase):
    """A1 -- the tidy pass closes what an apposition leaves behind."""

    def test_the_comma_before_a_stop_collapses(self) -> None:
        from engine.prose import _tidy

        self.assertEqual(_tidy("A liner, a wreck,."), "A liner, a wreck.")

    def test_a_doubled_comma_collapses(self) -> None:
        from engine.prose import _tidy

        self.assertEqual(_tidy("A liner, a wreck,, is here"), "A liner, a wreck, is here")
        self.assertEqual(_tidy("A liner, a wreck, , is here"), "A liner, a wreck, is here")

    def test_a_space_before_punctuation_collapses(self) -> None:
        from engine.prose import _tidy

        self.assertEqual(_tidy("A liner, a wreck , is here"), "A liner, a wreck, is here")
        self.assertEqual(_tidy("A liner, a wreck ."), "A liner, a wreck.")

    def test_an_ordinary_conjunction_is_left_alone(self) -> None:
        from engine.prose import _tidy

        self.assertEqual(_tidy("It is a liner, and a wreck."), "It is a liner, and a wreck.")

    def test_a_closed_sentence_absorbs_the_appositions_comma(self) -> None:
        """The clause fallback closes the sentence before tidying, so a
        subject-final apposition does not leave `,.`."""
        from engine.prose import _sentence

        self.assertEqual(_sentence("a wreck, a starship,"), "A wreck, a starship.")
        self.assertEqual(
            _sentence("a wreck, a starship, is here"), "A wreck, a starship, is here."
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
