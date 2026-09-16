"""Todo 13 -- count grammar and the article helper.

Two halves, and the second is the one that catches real bugs:

* Table-driven unit tests over the helpers themselves.
* A sweep over the **whole shipped corpus** -- every count token crossed with
  every count-partnered value in every kind's pool, not a sample. A value that
  needs a manual exception is a data bug, and this is where it surfaces.
"""
from __future__ import annotations

import unittest

from data.genre import pool_for
from data.scifi import SCIFI_PACK
from engine.grammar import (
    AMBIGUOUS_SINGULARS,
    _MASS_HEADS,
    article_for,
    count_phrase,
    head_noun,
    is_singular_count,
    join_clauses,
    pluralize,
    with_article,
    with_article_if_singular,
)


def _count_partnered_fields() -> tuple[str, ...]:
    """The noun fields a count partners -- not the count fields themselves."""
    return tuple(
        name
        for name, spec in SCIFI_PACK.entity_fields.items()
        if spec.count_partner is not None and spec.renders_with is None
    )


def _every_value(field: str) -> tuple[tuple[str, str], ...]:
    """``(kind, value)`` for every value of ``field`` under every kind."""
    return tuple(
        (kind, value)
        for kind, values in (SCIFI_PACK.pools.get(field) or {}).items()
        for value in values
    )


class ArticleTests(unittest.TestCase):
    def test_the_plain_vowel_and_consonant_cases(self) -> None:
        self.assertEqual(with_article("saucer hull"), "a saucer hull")
        self.assertEqual(with_article("arrowhead hull"), "an arrowhead hull")
        self.assertEqual(with_article("ion thruster"), "an ion thruster")
        self.assertEqual(with_article("needle hull"), "a needle hull")

    def test_a_yoo_glide_takes_a_despite_the_vowel_letter(self) -> None:
        for phrase in ("utility manipulator arm", "uniform grey hull",
                       "one-piece canopy", "eucalyptus green"):
            with self.subTest(phrase=phrase):
                self.assertEqual(article_for(phrase), "a")

    def test_a_silent_h_takes_an_despite_the_consonant_letter(self) -> None:
        for phrase in ("hourglass hull", "honest reading"):
            with self.subTest(phrase=phrase):
                self.assertEqual(article_for(phrase), "an")

    def test_a_leading_numeral_follows_the_spoken_sound(self) -> None:
        self.assertEqual(article_for("8-metre spar"), "an")
        self.assertEqual(article_for("18-deck hull"), "an")
        self.assertEqual(article_for("11-tonne pod"), "an")
        self.assertEqual(article_for("110-metre boom"), "a")
        self.assertEqual(article_for("3-metre fin"), "a")

    def test_an_empty_phrase_does_not_produce_a_bare_article(self) -> None:
        self.assertEqual(with_article(""), "")
        self.assertEqual(with_article_if_singular(""), "")

    def test_a_plural_head_is_left_unarticled(self) -> None:
        self.assertEqual(with_article_if_singular("hazard chevrons"), "hazard chevrons")
        self.assertEqual(with_article_if_singular("cargo pod"), "a cargo pod")

    def test_an_articled_head_is_found_before_its_post_modifier(self) -> None:
        """"mane of filaments" heads on *mane*; the naive last-word test reads
        the trailing plural and drops the article."""
        self.assertEqual(with_article_if_singular("mane of filaments"), "a mane of filaments")
        self.assertEqual(
            with_article_if_singular("disc of dust and rock"), "a disc of dust and rock"
        )

    def test_a_singular_word_ending_in_s_keeps_its_article(self) -> None:
        self.assertEqual(with_article_if_singular("root-like foot mass"), "a root-like foot mass")
        self.assertEqual(with_article_if_singular("tracked chassis"), "a tracked chassis")


