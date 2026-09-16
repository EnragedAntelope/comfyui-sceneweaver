"""Proof that ``scripts/concern_flags_0914.py`` actually fires.

``feedback-verify-the-verifier``: a regex that has never been watched match is a
claim, not a check -- and a regex is exactly what a shell heredoc once corrupted
(``\\b`` became a backspace byte and the check silently matched nothing). So every
flag gets a planted positive built by hand, plus one clean scene that must report
nothing at all.
"""
from __future__ import annotations

import unittest

from data.scifi import SCIFI_PACK
from scripts.concern_flags_0914 import STRUCTURAL_0914, flags_0914

#: Places whose affordances each planted positive needs.
ORBIT = "high polar orbit"
TRENCH = "deep ocean trench of a water world"
CLOUD_DECK = "upper cloud deck of a gas giant"
GROUND = "frozen methane flats"
WILDERNESS = "barren alien wilderness"


def _doc(entity=None, environment="", context=""):
    record = {
        "kind": None, "subkind": None, "form": None, "situation": None,
        "material": None, "extras": None, "appendages": None, "armament": None,
        "scale": None, "condition": None,
    }
    record.update(entity or {})
    return {"entities": [record], "environment": environment, "context": context}


#: ``(flag, doc, text)`` -- one planted positive per class.
PLANTED: tuple[tuple[str, dict, str], ...] = (
    ("person-open-face-hostile",
     _doc({"kind": "spacefarer", "situation": "drifting in the void"}, ORBIT),
     "a suited person drifting in the void"),
    ("helmet-carried",
     _doc({"kind": "spacefarer"}, ORBIT),
     "a suited person who stops to carry a spare helmet"),
    ("face-condition-hostile",
     _doc({"kind": "spacefarer", "condition": "scarred"}, ORBIT),
     "a battle-scarred person"),
    ("earthcraft-in-atmosphere",
     _doc({"kind": "starship", "form": "crescent-wing hull"}, CLOUD_DECK),
     "a crescent-wing hull in the clouds"),
    ("tether-cable-chain",
     _doc({"kind": "wreck", "situation": "a tether snapping taut"}, ORBIT),
     "a tether snapping taut"),
    ("drag-without-grip",
     _doc({"kind": "wreck", "situation": "hauling a wrecked drone across a deck"}, GROUND),
     "hauling a wrecked drone across a deck"),
    ("earth-container",
     _doc({"kind": "spacefarer"}, GROUND),
     "a suited figure hauling a sample canister"),
    ("egg-bladder-balloon",
     _doc({"kind": "alien creature"}, CLOUD_DECK),
     "a drift of floating bladder-pods"),
    ("net-web-mesh",
     _doc({"kind": "space station", "situation": "under a canopy of filament nets"}, ORBIT),
     "under a canopy of filament nets"),
    ("bone-scenery",
     _doc({"kind": "wreck"}, ORBIT, "a spine of broken struts"),
     "a wreck adrift"),
    ("fish-bird-scenery",
     _doc({"kind": "alien creature"}, TRENCH, "a shoal of drifting motes"),
     "a creature adrift"),
    ("cloud-sit-at-ground",
     _doc({"kind": "surface vehicle", "situation": "crossing the cloud tops"}, GROUND),
     "crossing the cloud tops"),
    ("jump-in-atmosphere",
     _doc({"kind": "starship", "situation": "flaring its drive coils for a jump"}, CLOUD_DECK),
     "flaring its drive coils for a jump"),
    ("midair-underwater",
     _doc({"kind": "surface vehicle", "situation": "hanging in mid-air"}, TRENCH),
     "hanging in mid-air"),
    ("article-on-plural-head",
     _doc({"kind": "space station", "form": "tilted ring disc parted by a dark gap"}, ORBIT),
     "a tilted rings parted by a dark gap"),
    ("walker-without-legs",
     _doc({"kind": "robot or mech", "subkind": "scout walker",
           "form": "serpentine segmented chassis"}, GROUND),
     "a scout walker"),
    ("ice-tool-without-cold",
     _doc({"kind": "surface vehicle", "subkind": "ice cutter"}, WILDERNESS),
     "an ice cutter"),
    ("civilian-armed",
     _doc({"kind": "starship", "subkind": "starliner", "armament": "point-defence turret"}, ORBIT),
     "a starliner with a point-defence turret"),
    ("grown-hull-metal",
     _doc({"kind": "starship", "subkind": "bioship", "material": "polished chrome"}, ORBIT),
     "a bioship clad in polished chrome"),
    ("small-subject-furnished-room",
     _doc({"kind": "alien creature", "scale": "small"}, "crew galley"),
     "a small creature in the crew galley"),
    ("crew-without-floor",
     _doc({"kind": "spacefarer", "situation": "as the crew backs away"}, CLOUD_DECK),
     "as the crew backs away"),
)


class ConcernFlags0914Tests(unittest.TestCase):
    def test_every_flag_has_a_planted_positive(self) -> None:
        self.assertEqual({flag for flag, _, _ in PLANTED}, set(STRUCTURAL_0914))

    def test_each_planted_scene_reports_its_flag(self) -> None:
        for flag, doc, text in PLANTED:
            with self.subTest(flag=flag):
                self.assertIn(flag, flags_0914(SCIFI_PACK, doc, text))

    def test_a_clean_scene_reports_nothing(self) -> None:
        doc = _doc(
            {"kind": "starship", "subkind": "heavy freighter", "form": "needle hull",
             "situation": "drifting slowly through the void", "material": "titanium alloy",
             "scale": "large", "condition": "pristine"},
            ORBIT,
        )
        text = "a large heavy freighter, a starship, drifting slowly through the void"
        self.assertEqual(flags_0914(SCIFI_PACK, doc, text), [])

    def test_an_empty_document_reports_nothing(self) -> None:
        self.assertEqual(flags_0914(SCIFI_PACK, {"entities": []}, ""), [])


if __name__ == "__main__":
    unittest.main()
