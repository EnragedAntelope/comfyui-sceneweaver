"""Coherence sweep -- measure the defect classes a viewer actually reports.

    python scripts/coherence_sweep.py                    # 3000 scenes, wired path
    python scripts/coherence_sweep.py --path unwired
    python scripts/coherence_sweep.py --gate             # exit 1 over a ceiling
    python scripts/coherence_sweep.py --examples 3       # print real prompts

**Why this exists, and why it is not another concern_flags file.**

``scripts/concern_flags*.py`` are frozen per-round lists: a defect gets reported,
it becomes a named flag, data changes until the flag reads zero, and the round
ends. They are regression instruments and they are good ones. What they cannot
do is find the *next* class, because every one of them was written by reading a
batch that had already been generated.

That is not a hypothetical. On the 2026-09-15 batch ``concern_audit.py`` reported
**0.0% of scenes flagged** while 44 of 101 rendered images -- 43.6% -- were bad
enough that the user pulled them out by hand. Twelve rounds had each driven their
own flag set to zero and generalised nothing.

So this sweep is written the other way round: each class is a *shape* of
incoherence rather than a list of known-bad strings, and wherever the pack
already declares the fact, the class reads the pack's declaration instead of
re-stating it. ``count-vs-noun`` asks ``value_cardinality`` how many of a thing
there can be; it does not keep a word list of singular nouns. When the data
grows, the class keeps working.

**Reading the numbers.** A class here is a *suspicion*, not a proven defect --
some are deliberately a little wide, and the docstring on each says where. The
ceilings in ``CEILINGS`` are what the round left them at, so a change that puts
one back up is visible. Raise a ceiling only with a measured reason written next
to it.

An instrument, not a test: ``tests/`` owns the gates. Imports ``data.scifi``
directly, never the entrypoint, so ``user_options.json`` can never reach a number.
"""
from __future__ import annotations