class HeadNounTests(unittest.TestCase):
    def test_the_head_is_the_last_word_of_a_bare_noun_phrase(self) -> None:
        self.assertEqual(head_noun("phased array panel"), "panel")
        self.assertEqual(head_noun("point-defence turret"), "turret")

    def test_the_head_stops_at_a_post_modifier(self) -> None:
        self.assertEqual(head_noun("mane of filaments"), "mane")
        self.assertEqual(head_noun("overgrown with alien flora"), "overgrown")

    def test_an_empty_phrase_has_no_head(self) -> None:
        self.assertEqual(head_noun(""), "")

    def test_a_participle_after_a_noun_ends_the_head(self) -> None:
        """D2: the participle boundary, so the article agrees with the head."""
        self.assertEqual(
            head_noun("figures moving along a walkway for scale"), "figures"
        )
        self.assertEqual(head_noun("hatch standing open at the far end"), "hatch")

    def test_a_participle_after_a_determiner_stays_in_the_head(self) -> None:
        """A suffix rule would break these: the head is the noun, not the
        participle in front of it."""
        self.assertEqual(head_noun("a parked shuttle"), "shuttle")
        self.assertEqual(head_noun("a spent booster"), "booster")
        self.assertEqual(head_noun("a docking ring"), "ring")

    def test_a_participle_after_a_noun_ends_the_head_at_the_participle(self) -> None:
        """A ring plane's head is the disc, not the noun after the participle."""
        self.assertEqual(head_noun("tilted ring disc parted by a dark gap"), "disc")
        self.assertEqual(head_noun("a hull section split by a seam"), "section")

    def test_a_directional_preposition_ends_the_head(self) -> None:
        self.assertEqual(head_noun("path toward the ridge"), "path")
        self.assertEqual(head_noun("passage into darkness"), "passage")


class PluralTests(unittest.TestCase):
    def test_the_regular_rule(self) -> None:
        self.assertEqual(pluralize("ion thruster"), "ion thrusters")
        self.assertEqual(pluralize("stalked eye"), "stalked eyes")
        self.assertEqual(pluralize("vibro-blade"), "vibro-blades")

    def test_a_sibilant_takes_es(self) -> None:
        self.assertEqual(pluralize("torpedo hatch"), "torpedo hatches")
        self.assertEqual(pluralize("sparking junction box"), "sparking junction boxes")
        self.assertEqual(pluralize("gun blister"), "gun blisters")

    def test_consonant_y_becomes_ies_and_vowel_y_does_not(self) -> None:
        self.assertEqual(pluralize("missile battery"), "missile batteries")
        self.assertEqual(pluralize("torpedo bay"), "torpedo bays")
        self.assertEqual(pluralize("mast-mounted array"), "mast-mounted arrays")

    def test_only_the_head_inflects(self) -> None:
        self.assertEqual(pluralize("mane of filaments"), "manes of filaments")

    def test_the_irregular_table_is_reachable_for_a_genre_author(self) -> None:
        """The table is a safety net for a future pack, so it must actually work
        -- but no shipped value may need it (see the corpus sweep below)."""
        self.assertEqual(pluralize("dire wolf"), "dire wolves")
        self.assertEqual(pluralize("feathered antenna"), "feathered antennae")
        self.assertEqual(pluralize("clawed foot"), "clawed feet")

    def test_an_empty_phrase_pluralizes_to_nothing(self) -> None:
        self.assertEqual(pluralize(""), "")


class CountPhraseTests(unittest.TestCase):
    def test_only_a_one_token_keeps_the_noun_singular(self) -> None:
        self.assertTrue(is_singular_count("a single"))
        for token in ("a pair of", "three", "four", "six", "eight", "a dozen",
                      "rows of", "banks of", "a ring of", "a crown of"):
            with self.subTest(token=token):
                self.assertFalse(is_singular_count(token))

    def test_the_plan_examples(self) -> None:
        self.assertEqual(count_phrase("a single", "ion thruster"), "a single ion thruster")
        self.assertEqual(count_phrase("a pair of", "ion thruster"), "a pair of ion thrusters")
        self.assertEqual(count_phrase("six", "ion thruster"), "six ion thrusters")
        self.assertEqual(count_phrase("a crown of", "stalked eye"), "a crown of stalked eyes")
        self.assertEqual(count_phrase("banks of", "ion thruster"), "banks of ion thrusters")

    def test_an_adjective_goes_inside_so_the_head_still_inflects(self) -> None:
        self.assertEqual(
            count_phrase("six", "ion thruster", "cyan"), "six cyan ion thrusters"
        )
        self.assertEqual(
            count_phrase("a single", "ion thruster", "cyan"), "a single cyan ion thruster"
        )

    def test_no_count_voices_the_bare_plural(self) -> None:
        """Asserting "an ion thruster" would claim a count the user never asked
        for, which is the same class of mistake as asserting an absence."""
        self.assertEqual(count_phrase(None, "ion thruster"), "ion thrusters")
        self.assertEqual(count_phrase(None, "ion thruster", "cyan"), "cyan ion thrusters")

    def test_an_empty_noun_yields_nothing_rather_than_a_dangling_count(self) -> None:
        self.assertEqual(count_phrase("six", ""), "")
        self.assertEqual(count_phrase(None, ""), "")


