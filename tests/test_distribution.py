"""Todo 22 -- the distribution ceilings, as a gate rather than a report.

``scripts/sample_distribution.py`` is the tool a maintainer runs after a pool
change; this is the part of it that must never regress silently. The two are the
same code -- the ceilings and the sweep are imported, not restated -- so a
ceiling raised in one place cannot stay green in the other.

The bug class this exists for has no single-scene symptom. Identity Forge's
13.7% handbag rate broke no test, violated no rule and looked correct in every
individual render; it was only visible in a thousand of them at once. Every
other suite in this repo asks "is this scene right?". This one asks "are these
scenes, together, the spread the pack was authored for?".

The sweep is deliberately narrower here than the script's default, because a
gate that takes a minute stops being run. The script is where you go for the
full picture and the per-value table.
"""
from __future__ import annotations

import unittest

from data.scifi import SCIFI_PACK
from scripts.sample_distribution import (
    KIND_CEILING,
    MOTIF_CEILING,
    SCALE_EXTREME_CEILING,
    SCALE_EXTREMES,
    sweep,
)

#: Enough that a kind at twice its expected share is unambiguous, and few enough
#: that this stays a gate rather than a chore. 500 rather than 300 keeps the
#: widest motif (`heat`, ~64%) clear of its 70% ceiling with margin: at 300
#: seeds sampling noise put it within ~2 sigma of a spurious failure.
GATE_SEEDS = 500


class DistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fields, cls.slots, cls.scenes, cls.motifs = sweep(GATE_SEEDS, "Any")

    def test_the_sweep_actually_produced_entities(self) -> None:
        """Without this every ceiling below passes on an empty counter."""
        self.assertGreater(self.slots, GATE_SEEDS)

    def test_no_kind_crowds_out_the_others(self) -> None:
        for kind, count in self.fields["kind"].items():
            with self.subTest(kind=kind):
                self.assertLess(count / self.slots, KIND_CEILING)

    def test_every_kind_is_actually_reachable(self) -> None:
        """The other half of the ceiling: a kind at 0% is as wrong as one at
        40%, and a ceiling alone would never say so."""
        self.assertEqual(set(self.fields["kind"]), set(SCIFI_PACK.kinds))

    def test_the_scale_weighting_holds_the_extremes_down(self) -> None:
        total = sum(self.fields["scale"].values())
        extreme = sum(self.fields["scale"][value] for value in SCALE_EXTREMES)
        self.assertLess(extreme / total, SCALE_EXTREME_CEILING)

    def test_the_scale_ladder_is_still_fully_reachable(self) -> None:
        """Weighting an extreme down must not weight it out.

        ``planetary`` is drawn at about 0.1% of slots, so the 500-seed gate
        sample can miss it by chance; reachability gets its own larger sweep.
        """
        fields, _slots, _scenes, _motifs = sweep(3000, "Any")
        for value in SCALE_EXTREMES:
            with self.subTest(value=value):
                self.assertGreater(fields["scale"][value], 0)

    def test_every_occupied_slot_is_described(self) -> None:
        """Measured rather than assumed: no slot is a bare name.

        Supporting slots carry fewer widgets but the whole morphology, so
        ``form`` -- the field that makes two things actually look different --
        should reach nearly every occupied slot. It falls short of 1.0 only
        where the detail budget cut it on a crowded scene, which is the budget
        doing its job rather than the widget list doing it by accident.
        """
        share = sum(self.fields["form"].values()) / self.slots
        self.assertGreater(share, 0.60, "slots are being left as bare names")

    def test_no_motif_crowds_the_output(self) -> None:
        """A motif is a bias spread across several fields, which no per-value
        check can see. The ceiling is the script's, not restated here."""
        self.assertEqual(set(self.motifs), set(SCIFI_PACK.motifs))
        for name, count in self.motifs.items():
            with self.subTest(motif=name):
                self.assertLess(count / self.scenes, MOTIF_CEILING)

    def test_a_breached_motif_is_reported(self) -> None:
        """Watched failing, not assumed: a motif over the ceiling is a finding."""
        from collections import Counter

        from scripts.sample_distribution import report

        fields = {"kind": Counter({"starship": 1}), "scale": Counter({"small": 1})}
        failures = report(fields, slots=1, scenes=1, top=1, motifs=Counter({"ice": 1}))
        self.assertTrue(any("motif 'ice'" in f for f in failures), failures)


if __name__ == "__main__":
    unittest.main()
