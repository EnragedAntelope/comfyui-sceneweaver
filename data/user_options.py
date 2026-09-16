"""Optional user-supplied option values (they survive ``git pull``).

Drop a ``user_options.json`` in the pack root to add choices without editing the
source, so an update cannot clobber them. The file is gitignored and shipped
alongside a committed ``user_options.example.json`` so the shape is discoverable
without the file existing.

**Rule 1 -- the merge is never a side effect of an import.** ``import
data.scifi`` yields the built-in pack and nothing else. A build or check script
that read the data layer by importing it would otherwise run this merge and bake
the maintainer's private entries into a committed, published file
(``feedback-generator-cannot-leak-user-data``). Such scripts parse the pack with
``ast`` instead -- ``scripts/builtin_options.py`` is the reader, and
``tests/test_user_options.py`` proves it sees the built-ins only while a
``user_options.json`` is sitting on disk. The merge happens exactly once, in the
repo-root ``__init__.py``, between importing the pack and generating the node
classes.

**Rule 2 -- the merge returns a new pack.** ``GenrePack`` and its pools are
frozen and shared process-wide, so a merge that appended in place would leak one
caller's additions into every other reader.

**Rule 3 -- a bad file never stops the nodes loading.** Every problem here is
logged and skipped: an unreadable file, an unknown field, an unknown kind, a
value that breaks the pack's own authoring rules. A user who mistypes a field
name gets a warning in the ComfyUI console and a pack that still works, not a
custom-node import error and a missing node.

**What it does not do: constraints.** Constraint rules name values by exact
string. A value you add is therefore not named by any rule, and no rule excludes
it -- unless the string you add is exactly one a rule already names, in which
case that rule applies to it as it always did. Nothing is inferred, and the merge
never writes a rule.

File shape (see ``user_options.example.json``)::

    {
      "pools": {
        "primary_color": {"_default": ["hunter green"]},
        "situation":     {"vessel": ["running dark past a picket line"]}
      },
      "tags": {
        "situation": {"running dark past a picket line": "conflict_only"}
      }
    }

``pools`` maps a field to ``{kind: [values]}``. ``"_default"`` is the
fall-through every kind reads when it has no override of its own -- note that a
field where every kind *does* override (``markings``, ``form``, ``situation``)
never reads ``_default``, so a value added there would be authored into a pool
nothing draws from. The log says so when it happens.

``tags`` is optional and only meaningful for the filter-scoped fields. An
untagged value reads as ``neutral`` and is drawn under all three filters.
"""
from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path
from typing import Any, Mapping

try:
    from .genre import CONTENT_TAGS, POOL_DEFAULT_KEY, GenrePack
except ImportError:  # pragma: no cover -- standalone/test context
    from data.genre import CONTENT_TAGS, POOL_DEFAULT_KEY, GenrePack

__all__ = [
    "USER_OPTIONS_FILENAME",
    "apply_user_options",
    "load_user_options",
    "merge_user_options",
    "user_options_path",
]

_LOG = logging.getLogger(__name__)

#: Gitignored, and shipped alongside a committed ``user_options.example.json``.
USER_OPTIONS_FILENAME = "user_options.json"

#: Words that make a value break a promise the pack makes about its output. A
#: user's own file is their business, so these warn rather than reject -- but
#: silence would leave them wondering why their scenes started saying "lit by".
#: The authoritative lists are in ``tests/boundary.py``; this is the short form,
#: because the data layer must not import from the test tree.
_SUSPECT_SUBSTRINGS = ("lighting", "lit by", "backlit", "golden hour", "bokeh", "cinematic")
_SUSPECT_WORDS = ("no", "not", "without", "lacking", "devoid", "shot", "lens", "camera")


def user_options_path() -> Path:
    """Where the optional overrides file is looked for: the pack root."""
    return Path(__file__).resolve().parent.parent / USER_OPTIONS_FILENAME


def load_user_options(path: Path | None = None) -> dict[str, Any]:
    """Read the overrides file, or return ``{}`` if there is nothing usable.

    Never raises. A missing file is the normal case; a malformed one is a user
    error that must not take the node pack down with it.
    """
    path = path or user_options_path()
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as error:  # pragma: no cover -- permissions, a directory, ...
        _LOG.warning("sceneweaver: could not read %s: %s", path, error)
        return {}
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        _LOG.warning(
            "sceneweaver: %s is not valid JSON (%s); no user options were loaded",
            path, error,
        )
        return {}
    if not isinstance(document, dict):
        _LOG.warning("sceneweaver: %s must contain a JSON object; ignoring it", path)
        return {}
    return document