class JoinTests(unittest.TestCase):
    def test_empty_clauses_are_dropped(self) -> None:
        self.assertEqual(join_clauses(["a needle hull", "", "gunmetal grey"]),
                         "a needle hull, gunmetal grey")

    def test_no_clauses_yield_an_empty_string(self) -> None:
        self.assertEqual(join_clauses([]), "")


class CorpusSweepTests(unittest.TestCase):
    """The whole corpus, not a sample -- the plan's Todo 13 acceptance criterion.

    Every count-partnered value in every kind's pool, crossed with every count
    token. A single failure here is a **data** bug: rename the value rather than
    teaching the engine about it.
    """

    def test_the_pack_actually_has_count_partnered_fields(self) -> None:
        """Guards the sweeps below against passing vacuously."""
        fields = _count_partnered_fields()
        self.assertTrue(fields)
        for field in fields:
            with self.subTest(field=field):
                self.assertTrue(_every_value(field))

    def test_no_count_partnered_value_needs_the_irregular_table(self) -> None:
        offenders = [
            f"{field}[{kind}]: {value!r} (head {head_noun(value)!r})"
            for field in _count_partnered_fields()
            for kind, value in _every_value(field)
            if head_noun(value).lower() in AMBIGUOUS_SINGULARS
        ]
        self.assertEqual(
            offenders,
            [],
            "these values pluralize irregularly, so two pools sharing the head "
            "would want different plurals. Rename the value in data/scifi.py; do "
            "not add an exception to IRREGULAR_PLURALS",
        )

    def test_every_count_partnered_value_is_a_bare_noun_phrase(self) -> None:
        """Its head must be its last word, so the engine can inflect it without
        parsing. A post-modifier ("mane of filaments") belongs in a field the
        engine never counts."""
        offenders = [
            f"{field}[{kind}]: {value!r}"
            for field in _count_partnered_fields()
            for kind, value in _every_value(field)
            if head_noun(value) != value.split()[-1]
        ]
        self.assertEqual(offenders, [])

    def test_every_count_partnered_value_is_authored_singular(self) -> None:
        offenders = [
            f"{field}[{kind}]: {value!r}"
            for field in _count_partnered_fields()
            for kind, value in _every_value(field)
            if pluralize(value) == value
        ]
        self.assertEqual(
            offenders, [], "authored plural: the engine pluralizes, so author the singular"
        )

    def test_every_count_token_crossed_with_every_value_composes(self) -> None:
        """The full cross product. Asserts the phrase is well-formed: it opens
        with the token, ends with an inflected head, and never doubles a plural.
        """
        tokens = pool_for(SCIFI_PACK, "emitter_count")
        self.assertTrue(tokens)
        for field in _count_partnered_fields():
            for kind, value in _every_value(field):
                for token in tokens:
                    phrase = count_phrase(token, value)
                    with self.subTest(field=field, kind=kind, value=value, token=token):
                        self.assertTrue(phrase.startswith(f"{token} "))
                        expected = value if is_singular_count(token) else pluralize(value)
                        self.assertEqual(phrase, f"{token} {expected}")

    def test_every_articled_value_gets_a_sane_article(self) -> None:
        """``aperture``, ``extras`` and ``form`` are voiced with an article, so
        sweep them too: an article is chosen for every value and never emitted
        bare."""
        for field in ("form", "aperture", "extras"):
            for kind, value in _every_value(field):
                with self.subTest(field=field, kind=kind, value=value):
                    rendered = with_article_if_singular(value)
                    self.assertTrue(rendered)
                    self.assertNotIn("  ", rendered)
                    self.assertFalse(rendered.startswith("a  "))


class MassNounTests(unittest.TestCase):
    """A mass noun takes no article; a singular count noun needs one."""

    def test_a_mass_head_is_left_unarticled(self) -> None:
        for phrase in (
            "pitted erosion",
            "verdigris patina",
            "fine fractal etching",
            "banded strata layering",
            "hairline fracture crazing",
        ):
            with self.subTest(phrase=phrase):
                self.assertEqual(with_article_if_singular(phrase), phrase)

    def test_a_singular_count_head_still_takes_its_article(self) -> None:
        for phrase in ("panel-line grid", "welded patchwork"):
            with self.subTest(phrase=phrase):
                self.assertTrue(with_article_if_singular(phrase).startswith(("a ", "an ")))

    def test_a_plural_head_still_drops_the_article(self) -> None:
        self.assertEqual(with_article_if_singular("stacked ring tiers"), "stacked ring tiers")

    def test_the_mass_heads_are_lowercase_words(self) -> None:
        self.assertTrue(_MASS_HEADS)
        for head in _MASS_HEADS:
            with self.subTest(head=head):
                self.assertEqual(head, head.lower())
                self.assertNotIn(" ", head)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
