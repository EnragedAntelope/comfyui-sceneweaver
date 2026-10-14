"""Reach audit -- a value nobody draws is dead.

    python scripts/reach_audit.py --seeds 12000 [--path wired|unwired|locked|both] [--gate]
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


def _scenes(path, seeds):
    """Yield ``(text, document)`` for ``seeds`` one-entity scenes on ``path``."""
    rng = random.Random(_SEED)
    # 0.8.0: the locked path gives every subject the same share of scenes, so a
    # one-type value is not left to how often a random scene happens to pick its type.
    subjects = list(G.subjects(P))
    type_widget = f"entity1_{G.type_field(P)}"
    for index in range(seeds):
        if path == "locked":
            kind, value = subjects[index % len(subjects)]
            widgets = {"entity1_kind": kind} | ({type_widget: value} if value else {})
            yield generate_scene(rng.randrange(2**48), P, widgets=widgets, entity_count=1)
        elif path == "wired":
            _text, payload = generate_entity(rng.randrange(2**48), P)
            yield generate_scene(
                rng.randrange(2**48), P, wired_entities={1: payload}, entity_count=1
            )
        else:
            yield generate_scene(rng.randrange(2**48), P, entity_count=1)
        done = index + 1
        if done % _PROGRESS == 0:
            print(f"  {path}: {done}/{seeds} scenes", flush=True)


def _sweep(path, seeds):
    """Count every non-None value of every field over ``seeds`` scenes on ``path``."""
    counts = {field: Counter() for field in FIELDS}
    for _text, document in _scenes(path, seeds):
        record = document["entities"][0] if document["entities"] else {}
        for field in FIELDS:
            value = document.get(field) if field in _SCENE_FIELDS else record.get(field)
            if value is not None:
                counts[field][value] += 1
    return counts


#: The fields that put a face on the subject; their share is reported, not gated.
_FACE_FIELDS = ("sensors", "aperture")


def _variety(path, seeds):
    """Print the look and act variety a user actually sees, per pack.

    The numbers the 0.8.0 floors are judged by: distinct ``(variant, form)``
    silhouettes per type, the share of drawn acts that are the subject's own,
    the most common opening verb, how often the context goes unsaid, and how
    often a face is named.
    """
    name = G.type_field(P)
    owned = G.own_values(P, G.SITUATION_FIELD)
    looks: dict[str, set] = {}
    draws: Counter = Counter()
    verbs: Counter = Counter()
    acts = own = no_context = faces = 0
    for _text, document in _scenes(path, seeds):
        if document.get(G.CONTEXT_FIELD) is None:
            no_context += 1
        if not document["entities"]:
            continue
        record = document["entities"][0]
        subject = record.get(name) or record.get(G.KIND_FIELD)
        draws[subject] += 1
        looks.setdefault(subject, set()).add((record.get("variant"), record.get(G.STANCE_FIELD)))
        if any(record.get(field) for field in _FACE_FIELDS):
            faces += 1
        act = record.get(G.SITUATION_FIELD)
        if act:
            acts += 1
            own += act in owned
            verbs[act.split()[0]] += 1
    top_verb, top_count = verbs.most_common(1)[0] if verbs else ("-", 0)
    silhouettes = sorted((len(v), k) for k, v in looks.items())
    thin = [k for n, k in silhouettes if n < 8 and draws[k] >= 30]
    print(f"\nvariety -- {path} path, {seeds} scenes")
    print(f"  own-act share        {own / max(acts, 1):6.1%}   (held by <= 3 types or one group)")
    print(f"  top first verb       {top_count / max(acts, 1):6.1%}   ({top_verb!r})")
    print(f"  context absent       {no_context / seeds:6.1%}")
    print(f"  face named           {faces / seeds:6.1%}")
    median = silhouettes[len(silhouettes) // 2][0] if silhouettes else 0
    print(f"  silhouettes / type   median {median}, types drawn {len(silhouettes)}")
    print(f"  under 8 silhouettes  {len(thin)} types drawn 30+ times")
    if thin:
        print("    " + ", ".join(thin[:40]) + (" ..." if len(thin) > 40 else ""))
    return thin


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
        reach = G.value_reach(P, field)
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
        reach = G.value_reach(P, field)
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
    parser.add_argument("--path", choices=("wired", "unwired", "locked", "both"), default="both")
    parser.add_argument("--gate", action="store_true")
    parser.add_argument("--explain", default="", metavar="VALUE")
    parser.add_argument("--variety", action="store_true", help="report look and act variety")
    parser.add_argument("--seed", type=int, default=4242, help="sweep seed (--variety)")
    parser.add_argument("--pack", choices=("scifi", "fantasy", "horror"), default="scifi")
    args = parser.parse_args(argv)
    if args.pack == "fantasy":
        global P
        from data.fantasy import FANTASY_PACK as P  # noqa: PLW0603
    elif args.pack == "horror":
        from data.horror import HORROR_PACK as P  # noqa: PLW0603
    logging.getLogger("sceneweaver").setLevel(logging.ERROR)
    if args.explain:
        return _explain(args.explain)
    paths = ("wired", "unwired", "locked") if args.path == "both" else (args.path,)
    if args.variety:
        global _SEED
        _SEED = args.seed
        thin = [_variety(path, args.seeds) for path in paths if path != "locked"]
        return 1 if args.gate and any(thin) else 0
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
