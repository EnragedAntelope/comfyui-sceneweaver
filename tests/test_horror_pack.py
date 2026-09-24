"""The horror pack: sound data, coherent scenes on both paths, the gore filter, and wiring.

The gore filter is the genre's promise to a first-time user: an untouched node shows
no graphic content. These tests hold it to that on the unwired path, on the wired
path (where the Scene Entity node has no filter of its own), and through the labels
the node face shows.
"""
from __future__ import annotations

import logging
import random
import re
import unittest

import data.genre as G
from data import horror as H
from data.fantasy import FANTASY_PACK
from data.horror import HORROR_PACK
from data.scifi import SCIFI_PACK
from engine.foreign import guest_fits_place
from engine.scene import generate_entity, generate_scene
from scripts.builtin_options import builtin_pools
from tests.boundary import negation_findings, rendering_findings
from tests.validate_data import validate

_FOREIGN = re.compile(r"\b(" + "|".join(HORROR_PACK.foreign_nouns) + r")\b")
_REST = {"entombed", "dormant", "abandoned", "boarded-up", "slumbering"}


def _gore_values() -> set[str]:
    """Every value the pack tags as graphic, across every tag-scoped field."""
    return {
        value for table in HORROR_PACK.tags.values() for value, tag in table.items()
        if tag == G.TAG_CONFLICT_ONLY
    }


def _classes(text: str, document: dict) -> set[str]:
    """Every incoherence class one scene falls into."""
    found: set[str] = set()
    place = document["environment"]
    for entity in document["entities"]:
        situation = entity.get("situation") or ""
        if not situation:
            found.add("no-situation")
        if entity.get("condition") in _REST and situation not in H.DORMANT_ACTS:
            found.add("at-rest-but-acting")
        if entity.get("form") and not G.form_can_stand(HORROR_PACK, place, entity["form"]):
            found.add("body-cannot-stand")
        if entity.get("subkind") in H._BARE_BONE and entity.get("condition") in H._FLESH_CONDITIONS:
            found.add("skeleton-with-flesh")
    if _FOREIGN.search(text.lower()):
        found.add("foreign-genre-word")
    if rendering_findings(text) or negation_findings(text):
        found.add("rendering-or-negation")
    return found


def _sweep(count: int, scene_filter: str, seed: int = 917):
    rng = random.Random(seed)
    logging.disable(logging.CRITICAL)
    try:
        for index in range(count):
            entity_seed, scene_seed = rng.randrange(2**48), rng.randrange(2**48)
            wired = {1: generate_entity(entity_seed, HORROR_PACK)[1]} if index % 2 else {}
            yield generate_scene(
                scene_seed, HORROR_PACK, wired_entities=wired, entity_count=1 + index % 2,
                scene_filter=scene_filter,
            )
    finally:
        logging.disable(logging.NOTSET)


class HorrorDataTests(unittest.TestCase):
    def test_the_validator_finds_nothing(self) -> None:
        self.assertEqual(validate(HORROR_PACK).failures, [])

    def test_the_ast_reader_agrees_with_the_pack_field_for_field(self) -> None:
        read = builtin_pools(pack="horror")
        for field_name, by_key in HORROR_PACK.pools.items():
            with self.subTest(field=field_name):
                self.assertEqual(
                    {key: tuple(values) for key, values in by_key.items()}, read.get(field_name)
                )

    def test_every_situation_is_in_a_bucket(self) -> None:
        values = {v for pool in H.SITUATION_POOLS.values() for v in pool}
        self.assertEqual(values - set(H.SITUATION_TIERS), set())

    def test_the_pack_declares_graphic_values(self) -> None:
        """A gore filter with nothing to hide is decoration."""
        self.assertTrue(_gore_values() & set(H.SITUATION_TIERS))
        self.assertTrue(_gore_values() - set(H.SITUATION_TIERS))


class HorrorCoherenceTests(unittest.TestCase):
    """A seeded sweep over both paths; every class must read zero."""

    def test_no_class_fires_on_either_path(self) -> None:
        hits: dict[str, list[str]] = {}
        for text, document in _sweep(400, "Any"):
            self.assertTrue(text.startswith("A horror scene"), text[:40])
            for name in _classes(text, document):
                hits.setdefault(name, []).append(text[:160])
        self.assertEqual(hits, {}, hits)


