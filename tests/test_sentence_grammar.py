"""The sentence grammar: the parser, the renderer, and the coverage validator.

Wave 1 of the coherence overhaul replaced the clause list with genre-authored
sentences with holes. These tests exercise that machinery against a small local
pack, deliberately independent of the shipped genre -- the sci-fi data is
migrated separately, and the genre seam must stay free of it.
"""
from __future__ import annotations

import unittest
from collections import OrderedDict

from data.genre import (
    NONE,
    POOL_DEFAULT_KEY,
    Archetype,
    FieldSpec,
    GenrePack,
    HeadPhrase,
    ListSlot,
    Literal,
    ProseSpec,
    Sentence,
    Slot,
    pattern_covers,
    pattern_slots,
)
from engine.prose import render_entity
from engine.resolution import ResolvedEntity


def _field(label: str, **kwargs) -> FieldSpec:
    return FieldSpec(group="Group", label=label, **kwargs)


def _pack(
    *,
    entity_sentences: "tuple[Sentence, ...]" = (),
    archetypes: "dict[str, Archetype] | None" = None,
    archetype_of_kind: "dict[str, str] | None" = None,
    head_phrase: "dict | None" = None,
    **prose_kwargs,
) -> GenrePack:
    entity_fields = OrderedDict(
        [
            ("kind", _field("Kind")),
            ("form", _field("Form")),
            ("material", _field("Material")),
            ("hue", _field("Hue")),
            ("scale", _field("Scale")),
        ]
    )
    scene_fields = OrderedDict(
        [
            ("environment", _field("Environment")),
            ("situation", _field("Situation", kind_scoped=True)),
            ("relation", _field("Relation", default=NONE)),
            ("relation_position", _field("Position", default=NONE)),
        ]
    )
    if head_phrase is None:
        head_phrase = {
            POOL_DEFAULT_KEY: HeadPhrase(noun=("kind",), modifiers=("scale",))
        }
    prose = ProseSpec(
        scene_order=("environment", "entities", "relations"),
        entity_clause_order=tuple(entity_fields),
        head_phrase=head_phrase,
        entity_sentences=entity_sentences,
        **prose_kwargs,
    )
    return GenrePack(
        slug="fixture",
        display="Fixture",
        class_suffix="Fixture",
        kinds=("beast",),
        entity_fields=entity_fields,
        scene_fields=scene_fields,
        archetypes=archetypes or {},
        archetype_of_kind=archetype_of_kind or {},
        prose=prose,
    )


def _entity(fields: "dict[str, str]", situation: "str | None" = None) -> ResolvedEntity:
    base = {"kind": "beast"}
    base.update(fields)
    return ResolvedEntity(
        index=1, source="widgets", genre="fixture", fields=base, situation=situation
    )


LADDER = (
    Sentence(text="{subject} {copula} {situation}."),
    Sentence(text="{possessive} {form} is clad in {material}[, {hue}]."),
    Sentence(text="{pronoun} is clad in {material}[, {hue}]."),
    Sentence(text="{pronoun} has {form}[, {hue}]."),
    Sentence(text="{pronoun} shows {hue}."),
)


