"""Todo 11 -- the content-filter tag rule, in both directions.

The rule has two halves and both are easy to half-break:

* **Exactly one tag on every value of the five tagged fields.** An untagged
  value is not an error at render time -- ``tag_for`` reads it as neutral on
  purpose, so a gap costs a value its filtering rather than its existence -- and
  that is precisely why it needs a test. Nothing else would ever notice.
* **Nothing else is tagged.** A tag on ``environment`` or on a colour would make
  the filter silently shrink pools it has no opinion about, and the symptom
  ("Peaceful scenes are all set in orbit") looks nothing like the cause.

The third assertion is the one the plan singles out: under Peaceful the
``armament`` pool masks to *empty* for every kind. That is the whole no-negation
mechanism -- the field resolves to ``None`` and the prose says nothing about
weapons, rather than saying the subject is unarmed.
"""
from __future__ import annotations

import unittest

from data.genre import (
    CONTENT_TAGS,
    SCENE_FILTERS,
    TAG_CONFLICT_ONLY,
    TAG_NEUTRAL,
    TAG_PEACEFUL_ONLY,
    allowed_tags,
    filtered_pool,
    pool_for,
    pool_options,
)
from data.scifi import SCIFI_PACK, _tag_map

#: Below this a filtered kind stops feeling random and starts repeating. It is a
#: floor on the *masked* pool, so it catches a tagging pass that guts a kind --
#: which the unmasked pool-size check in Todo 10 cannot see.
MIN_FILTERED_VALUES = 8

#: The fields the plan names, and the only ones that may appear in ``tags``.
TAGGED_FIELDS = frozenset({"subkind", "armament", "aperture", "situation", "relation"})


def _tagged_field_names(pack) -> frozenset[str]:
    specs = {**pack.entity_fields, **pack.scene_fields}
    return frozenset(name for name, spec in specs.items() if spec.tag_scoped)


class TagVocabularyTests(unittest.TestCase):
    def test_the_vocabulary_is_frozen_at_three(self) -> None:
        self.assertEqual(
            CONTENT_TAGS,
            frozenset({TAG_NEUTRAL, TAG_PEACEFUL_ONLY, TAG_CONFLICT_ONLY}),
        )

    def test_the_declared_fields_are_the_ones_the_plan_names(self) -> None:
        self.assertEqual(_tagged_field_names(SCIFI_PACK), TAGGED_FIELDS)

    def test_exactly_one_tag_on_every_value_of_every_tagged_field(self) -> None:
        for name in sorted(TAGGED_FIELDS):
            with self.subTest(field=name):
                tagged = SCIFI_PACK.tags[name]
                self.assertEqual(
                    set(tagged), set(pool_options(SCIFI_PACK, name)),
                    "every value of a tagged field carries a tag, and every tag "
                    "names a value that exists",
                )
                for value, tag in tagged.items():
                    self.assertIn(tag, CONTENT_TAGS, f"{name}={value!r}")

    def test_nothing_else_is_tagged(self) -> None:
        self.assertEqual(set(SCIFI_PACK.tags), set(TAGGED_FIELDS))

    def test_all_three_tags_are_actually_used(self) -> None:
        """Not per field -- ``subkind`` deliberately has no peaceful_only value --
        but across the pack, or one third of the vocabulary is dead weight."""
        used = {tag for tagged in SCIFI_PACK.tags.values() for tag in tagged.values()}
        self.assertEqual(used, CONTENT_TAGS)

    def test_a_typo_in_a_tag_list_is_rejected(self) -> None:
        """The generator raises rather than silently ignoring a name that is not
        a real value -- otherwise the value it meant to tag keeps drawing under
        the wrong filter, and the only symptom is 'Peaceful looks violent'."""
        with self.assertRaises(ValueError):
            _tag_map(("cargo maw",), conflict=("carg maw",))
        with self.assertRaises(ValueError):
            _tag_map(("cargo maw",), conflict=("cargo maw",), peaceful=("cargo maw",))


