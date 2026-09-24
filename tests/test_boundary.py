"""Todo 21 -- the two denylists, over pool values and over generated prose.

The rule this file exists to hold is a *split*, not a ban, and a split can fail
in two directions. So can this suite:

* :class:`RenderingIsRejectedTests` proves the banned side is actually caught --
  in the pools, in ``prompt_text`` across a 500-seed sweep, and against
  planted probes for every category the plan names.
  names.
* :class:`SubjectSurvivesTests` proves the allowed side is actually allowed. A
  denylist that quietly banned every colour word would make hull livery and
  engine glow inexpressible and would still pass a one-directional test green.
  That is the exact mistake the previous plan made, so the passing direction is
  asserted as hard as the failing one.

Scanning *prose* as well as pool values is not belt-and-braces. A rendering term
can arrive by composition -- a template word next to a pool word -- with no
single pool value containing one, so a pools-only check would miss it.

The end-to-end probes go further than scanning a string: they plant a value in a
copy of the pack, generate scenes from it, and require the sweep's own scanner
to catch it. A test that only ever scans hand-written strings proves the
*scanner* works; these prove the *sweep* works.
"""
from __future__ import annotations

import dataclasses
import unittest

from data.genre import POOL_DEFAULT_KEY, spoken_value
from data.scifi import SCIFI_PACK
from engine.scene import generate_scene
from tests.boundary import (
    NEGATION_PROBES,
    RENDERING_PROBES,
    SUBJECT_PROBES,
    leading_article,
    negation_findings,
    rendering_findings,
)

#: The plan's sweep width. Wide enough that a value drawn one time in three
#: hundred is still seen at every level.
SWEEP_SEEDS = 500


#: Subject colour the pack must actually ship, checked by name. "No rendering
#: terms" is trivially satisfiable by a pack that describes nothing, so the
#: passing direction needs a value that exists rather than a value that could.
REQUIRED_SUBJECT_COLOURS = ("oxide red", "gunmetal grey", "off-white")

#: Fields whose values are the engine's composition vocabulary rather than noun
#: phrases: "a pair of" legitimately opens with an article.
_COUNT_FIELDS = frozenset(
    name
    for name, spec in SCIFI_PACK.entity_fields.items()
    if spec.renders_with is not None and spec.count_partner is not None
)


def _every_pool_value():
    """``(field, kind, value)`` for every authored value in the pack."""
    for field, by_kind in SCIFI_PACK.pools.items():
        for kind, values in by_kind.items():
            for value in values:
                yield field, kind, value


#: Wet-navy (ocean-vessel) vocabulary that must never appear in a pool value.
#: The pack is space-faring; a sailing-ship term is an anachronism a render
#: would surface as a modern battleship (todo 7).
WET_NAVY_TERMS = (
    "broadside", "torpedo", "gun blister", "deckhand", "keel",
    "crown of", "tender",
)

def _sweep_texts(pack=SCIFI_PACK, seeds: int = SWEEP_SEEDS):
    """``(seed, level, prompt_text)`` across the whole sweep."""
    for seed in range(seeds):
        text, _ = generate_scene(seed, pack)
        yield seed, None, text


def _pack_with(field: str, value: str, kind: str = POOL_DEFAULT_KEY):
    """A copy of the sci-fi pack with one extra value planted in one pool.

    Built by replacing the whole ``pools`` mapping rather than by mutating it:
    a ``GenrePack`` is frozen and shared process-wide, and an in-place append
    here would leak the planted value into every other test in the process.
    """
    pools = {name: dict(by_kind) for name, by_kind in SCIFI_PACK.pools.items()}
    existing = tuple(pools[field].get(kind, ()))
    pools[field][kind] = (*existing, value)
    return dataclasses.replace(SCIFI_PACK, pools=pools)


class PoolValueTests(unittest.TestCase):
    """Denylist 1, over every authored value."""

    def test_no_pool_value_names_a_rendering_term(self) -> None:
        for field, kind, value in _every_pool_value():
            findings = rendering_findings(value)
            if findings:
                self.fail(f"{field}[{kind}] {value!r} contains {', '.join(findings)}")

    def test_no_pool_value_negates(self) -> None:
        for field, kind, value in _every_pool_value():
            findings = negation_findings(value)
            if findings:
                self.fail(f"{field}[{kind}] {value!r} contains {', '.join(findings)}")

    def test_no_pool_value_carries_a_leading_article(self) -> None:
        """The engine composes the article; a value that carries its own gets
        "a a pair of ion thrusters" the first time it is counted."""
        for field, kind, value in _every_pool_value():
            if field in _COUNT_FIELDS:
                continue
            with self.subTest(field=field, kind=kind, value=value):
                self.assertFalse(leading_article(value))

    def test_the_count_vocabulary_is_the_only_articled_pool(self) -> None:
        """Stated as its own assertion so the exemption above cannot silently
        widen to cover a field that simply has a bad value in it."""
        articled = {
            field
            for field, _, value in _every_pool_value()
            if leading_article(value)
        }
        self.assertEqual(articled, set(_COUNT_FIELDS))