class ParserTests(unittest.TestCase):
    def test_each_construct_parses(self) -> None:
        self.assertEqual(
            Sentence(text="{subject}.")._segments,
            (Slot(name="subject"), Literal(text=".")),
        )
        self.assertEqual(
            Sentence(text="{a, b}.")._segments,
            (ListSlot(names=("a", "b")), Literal(text=".")),
        )
        pattern = Sentence(text="{subject}[, {form}].")
        self.assertIn("form", pattern_slots(pattern))

    def test_a_pattern_with_no_outer_slot_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Sentence(text="It is here.")

    def test_an_unbalanced_bracket_is_rejected(self) -> None:
        for text in ("[{a}", "]"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    Sentence(text=text)

    def test_a_nested_bracket_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Sentence(text="[[{a}]]")

    def test_an_empty_slot_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Sentence(text="{}")

    def test_a_list_slot_needs_two_distinct_members(self) -> None:
        with self.assertRaises(ValueError):
            Sentence(text="{a, a}")
        with self.assertRaises(ValueError):
            Sentence(text="{a,}")

    def test_a_bracket_with_no_slot_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Sentence(text="{a}[, ]")

    def test_an_unclosed_slot_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Sentence(text="{a")


class CoverageTests(unittest.TestCase):
    def test_a_solo_slot_and_a_list_member_are_unconditional(self) -> None:
        self.assertTrue(pattern_covers(Sentence(text="{pronoun} shows {hue}."), "hue"))
        self.assertTrue(
            pattern_covers(Sentence(text="{pronoun} carries {hue, material}."), "hue")
        )
        self.assertTrue(
            pattern_covers(Sentence(text="{pronoun} carries {hue, material}."), "material")
        )

    def test_an_optional_or_a_gated_slot_is_not_unconditional(self) -> None:
        self.assertFalse(
            pattern_covers(Sentence(text="{pronoun} is clad in {material}[, {hue}]."), "hue")
        )
        self.assertFalse(
            pattern_covers(Sentence(text="{pronoun} has {form} and {hue}."), "hue")
        )

    def test_a_grammar_slot_does_not_gate(self) -> None:
        self.assertTrue(
            pattern_covers(Sentence(text="{subject} {copula} {situation}."), "situation")
        )

    def test_an_orphan_only_in_an_optional_is_rejected(self) -> None:
        archetype = Archetype(
            sentences=(
                Sentence(text="{subject} {copula} {situation}."),
                Sentence(text="{pronoun} is clad in {material}[, {hue}]."),
            )
        )
        with self.assertRaises(ValueError):
            _pack(archetypes={"thing": archetype}, archetype_of_kind={"beast": "thing"})

    def test_an_orphan_gated_behind_another_slot_is_rejected(self) -> None:
        archetype = Archetype(
            sentences=(
                Sentence(text="{subject} {copula} {situation}."),
                Sentence(text="{pronoun} is clad in {material}."),
                Sentence(text="{pronoun} has {form} and {hue}."),
            )
        )
        with self.assertRaises(ValueError):
            _pack(archetypes={"thing": archetype}, archetype_of_kind={"beast": "thing"})

    def test_a_covered_set_builds(self) -> None:
        archetype = Archetype(
            sentences=(
                Sentence(text="{subject} {copula} {situation}."),
                Sentence(text="{pronoun} is clad in {material}."),
                Sentence(text="{pronoun} has {form}."),
                Sentence(text="{pronoun} carries {hue}."),
            )
        )
        pack = _pack(archetypes={"thing": archetype}, archetype_of_kind={"beast": "thing"})
        self.assertIn("thing", pack.archetypes)


class RendererTests(unittest.TestCase):
    def test_a_ladder_fires_exactly_one_rung(self) -> None:
        pack = _pack(entity_sentences=LADDER)
        text = render_entity(_entity({"form": "needle hull", "material": "titanium"}), pack)
        self.assertIn("is clad in titanium", text)
        self.assertEqual(text.count("clad in"), 1)

    def test_a_missing_form_falls_to_the_next_rung(self) -> None:
        pack = _pack(entity_sentences=LADDER)
        text = render_entity(_entity({"material": "titanium"}), pack)
        self.assertIn("It is clad in titanium.", text)
        self.assertNotIn("has ", text)

    def test_a_missing_material_falls_to_the_form_rung(self) -> None:
        pack = _pack(entity_sentences=LADDER)
        text = render_entity(_entity({"form": "needle hull"}), pack)
        self.assertIn("It has needle hull.", text)

    def test_an_unresolved_optional_leaves_no_gap(self) -> None:
        pack = _pack(entity_sentences=LADDER)
        text = render_entity(_entity({"form": "needle hull", "material": "titanium"}), pack)
        self.assertNotIn("  ", text)
        self.assertNotIn(" .", text)
        self.assertNotIn(" ,", text)

    def test_an_optional_that_resolves_is_spoken_once(self) -> None:
        pack = _pack(entity_sentences=LADDER)
        text = render_entity(
            _entity({"form": "needle hull", "material": "titanium", "hue": "oxide red"}),
            pack,
        )
        self.assertIn("oxide red", text)
        self.assertEqual(text.count("oxide red"), 1)

    def test_a_list_slot_joins_the_members_it_spoke(self) -> None:
        pack = _pack(
            entity_sentences=(
                Sentence(text="{subject} {copula} {situation}."),
                Sentence(text="{pronoun} carries {hue, material}."),
            )
        )
        text = render_entity(_entity({"hue": "oxide red", "material": "titanium"}), pack)
        self.assertIn("It carries oxide red and titanium.", text)

    def test_a_pack_with_no_patterns_uses_the_fallback(self) -> None:
        pack = _pack(entity_sentences=())
        text = render_entity(_entity({"form": "needle hull", "material": "titanium"}), pack)
        self.assertIn("needle hull", text)
        self.assertIn("titanium", text)

    def test_copula_agrees_with_a_plural_subject(self) -> None:
        pack = _pack(
            entity_sentences=(
                Sentence(text="{subject} {copula} {situation}."),
            )
        )
        text = render_entity(
            _entity({"kind": "stacked ring tiers"}, situation="drifting"), pack
        )
        self.assertIn("Stacked ring tiers are drifting", text)


class GrammarSlotTests(unittest.TestCase):
    def _archetype_pack(self, archetype: Archetype) -> GenrePack:
        return _pack(
            archetypes={"thing": archetype},
            archetype_of_kind={"beast": "thing"},
        )

    def test_pronoun_and_possessive_come_from_the_archetype(self) -> None:
        archetype = Archetype(
            pronoun="they",
            possessive="their",
            pronoun_copula="are",
            sentences=(
                Sentence(text="{subject} {copula} {situation}."),
                Sentence(text="{pronoun} {pronoun_copula} clad in {material}."),
                Sentence(text="{possessive} {form} is intact."),
                Sentence(text="{pronoun} has {hue}."),
            ),
        )
        pack = self._archetype_pack(archetype)
        text = render_entity(_entity({"material": "titanium"}), pack)
        self.assertIn("They are", text)

    def test_pronoun_copula_follows_the_pronoun_not_the_subject(self) -> None:
        archetype = Archetype(
            pronoun="they",
            possessive="their",
            pronoun_copula="are",
            sentences=(
                Sentence(text="{subject} {copula} {situation}."),
                Sentence(text="{pronoun} {pronoun_copula} marked with {hue}."),
                Sentence(text="{pronoun} is clad in {material}."),
                Sentence(text="{pronoun} has {form}."),
            ),
        )
        pack = self._archetype_pack(archetype)
        text = render_entity(_entity({"hue": "oxide red"}), pack)
        self.assertIn("They are marked with oxide red.", text)

    def test_a_singular_subject_keeps_the_singular_copula(self) -> None:
        pack = _pack(
            entity_sentences=(
                Sentence(text="{subject} {copula} {situation}."),
            )
        )
        text = render_entity(_entity({}, situation="drifting"), pack)
        self.assertIn("A beast is drifting", text)


if __name__ == "__main__":
    unittest.main()
