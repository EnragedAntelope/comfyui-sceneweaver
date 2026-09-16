"""Todo 19/20 -- the contract between ``nodes/frontend.py`` and the frontend.

The jsdom suite runs against a small hand-written fixture rather than the real
134KB payload, for two reasons: a generated fixture would have to import the data
layer, and importing it runs the ``user_options.json`` merge -- which bakes
whichever pool values the maintainer happens to have locally into a committed
file (``feedback-generator-cannot-leak-user-data``) -- and eight fields prove the
frontend's logic exactly as well as four hundred do.

What that trade costs is drift protection, and this file is what buys it back.
The frontend reads a *shape*; Python has to keep emitting that shape. So every
structural claim the fixture makes is asserted here against the live pack, in the
direction that can actually break: fixture says it, real payload must have it.

The route string is pinned across the language boundary too. It is the one
literal that appears in both files and a rename on one side is silent on the
other -- the node keeps loading, the frontend just quietly stops working.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from data.genre import ENTITY_NODE_SLOTS, KIND_FIELD, NONE, RANDOM, SCENE_NODE_SLOTS
from data.scifi import SCIFI_PACK
from nodes.frontend import FRONTEND_ROUTE, frontend_payload, node_payload

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = REPO_ROOT / "tests" / "frontend" / "fixtures" / "nodes.json"
JS_PATH = REPO_ROOT / "js" / "sceneweaver.js"

FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

#: Which fixture node stands in for which real one.
ROLE_FIXTURES = {
    "SceneWeaverFixture": SCENE_NODE_SLOTS,
    "SceneEntityFixture": ENTITY_NODE_SLOTS,
}


class RouteTests(unittest.TestCase):
    def test_the_route_string_matches_on_both_sides(self) -> None:
        match = re.search(r'const ROUTE = "([^"]+)"', JS_PATH.read_text(encoding="utf-8"))
        self.assertIsNotNone(match, "js/sceneweaver.js no longer declares a ROUTE")
        self.assertEqual(match.group(1), FRONTEND_ROUTE)

    def test_the_body_is_json_serializable(self) -> None:
        """It is handed to ``web.json_response``; a tuple or a MappingProxy in
        there would raise inside aiohttp, at request time, on a machine that is
        not this one."""
        body = frontend_payload(
            {
                "SceneWeaverSciFi": (SCIFI_PACK, SCENE_NODE_SLOTS),
                "SceneEntitySciFi": (SCIFI_PACK, ENTITY_NODE_SLOTS),
            }
        )
        round_tripped = json.loads(json.dumps(body))
        self.assertEqual(set(round_tripped["nodes"]), {"SceneWeaverSciFi", "SceneEntitySciFi"})


class ShapeTests(unittest.TestCase):
    """Every structural claim the jsdom fixture makes, checked against the pack."""

    def _pairs(self):
        for fixture_id, slots in ROLE_FIXTURES.items():
            yield fixture_id, FIXTURE["nodes"][fixture_id], node_payload(SCIFI_PACK, slots)

    def test_top_level_keys_match(self) -> None:
        for name, fixture, real in self._pairs():
            with self.subTest(node=name):
                self.assertEqual(set(fixture), set(real))

    def test_field_descriptor_keys_match(self) -> None:
        for name, fixture, real in self._pairs():
            expected = set(next(iter(fixture["fields"].values())))
            for key, descriptor in real["fields"].items():
                with self.subTest(node=name, field=key):
                    self.assertEqual(set(descriptor), expected)

    def test_sentinels_and_role_markers(self) -> None:
        for name, fixture, real in self._pairs():
            with self.subTest(node=name):
                self.assertEqual((real["random"], real["none"]), (RANDOM, NONE))
                self.assertEqual(real["kind_field"], KIND_FIELD)
                self.assertEqual(real["role"], fixture["role"])
                self.assertEqual("set_all" in real, "set_all" in fixture)

    def test_order_covers_every_field_plus_the_controls(self) -> None:
        for name, _fixture, real in self._pairs():
            with self.subTest(node=name):
                self.assertTrue(set(real["fields"]) <= set(real["order"]))
                self.assertEqual(len(real["order"]), len(set(real["order"])))

    def test_kind_widgets_name_real_widgets_and_never_themselves(self) -> None:
        for name, _fixture, real in self._pairs():
            for kind_key, scoped in real["kind_widgets"].items():
                with self.subTest(node=name, kind=kind_key):
                    self.assertIn(kind_key, real["fields"])
                    self.assertNotIn(kind_key, scoped)
                    for key in scoped:
                        self.assertIn(key, real["fields"])

    def test_every_slot_has_a_kind_control(self) -> None:
        """Without one, a slot could never be relabelled or scoped."""
        scene = node_payload(SCIFI_PACK, SCENE_NODE_SLOTS)
        self.assertEqual(len(scene["kind_widgets"]), SCENE_NODE_SLOTS)
        entity = node_payload(SCIFI_PACK, ENTITY_NODE_SLOTS)
        self.assertEqual(list(entity["kind_widgets"]), [KIND_FIELD])

    def test_choices_and_pools_are_keyed_by_field_not_by_widget(self) -> None:
        for name, _fixture, real in self._pairs():
            bases = {descriptor["base"] for descriptor in real["fields"].values()}
            with self.subTest(node=name):
                self.assertEqual(set(real["choices"]), bases)
                self.assertTrue(set(real["pools"]) <= bases)
                for values in real["choices"].values():
                    self.assertEqual(values[0], RANDOM)
                    self.assertEqual(values[-1], NONE)

    def test_every_kind_scoped_field_resolves_a_pool_for_every_kind(self) -> None:
        """The frontend narrows a list per kind and falls through to the pack
        default. A field that resolved to nothing would show an empty dropdown,
        which reads as a broken node rather than as an empty pool."""
        real = node_payload(SCIFI_PACK, SCENE_NODE_SLOTS)
        kinds = real["pools"][KIND_FIELD][real["default_key"]]
        for key, descriptor in real["fields"].items():
            if not descriptor["kind_scoped"]:
                continue
            pools = real["pools"][descriptor["base"]]
            for kind in kinds:
                with self.subTest(field=key, kind=kind):
                    self.assertIsNotNone(
                        pools.get(kind, pools.get(real["default_key"])),
                        f"{descriptor['base']} resolves no pool for {kind!r}",
                    )

    def test_the_qualifier_tells_repeated_widgets_apart(self) -> None:
        scene = node_payload(SCIFI_PACK, SCENE_NODE_SLOTS)
        displayed = [
            f"{d['label']}{d['qualifier']}" for d in scene["fields"].values()
        ]
        self.assertEqual(len(displayed), len(set(displayed)), "two widgets read alike")
        entity = node_payload(SCIFI_PACK, ENTITY_NODE_SLOTS)
        for descriptor in entity["fields"].values():
            self.assertEqual(descriptor["qualifier"], "", "a lone entity has no slots")

    def test_the_relabelling_data_actually_relabels(self) -> None:
        """A labels map that gave every kind the same word would satisfy every
        structural check above and do nothing at all on screen."""
        real = node_payload(SCIFI_PACK, SCENE_NODE_SLOTS)
        differing = [
            name
            for name, per_kind in real["labels"].items()
            if len(set(per_kind.values())) > 1
        ]
        self.assertTrue(differing, "no field's label varies by kind")
        self.assertEqual(
            real["labels"]["emitter_count"]["starship"], "Engine count"
        )
        self.assertEqual(
            real["labels"]["emitter_count"]["alien creature"], "Organ count"
        )

    def test_set_all_payload_names_the_actions_not_indices(self) -> None:
        """The frontend picks a direction from named keys, never from an
        "option position, so reordering the options cannot reverse the edit."""
        scene = node_payload(SCIFI_PACK, SCENE_NODE_SLOTS)
        self.assertEqual(set(scene["set_all"]), {"key", "off", "clear", "randomize"})
        self.assertEqual(scene["set_all"]["clear"], "Clear all")
        self.assertEqual(scene["set_all"]["randomize"], "Randomize all")

    def test_no_control_widget_reaches_the_frontend_as_a_field(self) -> None:
        """A control has no pool and must never be swept by set_all_fields."""
        for name, _fixture, real in self._pairs():
            with self.subTest(node=name):
                for control in ("seed", "scene_filter", "set_all_fields"):
                    self.assertNotIn(control, real["fields"])

    def test_scope_widgets_name_real_widgets_and_never_themselves(self) -> None:
        """The scope chain narrows through named controls, not a name pattern."""
        for name, _fixture, real in self._pairs():
            for control_key, dependents in real["scope_widgets"].items():
                with self.subTest(node=name, control=control_key):
                    self.assertIn(control_key, real["fields"])
                    self.assertNotIn(control_key, dependents)
                    for key in dependents:
                        self.assertIn(key, real["fields"])

    def test_every_field_declares_a_scope(self) -> None:
        """``scope`` is the ordered control chain, a list on every field."""
        for name, _fixture, real in self._pairs():
            for key, descriptor in real["fields"].items():
                with self.subTest(node=name, field=key):
                    self.assertIsInstance(descriptor["scope"], list)

if __name__ == "__main__":  # pragma: no cover
    unittest.main()