class SubjectSurvivesTests(unittest.TestCase):
    """Denylist 2 -- the allowed side. These must NOT be caught."""

    def test_every_subject_probe_survives_the_rendering_scan(self) -> None:
        for probe in SUBJECT_PROBES:
            with self.subTest(probe=probe):
                self.assertEqual(
                    rendering_findings(probe),
                    [],
                    "a subject-intrinsic phrase was rejected: the rule is a split, "
                    "not a ban on colour",
                )

    def test_crimson_hull_passes(self) -> None:
        """The plan names this one by name, in both directions."""
        self.assertEqual(rendering_findings("crimson hull"), [])
        self.assertEqual(negation_findings("crimson hull"), [])

    def test_the_pack_actually_ships_subject_colour(self) -> None:
        colours = set()
        for field in ("primary_color", "accent_color", "emitter_color"):
            for by_kind in (SCIFI_PACK.pools[field],):
                for values in by_kind.values():
                    colours.update(values)
        for expected in REQUIRED_SUBJECT_COLOURS:
            with self.subTest(colour=expected):
                self.assertIn(expected, colours)

    def test_subject_colour_reaches_the_prompt(self) -> None:
        """A pack could pass every ban above by describing nothing at all."""
        colours = set(SCIFI_PACK.pools["primary_color"][POOL_DEFAULT_KEY])
        spoken = set()
        for _, _, text in _sweep_texts(seeds=100):
            low = text.lower()
            spoken.update(
                c for c in colours
                if c in low or spoken_value(SCIFI_PACK, "primary_color", c) in low
            )
        self.assertGreater(
            len(spoken),
            len(colours) // 2,
            "fewer than half the hull colours ever reach the prompt",
        )

    def test_a_planted_subject_colour_survives_the_whole_sweep(self) -> None:
        """End to end: the sweep scanner must not reject "crimson hull"."""
        pack = _pack_with("primary_color", "crimson")
        for seed, level, text in _sweep_texts(pack, seeds=60):
            findings = rendering_findings(text)
            if findings:
                self.fail(f"seed {seed} at {level}: {', '.join(findings)} in {text!r}")


class RenderingIsRejectedTests(unittest.TestCase):
    """Denylist 1 -- the banned side, proven by planting each category."""

    def test_every_rendering_probe_is_caught(self) -> None:
        for probe in RENDERING_PROBES:
            with self.subTest(probe=probe):
                self.assertNotEqual(
                    rendering_findings(probe),
                    [],
                    "the denylist does not catch this category of rendering term",
                )

    def test_every_negation_probe_is_caught(self) -> None:
        for probe in NEGATION_PROBES:
            with self.subTest(probe=probe):
                self.assertNotEqual(negation_findings(probe), [])

    def test_a_planted_rendering_value_fails_the_pool_scan(self) -> None:
        pack = _pack_with("primary_color", "cinematic lighting")
        offenders = [
            value
            for values in pack.pools["primary_color"].values()
            for value in values
            if rendering_findings(value)
        ]
        self.assertEqual(offenders, ["cinematic lighting"])

    def test_a_planted_rendering_value_fails_the_prose_sweep(self) -> None:
        """The check that matters: the sweep, not a hand-written string.

        A pool with one planted value in it is drawn eventually, and when it is,
        the sweep's own scanner has to be what catches it.
        """
        pack = _pack_with("primary_color", "cinematic lighting")
        caught = False
        for _, _, text in _sweep_texts(pack, seeds=SWEEP_SEEDS):
            if rendering_findings(text):
                caught = True
                break
        self.assertTrue(
            caught,
            "a rendering term planted in a pool was never caught by the prose sweep",
        )

    def test_a_planted_negation_fails_the_prose_sweep(self) -> None:
        # Planted in ``accent_color``: its only pool is ``_default``, drawn for
        # every kind, so the probe is reached rather than merely present.
        # ``markings`` would not do -- every kind overrides it, so a value added
        # to its ``_default`` is authored into a pool nothing ever reads -- and
        # since round XV neither would ``condition``, whose made kinds declare
        # their own key (validator check 32).
        pack = _pack_with("accent_color", "missing every hull plate")
        caught = any(negation_findings(text) for _, _, text in _sweep_texts(pack, seeds=SWEEP_SEEDS))
        self.assertTrue(caught)


class ProseSweepTests(unittest.TestCase):
    """The shipped pack, swept at every level. The gate the plan names."""

    def test_no_prompt_names_a_rendering_term(self) -> None:
        for seed, level, text in _sweep_texts():
            findings = rendering_findings(text)
            if findings:
                self.fail(f"seed {seed} at {level}: {', '.join(findings)} in {text!r}")

    def test_no_prompt_negates(self) -> None:
        for seed, level, text in _sweep_texts():
            findings = negation_findings(text)
            if findings:
                self.fail(f"seed {seed} at {level}: {', '.join(findings)} in {text!r}")

    def test_the_filters_are_swept_too(self) -> None:
        """``Peaceful`` and ``Conflict`` reshape the pools, so they reshape the
        prose. Sweeping only the default filter would leave two thirds of the
        reachable output unscanned."""
        for scene_filter in ("Peaceful", "Conflict"):
            for seed in range(SWEEP_SEEDS):
                text, _ = generate_scene(
                    seed, SCIFI_PACK, scene_filter=scene_filter,                 )
                findings = rendering_findings(text) + negation_findings(text)
                if findings:
                    self.fail(f"{scene_filter} seed {seed}: {', '.join(findings)}")

    def test_a_wired_entity_is_swept_too(self) -> None:
        """The Scene Entity node's own prose reaches a prompt as well."""
        from engine.scene import generate_entity

        for seed in range(SWEEP_SEEDS):
            text, _ = generate_entity(seed, SCIFI_PACK)
            findings = rendering_findings(text) + negation_findings(text)
            if findings:
                self.fail(f"entity seed {seed}: {', '.join(findings)} in {text!r}")

class NavalLeakTests(unittest.TestCase):
    """No pool value carries ocean-vessel vocabulary (todo 7)."""

    def test_no_pool_value_uses_wet_navy_vocabulary(self) -> None:
        for field, kind, value in _every_pool_value():
            for term in WET_NAVY_TERMS:
                with self.subTest(field=field, kind=kind, value=value, term=term):
                    self.assertNotIn(term, value.lower())

if __name__ == "__main__":
    unittest.main()