class GoreFilterTests(unittest.TestCase):
    def test_the_node_offers_the_genre_labels_and_starts_on_no_gore(self) -> None:
        definitions = G.build_field_definitions(HORROR_PACK, G.SCENE_NODE_SLOTS)
        control = definitions[G.SCENE_FILTER_KEY]
        self.assertEqual(control.options, ("No gore", "Any", "Gore only"))
        self.assertEqual(control.default, "No gore")

    def test_the_other_genres_keep_their_labels(self) -> None:
        for pack in (SCIFI_PACK, FANTASY_PACK):
            control = G.build_field_definitions(pack, G.SCENE_NODE_SLOTS)[G.SCENE_FILTER_KEY]
            with self.subTest(pack=pack.slug):
                self.assertEqual(control.options, G.SCENE_FILTERS)
                self.assertEqual(control.default, G.DEFAULT_SCENE_FILTER)

    def test_no_gore_shows_no_graphic_value_on_either_path(self) -> None:
        gore = _gore_values()
        for text, document in _sweep(400, "No gore"):
            self.assertEqual(document["_meta"]["filter_applied"], "No gore")
            for entity in document["entities"]:
                shown = {value for value in entity.values() if isinstance(value, str)} & gore
                self.assertEqual(shown, set(), text)

    def test_gore_only_does_reach_graphic_values(self) -> None:
        gore = _gore_values()
        seen = set()
        for _text, document in _sweep(400, "Gore only"):
            for entity in document["entities"]:
                seen |= {value for value in entity.values() if isinstance(value, str)} & gore
        self.assertTrue(seen)

    def test_a_label_and_its_canonical_name_are_the_same_filter(self) -> None:
        self.assertEqual(G.canonical_scene_filter(HORROR_PACK, "No gore"), "Peaceful")
        self.assertEqual(G.canonical_scene_filter(HORROR_PACK, "Peaceful"), "Peaceful")
        with self.assertRaises(ValueError):
            G.canonical_scene_filter(SCIFI_PACK, "No gore")

    def test_a_pack_must_label_every_filter(self) -> None:
        with self.assertRaises(ValueError):
            G.GenrePack(**{
                **{f.name: getattr(HORROR_PACK, f.name) for f in G.dataclass_fields(HORROR_PACK)},
                "scene_filter_labels": {"No gore": "Peaceful", "Any": "Any"},
            })


class HorrorCrossGenreTests(unittest.TestCase):
    def test_a_horror_entity_in_a_fantasy_scene(self) -> None:
        for seed in range(20):
            _text, payload = generate_entity(seed, HORROR_PACK)
            text, document = generate_scene(seed, FANTASY_PACK, wired_entities={1: payload},
                                            entity_count=1)
            with self.subTest(seed=seed):
                self.assertTrue(text.startswith("A fantasy scene"))
                self.assertEqual(document["entities"][0]["genre"], "horror")

    def test_a_scifi_entity_in_a_horror_scene(self) -> None:
        for seed in range(20):
            _text, payload = generate_entity(seed, SCIFI_PACK)
            text, document = generate_scene(seed, HORROR_PACK, wired_entities={1: payload},
                                            entity_count=1)
            with self.subTest(seed=seed):
                self.assertTrue(text.startswith("A horror scene"))
                self.assertEqual(document["entities"][0]["genre"], "scifi")

    def test_a_guest_fire_elemental_is_never_placed_underwater(self) -> None:
        # A drowned church is ``aqueous``, which the guest's own genre pairs
        # against ``combustion``; a fire elemental burned there (#597).
        payload = next(
            payload for seed in range(2000)
            for _text, payload in [generate_entity(seed, FANTASY_PACK)]
            if payload["fields"].get("subkind") == "fire elemental"
        )
        for primary_only, strict in ((True, True), (False, True), (False, False)):
            self.assertFalse(guest_fits_place(
                FANTASY_PACK, HORROR_PACK, payload["fields"], "drowned church nave",
                primary_only=primary_only, strict=strict,
            ))
        self.assertTrue(guest_fits_place(
            FANTASY_PACK, HORROR_PACK, payload["fields"], "abandoned chapel"
        ))

    def test_a_guest_drops_gear_the_host_place_cannot_hold(self) -> None:
        # A "rain-soaked" coat brought rain indoors; the host has no sky there.
        seen = 0
        for seed in range(300):
            _text, payload = generate_entity(seed, HORROR_PACK)
            if "rain-soaked" not in " ".join(str(v) for v in payload["fields"].values()):
                continue
            seen += 1
            _t, document = generate_scene(seed, SCIFI_PACK, wired_entities={1: payload},
                                          widgets={"environment": "crew quarters"}, entity_count=1)
            with self.subTest(seed=seed):
                values = " ".join(str(v) for v in document["entities"][0].values())
                self.assertNotIn("rain-soaked", values)
        self.assertGreater(seen, 0)


if __name__ == "__main__":
    unittest.main()
