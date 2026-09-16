"""Todo 22 -- measure what the generator actually produces.

    python scripts/sample_distribution.py                 # 1000 seeds, Everything
    python scripts/sample_distribution.py --seeds 5000
    python scripts/sample_distribution.py --detail-level Standard --filter Peaceful

**Bias is measured, not assumed.** Identity Forge only discovered that 13.7% of
its default male renders were carrying a handbag by sweeping a thousand seeds --
no test failed, no pool looked wrong, and every individual draw was legal. The
defect was in the *distribution*, which is invisible to every check that looks
at one scene at a time. This script is the check that looks at all of them.

It reports four things and enforces three ceilings:

* **per-kind share** -- which of the nine kinds a slot actually gets. A kind
  above ``KIND_CEILING`` means one subject dominates the pack.
* **``scale`` extremes** -- ``colossal`` + ``planetary`` share, held under
  ``SCALE_EXTREME_CEILING`` by the pack's own weights. Scale reads by contrast:
  a generator that makes everything enormous has no scale at all.
* **per-value share within each field** -- the handbag check. A value far above
  its pool's uniform share is flagged, unless the pack weights that field on
  purpose.
* **motif share** -- the share of prompts containing any word of a declared
  cross-field motif (ice, heat, rust, growth, dust). A per-value check cannot
  see a bias spread across five fields; this is the number that can, and it is
  held under ``MOTIF_CEILING``.

Zero dependencies and no ComfyUI, so it runs anywhere the pack does. Exits 1
when a ceiling is breached, so it can be a gate rather than a report nobody
reads. Re-run it after any pool change and update the baseline recorded in
``docs/architecture.md``.

**It imports ``data.scifi``, not the pack entrypoint.** The ``user_options.json``
merge happens in the repo-root ``__init__.py``, so importing the data module
yields the built-ins and only the built-ins -- a maintainer's private entries can
never reach a number that gets written into a committed document. See
``data/user_options.py`` and ``scripts/builtin_options.py``.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from data.genre import SCENE_FILTERS, SCENE_NODE_SLOTS, pool_for  # noqa: E402
from data.scifi import SCIFI_PACK  # noqa: E402
from engine.scene import generate_scene  # noqa: E402

#: No kind may take more than this share of occupied slots. Nine kinds draw
#: uniformly, so the expected share is ~11%; the ceiling leaves room for the
#: constraint pass to redistribute without letting one subject take over.
KIND_CEILING = 0.20

#: ``colossal`` + ``planetary`` share of drawn scales. Two values out of a
#: seven-rung ladder would be ~29% on a flat draw; the pack weights them down,
#: because a scene where everything is enormous has no sense of scale at all.
#: Measured at 7.2% over 1000 seeds.
SCALE_EXTREME_CEILING = 0.10

#: No declared motif may appear in more than this share of prompts. A motif is a
#: word family measured across the WHOLE prompt, so the per-value ceiling cannot
#: see it: the ice motif reached about a quarter of output while every individual
#: pool looked unremarkable. Each substring is matched at a WORD START, so "ice"
#: does not fire on "service" and "ash" not on "crash".
#:
#: Calibrated to the measured baseline, not started at the plan's 0.25: the plan
#: expected ice to be the worst family, but measured over the widest scene the
#: heat family sits far higher because it is woven through twelve fields
#: (scorched/soot-blackened in every condition pool, lava/molten in materials,
#: emitters and markings, four situations). Pulling it under 0.25 would mean
#: culling, which the pack forbids; the ceiling is therefore baseline + headroom
#: and acts as a regression gate. The per-motif baseline is recorded in
#: ``docs/architecture.md``.
MOTIF_CEILING = 0.70

#: Per-motif overrides of ``MOTIF_CEILING``. A motif that is one idea spread
#: across several fields needs a tighter gate than the family baseline: the
#: ring motif reached ~39% of prompts from fifteen fields at once.
MOTIF_CEILINGS: dict[str, float] = {"ring": 0.15}

#: A value more than this multiple of its pool's uniform share is flagged. Not
#: a failure, and usually not a defect either: the commonest cause is a value
#: several kinds share ("hazard chevrons" is in the vessel, station and vehicle
#: markings pools, so it draws about four times as often as a value only one
#: kind offers). It is the number to look at first when the output starts
#: feeling repetitive.
VALUE_SKEW_FACTOR = 2.5

SCALE_EXTREMES = ("colossal", "planetary")


def motif_hits(text: str, motifs) -> set[str]:
    """The declared motifs whose substrings appear in ``text``.

    Genre-blind: it reads whatever ``{motif: (substring, ...)}`` mapping it is
    given. A substring is matched at a WORD START, so a stem like "oxid" still
    catches "oxidised" while "ice" does not fire on "service".
    """
    low = text.lower()
    return {
        name
        for name, substrings in motifs.items()
        if any(re.search(rf"\b{re.escape(s)}", low) for s in substrings)
    }


def sweep(seeds: int, scene_filter: str):
    """``(per-field counter, slots, scenes, motif counter)``."""
    fields: dict[str, Counter] = {name: Counter() for name in SCIFI_PACK.entity_fields}
    fields["environment"] = Counter()
    fields["situation"] = Counter()
    motifs: Counter = Counter()
    slots = 0
    for seed in range(seeds):
        # Every slot occupied, so the sweep measures the widest scene the node
        # can build. ``entity_count`` is the control that fills them; setting
        # the kind widgets alone stopped being enough when the count arrived,
        # and this silently measured one slot per scene until it did.
        text, document = generate_scene(
            seed, SCIFI_PACK, scene_filter=scene_filter,
            entity_count=SCENE_NODE_SLOTS,
        )
        for name in motif_hits(text, SCIFI_PACK.motifs):
            motifs[name] += 1
        if document["environment"]:
            fields["environment"][document["environment"]] += 1
        for record in document["entities"]:
            slots += 1
            for name in SCIFI_PACK.entity_fields:
                if record.get(name):
                    fields[name][record[name]] += 1
            if record.get("situation"):
                fields["situation"][record["situation"]] += 1
    return fields, slots, seeds, motifs


def _share_table(counter: Counter, total: int, limit: int) -> list[str]:
    if not total:
        return ["    (never drawn)"]
    return [
        f"    {value:<38} {count / total:6.2%}  ({count})"
        for value, count in counter.most_common(limit)
    ]


def report(fields, slots: int, scenes: int, top: int, motifs: "Counter | None" = None) -> list[str]:
    failures: list[str] = []

    print(f"scenes {scenes}   occupied slots {slots}")
    print()
    print("per-kind share of occupied slots")
    for kind, count in fields["kind"].most_common():
        share = count / slots if slots else 0.0
        flag = "  <-- over ceiling" if share > KIND_CEILING else ""
        print(f"    {kind:<38} {share:6.2%}  ({count}){flag}")
        if share > KIND_CEILING:
            failures.append(
                f"kind {kind!r} takes {share:.2%} of slots, over the {KIND_CEILING:.0%} "
                "ceiling: one subject is crowding out the rest"
            )
    print()

    scale_total = sum(fields["scale"].values())
    extreme = sum(fields["scale"][value] for value in SCALE_EXTREMES)
    share = extreme / scale_total if scale_total else 0.0
    print(f"scale extremes ({' + '.join(SCALE_EXTREMES)}): {share:.2%} of drawn scales")
    flat = len(SCALE_EXTREMES) / max(1, len(pool_for(SCIFI_PACK, "scale")))
    print(f"    a flat draw over the ladder would give {flat:.2%}")
    if share > SCALE_EXTREME_CEILING:
        failures.append(
            f"colossal+planetary at {share:.2%}, over the {SCALE_EXTREME_CEILING:.0%} "
            "ceiling: scale reads by contrast and everything being enormous has none"
        )
    print()

    print(f"per-field value share (top {top})")
    for name in sorted(fields):
        counter = fields[name]
        total = sum(counter.values())
        voiced = total / slots if slots and name != "environment" else total / max(1, scenes)
        print(f"  {name}  --  voiced on {voiced:.1%} of {'scenes' if name == 'environment' else 'slots'}")
        for line in _share_table(counter, total, top):
            print(line)
        spec = SCIFI_PACK.entity_fields.get(name)
        if total and counter and not (spec and spec.weights):
            uniform = 1.0 / len(counter)
            value, count = counter.most_common(1)[0]
            if count / total > uniform * VALUE_SKEW_FACTOR:
                print(
                    f"    NOTE {value!r} is {count / total / uniform:.1f}x the uniform "
                    "share of the values that were drawn"
                )
    print()
    print("motif share (per-motif ceilings)")
    for name, count in (motifs or Counter()).most_common():
        share = count / scenes if scenes else 0.0
        ceiling = MOTIF_CEILINGS.get(name, MOTIF_CEILING)
        flag = "  <-- over ceiling" if share > ceiling else ""
        print(f"    {name:<12} {share:6.2%}  ({count}){flag}")
        if share > ceiling:
            failures.append(
                f"motif {name!r} appears in {share:.2%} of prompts, over the "
                f"{ceiling:.0%} ceiling: one idea is spread across several fields"
            )
    return failures


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=1000)
    parser.add_argument("--filter", dest="scene_filter", default="Any", choices=SCENE_FILTERS)
    parser.add_argument("--top", type=int, default=5, help="values listed per field")
    args = parser.parse_args(argv)

    print(f"sample_distribution -- {SCIFI_PACK.display} pack")
    print(f"scene_filter={args.scene_filter}")
    print()
    fields, slots, scenes, motifs = sweep(args.seeds, args.scene_filter)
    failures = report(fields, slots, scenes, args.top, motifs)
    print()
    if failures:
        print(f"FAILED with {len(failures)} finding(s):")
        for line in failures:
            print(f"  {line}")
        return 1
    print("OK -- no kind, scale or motif ceiling breached.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