class FilterMaskTests(unittest.TestCase):
    def test_peaceful_describes_no_weapons_at_all(self) -> None:
        """The plan's key subtlety: absence by omission. The pool masks to empty,
        so the field resolves to None and the prose stays silent -- it never
        emits 'unarmed', which would put a weapon in the image."""
        for kind in SCIFI_PACK.kinds:
            with self.subTest(kind=kind):
                self.assertEqual(
                    filtered_pool(SCIFI_PACK, "armament", kind, "Peaceful"), ()
                )

    def test_conflict_and_any_keep_the_weapons(self) -> None:
        for kind in SCIFI_PACK.kinds:
            for scene_filter in ("Any", "Conflict"):
                with self.subTest(kind=kind, scene_filter=scene_filter):
                    self.assertEqual(
                        filtered_pool(SCIFI_PACK, "armament", kind, scene_filter),
                        pool_for(SCIFI_PACK, "armament", kind),
                    )

    def test_the_armament_count_is_never_voiced_without_its_noun(self) -> None:
        """Peaceful leaves ``armament`` empty; its count is composed into that
        clause rather than heading one, so nothing can render "a pair of" with
        nothing to count."""
        spec = SCIFI_PACK.entity_fields["armament_count"]
        self.assertEqual(spec.renders_with, "armament")
        self.assertNotIn("armament_count", SCIFI_PACK.prose.entity_clause_order)

    def test_every_other_tagged_field_survives_every_filter(self) -> None:
        """Armament is the one field a filter may empty. Anything else emptying
        would silently drop a whole clause from every scene."""
        for name in sorted(TAGGED_FIELDS - {"armament"}):
            for kind in SCIFI_PACK.kinds:
                for scene_filter in SCENE_FILTERS:
                    with self.subTest(field=name, kind=kind, scene_filter=scene_filter):
                        values = filtered_pool(SCIFI_PACK, name, kind, scene_filter)
                        floor = MIN_FILTERED_VALUES if name == "situation" else 1
                        self.assertGreaterEqual(len(values), floor)

    def test_the_cross_genre_situation_pool_survives_every_filter(self) -> None:
        for scene_filter in SCENE_FILTERS:
            with self.subTest(scene_filter=scene_filter):
                self.assertGreaterEqual(
                    len(filtered_pool(SCIFI_PACK, "situation", "wyrm", scene_filter)),
                    MIN_FILTERED_VALUES,
                )

    def test_an_untouched_field_is_returned_whole(self) -> None:
        """One place decides what the filter reaches: the field's own
        ``tag_scoped`` declaration."""
        for name in ("environment", "condition", "scale", "form", "primary_color"):
            with self.subTest(field=name):
                for scene_filter in SCENE_FILTERS:
                    self.assertEqual(
                        filtered_pool(SCIFI_PACK, name, "starship", scene_filter),
                        pool_for(SCIFI_PACK, name, "starship"),
                    )

    def test_each_filter_admits_the_tags_it_should(self) -> None:
        self.assertEqual(allowed_tags("Any"), CONTENT_TAGS)
        self.assertNotIn(TAG_CONFLICT_ONLY, allowed_tags("Peaceful"))
        self.assertNotIn(TAG_PEACEFUL_ONLY, allowed_tags("Conflict"))
        self.assertIn(TAG_NEUTRAL, allowed_tags("Peaceful"))
        self.assertIn(TAG_NEUTRAL, allowed_tags("Conflict"))

    def test_an_unknown_filter_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            allowed_tags("Violent")


class NoNegationTests(unittest.TestCase):
    """The filter's whole reason for existing: a masked pool must not be
    replaced anywhere by a value that names what is missing."""

    NEGATIONS = ("unarmed", "no weapon", "without", "lacking", "devoid", "weaponless")

    def test_no_pool_value_negates(self) -> None:
        for name, by_kind in SCIFI_PACK.pools.items():
            for kind, values in by_kind.items():
                for value in values:
                    for negation in self.NEGATIONS:
                        with self.subTest(field=name, kind=kind, value=value):
                            self.assertNotIn(negation, value.lower())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
