"""Todo 23 -- the ``user_options.json`` merge, and the leak it must not have.

Two questions, and the second is the one with a history:

1. **Does a user's value actually work?** It has to reach the pool, the widget
   options, the random draw and the prose -- not just the pool, which is where a
   merge that looked right stopped being right.
2. **Can a maintainer's private values escape into a committed file?** Identity
   Forge shipped exactly that: a build script imported the data layer, the import
   ran the merge, and one machine's private entries were baked into a file
   everybody downloaded (``feedback-generator-cannot-leak-user-data``).

The defence is structural rather than procedural. ``import data.scifi`` runs no
merge -- the merge happens once, in the repo-root ``__init__.py`` -- and any
script needing pool values reads them with ``scripts/builtin_options.py``, which
parses the source and has no code path that could open the JSON file.

:class:`NoLeakTests` proves it with a **real ``user_options.json`` on disk**,
because that is the only condition under which the bug can happen and a test
with a temp path elsewhere would prove nothing about it. It refuses to run if
the maintainer already has one, rather than overwriting it.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import unittest
from pathlib import Path

from data.genre import filtered_pool, pool_for, pool_options
from data.scifi import SCIFI_PACK
from data.user_options import (
    USER_OPTIONS_FILENAME,
    apply_user_options,
    load_user_options,
    merge_user_options,
    user_options_path,
)
from engine.scene import generate_scene
from scripts.builtin_options import builtin_pools, builtin_values
from tests._loader import REPO_ROOT, load_entrypoint

#: Deliberately unlike anything in the shipped pools, so finding it anywhere is
#: unambiguous.
CUSTOM_COLOUR = "zzz-test-hunter-green"
CUSTOM_SITUATION = "zzz-test drifting past a survey buoy"

DOCUMENT = {
    "pools": {
        "primary_color": {"_default": [CUSTOM_COLOUR]},
        "situation": {"starship": [CUSTOM_SITUATION]},
    },
    "tags": {"situation": {CUSTOM_SITUATION: "peaceful_only"}},
}


class MergeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.merged = merge_user_options(SCIFI_PACK, DOCUMENT)

    def test_a_custom_value_joins_its_pool(self) -> None:
        self.assertIn(CUSTOM_COLOUR, pool_for(self.merged, "primary_color"))
        self.assertIn(CUSTOM_SITUATION, pool_for(self.merged, "situation", "starship"))

    def test_the_built_in_pack_is_left_alone(self) -> None:
        """A pack is frozen and shared process-wide; a merge that appended in
        place would leak one caller's additions into every other reader."""
        self.assertNotIn(CUSTOM_COLOUR, pool_for(SCIFI_PACK, "primary_color"))
        self.assertNotIn(CUSTOM_SITUATION, pool_for(SCIFI_PACK, "situation", "starship"))

    def test_a_custom_value_becomes_a_widget_option(self) -> None:
        """Pools are not enough: a value a user cannot select is not an option."""
        self.assertIn(CUSTOM_COLOUR, pool_options(self.merged, "primary_color"))

    def test_a_custom_value_reaches_the_prose(self) -> None:
        text, document = generate_scene(
            1,
            self.merged,
            widgets={"entity1_kind": "starship", "entity1_primary_color": CUSTOM_COLOUR},
        )
        self.assertIn(CUSTOM_COLOUR, text)
        self.assertEqual(document["entities"][0]["primary_color"], CUSTOM_COLOUR)

    def test_a_custom_tag_is_read_by_the_content_filter(self) -> None:
        peaceful = filtered_pool(self.merged, "situation", "starship", "Peaceful")
        conflict = filtered_pool(self.merged, "situation", "starship", "Conflict")
        self.assertIn(CUSTOM_SITUATION, peaceful)
        self.assertNotIn(CUSTOM_SITUATION, conflict)

    def test_an_untagged_value_is_drawn_under_every_filter(self) -> None:
        merged = merge_user_options(SCIFI_PACK, {"pools": DOCUMENT["pools"]})
        for scene_filter in ("Any", "Peaceful", "Conflict"):
            with self.subTest(scene_filter=scene_filter):
                self.assertIn(
                    CUSTOM_SITUATION,
                    filtered_pool(merged, "situation", "starship", scene_filter),
                )

    def test_the_merge_is_idempotent(self) -> None:
        twice = merge_user_options(self.merged, DOCUMENT)
        self.assertEqual(
            pool_for(twice, "primary_color").count(CUSTOM_COLOUR), 1
        )

    def test_constraints_are_never_written(self) -> None:
        """Rules match by exact string; a new value is simply not named by one."""
        self.assertEqual(self.merged.constraints, SCIFI_PACK.constraints)


