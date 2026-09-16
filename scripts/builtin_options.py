"""Todo 23 -- read the pack's **built-in** option values without importing it.

    python scripts/builtin_options.py                 # every field, with counts
    python scripts/builtin_options.py markings form   # just these fields
    python scripts/builtin_options.py --kind vessel markings

**Why this exists.** A user's ``user_options.json`` is merged into the pack at
import time, in the repo-root ``__init__.py``. Any script that reads the data
layer *by importing it* therefore sees the maintainer's private entries, and
anything it writes into a committed file ships them to everyone
(``feedback-generator-cannot-leak-user-data``). Identity Forge shipped exactly
that. Parsing the source instead makes the leak impossible rather than merely
avoided -- there is no code path here that could read the JSON file.

So: **any future generator, checker or doc-builder that needs pool values must
use this module, not ``import data.scifi``.** The rule is not "remember to be
careful"; it is "the careful path is the only one that exists".

``tests/test_user_options.py`` proves it, with a real ``user_options.json`` on
disk: the merged pack contains the custom value and this reader does not.

**How.** ``ast.parse`` on ``data/genre.py`` and ``data/scifi.py``, then a small
evaluator over the top-level assignments that understands literals, names bound
earlier in the file, tuple/list/string concatenation, starred unpacking and
constant subscripts. An expression it cannot resolve binds nothing and is
reported by ``--unresolved``; it never guesses and never executes anything.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

#: Parsed in order, so ``data/scifi.py`` can resolve the constants it imports
#: from ``data/genre.py`` without either module being executed.
_SOURCES = ("data/genre.py", "data/scifi.py")

#: Sentinel for an expression the evaluator declines to resolve. Distinct from
#: ``None``, which is a value a module can legitimately bind.
UNRESOLVED = object()


class _Evaluator:
    """Resolves the literal subset of a module's top-level assignments.

    Nothing here executes code. ``resolve`` walks the AST and rebuilds values
    from node types it recognises; anything else returns ``UNRESOLVED``. There
    is no ``eval``, no ``exec`` and no ``compile`` -- which is the whole point,
    since the reason not to import the module is precisely that importing runs
    it.
    """

    def __init__(self) -> None:
        self.env: dict[str, Any] = {}
        self.unresolved: list[str] = []

    def load(self, path: Path) -> None:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id] if node.value is not None else []
            else:
                continue
            if not targets:
                continue
            value = self.resolve(node.value)
            for name in targets:
                if value is UNRESOLVED:
                    self.unresolved.append(f"{path.name}:{node.lineno} {name}")
                else:
                    self.env[name] = value

    def resolve(self, node: ast.AST | None) -> Any:
        if node is None:
            return UNRESOLVED
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return self.env.get(node.id, UNRESOLVED)
        if isinstance(node, (ast.Tuple, ast.List)):
            items: list[Any] = []
            for element in node.elts:
                if isinstance(element, ast.Starred):
                    inner = self.resolve(element.value)
                    if inner is UNRESOLVED:
                        return UNRESOLVED
                    items.extend(inner)
                    continue
                value = self.resolve(element)
                if value is UNRESOLVED:
                    return UNRESOLVED
                items.append(value)
            return tuple(items) if isinstance(node, ast.Tuple) else items
        if isinstance(node, ast.Set):
            values = [self.resolve(e) for e in node.elts]
            return UNRESOLVED if UNRESOLVED in values else set(values)
        if isinstance(node, ast.Dict):
            result: dict[Any, Any] = {}
            for key_node, value_node in zip(node.keys, node.values):
                if key_node is None:  # {**other}
                    inner = self.resolve(value_node)
                    if inner is UNRESOLVED:
                        return UNRESOLVED
                    result.update(inner)
                    continue
                key = self.resolve(key_node)
                value = self.resolve(value_node)
                if key is UNRESOLVED or value is UNRESOLVED:
                    return UNRESOLVED
                result[key] = value
            return result
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = self.resolve(node.left), self.resolve(node.right)
            if left is UNRESOLVED or right is UNRESOLVED:
                return UNRESOLVED
            try:
                return left + right
            except TypeError:
                return UNRESOLVED
        if isinstance(node, ast.Subscript):
            container, index = self.resolve(node.value), self.resolve(node.slice)
            if container is UNRESOLVED or index is UNRESOLVED:
                return UNRESOLVED
            try:
                return container[index]
            except (KeyError, IndexError, TypeError):
                return UNRESOLVED
        return UNRESOLVED


def read_pack(root: Path = _ROOT) -> _Evaluator:
    """Parse the data modules and return the resolved top-level environment."""
    evaluator = _Evaluator()
    for relative in _SOURCES:
        evaluator.load(root / relative)
    return evaluator


def builtin_pools(root: Path = _ROOT) -> dict[str, dict[str, tuple[str, ...]]]:
    """``{field: {kind: (values, ...)}}`` as committed in ``data/scifi.py``.

    Never includes anything from ``user_options.json`` -- there is no code here
    that reads it.
    """
    pools = read_pack(root).env.get("POOLS")
    if pools is UNRESOLVED or not isinstance(pools, dict):
        raise SystemExit(
            "could not resolve POOLS from the source. The evaluator understands "
            "literals, earlier names, + concatenation, *unpacking and constant "
            "subscripts; something in data/scifi.py now needs more than that. "
            "Widen the evaluator -- do not fall back to importing the module."
        )
    return {field: {kind: tuple(values) for kind, values in by_kind.items()}
            for field, by_kind in pools.items()}


def builtin_values(field: str, kind: str | None = None, root: Path = _ROOT) -> tuple[str, ...]:
    """Every built-in value of ``field``, optionally narrowed to one ``kind``."""
    by_kind = builtin_pools(root).get(field, {})
    if kind is not None:
        return by_kind.get(kind, by_kind.get("_default", ()))
    seen: dict[str, None] = {}
    for values in by_kind.values():
        for value in values:
            seen.setdefault(value, None)
    return tuple(seen)


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("fields", nargs="*", help="fields to list; default is all")
    parser.add_argument("--kind", help="narrow to one kind's pool")
    parser.add_argument("--unresolved", action="store_true",
                        help="list assignments the evaluator declined to resolve")
    args = parser.parse_args(argv)

    if args.unresolved:
        evaluator = read_pack()
        for line in evaluator.unresolved:
            print(line)
        return 0

    pools = builtin_pools()
    fields = args.fields or sorted(pools)
    for field in fields:
        if field not in pools:
            print(f"unknown field {field!r}", file=sys.stderr)
            return 2
        values = builtin_values(field, args.kind)
        print(f"{field}{f'[{args.kind}]' if args.kind else ''}  ({len(values)})")
        for value in values:
            print(f"    {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
