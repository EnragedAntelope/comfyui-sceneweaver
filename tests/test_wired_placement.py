"""The place adapts to a wired subject before the subject adapts to the place."""
from __future__ import annotations

import random
import unittest

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