class BadFileTests(unittest.TestCase):
    """A user's mistake warns and is skipped; it never stops the nodes loading."""

    def merge(self, document):
        with self.assertLogs("data.user_options", "WARNING"):
            return merge_user_options(SCIFI_PACK, document)

    def test_an_unknown_field_is_skipped(self) -> None:
        merged = self.merge({"pools": {"warp_core": {"_default": ["singularity"]}}})
        self.assertNotIn("warp_core", merged.pools)

    def test_an_unknown_kind_is_skipped(self) -> None:
        merged = self.merge({"pools": {"situation": {"dragon": ["hoarding gold"]}}})
        self.assertNotIn("dragon", merged.pools["situation"])

    def test_a_non_list_value_is_skipped(self) -> None:
        merged = self.merge({"pools": {"primary_color": {"_default": "puce"}}})
        self.assertNotIn("puce", pool_for(merged, "primary_color"))

    def test_an_unknown_tag_leaves_the_value_neutral(self) -> None:
        merged = self.merge({"tags": {"situation": {"orbiting": "spooky"}}})
        self.assertNotEqual(merged.tags["situation"].get("orbiting"), "spooky")

    def test_tagging_a_field_the_filter_ignores_is_reported(self) -> None:
        self.merge({"tags": {"primary_color": {"oxide red": "neutral"}}})

    def test_an_unknown_top_level_key_is_reported(self) -> None:
        self.merge({"poolz": {}})

    def test_a_comment_key_is_not_reported(self) -> None:
        """The shipped example uses ``_README``; JSON has no comments."""
        logger = logging.getLogger("data.user_options")
        with self.assertRaises(AssertionError):
            with self.assertLogs(logger, "WARNING"):
                merge_user_options(SCIFI_PACK, {"_README": ["hello"], "pools": {}})

    def test_a_value_that_breaks_the_house_rules_warns_but_is_kept(self) -> None:
        merged = self.merge(
            {"pools": {"primary_color": {"_default": ["a cinematic lighting grey"]}}}
        )
        self.assertIn("a cinematic lighting grey", pool_for(merged, "primary_color"))

    def test_a_missing_file_is_the_normal_case(self) -> None:
        self.assertEqual(load_user_options(REPO_ROOT / "no-such-file.json"), {})

    def test_malformed_json_does_not_raise(self) -> None:
        broken = REPO_ROOT / "tests" / "_broken_user_options.json"
        broken.write_text("{ not json", encoding="utf-8")
        try:
            with self.assertLogs("data.user_options", "WARNING"):
                self.assertEqual(load_user_options(broken), {})
        finally:
            broken.unlink()

    def test_the_shipped_example_file_parses_and_merges(self) -> None:
        example = REPO_ROOT / "user_options.example.json"
        self.assertTrue(example.is_file(), "user_options.example.json is not shipped")
        document = json.loads(example.read_text(encoding="utf-8"))
        merged = merge_user_options(SCIFI_PACK, document)
        self.assertIn("hunter green", pool_for(merged, "primary_color"))


