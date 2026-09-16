"""Reach audit -- a value nobody draws is dead.

    python scripts/reach_audit.py --seeds 12000 [--path wired|unwired|both] [--gate]
    python scripts/reach_audit.py --explain "luminous flank slit"

``check_shadowed_values`` in ``tests/validate_data.py`` proves a value is *reachable*: some
subject's scope chain resolves the key it is authored under. Reachable is not drawn. A
value can be reachable on paper and still never appear in a real scene -- a creature
emitter, a world-scale feature, a situation in a place no scene ever picks -- and the
per-field liveness test cannot see it, because it measures the field, not the value.

This sweep measures the values: it generates real scenes on the path the user runs, counts
every non-None value of every head field, and reports the ones that never came up. A value
is exempt when it is stranger vocabulary (authored under ``_default`` alone, the same test
``check_shadowed_values`` uses) or when every archetype of every subject whose resolved
pool holds it lists the field in ``omits`` -- a station has no colour to draw, so its
colours are not dead.

An instrument, not a gate: ``tests/`` owns the gates. ``--gate`` is for CI. There is no
allowlist: a never-drawn value is fixed by scoping, needs, or replacement.
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

import data.genre as G  # noqa: E402
from data.scifi import SCIFI_PACK as P  # noqa: E402
from engine.scene import generate_entity, generate_scene  # noqa: E402

_SEED = 4242
_PROGRESS = 2000
#: Read from the document rather than the entity record.
_SCENE_FIELDS = (G.CONTEXT_FIELD, G.ENVIRONMENT_FIELD)

#: Every field the sweep counts: a head field of the entity, plus situation and the two
#: scene fields. ``situation`` is a scene field in this pack but is stored per entity, so
#: it is read from the record like the rest.
FIELDS = tuple(sorted(
    {name for name, spec in P.entity_fields.items()
     if spec.renders_with is None and name != G.KIND_FIELD}
    | {G.SITUATION_FIELD}
    | set(_SCENE_FIELDS)
))


def _subjects(pack):
    """Every ``(kind, type)`` a scene can hold; ``(kind, None)`` for a kind with no types."""
    name = G.type_field(pack)
    for kind in pack.kinds:
        values = G.pool_for(pack, name, {G.KIND_FIELD: kind}) if name else ()
        for value in values or (None,):
            yield kind, value


def _reach(pack, field_name):
    """``{value: [(kind, type), ...]}`` -- every subject whose resolved pool holds the value."""
    name = G.type_field(pack)
    reach: dict[str, list[tuple[str, str | None]]] = {}
    for kind, value in _subjects(pack):
        scope = {G.KIND_FIELD: kind}
        if name and value is not None:
            scope[name] = value
        for option in G.pool_for(pack, field_name, scope):
            reach.setdefault(option, []).append((kind, value))
    return reach


def _exempt(field, value, reach):
    """Whether a never-drawn value is excused rather than dead."""
    if G.pool_keys_for_value(P, field, value) == (G.POOL_DEFAULT_KEY,):
        return True
    name = G.type_field(P)
    for kind, subkind in reach.get(value, ()):
        scope = {G.KIND_FIELD: kind}
        if name is not None and subkind is not None:
            scope[name] = subkind
        archetype = G.archetype_for(P, scope)
        if archetype is None or field not in archetype.omits:
            return False
    return True


def _sweep(path, seeds):
    """Count every non-None value of every field over ``seeds`` scenes on ``path``."""
    rng = random.Random(_SEED)
    counts = {field: Counter() for field in FIELDS}
    for index in range(seeds):
        if path == "wired":
            _text, payload = generate_entity(rng.randrange(2**48), P)
            _text, document = generate_scene(
                rng.randrange(2**48), P, wired_entities={1: payload}, entity_count=1
            )
        else:
            _text, document = generate_scene(rng.randrange(2**48), P, entity_count=1)
        record = document["entities"][0] if document["entities"] else {}
        for field in FIELDS:
            value = document.get(field) if field in _SCENE_FIELDS else record.get(field)
            if value is not None:
                counts[field][value] += 1
        done = index + 1
        if done % _PROGRESS == 0:
            print(f"  {path}: {done}/{seeds} scenes", flush=True)
    return counts


def _report(label, counts):
    """Print the per-field table and the never/exempt lists; return ``{field: dead}``."""
    print(f"\nreach_audit -- {label}")
    print(f"  {'field':<16}{'options':>8}{'drawn':>7}{'rare<=2':>9}{'never':>7}{'exempt':>8}")
    dead_by_field: dict[str, list[str]] = {}
    exempt_by_field: dict[str, list[str]] = {}
    for field in FIELDS:
        options = G.pool_options(P, field)
        seen = counts[field]
        never = [value for value in options if value not in seen]
        reach = _reach(P, field)
        exempt = {value for value in never if _exempt(field, value, reach)}
        dead = [value for value in never if value not in exempt]
        dead_by_field[field] = dead
        exempt_by_field[field] = sorted(exempt)
        rare = sum(1 for count in seen.values() if count <= 2)
        print(f"  {field:<16}{len(options):>8}{len(seen):>7}{rare:>9}"
              f"{len(dead):>7}{len(exempt):>8}")
    for field in FIELDS:
        if dead_by_field[field]:
            print(f"  never  {field}: " + ", ".join(dead_by_field[field]))
    for field in FIELDS:
        if exempt_by_field[field]:
            print(f"  exempt {field}: " + ", ".join(exempt_by_field[field]))
    return dead_by_field


def _explain(value):
    """Print everything known about one value, without a sweep."""
    fields = sorted(set(P.pools) | set(FIELDS))
    found = False
    for field in fields:
        if value not in G.pool_options(P, field):
            continue
        found = True
        reach = _reach(P, field)
        print(f"{field}: {value!r}")
        print(f"  pool keys: {G.pool_keys_for_value(P, field, value)}")
        print(f"  subjects: {reach.get(value, [])}")
        print(f"  needs: {P.value_needs.get(field, {}).get(value, '<unset>')}")
        print(f"  traits: {P.value_traits.get(field, {}).get(value, '<unset>')}")
        print(f"  stances: {P.value_stances.get(field, {}).get(value, '<unset>')}")
        print(f"  tier: {P.value_tiers.get(field, {}).get(value, '<untiered>')}")
    if not found:
        print(f"{value!r} is not a value of any pool in this pack.")
    return 0


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=12000)
    parser.add_argument("--path", choices=("wired", "unwired", "both"), default="both")
    parser.add_argument("--gate", action="store_true")
    parser.add_argument("--explain", default="", metavar="VALUE")
    args = parser.parse_args(argv)
    logging.getLogger("sceneweaver").setLevel(logging.ERROR)
    if args.explain:
        return _explain(args.explain)
    paths = ("wired", "unwired") if args.path == "both" else (args.path,)
    merged = {field: Counter() for field in FIELDS}
    dead_by_field: dict[str, list[str]] = {}
    for path in paths:
        counts = _sweep(path, args.seeds)
        dead_by_field = _report(f"{path} path, {args.seeds} scenes", counts)
        for field in FIELDS:
            merged[field].update(counts[field])
    if len(paths) > 1:
        dead_by_field = _report(f"union of {args.seeds} scenes on each path", merged)
    if args.gate:
        present = sorted(field for field, dead in dead_by_field.items() if dead)
        if present:
            print("\nFAILED -- never-drawn values in: " + ", ".join(present))
            return 1
        print("\nOK -- every non-exempt value is drawn.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
