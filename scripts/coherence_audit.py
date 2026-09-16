"""Coherence audit -- measure the scope chain, not the single scene.

    python scripts/coherence_audit.py                # 1000 seeds
    python scripts/coherence_audit.py --seeds 2000

**Why this exists.** ``tests/test_coherence.py`` sweeps and asserts invariants;
this is the maintainer's instrument that *names* a defect instead of failing a
boolean. It answers the question the scope chain was built to answer: does a
subkind resolve its ``form`` through a declared group, or does it fall through to
the kind pool -- which is exactly where "a dust-caked dwarf planet, a spiral
coil of gas" came from?

**Four numbers**, all measured over a sweep of the live generator:

* **group resolution per kind** -- the share of entities whose ``form`` resolved
  through a subkind group (or the raw subkind key) rather than the kind
  fall-through. The target is the celestial and alien-artifact kinds at 100%:
  every one of their subkinds is classified.
* **fall-through by subkind** -- the subkinds whose ``form`` still resolved
  through the kind pool, so an unclassified subkind is named rather than
  averaged away.
* **head-noun collision rate** -- the share of entities where two clause heads
*   inflect the same noun outside a shared vocabulary, which the engine's repeat
*   guard should hold at zero.
* **shape, per archetype** -- mean and p95 optional clause heads and tokens, the
*   share that speak an action, and the share that speak four or more component
*   clauses in one sentence. That last number is what separated the GOOD and BAD
*   buckets of the reference corpus, and it should sit near zero for the built and
*   inert archetypes. A report, not a gate.

Zero dependencies and no ComfyUI; imports ``data.scifi`` directly (never the
entrypoint) so ``user_options.json`` can never reach a committed number.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from data.genre import KIND_FIELD, archetype_name_for, scope_keys  # noqa: E402
from data.scifi import SCIFI_PACK  # noqa: E402
from engine.budget import count_tokens  # noqa: E402
from engine.grammar import head_noun  # noqa: E402
from engine.prose import render_entity  # noqa: E402
from engine.resolution import ResolvedEntity  # noqa: E402
from engine.scene import generate_scene  # noqa: E402


def _normalized_head(value: str) -> str:
    return head_noun(value).lower().rstrip("s")


def _form_route(pack, values, environment):
    """Which key ``form`` resolved through for one entity: group, raw, kind or default."""
    spec = pack.entity_fields["form"]
    scope = {
        control: values.get(control) if control in pack.entity_fields else environment
        for control in spec.scope
    }
    by_kind = pack.pools["form"]
    subkind = values.get("subkind")
    kind = values.get(KIND_FIELD)
    for key in scope_keys(pack, spec, scope):
        if key not in by_kind:
            continue
        if key in pack.pool_groups.get("subkind", {}):
            return "group"
        if key == subkind:
            return "raw"
        if key == kind:
            return "kind"
        return "default"
    return "none"


def _share_vocabulary(pack, a, b) -> bool:
    return any(a in group and b in group for group in pack.shared_vocabulary)


def _head_noun_collisions(pack, values) -> int:
    owner: dict[str, str] = {}
    collisions = 0
    for name in pack.entity_fields:
        if name == KIND_FIELD:
            continue
        if pack.entity_fields[name].renders_with is not None:
            continue
        value = values.get(name)
        if value is None:
            continue
        head = _normalized_head(value)
        held_by = owner.get(head)
        if held_by is None:
            owner[head] = name
            continue
        if _share_vocabulary(pack, name, held_by):
            continue
        collisions += 1
    return collisions


def _p95(values: list[int]) -> int:
    """The nearest-rank 95th percentile, or 0 for an empty sample."""
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return ordered[index]


def _optional_heads(pack, record) -> int:
    """Clause heads the entity actually speaks, excluding the kind spine."""
    return sum(
        1
        for name, spec in pack.entity_fields.items()
        if name != KIND_FIELD
        and spec.renders_with is None
        and record.get(name) is not None
    )


def _component_clauses(pack, record) -> int:
    """Component clauses in one sentence: the number that separated GOOD/BAD."""
    return sum(
        1
        for name in (
            "appendages", "emitters", "armament", "sensors", "aperture", "extras",
        )
        if record.get(name) is not None
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=1000, help="seeds to sweep")
    args = parser.parse_args(argv)

    pack = SCIFI_PACK
    by_kind_routes: dict[str, Counter] = defaultdict(Counter)
    fallthrough_subkinds: dict[str, Counter] = defaultdict(Counter)
    archetype_shape: dict[str, dict[str, list[int] | int]] = defaultdict(
        lambda: {"heads": [], "tokens": [], "action": 0, "heavy": 0, "total": 0}
    )
    entities = 0
    collisions = 0

    for seed in range(args.seeds):
        _text, document = generate_scene(seed, pack)
        environment = document["environment"]
        for record in document["entities"]:
            values = {k: v for k, v in record.items() if v is not None}
            kind = record.get(KIND_FIELD)
            if kind is None:
                continue
            entities += 1
            route = _form_route(pack, values, environment)
            by_kind_routes[kind][route] += 1
            if route in ("kind", "default"):
                subkind = record.get("subkind")
                fallthrough_subkinds[kind][subkind or "(none)"] += 1
            collisions += _head_noun_collisions(pack, record)

            name = archetype_name_for(
                pack, {n: record.get(n) for n in pack.entity_fields}
            )
            if name is not None:
                stats = archetype_shape[name]
                stats["total"] += 1
                stats["heads"].append(_optional_heads(pack, record))
                entity = ResolvedEntity(
                    index=record["index"],
                    source=record["source"],
                    genre=record["genre"],
                    fields={n: record.get(n) for n in pack.entity_fields},
                    situation=record.get("situation"),
                )
                stats["tokens"].append(count_tokens(render_entity(entity, pack)))
                if record.get("situation") is not None:
                    stats["action"] += 1
                if _component_clauses(pack, record) >= 4:
                    stats["heavy"] += 1

    print(f"seeds {args.seeds} -- {entities} entities")
    print()
    print("form resolution, per kind (share through a group/raw key):")
    for kind in pack.kinds:
        routes = by_kind_routes.get(kind, Counter())
        total = sum(routes.values())
        if total == 0:
            continue
        grouped = routes.get("group", 0) + routes.get("raw", 0)
        print(f"  {kind:<18} {grouped}/{total} group  ({100 * grouped / total:.1f}%)")
    print()
    print("form fall-through, by subkind (the unclassified holes):")
    for kind in pack.kinds:
        subs = fallthrough_subkinds.get(kind)
        if not subs:
            continue
        print(f"  {kind}:")
        for subkind, count in sorted(subs.items(), key=lambda kv: -kv[1]):
            print(f"    {subkind!r}  {count}")
    print()
    print(f"head-noun collisions: {collisions} across {entities} entities "
          f"({100 * collisions / entities:.2f}%)" if entities else "no entities")
    print()
    print("shape, per archetype (heads spoken / tokens / action / heavy):")
    header = f"  {'archetype':<12} {'n':>5} {'heads mean':>10} {'p95':>4} "
    print(header + f"{'tok mean':>9} {'p95':>4} {'action':>7} {'4+ comp':>8}")
    for name in sorted(archetype_shape):
        stats = archetype_shape[name]
        total = stats["total"]
        if not total:
            continue
        heads = stats["heads"]
        tokens = stats["tokens"]
        print(
            f"  {name:<12} {total:>5} {sum(heads) / total:>10.1f} {_p95(heads):>4} "
            f"{sum(tokens) / total:>9.1f} {_p95(tokens):>4} "
            f"{100 * stats['action'] / total:>6.1f}% "
            f"{100 * stats['heavy'] / total:>7.1f}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
