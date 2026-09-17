"""Proof that ``scripts/concern_flags_0916.py`` actually fires.

A regex that has never been watched match is a claim, not a check. Every flag gets a
planted positive built by hand, plus one clean scene that must report nothing at all, and
the shipped pack must report none of them over a seeded sweep.
"""
from __future__ import annotations

import random
import unittest

from data.scifi import SCIFI_PACK
from engine.scene import generate_entity, generate_scene
from scripts.concern_flags_0916 import STRUCTURAL_0916, flags_0916

ORBIT = "high polar orbit"
GROUND = "frozen methane flats"
ROOM = "crew commons"


def _doc(entity=None, environment="", context=""):
    record = {
        "kind": None, "subkind": None, "form": None, "situation": None,
        "material": None, "extras": None, "appendages": None, "armament": None,
        "emitters": None, "aperture": None, "sensors": None, "markings": None,
        "surface_detail": None, "scale": None, "condition": None,
    }
    record.update(entity or {})
    return {"entities": [record], "environment": environment, "context": context}


PLANTED: tuple[tuple[str, dict, str], ...] = (
    ("dead-state-on-live-noun",
     _doc({"kind": "starship", "condition": "crashed"}, GROUND), "a crashed starship"),
    ("wreck-lit-or-acting",
     _doc({"kind": "wreck", "emitters": "cracked reactor window"}, GROUND), "a lit wreck"),
    ("context-stance-verb",
     _doc({"kind": "starship"}, ORBIT, "ladder rising into the dark"),
     "a starship. a ladder rising into the dark crowds in close behind it"),
    ("sewn-patch-word",
     _doc({"kind": "spacefarer"}, GROUND), "a navigator fighting a breach with a patch kit"),
    ("cable-on-wreck",
     _doc({"kind": "wreck", "appendages": "dangling conduit bundle"}, GROUND), "a wreck"),
    ("box-part-word",
     _doc({"kind": "robot or mech"}, GROUND), "a drone. it carries a spare battery pack"),
    ("construction-word",
     _doc({"kind": "robot or mech"}, GROUND), "a mining loader with a hydraulic breaker arm"),
    ("creature-rigging-word",
     _doc({"kind": "alien creature"}, ORBIT), "a creature with a pair of folding sail vanes"),
    ("open-fire",
     _doc({"kind": "surface vehicle", "situation": "catching fire after a hard impact"},
          ROOM), "a drop pod catching fire"),
    ("machine-breaks-itself",
     _doc({"kind": "robot or mech", "situation": "losing a tool arm in a hard strike"},
          ROOM), "an android losing a tool arm"),
    ("craft-prey-small-or-indoors",
     _doc({"kind": "alien creature", "scale": "tiny",
           "situation": "snaring a passing drone"}, GROUND), "a tiny creature"),
    ("meal-word",
     _doc({"kind": "spacefarer", "situation": "sharing a meal with an alien delegation"},
          GROUND), "a meal"),
    ("ice-ejection-context",
     _doc({"kind": "starship"}, ORBIT, "long trail of frozen vapour"), "a starship"),
    ("crew-beside-creature",
     _doc({"kind": "alien creature"}, ROOM, "crew working at the far end"), "a creature"),
    ("station-exhaust",
     _doc({"kind": "space station", "emitters": "station keeping thruster"}, ORBIT),
     "a station"),
    ("thrust-twice",
     _doc({"kind": "starship", "emitters": "fusion torch nozzle",
           "situation": "decelerating on a long plume"}, ORBIT), "a starship"),
    ("earth-arthropod-skin",
     _doc({"kind": "alien creature", "subkind": "arachnoid",
           "material": "chitinous carapace"}, GROUND), "an arachnoid"),
    ("cockpit-on-android",
     _doc({"kind": "robot or mech", "subkind": "android", "aperture": "cockpit hatch"},
          ROOM), "an android with a cockpit hatch"),
)


class PlantedPositiveTests(unittest.TestCase):
    def test_every_class_has_a_planted_positive(self) -> None:
        self.assertEqual({name for name, _doc_, _text in PLANTED}, set(STRUCTURAL_0916))

    def test_each_planted_positive_fires_its_own_class(self) -> None:
        for name, document, text in PLANTED:
            with self.subTest(flag=name):
                self.assertIn(name, flags_0916(SCIFI_PACK, document, text.lower()))

    def test_a_clean_scene_reports_nothing(self) -> None:
        document = _doc({"kind": "starship", "situation": "settling into a parking orbit",
                         "emitters": "beacon strip"}, ORBIT, "scatter of navigation beacons")
        text = ("a starship is settling into a parking orbit. "
                "beyond it, a scatter of navigation beacons is visible.")
        self.assertEqual(flags_0916(SCIFI_PACK, document, text), [])


class ShippedPackTests(unittest.TestCase):
    """The pack the 916 batch was replayed against must not produce any class again."""

    def test_no_class_fires_on_either_path(self) -> None:
        rng = random.Random(916)
        hits: dict[str, list[str]] = {}
        for index in range(600):
            entity_seed, scene_seed = rng.randrange(2**48), rng.randrange(2**48)
            wired = {1: generate_entity(entity_seed, SCIFI_PACK)[1]} if index % 2 else {}
            text, document = generate_scene(
                scene_seed, SCIFI_PACK, wired_entities=wired, entity_count=1
            )
            for name in flags_0916(SCIFI_PACK, document, text):
                hits.setdefault(name, []).append(text[:160])
        self.assertEqual(hits, {}, hits)


if __name__ == "__main__":
    unittest.main()
