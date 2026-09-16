"""Replay a folder of ComfyUI images through the engine and name what each one got wrong.

    python scripts/replay_batch.py D:/SDshared/output/sceneweaver/913concern
    python scripts/replay_batch.py --label concern=D:/SDshared/output/sceneweaver/913concern \
        --label keeper=D:/SDshared/output/sceneweaver --glob "sceneweaver0913__*.png"

Reads each PNG's ``prompt`` chunk (the executed graph), finds the Scene Weaver node and
every Scene Entity wired into it, re-runs them with the same seeds and widgets, and
prints the resolved place, subject, action and context with the concern flags. When an
``extracted_*/prompts.csv`` sits in the folder, each replayed prompt is compared with it:
a match proves the replay is the code that made the image. Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _entry in (str(_ROOT), str(_ROOT / "scripts")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from concern_flags import flags  # noqa: E402
from concern_flags_0914 import flags_0914  # noqa: E402
from concern_flags_0915 import flags_0915  # noqa: E402
from data.scifi import SCIFI_PACK  # noqa: E402
from engine.scene import generate_entity, generate_scene  # noqa: E402
from pngmeta import png_text_chunks  # noqa: E402

_CONTROL_KEYS = frozenset({"seed", "scene_filter", "set_all_fields", "entity_count"})


def _widgets(inputs: dict) -> dict:
    """Widget values only: links are lists, and controls are passed separately."""
    return {
        key: value for key, value in inputs.items()
        if not isinstance(value, list) and key not in _CONTROL_KEYS
    }


def replay(path: Path) -> "tuple[str, dict] | None":
    """``(prompt_text, prompt_json)`` for one image, or ``None`` without a Scene Weaver."""
    graph = json.loads(png_text_chunks(path).get("prompt", "{}"))
    weaver = next(
        (node for node in graph.values()
         if str(node.get("class_type", "")).startswith("SceneWeaver")),
        None,
    )
    if weaver is None:
        return None
    inputs = weaver["inputs"]
    wired = {}
    for slot in range(1, 5):
        link = inputs.get(f"entity_{slot}_in")
        if not isinstance(link, list):
            continue
        entity_inputs = graph[str(link[0])]["inputs"]
        _text, payload = generate_entity(
            int(entity_inputs["seed"]), SCIFI_PACK, widgets=_widgets(entity_inputs)
        )
        wired[slot] = payload
    return generate_scene(
        int(inputs["seed"]), SCIFI_PACK,
        widgets=_widgets(inputs),
        wired_entities=wired,
        scene_filter=inputs.get("scene_filter", "Any"),
        set_all_fields=inputs.get("set_all_fields", "Off"),
        entity_count=int(inputs.get("entity_count", 1)),
    )


def _recorded_prompts(folder: Path) -> dict[str, str]:
    recorded: dict[str, str] = {}
    for csv_path in folder.glob("extracted_*/prompts.csv"):
        with open(csv_path, encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                recorded[row["filename"]] = row["prompt"]
    return recorded


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folders", nargs="*", type=Path)
    parser.add_argument("--label", action="append", default=[], metavar="NAME=FOLDER")
    parser.add_argument("--glob", default="*.png")
    args = parser.parse_args(argv)
    logging.getLogger("sceneweaver").setLevel(logging.ERROR)
    batches = [(folder.name, folder) for folder in args.folders]
    batches += [
        (item.split("=", 1)[0], Path(item.split("=", 1)[1])) for item in args.label
    ]
    summary: dict[str, Counter] = {}
    totals: Counter = Counter()
    flagged: Counter = Counter()
    mismatches = 0
    for label, folder in batches:
        recorded = _recorded_prompts(folder)
        tally = summary.setdefault(label, Counter())
        for path in sorted(folder.glob(args.glob)):
            result = replay(path)
            if result is None:
                continue
            text, document = result
            found = [
                n for n in (*flags(SCIFI_PACK, document, text),
                             *flags_0914(SCIFI_PACK, document, text),
                             *flags_0915(SCIFI_PACK, document, text))
                if not n.startswith("info-")
            ]
            totals[label] += 1
            flagged[label] += bool(found)
            tally.update(set(found))
            status = ""
            if path.name in recorded:
                matched = recorded[path.name].endswith(text)
                mismatches += not matched
                status = "match" if matched else "MISMATCH"
            record = document["entities"][0] if document["entities"] else {}
            print("\t".join((
                label, path.name, status,
                f"{document['environment']} | {record.get('kind')} | {record.get('subkind')} | "
                f"{record.get('form')} | {record.get('situation')} | {document.get('context')}",
                ",".join(found) or "-",
            )))
    print()
    print("flag".ljust(30) + "".join(f"{label:>14}" for label in summary))
    for name in sorted({name for tally in summary.values() for name in tally}):
        print(name.ljust(30) + "".join(f"{summary[label][name]:>14}" for label in summary))
    print("ANY FLAG".ljust(30) + "".join(
        f"{flagged[label]:>9}/{totals[label]:<4}" for label in summary
    ))
    if mismatches:
        print(f"{mismatches} image(s) did not replay to their recorded prompt: "
              "the engine has changed since they were made")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