class NoLeakTests(unittest.TestCase):
    """The bug this todo exists to make impossible, tested where it happens.

    A real ``user_options.json`` at the pack root, for the duration of the test.
    """

    path: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.path = user_options_path()
        if cls.path.exists():
            raise unittest.SkipTest(
                f"{cls.path} already exists; refusing to overwrite a real one"
            )
        cls.path.write_text(json.dumps(DOCUMENT), encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.path.unlink(missing_ok=True)

    def test_the_file_is_gitignored(self) -> None:
        ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(USER_OPTIONS_FILENAME, ignored)

    def test_importing_the_data_module_does_not_run_the_merge(self) -> None:
        """Rule 1. ``import data.scifi`` is the built-ins and only the built-ins,
        even with the file sitting right there.

        Run in a **subprocess**, and that is not fussiness. This module imported
        ``data.scifi`` before ``setUpClass`` wrote the file, so the in-process
        pack would look clean however the data module behaved -- a planted
        ``SCIFI_PACK = apply_user_options(SCIFI_PACK)`` at the end of
        ``data/scifi.py`` passed this test in its in-process form. The bug only
        exists when the file is already on disk as the process starts, so the
        test has to start a process.
        """
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, '.');"
             "from data.scifi import SCIFI_PACK;"
             "from data.genre import pool_for;"
             "print(repr(pool_for(SCIFI_PACK, 'primary_color')))"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(CUSTOM_COLOUR, result.stdout)
        self.assertIn("oxide red", result.stdout, "the subprocess read no pool at all")

    def test_the_ast_reader_sees_the_built_ins_only(self) -> None:
        """The plan's acceptance criterion, stated exactly."""
        self.assertNotIn(CUSTOM_COLOUR, builtin_values("primary_color"))
        self.assertNotIn(CUSTOM_SITUATION, builtin_values("situation"))

    def test_the_ast_reader_agrees_with_the_unmerged_pack_field_for_field(self) -> None:
        """Not just "the custom value is absent" -- the whole thing matches.

        A reader that returned an empty dict would pass the test above.
        """
        parsed = builtin_pools()
        self.assertEqual(set(parsed), set(SCIFI_PACK.pools))
        for field, by_kind in parsed.items():
            with self.subTest(field=field):
                self.assertEqual(
                    {k: tuple(v) for k, v in by_kind.items()},
                    {k: tuple(v) for k, v in SCIFI_PACK.pools[field].items()},
                )

    def test_the_entrypoint_does_run_the_merge(self) -> None:
        """The other half: an isolation that also isolated the user would be a
        merge that does nothing."""
        module = load_entrypoint("comfyui_sceneweaver_user_options")
        self.assertIn(CUSTOM_COLOUR, pool_for(module.SCIFI_PACK, "primary_color"))

    def test_a_merged_value_reaches_the_generated_node_widget(self) -> None:
        module = load_entrypoint("comfyui_sceneweaver_user_options_widgets")
        schema = module.SceneWeaverSciFi.define_schema()
        widget = next(i for i in schema.inputs if i.id == "entity1_primary_color")
        self.assertIn(CUSTOM_COLOUR, widget.options)

    def test_a_merged_value_reaches_the_frontend_route_payload(self) -> None:
        """The route serves the live pack, which is why it is a route and not a
        generated .js file -- a generated file would be wrong on exactly the
        machine that customised it."""
        module = load_entrypoint("comfyui_sceneweaver_user_options_frontend")
        from nodes.frontend import frontend_payload

        payload = frontend_payload(module.NODE_PACKS)
        pools = payload["nodes"]["SceneWeaverSciFi"]["pools"]
        self.assertIn(CUSTOM_COLOUR, pools["primary_color"]["_default"])

    def test_apply_user_options_reads_the_default_path(self) -> None:
        merged = apply_user_options(SCIFI_PACK)
        self.assertIn(CUSTOM_COLOUR, pool_for(merged, "primary_color"))


if __name__ == "__main__":
    unittest.main()
