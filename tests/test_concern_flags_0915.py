"""Proof that ``scripts/concern_flags_0915.py`` actually fires.

A regex that has never been watched match is a claim, not a check -- and a regex is
exactly what a shell heredoc once corrupted. So every flag gets a planted positive
built by hand, plus one clean scene that must report nothing at all.
"""
from __future__ import annotations

import unittest

from data.scifi import SCIFI_PACK
from scripts.concern_flags_0915 import STRUCTURAL_0915, flags_0915

#: Places whose affordances each planted positive needs.
ORBIT = "high polar orbit"
TRENCH = "deep ocean trench of a water world"
CLOUD_DECK = "upper cloud deck of a gas giant"
GROUND = "frozen methane flats"
DUST = "red dust plain of a dead world"
ROOM = "crew commons"


def _doc(entity=None, environment="", context=""):
    record = {
        "kind": None, "subkind": None, "form": None, "situation": None,
        "material": None, "extras": None, "appendages": None, "armament": None,
        "armament_count": None, "emitters": None, "aperture": None,
        "surface_detail": None, "scale": None, "condition": None,
    }
    record.update(entity or {})
    return {"entities": [record], "environment": environment, "context": context}


#: ``(flag, doc, text)`` -- one planted positive per class.
PLANTED: tuple[tuple[str, dict, str], ...] = (
    ("civil-machine-armed",
     _doc({"kind": "robot or mech", "subkind": "repair drone",
           "armament": "arc welding port"}, GROUND),
     "a repair drone with an arc welding port"),
    ("blade-part-on-noncombat",
     _doc({"kind": "robot or mech", "subkind": "repair drone",
           "appendages": "folding blade arm"}, GROUND),
     "a repair drone with a folding blade arm"),
    ("machine-weapon-swarm",
     _doc({"kind": "robot or mech", "subkind": "combat mech",
           "armament_count": "four"}, GROUND),
     "a combat mech with four weapons"),
    ("jets-on-grounded-body",
     _doc({"kind": "surface vehicle", "subkind": "rover",
           "emitters": "twin thruster nozzles"}, GROUND),
     "a rover with twin thruster nozzles"),
    ("tracks-on-trackless",
     _doc({"kind": "surface vehicle", "subkind": "hovercraft",
           "appendages": "broad tracks"}, GROUND),
     "a hovercraft on broad tracks"),
    ("legs-on-legless",
     _doc({"kind": "robot or mech", "subkind": "medical automaton",
           "form": "tracked chassis", "appendages": "two legs"}, GROUND),
     "a medical automaton on two legs"),
    ("station-as-building",
     _doc({"kind": "space station"}, ORBIT),
     "a station out in open space. a stepped tower of modules"),
    ("space-without-float-cue",
     _doc({"kind": "starship"}, ORBIT),
     "a freighter adrift"),
    ("underwater-without-cue",
     _doc({"kind": "surface vehicle", "subkind": "submersible"}, TRENCH),
     "a submersible cruising"),
    ("cloud-deck-without-cue",
     _doc({"kind": "surface vehicle", "subkind": "high-altitude glider"}, CLOUD_DECK),
     "a glider cruising"),
    ("crowd-actor",
     _doc({"kind": "starship", "situation": "as the crew backs away"}, ORBIT),
     "a starship going dark"),
    ("fire-word-not-fire",
     _doc({"kind": "starship", "situation": "taking fire from a ridge line"}, GROUND),
     "a starship taking fire from a ridge line"),
    ("colour-object-word",
     _doc({"kind": "robot or mech"}, GROUND),
     "a machine. the hull is rose-coloured"),
    ("earth-creature-or-flora",
     _doc({"kind": "alien creature"}, GROUND),
     "a survey of moths"),
    ("earth-room-word",
     _doc({"kind": "starship"}, GROUND),
     "a starship passing the galley"),
    ("rain-in-dry-sky",
     _doc({"kind": "starship"}, DUST, "curtain of rain sweeping past"),
     "a starship in a dust storm"),
    ("still-body-mobile-action",
     _doc({"kind": "alien creature", "subkind": "fungal colony",
           "situation": "crawling up a vertical face"}, GROUND),
     "a fungal colony crawling up a vertical face"),
    ("sealed-helmet-open-face",
     _doc({"kind": "spacefarer", "aperture": "open visor"}, ORBIT),
     "a suited figure. a sealed helmet with an open visor"),
    ("heavy-body-cramped-room",
     _doc({"kind": "robot or mech", "subkind": "exosuit walker"}, ROOM),
     "an exosuit walker in the crew commons"),
    ("readable-sign-word",
     _doc({"kind": "starship", "situation": "following a warning beacon"}, GROUND),
     "a starship following a warning beacon"),
    ("world-small-feature",
     _doc({"kind": "celestial body", "surface_detail": "wind-carved dune ripples"}, ORBIT),
     "a world with wind-carved dune ripples"),
    ("info-fire-situation",
     _doc({"kind": "starship", "situation": "burning along its flank"}, GROUND),
     "a starship burning along its flank"),
)


class ConcernFlags0915Tests(unittest.TestCase):
    def test_every_flag_has_a_planted_positive(self) -> None:
        self.assertEqual(
            {flag for flag, _, _ in PLANTED},
            set(STRUCTURAL_0915) | {"info-fire-situation"},
        )

    def test_each_planted_scene_reports_its_flag(self) -> None:
        for flag, doc, text in PLANTED:
            with self.subTest(flag=flag):
                self.assertIn(flag, flags_0915(SCIFI_PACK, doc, text))

    def test_a_clean_scene_reports_nothing(self) -> None:
        doc = _doc(
            {"kind": "starship", "subkind": "heavy freighter", "form": "needle hull",
             "situation": "drifting slowly through the void", "material": "titanium alloy",
             "scale": "large", "condition": "pristine"},
            ORBIT,
        )
        text = ("a large heavy freighter, a starship, drifting slowly through the void, "
                "out in open space")
        self.assertEqual(flags_0915(SCIFI_PACK, doc, text), [])

    def test_an_empty_document_reports_nothing(self) -> None:
        self.assertEqual(flags_0915(SCIFI_PACK, {"entities": []}, ""), [])


if __name__ == "__main__":
    unittest.main()
