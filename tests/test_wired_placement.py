"""The place adapts to a wired subject before the subject adapts to the place."""
from __future__ import annotations

import random
import unittest

from data.fantasy import FANTASY_PACK
from data.genre import affordances_of
from data.horror import HORROR_PACK
from data.scifi import SCIFI_PACK
from engine.scene import JSON_SCHEMA_VERSION, generate_entity, generate_scene
from nodes.readout import scene_readout


def _drawn_vehicles(limit: int):
    """Scene Entity payloads whose kind was drawn as a surface vehicle."""
    found = 0
    for seed in range(2000):
        _text, payload = generate_entity(seed, SCIFI_PACK)
        if payload["fields"].get("kind") == "surface vehicle":
            found += 1
            yield seed, payload
            if found >= limit:
                return


class WiredPlacementTests(unittest.TestCase):
    def test_the_scene_keeps_the_subject_the_entity_node_showed(self) -> None:
        rng = random.Random(4242)
        kept_type = kept_form = total = 0
        for _ in range(600):
            _text, payload = generate_entity(rng.randrange(2**48), SCIFI_PACK)
            _text, document = generate_scene(
                rng.randrange(2**48), SCIFI_PACK, wired_entities={1: payload}, entity_count=1
            )
            record = document["entities"][0]
            total += 1
            kept_type += record["subkind"] == payload["fields"]["subkind"]
            kept_form += record["form"] == payload["fields"]["form"]
        self.assertGreaterEqual(kept_type / total, 0.98, f"type kept {kept_type}/{total}")
        self.assertGreaterEqual(kept_form / total, 0.95, f"form kept {kept_form}/{total}")

    def test_a_locked_place_re_draws_a_drawn_subject_that_cannot_exist_there(self) -> None:
        seen = 0
        for seed, payload in _drawn_vehicles(20):
            seen += 1
            _text, document = generate_scene(
                seed, SCIFI_PACK, widgets={"environment": "deep interstellar void"},
                wired_entities={1: payload}, entity_count=1,
            )
            record = document["entities"][0]
            with self.subTest(seed=seed):
                self.assertNotEqual(record["kind"], "surface vehicle")
                self.assertIsNotNone(record["form"])
        self.assertGreater(seen, 0)

    def test_re_drawn_wired_fields_are_recorded_and_shown(self) -> None:
        self.assertEqual(JSON_SCHEMA_VERSION, 3)
        for seed, payload in _drawn_vehicles(20):
            text, document = generate_scene(
                seed, SCIFI_PACK, widgets={"environment": "deep interstellar void"},
                wired_entities={1: payload}, entity_count=1,
            )
            redrawn = document["_meta"]["redrawn_fields"].get("1", [])
            self.assertIn("kind", redrawn)
            if not document["_meta"]["warnings"]:
                self.assertIn("re-drawn to fit", scene_readout(document, text)[-1])
            return
        self.fail("no drawn surface vehicle found to wire")

    def test_a_wired_entity_with_no_kind_yields_to_its_slot(self) -> None:
        for seed in range(30):
            _text, payload = generate_entity(seed, SCIFI_PACK, widgets={"kind": "None"})
            self.assertIsNone(payload["fields"]["kind"])
            _text, document = generate_scene(
                seed + 1000, SCIFI_PACK, wired_entities={1: payload}, entity_count=1
            )
            record = document["entities"][0]
            with self.subTest(seed=seed):
                self.assertIsNotNone(record["kind"])
                self.assertTrue(
                    any("has no kind" in message
                        for message in document["_meta"]["warnings"]),
                    document["_meta"]["warnings"],
                )


def _guest(pack, kind: str, subkind: str) -> dict:
    """A Scene Entity payload of ``subkind``, drawn (not locked) under a locked kind."""
    for seed in range(4000):
        _text, payload = generate_entity(seed, pack, widgets={"kind": kind})
        if payload["fields"].get("subkind") == subkind:
            return payload
    raise AssertionError(f"no {subkind} drawn")


class CrossGenrePlacementTests(unittest.TestCase):
    """Round XXV: a guest keeps its habitat even where the host has no word for it."""

    def _places(self, guest_pack, kind, subkind, host):
        payload = _guest(guest_pack, kind, subkind)
        for seed in range(25):
            _text, document = generate_scene(seed, host, wired_entities={1: payload}, entity_count=1)
            yield affordances_of(host, document["environment"]), document["environment"]

    def test_a_planet_in_a_genre_without_space_hangs_in_the_sky(self) -> None:
        # A rogue planet was put in a manor ballroom (#1136).
        for afforded, place in self._places(SCIFI_PACK, "celestial body", "rogue planet", HORROR_PACK):
            with self.subTest(place=place):
                self.assertIn("sky", afforded)

    def test_a_flying_ship_in_a_genre_without_gravity_words_still_flies(self) -> None:
        # Horror has no word for gravity, so a cloud skiff failed every strict placement (#1131).
        for afforded, place in self._places(FANTASY_PACK, "vessel", "cloud skiff", HORROR_PACK):
            with self.subTest(place=place):
                self.assertIn("sky", afforded)

    def test_a_guest_no_host_place_lets_stand_keeps_its_needs(self) -> None:
        # A war galley went into a cloud deck (#1036), a sunken submersible into an apothecary (#1089).
        for afforded, place in self._places(FANTASY_PACK, "vessel", "war galley", SCIFI_PACK):
            with self.subTest(place=place):
                self.assertIn("shoreline", afforded)
        for afforded, place in self._places(SCIFI_PACK, "wreck", "sunken submersible", FANTASY_PACK):
            with self.subTest(place=place):
                self.assertIn("submerged", afforded)

    def test_a_keepsake_is_not_set_in_an_open_landscape(self) -> None:
        # A cursed box in an open dune sea was drawn the size of a house (#899).
        for host in (SCIFI_PACK, FANTASY_PACK):
            payload = _guest(HORROR_PACK, "cursed object", "puzzle box")
            for seed in range(25):
                _text, document = generate_scene(seed, host, wired_entities={1: payload}, entity_count=1)
                with self.subTest(host=host.slug, place=document["environment"]):
                    self.assertNotIn(
                        "open-landscape", host.value_traits["environment"].get(document["environment"], ())
                    )