def _warn_about(field: str, kind: str, value: str) -> None:
    low = value.lower()
    reasons = [f"{s!r}" for s in _SUSPECT_SUBSTRINGS if s in low]
    reasons += [f"the word {w!r}" for w in _SUSPECT_WORDS if w in low.split()]
    if reasons:
        _LOG.warning(
            "sceneweaver: user option %s[%s] %r contains %s. SceneWeaver describes "
            "subjects, not rendering, and never says what is absent -- this value "
            "was added anyway, but it may fight whatever style node you pair it with",
            field, kind, value, ", ".join(reasons),
        )
    if low.startswith(("a ", "an ", "the ")):
        _LOG.warning(
            "sceneweaver: user option %s[%s] %r starts with an article. The engine "
            "composes articles, counts and plurals, so this will read as "
            "\"a a hunter green hull\" once it is drawn",
            field, kind, value,
        )


def _merge_pools(
    pack: GenrePack, requested: Mapping[str, Any]
) -> dict[str, dict[str, tuple[str, ...]]]:
    known_fields = set(pack.entity_fields) | set(pack.scene_fields)
    pools = {name: dict(by_kind) for name, by_kind in pack.pools.items()}
    for field, by_kind in requested.items():
        if field not in known_fields:
            _LOG.warning(
                "sceneweaver: user options name field %r, which this pack does not "
                "have; skipping it", field,
            )
            continue
        if not isinstance(by_kind, Mapping):
            _LOG.warning(
                "sceneweaver: user options for %r must be an object of "
                "{kind: [values]}; skipping it", field,
            )
            continue
        target = pools.setdefault(field, {})
        for kind, values in by_kind.items():
            if kind != POOL_DEFAULT_KEY and kind not in pack.kinds:
                _LOG.warning(
                    "sceneweaver: user options name kind %r for field %r, which this "
                    "pack does not have; skipping it", kind, field,
                )
                continue
            if not isinstance(values, (list, tuple)):
                _LOG.warning(
                    "sceneweaver: user options for %s[%s] must be a list; skipping it",
                    field, kind,
                )
                continue
            if kind == POOL_DEFAULT_KEY and target and POOL_DEFAULT_KEY not in target:
                _LOG.warning(
                    "sceneweaver: every kind overrides %r, so nothing ever reads its "
                    "%r pool. Add your values under a kind name instead",
                    field, POOL_DEFAULT_KEY,
                )
            existing = list(target.get(kind, ()))
            for value in values:
                if not isinstance(value, str) or not value.strip():
                    _LOG.warning(
                        "sceneweaver: user options for %s[%s] contain a non-string "
                        "value; skipping it", field, kind,
                    )
                    continue
                value = value.strip()
                if value in existing:
                    continue  # idempotent: re-running the merge adds nothing
                _warn_about(field, kind, value)
                existing.append(value)
            target[kind] = tuple(existing)
    return pools


def _merge_tags(pack: GenrePack, requested: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    tags = {name: dict(by_value) for name, by_value in pack.tags.items()}
    for field, by_value in requested.items():
        spec = pack.entity_fields.get(field) or pack.scene_fields.get(field)
        if spec is None or not spec.tag_scoped:
            _LOG.warning(
                "sceneweaver: user options tag %r, which the content filter does not "
                "read; the tag is ignored", field,
            )
            continue
        if not isinstance(by_value, Mapping):
            _LOG.warning("sceneweaver: user tags for %r must be an object; skipping", field)
            continue
        target = tags.setdefault(field, {})
        for value, tag in by_value.items():
            if tag not in CONTENT_TAGS:
                _LOG.warning(
                    "sceneweaver: user options tag %s[%r] as %r, which is not one of "
                    "%s; leaving it neutral", field, value, tag, sorted(CONTENT_TAGS),
                )
                continue
            target[value] = tag
    return tags


def merge_user_options(pack: GenrePack, document: Mapping[str, Any]) -> GenrePack:
    """Return a new pack with ``document``'s options merged in.

    Split from :func:`apply_user_options` so a test can merge a document without
    a file on disk, and so the file-reading and the merging fail independently.
    """
    pools = _merge_pools(pack, document.get("pools") or {})
    tags = _merge_tags(pack, document.get("tags") or {})
    # A key starting with "_" is a comment: JSON has none, and the shipped
    # example file uses "_README" for its instructions.
    unknown = {k for k in document if not k.startswith("_")} - {"pools", "tags"}
    if unknown:
        _LOG.warning(
            "sceneweaver: user options contain unknown top-level key(s) %s; expected "
            "'pools' and 'tags'", sorted(unknown),
        )
    return dataclasses.replace(pack, pools=pools, tags=tags)


def apply_user_options(pack: GenrePack, path: Path | None = None) -> GenrePack:
    """Return ``pack`` with any user-supplied options merged in.

    Called once, from the repo-root ``__init__.py``, between importing the pack
    and generating the node classes -- so the added values reach the widgets, the
    random draws and the frontend route, and nothing else in the process sees a
    mutated pack.
    """
    document = load_user_options(path)
    if not document:
        return pack
    merged = merge_user_options(pack, document)
    added = sum(
        len(set(merged.pools.get(field, {}).get(kind, ())) - set(pack.pools.get(field, {}).get(kind, ())))
        for field, by_kind in merged.pools.items()
        for kind in by_kind
    )
    if added:
        _LOG.info("sceneweaver: merged %d user option(s) from %s", added, path or user_options_path())
    return merged