import argparse
import logging
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _entry in (str(_ROOT), str(_ROOT / "scripts")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from data.genre import (  # noqa: E402
    CONTEXT_FIELD, ENVIRONMENT_FIELD, SITUATION_FIELD, affordances_of,
)
from data.scifi import SCIFI_PACK as PACK  # noqa: E402
from engine.scene import generate_entity, generate_scene  # noqa: E402


def _words(*terms: str) -> "re.Pattern[str]":
    return re.compile(r"\b(" + "|".join(terms) + r")\b", re.I)


#: More than two of something.
MANY = {"a dozen", "rows of", "banks of", "a constellation of", "a ring of",
        "a cluster of", "a fan of", "eight", "six", "four", "three"}
#: Cardinality classes whose noun cannot honestly appear more than twice. Read
#: from the pack rather than from a word list -- see the module docstring.
AT_MOST_TWO = frozenset({
    "a lone part", "a matched pair", "a worn fitting", "a satellite",
    "a long arm", "a hand weapon", "a spinal mount",
})

#: Fields describing substance and state. Colour fields are deliberately absent:
#: scanning the rendered text instead made "ice-blue" read as ice.
SUBSTANCE_FIELDS = ("condition", "material", "surface_detail", "form", "aperture",
                    "extras", "appendages", "emitters", "markings", "subkind")

HOT = _words("scorched", "molten", "lava", "ember", "ember-hot", "burning", "ablaze",
             "soot-blackened", "incandescent", "sunburnt", "volcanic", "magma",
             "smouldering", "cinder", "furnace")
COLD = _words("frost", "frost-rimed", "ice-encrusted", "icy", "cryovolcanic", "frozen",
              "glacial", "rime", "sublimating", "snow", "hoar", "methane ice", "water ice")
FIRE = _words("fire", "burning", "ablaze", "igniting", "aflame", "flames?",
              "catching fire", "trailing fire", "smouldering")
#: No "storm": a gas giant's own storm bands are real and wanted.
WEATHER = _words("wind", "gust", "windswept", "wind-scour", "rain", "downpour",
                 "squall", "breeze")
#: An actor the model has to invent at scale. A second person or a probe is
#: drawable and dramatic and is deliberately not here.
OFFFRAME = _words("closing formation", "escorts?", "a barrage", "moon-sized impactor",
                  "a moon", "a smaller companion", "a boarding party", "boarding assault")
#: Framings that claim depth. "Beyond them, a rack of tools stands" is fine in a
#: bay; "In the distance" inside a cockpit is not.
DISTANCE = _words("in the distance", "further back", "further off", "far edge",
                  "on the horizon")
#: A person's anatomy, or kit worn on the body. None of it is *carried*.
ANATOMY_OR_WORN = ("gauntleted hand", "magnetic boot", "prosthetic arm",
                   "articulated exo-limb", "backpack thruster pod",
                   "magnetic safety clamp", "shoulder optic boom")
#: Words a model draws as a present-day firearm.
EARTH_GUN = _words("holstered sidearm", "wrist blaster", "mag-rifle", "energy carbine",
                   "shoulder launcher", "stun prod", "grenade bandolier", "sidearm",
                   "rifle", "carbine", "pistol", "shotgun")

#: The highest share each class is allowed. Measured at the end of round XIII;
#: anything above is a regression worth a look, not necessarily a bug.
CEILINGS: dict[str, float] = {
    "count-vs-noun": 0.5,
    "offframe-actor": 3.0,
    "inactive-but-acting": 2.5,
    "pristine-but-destroyed": 1.5,
    "interior-wrong-subject": 1.5,
    "interior-distance-context": 1.0,
    "thermal-conflict": 1.5,
    "fire-in-wrong-medium": 0.5,
    "weather-in-wrong-medium": 1.0,
    "carries-worn-kit": 0.5,
    "earth-gun-word": 0.5,
    "noncombat-role-armed": 1.0,
    "body-bears-moonlets": 0.5,
}


def _trait_values(field: str, trait: str) -> "frozenset[str]":
    """Every value of ``field`` the pack says carries ``trait``."""
    return frozenset(
        value for value, traits in (PACK.value_traits.get(field) or {}).items()
        if trait in traits
    )


INACTIVE = _trait_values("condition", "inactive")
PRISTINE = _trait_values("condition", "pristine-state")
POWERED = _trait_values(SITUATION_FIELD, "powered-act")
DESTRUCTION = _trait_values(SITUATION_FIELD, "destruction-act")
COMBUSTION = _trait_values(SITUATION_FIELD, "combustion")
#: Deliberately wider than the pack's ``powered-act``: an independent check has
#: to be able to find an act the pack has NOT tagged yet. That is the whole
#: difference between this and a frozen flag file.
ACTIVE_GERUND = _words("firing", "launching", "catching", "raising", "unfolding",
                       "advancing", "chasing", "hauling", "lifting", "drilling",
                       "welding", "sweeping", "dragging", "engulfing", "settling",
                       "landing", "matching", "punching", "decelerating",
                       "patrolling", "slamming", "folding", "unloading",
                       "crash-landing", "dropping", "snapping")
BREAKING_GERUND = _words("breaking", "shattering", "bursting", "collapsing",
                         "venting", "tearing", "coming apart", "splitting",
                         "buckling", "crumbling", "disintegrating", "shearing",
                         "overloading")
#: Roles a viewer expects to see armed. Wider than "soldier" on purpose: the
#: reported defect was a scientist and a cartographer holding a gun.
COMBAT_ROLES = frozenset({
    "marine", "mercenary", "raider", "reptilian bounty hunter", "tusked mercenary",
    "horned warlord", "smuggler", "pilot", "captain", "salvager", "crested pilot",
    "amphibian admiral",
})


def classes(text: str, document: dict) -> "list[str]":
    """Every class this scene falls into."""
    out: list[str] = []
    if not document["entities"]:
        return out
    entity = document["entities"][0]
    place = document.get(ENVIRONMENT_FIELD) or ""
    affords = affordances_of(PACK, place)
    kind = entity.get("kind") or ""
    subkind = entity.get("subkind") or ""
    low = text.lower()
    context = (document.get(CONTEXT_FIELD) or "").lower()
    situation = (entity.get(SITUATION_FIELD) or "").lower()
    condition = entity.get("condition") or ""
    indoors = place in (PACK.environment_bands.get("interior") or ())
    substance = " ".join((entity.get(f) or "") for f in SUBSTANCE_FIELDS).lower()

    # A count the noun cannot support. Asks the pack's own cardinality table.
    for noun_field, count_field in PACK.counts.items():
        noun = entity.get(noun_field) or ""
        declared = (PACK.value_cardinality.get(noun_field) or {}).get(noun)
        if noun and (entity.get(count_field) or "") in MANY and declared in AT_MOST_TWO:
            out.append("count-vs-noun")
            break

    # A state and an act that cannot both be true.
    if condition in INACTIVE and ACTIVE_GERUND.search(situation):
        out.append("inactive-but-acting")
    if condition in PRISTINE and BREAKING_GERUND.search(situation):
        out.append("pristine-but-destroyed")

    # Two substances that cannot both be on one body.
    if HOT.search(substance) and COLD.search(substance):
        out.append("thermal-conflict")

    # An element the medium cannot carry.
    if FIRE.search(situation) and "submerged" in affords:
        out.append("fire-in-wrong-medium")
    if WEATHER.search(situation + " " + context) and (
            "submerged" in affords or "open-space" in affords):
        out.append("weather-in-wrong-medium")

    # An actor or a framing the scene cannot show.
    if OFFFRAME.search(situation):
        out.append("offframe-actor")
    if indoors and context and DISTANCE.search(low):
        out.append("interior-distance-context")
    if indoors and (
        kind in {"celestial body", "starship"}
        or (kind in {"alien creature", "wreck"}
            and entity.get("scale") in {"large", "massive", "colossal", "planetary"})
    ):
        out.append("interior-wrong-subject")

    # A world wearing its own satellites, in the COUNTED slot only.
    if kind == "celestial body" and re.search(r"\bmoonlets?\b", entity.get("appendages") or ""):
        out.append("body-bears-moonlets")

    # Worn kit behind a carrying verb, inside the carrying clause only.
    carried = re.search(r"\bcarr(?:y|ies)\b([^.]*)", low)
    if carried and any(word in carried.group(1) for word in ANATOMY_OR_WORN):
        out.append("carries-worn-kit")

    # A weapon that draws as a present-day firearm, and a role that should
    # not be holding one at all.
    if EARTH_GUN.search(low):
        out.append("earth-gun-word")
    if kind == "spacefarer" and subkind not in COMBAT_ROLES and entity.get("armament"):
        out.append("noncombat-role-armed")

    return out


def sweep(seeds: int, path: str, examples: int):
    """``(counts, scenes with any class, examples)`` over ``seeds`` scenes."""
    rng = random.Random(777)
    tally: Counter = Counter()
    shown: dict[str, list[str]] = defaultdict(list)
    flagged = 0
    for _ in range(seeds):
        entity_seed, scene_seed = rng.randrange(2**48), rng.randrange(2**48)
        wired = {}
        if path == "wired":
            _text, payload = generate_entity(entity_seed, PACK)
            wired = {1: payload}
        text, document = generate_scene(
            scene_seed, PACK, wired_entities=wired, entity_count=1
        )
        found = classes(text, document)
        tally.update(found)
        flagged += bool(found)
        for name in found:
            if len(shown[name]) < examples:
                shown[name].append(text)
    return tally, flagged, shown


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=3000)
    parser.add_argument("--path", choices=("wired", "unwired"), default="wired")
    parser.add_argument("--examples", type=int, default=0)
    parser.add_argument("--gate", action="store_true")
    args = parser.parse_args(argv)
    logging.getLogger("sceneweaver").setLevel(logging.ERROR)

    tally, flagged, shown = sweep(args.seeds, args.path, args.examples)
    share = 100.0 * flagged / args.seeds
    print(f"coherence_sweep -- {args.path} path, {args.seeds} scenes, "
          f"{share:.1f}% carry at least one class")
    over: list[str] = []
    for name in sorted(CEILINGS):
        count = tally.get(name, 0)
        pct = 100.0 * count / args.seeds
        ceiling = CEILINGS[name]
        mark = ""
        if pct > ceiling:
            mark = f"  <-- over ceiling {ceiling:.1f}%"
            over.append(f"{name} {pct:.1f}% > {ceiling:.1f}%")
        print(f"  {name:<28} {count:>5}  ({pct:>5.2f}%){mark}")

    if args.examples:
        for name, rows in shown.items():
            print(f"\n### {name}")
            for row in rows:
                print(f"  - {row[:300]}")

    if args.gate:
        if over:
            print("\nFAILED -- over ceiling: " + "; ".join(over))
            return 1
        print("\nOK -- every class within its ceiling.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
