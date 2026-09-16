"""Concern audit -- sweep the user's graph and count the defect classes users reported.

    python scripts/concern_audit.py                   # 1500 scenes, a Scene Entity wired into slot 1
    python scripts/concern_audit.py --path unwired    # the Scene Weaver alone
    python scripts/concern_audit.py --gate            # exit 1 if any structural class is present

An instrument, not a test: ``tests/`` owns the gates. Imports ``data.scifi`` directly,
never the entrypoint, so ``user_options.json`` can never reach a number.
"""
from __future__ import annotations

import argparse
import logging
import random
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _entry in (str(_ROOT), str(_ROOT / "scripts")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from concern_flags import flags  # noqa: E402
from concern_flags_0914 import STRUCTURAL_0914, flags_0914  # noqa: E402
from concern_flags_0915 import STRUCTURAL_0915, flags_0915  # noqa: E402
from data.scifi import SCIFI_PACK  # noqa: E402
from engine.scene import generate_entity, generate_scene  # noqa: E402

#: Every class that must be absent once this plan has landed. ``info-`` flags are never gated.
STRUCTURAL = frozenset({
    "noform", "subject-cannot-stand", "person-in-void", "creature-in-void", "mech-in-void",
    "ground-vehicle-in-sky", "ship-enclosed", "sit-needs-ground", "sit-needs-structure",
    "sit-needs-gravity", "sit-needs-water", "sit-needs-space", "body-no-wheels", "body-no-legs",
    "body-no-arms", "body-no-scales", "body-no-jaws", "body-cannot-coil",
    "celestial-surface-scale", "celestial-wrong-body", "celestial-gas-form-on-rock",
    "celestial-scale-context", "earth-noun", "material-is-a-part", "cube", "role-weapon",
    "role-claw", "scale-contradiction", "inactive-acting", "wreck-emitter-array",
    "context-enclosed",
})

#: Both instruments' gated classes: the round-X structural set and the round-XI render traps.
#: Every instrument's gated classes: round-X structural, round-XI render traps, round-XII parts.
GATED = STRUCTURAL | STRUCTURAL_0914 | STRUCTURAL_0915


def sweep(seeds: int, path: str) -> "tuple[Counter, int]":
    """``(class counts, scenes with any non-info flag)`` over ``seeds`` scenes."""
    rng = random.Random(777)
    tally: Counter = Counter()
    flagged = 0
    for _ in range(seeds):
        entity_seed, scene_seed = rng.randrange(2**48), rng.randrange(2**48)
        wired = {}
        if path == "wired":
            _text, payload = generate_entity(entity_seed, SCIFI_PACK)
            wired = {1: payload}
        text, document = generate_scene(
            scene_seed, SCIFI_PACK, wired_entities=wired, entity_count=1
        )
        found = set(flags(SCIFI_PACK, document, text)) | set(
            flags_0914(SCIFI_PACK, document, text)
        ) | set(flags_0915(SCIFI_PACK, document, text))
        tally.update(found)
        flagged += any(not name.startswith("info-") for name in found)
    return tally, flagged


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=1500)
    parser.add_argument("--path", choices=("wired", "unwired"), default="wired")
    parser.add_argument("--gate", action="store_true")
    args = parser.parse_args(argv)
    logging.getLogger("sceneweaver").setLevel(logging.ERROR)
    tally, flagged = sweep(args.seeds, args.path)
    share = 100.0 * flagged / args.seeds
    print(f"concern_audit -- {args.path} path, {args.seeds} scenes, {share:.1f}% flagged")
    for name, count in tally.most_common():
        print(f"  {name:<36} {count:>5}  ({100.0 * count / args.seeds:.1f}%)")
    if args.gate:
        present = sorted(name for name in tally if name in GATED)
        if present:
            print("FAILED -- structural classes present: " + ", ".join(present))
            return 1
        print("OK -- no structural class present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
