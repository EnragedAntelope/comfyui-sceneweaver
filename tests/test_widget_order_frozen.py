"""Saved-workflow compatibility, frozen.

ComfyUI stores a node's widgets as a positional ``widgets_values`` array and reads
it back by index, so the order ``data.genre.widget_order`` emits is a compatibility
surface: appending a widget is safe, inserting or reordering silently reassigns
every value after it in every graph anyone has saved.

The other order tests compare ``widget_order`` to itself, which proves consistency
and not stability. These two literals are the order as shipped in 0.5.1, typed out
once and never computed, so a reorder fails here by name. If you are *appending* a
widget, extend the literal; if this fails and you did not mean to, you reordered.
"""
from __future__ import annotations

import json
import unittest

from data.fantasy import FANTASY_PACK
from data.genre import (
    ENTITY_NODE_SLOTS,
    SCENE_NODE_SLOTS,
    SET_ALL_FIELDS_KEY,
    SET_ALL_OPTIONS,
    build_field_definitions,
    widget_choices,
    widget_order,
)
from data.horror import HORROR_PACK
from data.scifi import SCIFI_PACK
from tests._loader import REPO_ROOT

_SCENE_ORDER = (
    'seed', 'entity_count', 'scene_filter', 'set_all_fields', 'environment', 'entity1_kind',
    'entity1_subkind', 'entity1_scale', 'entity1_condition', 'entity1_form', 'entity1_material',
    'entity1_primary_color', 'entity1_accent_color', 'entity1_markings', 'entity1_surface_detail',
    'entity1_appendages', 'entity1_appendage_count', 'entity1_emitters', 'entity1_emitter_count',
    'entity1_emitter_color', 'entity1_armament', 'entity1_armament_count', 'entity1_sensors',
    'entity1_sensor_count', 'entity1_aperture', 'entity1_extras', 'entity1_situation',
    'entity2_kind', 'entity2_subkind', 'entity2_scale', 'entity2_condition', 'entity2_situation',
    'entity3_kind', 'entity3_subkind', 'entity3_scale', 'entity3_condition', 'entity3_situation',
    'entity4_kind', 'entity4_subkind', 'entity4_scale', 'entity4_condition', 'entity4_situation',
    'relation_1_2', 'relation_1_3', 'relation_1_4', 'relation_2_3', 'relation_2_4', 'relation_3_4',
    'relation_1_2_position', 'relation_1_3_position', 'relation_1_4_position',
    'relation_2_3_position', 'relation_2_4_position', 'relation_3_4_position', 'context'
)

_ENTITY_ORDER = (
    'seed', 'kind', 'subkind', 'scale', 'condition', 'form', 'material', 'primary_color',
    'accent_color', 'markings', 'surface_detail', 'appendages', 'appendage_count', 'emitters',
    'emitter_count', 'emitter_color', 'armament', 'armament_count', 'sensors', 'sensor_count',
    'aperture', 'extras'
)

#: Every registered node id, with the pack and slot count it is built from.
NODES = {
    "SceneWeaverSciFi": (SCIFI_PACK, SCENE_NODE_SLOTS, _SCENE_ORDER),
    "SceneWeaverFantasy": (FANTASY_PACK, SCENE_NODE_SLOTS, _SCENE_ORDER),
    "SceneWeaverHorror": (HORROR_PACK, SCENE_NODE_SLOTS, _SCENE_ORDER),
    "SceneEntitySciFi": (SCIFI_PACK, ENTITY_NODE_SLOTS, _ENTITY_ORDER),
    "SceneEntityFantasy": (FANTASY_PACK, ENTITY_NODE_SLOTS, _ENTITY_ORDER),
    "SceneEntityHorror": (HORROR_PACK, ENTITY_NODE_SLOTS, _ENTITY_ORDER),
}


class ShippedOrderTests(unittest.TestCase):
    def test_every_node_still_begins_with_its_shipped_order(self) -> None:
        for node_id, (pack, slots, shipped) in NODES.items():
            with self.subTest(node=node_id):
                current = widget_order(pack, slots)
                self.assertEqual(
                    current[: len(shipped)],
                    shipped,
                    f"{node_id}: a widget was inserted or reordered; saved workflows "
                    "would read every later value from the wrong widget. Append only.",
                )

    def test_the_order_may_only_grow_at_the_end(self) -> None:
        for node_id, (pack, slots, shipped) in NODES.items():
            with self.subTest(node=node_id):
                self.assertGreaterEqual(len(widget_order(pack, slots)), len(shipped))


class ExampleWorkflowTests(unittest.TestCase):
    """The shipped graphs are exported from a live ComfyUI; they must still load.

    A value that is not a choice of its widget loads as "value not in list", and a
    count that disagrees with the order means the graph was exported by a different
    release of the pack. ``seed`` carries two values: the number and the
    ``control_after_generate`` mode ComfyUI adds beside it.
    """

    def test_every_node_in_every_example_matches_the_current_widgets(self) -> None:
        graphs = sorted((REPO_ROOT / "example_workflows").glob("*.json"))
        self.assertTrue(graphs, "no example workflows are shipped")
        checked = 0
        for path in graphs:
            document = json.loads(path.read_text(encoding="utf-8"))
            for node in document["nodes"]:
                if node["type"] not in NODES:
                    continue
                pack, slots, _shipped = NODES[node["type"]]
                with self.subTest(graph=path.name, node=node["type"], id=node["id"]):
                    checked += 1
                    self._check(node, pack, slots)
        self.assertGreater(checked, 0, "no SceneWeaver node was found in any example")

    def _check(self, node, pack, slots) -> None:
        definitions = build_field_definitions(pack, slots)
        expected = []
        for key in widget_order(pack, slots):
            expected.append(key)
            if key == "seed":
                expected.append("control_after_generate")
        values = node["widgets_values"]
        self.assertEqual(len(values), len(expected), "the graph has a different widget count")
        for key, value in zip(expected, values):
            if key in ("seed", "control_after_generate"):
                continue
            options = (
                SET_ALL_OPTIONS if key == SET_ALL_FIELDS_KEY else widget_choices(definitions[key])
            )
            self.assertIn(value, options, f"{key} holds a value the pack no longer offers")


if __name__ == "__main__":
    unittest.main()
