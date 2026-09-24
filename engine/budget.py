"""The detail budget: how much of each entity reaches the prompt.

Four fully-described entities is a 400-token prompt. A text encoder holds ~77
tokens per chunk and reliably drops detail well before the end of a long one, so
the image turns to mush precisely when the user asked for the most. This module
is the control that stops that -- a fixed per-entity cap on how many *optional*
descriptive fields survive, plus a whole-scene token ceiling the sweep asserts.

**The one rule that is not a nicety.** A field the budget cuts is written back
to ``None``, so it is ``None`` in ``prompt_json`` too. There is no
"resolved but not voiced" state: a value that was drawn and then quietly
discarded is exactly the bug ``identity-forge-dead-widget-check`` names -- the
JSON promises a detail the image was never asked for, and every consumer
downstream believes it. ``apply_budget`` returns a new mapping rather than a
list of survivors for that reason: there is nowhere for a cut value to hide.

The resolution rules, in the order they apply:

1. **A locked field is never cut.** Choosing a value is an explicit statement of
   intent and outranks the cap. Locking a *count* protects the noun it
   counts, because a quantity of nothing cannot be spoken.
2. **A slot with a Scene Entity wired in gets the top allowance** -- whatever
   slot 1 gets for the current entity count. Wiring one *is* the request for
   detail; unwired supporting slots stay brief. It does **not** remove the cap:
   four wired entities with no cap at all measure ~320 tokens, which is the
   mush this module exists to prevent, and it is why a wired slot is promoted
   rather than exempted.
3. **A field with a widget on this slot is spent before one without.** A
   supporting slot shows four dropdowns and resolves twenty-one fields, so
   without this rule its ``scale`` widget competes with fifteen fields the user
   cannot see, loses every time, and is drawn every render and never voiced --
   ``identity-forge-dead-widget-check`` exactly. A control the user can see and
   set outranks a detail they cannot.
4. **An archetype's ``detail_cap`` lowers the allowance, never raises it.** A
   creature carries its whole component list because those clauses are its
   anatomy; a station, a wreck, a world or an artifact cannot, because the same
   clauses read as greebles the model cannot place. ``min`` is the whole rule,
   so a four-entity scene never gets *more* detail because one slot holds a
   creature.
5. **The remaining allowance is spent in the archetype's ``detail_priority``,
   then in ``pack.prose.detail_priority``**, which is genre data -- see the note
   there on why it is not the clause order.
5b. **On a full-depth slot the tail rotates.** A fixed priority spends the
   allowance in the same order every render, so every field below the cap is a
   dead widget. The archetype's ``detail_rotation_slots`` reserves that many
   slots, the core fields above them are spent in order, and each reserved slot
   is filled by a weighted draw from ``detail_rotation``. Only a full-depth slot
   rotates -- the hero slot (which shows every field, so rule 3's reorder is a
   no-op there), a wired slot and the Scene Entity node. A brief supporting slot
   keeps the fixed order, because its small allowance belongs to the silhouette.
   ``rng=None`` keeps the legacy order, which is what the seam fixture uses.
6. **Everything else becomes ``None``**, companions included.
"""
from __future__ import annotations

import random
import re
from typing import Iterable, Mapping

try:
    from ..data.genre import KIND_FIELD, POOL_DEFAULT_KEY, Archetype, GenrePack, HeadPhrase
except ImportError:  # pragma: no cover -- standalone/test context
    from data.genre import KIND_FIELD, POOL_DEFAULT_KEY, Archetype, GenrePack, HeadPhrase

__all__ = [
    "ALLOWANCE_BY_COUNT",
    "MAX_ALLOWANCE",
    "TOKEN_CEILING",
    "allowance_for",
    "apply_budget",
    "count_tokens",
]


# ---------------------------------------------------------------------------
# The fixed budget
# ---------------------------------------------------------------------------

#: How many optional descriptive fields each occupied slot keeps, indexed by how
#: ``ALLOWANCE_BY_COUNT[2] == (8, 6)`` means a
#: two-entity scene describes its first subject with eight details and its second
#: with six.
#:
#: **Detail is a whole-scene quantity, not a per-slot one.** The old model gave
#: slot 1 a fixed nine and halved it for the rest, so a scene got more total
#: description the more subjects it had -- exactly backwards. An image has one
#: subject's worth of attention to spend however many things are in it, so the
#: allowance falls as the scene fills. Nothing is ever reduced to a bare name:
#: three details is still a described thing, which is what keeps a wired Scene
#: Entity worth wiring in any slot.
#:
#: **Nine is not a token-count decision.** A one-entity scene at nine fields is
#: about 75 tokens, nowhere near ``TOKEN_CEILING``. It is a *sentence* decision:
#: nine details spread across the pack's four-sentence plan is four readable
#: sentences, where the same nine in one clause pile was the incoherence this
#: overhaul exists to fix. Cutting the count further was tried and cost real
#: things -- ``scale`` and ``condition`` fell off the priority list, taking the
#: kaiju path and half the visual variety with them. Shape, not length, is what
#: a prose text encoder chokes on.
#:
#: Sized so the four-entity worst case stays under ``TOKEN_CEILING`` and so no
#: allowance exceeds the shipped sentence plan's capacity -- a plan that cannot
#: hold what the budget kept has to spill into a repeated sentence.
ALLOWANCE_BY_COUNT: "dict[int, tuple[int, ...]]" = {
    1: (9,),
    2: (8, 6),
    3: (7, 5, 5),
    4: (6, 5, 4, 4),
}

#: The largest allowance any slot can receive. A sentence plan must be able to
#: speak this many clauses without spilling.
MAX_ALLOWANCE = max(max(row) for row in ALLOWANCE_BY_COUNT.values())

#: Whole-scene ``prompt_text`` ceiling, asserted across a seed sweep in
#: ``tests/test_engine.py``. A **regression** guard, not a target: a pool edit
#: that pushes a scene past it should fail the sweep rather than be discovered
#: in a mushy render.
#:
#: Raised from 256 with the sentence plan. The old number came from CLIP, which
#: holds 77 tokens per chunk and drops detail long before the end of a long one.
#: A modern prose encoder (Qwen3-4B behind Krea2, and its peers) reads several
#: hundred comfortably, and the multi-sentence grammar deliberately spends
#: tokens on connectives that make the prompt parseable. Coherence, not length,
#: is what was making renders mushy.
TOKEN_CEILING = 320


def allowance_for(occupied: int, slot_position: int) -> int:
    """Detail allowance for the ``slot_position``-th occupied slot (1-based).

    Falls back to the largest declared row for a scene with more occupied slots
    than the table anticipates, so a pack built with more slots than the shipped
    four still budgets rather than raising.
    """
    row = ALLOWANCE_BY_COUNT.get(occupied)
    if row is None:
        row = ALLOWANCE_BY_COUNT[max(ALLOWANCE_BY_COUNT)]
    index = min(max(slot_position, 1), len(row)) - 1
    return row[index]


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[^\s]+")
_PUNCTUATION_RE = re.compile(r"[.,;:]")
#: BPE splits most words longer than this into two or more pieces.
_LONG_WORD = 9


def count_tokens(text: str) -> int:
    """Approximate the CLIP token count of ``text``.

    A whitespace-and-punctuation count, plus one for every long word, because
    CLIP's BPE splits those. Deliberately biased **high**: this number is only
    ever compared against a ceiling, and an approximation that under-counts
    would let a real overrun through while the test stayed green.

    Not exact, and not trying to be -- an exact count would mean shipping a
    tokenizer, and the pack has zero dependencies by design.
    """
    words = _WORD_RE.findall(text)
    long_words = sum(1 for word in words if len(word.strip(".,;:")) >= _LONG_WORD)
    return len(words) + len(_PUNCTUATION_RE.findall(text)) + long_words


# ---------------------------------------------------------------------------
# Applying the budget
# ---------------------------------------------------------------------------


def _clause_heads(pack: GenrePack) -> tuple[str, ...]:
    """Entity fields that head a clause of their own, in pack order."""
    return tuple(n for n, s in pack.entity_fields.items() if s.renders_with is None)


def _priority(pack: GenrePack, archetype: "Archetype | None" = None) -> tuple[str, ...]:
    """Spend order for the allowance: the archetype's promotions, then the pack's.

    An archetype states only what it wants *differently*; fields it does not
    name follow in ``ProseSpec.detail_priority`` order, so a creature and a
    station share one authoring list and diverge only where it matters.

    The fallback is what lets a minimal fixture pack -- one that has authored no
    prose at all -- still be budgeted, which is what keeps the genre seam cheap
    enough to exercise.
    """
    base = pack.prose.detail_priority or tuple(
        n for n in _clause_heads(pack) if n != KIND_FIELD
    )
    if archetype is None or not archetype.detail_priority:
        return base
    promoted = tuple(archetype.detail_priority)
    return promoted + tuple(n for n in base if n not in promoted)


def _companions_of(pack: GenrePack, hosts: Iterable[str]) -> set[str]:
    """Fields composed into any of ``hosts`` -- counts, glow colours."""
    host_set = set(hosts)
    return {
        name
        for name, spec in pack.entity_fields.items()
        if spec.renders_with is not None and spec.renders_with in host_set
    }


def _head_phrase_for(
    pack: GenrePack, kind: "str | None", archetype: "Archetype | None"
) -> "HeadPhrase | None":
    """The opening noun phrase for one entity, most specific statement first."""
    if archetype is not None and archetype.head_phrase is not None:
        return archetype.head_phrase
    if kind is not None and kind in pack.prose.head_phrase:
        return pack.prose.head_phrase[kind]
    return pack.prose.head_phrase.get(POOL_DEFAULT_KEY)


def apply_budget(
    pack: GenrePack,
    values: Mapping[str, str | None],
    *,
    budget: int | None = None,
    archetype: "Archetype | None" = None,
    locked: "frozenset[str] | set[str]" = frozenset(),
    visible: "frozenset[str] | set[str]" = frozenset(),
    omits: "frozenset[str] | set[str]" = frozenset(),
    wired: bool = False,
    rng: "random.Random | None" = None,
    ) -> dict[str, str | None]:
    """Cut ``values`` down to the budget, writing every cut field back to ``None``.

    ``budget`` is this slot's allowance, already chosen by ``allowance_for``;
    ``None`` means "no cap" from the caller. ``archetype`` may still impose its
    own ``detail_cap`` below, so ``None`` reads as "whatever this kind of thing
    speaks" rather than "everything" -- which is what the Scene Entity node
    relies on.

    ``archetype`` is the grammar category governing this entity. Its
    ``detail_cap`` lowers the allowance and its ``detail_priority`` reorders the
    spend; both are empty for a pack that declares no archetypes, so the genre
    seam stays free.

    ``wired`` is carried for the caller's benefit only: the promotion of a
    wired slot to the top allowance happens where the allowance is chosen, not
    here, so this function has exactly one rule about how much to keep.

    ``visible`` holds the *base* field names this slot draws a widget for, and
    is what rule 3 spends first. Empty means the distinction does not apply.

    ``omits`` holds the fields this entity's archetype never voices. They are
    nulled here, before anything else, because this is the one function allowed
    to decide a field is unspoken *and* it writes what it decides back to
    ``None``. Suppressing them in the renderer instead would leave the value
    standing in ``prompt_json``, promising the image an integument the nebula
    does not have.

    ``locked`` holds *base* field names ("emitters"), not widget keys, because
    one rule set has to serve both node classes and only one of them prefixes
    its widgets with a slot.

    Returns a new dict with the same keys. Nothing is deleted and nothing is
    kept privately: what is not ``None`` is what will be spoken.
    """
    result = dict(values)

    # The archetype's omissions first: a field this kind of thing does not have
    # is not a budget question, and nulling it here means the count that rides
    # it is caught by the orphan pass immediately below.
    for name in omits:
        if name in result:
            result[name] = None

    # An orphaned companion next, and unconditionally -- before any budget
    # question, and even when there is no cap. A host can be absent for
    # reasons that have nothing to do with the budget: the content filter
    # emptied its pool ("Peaceful" masks every weapon), a constraint excluded
    # all of it, or the pack declares the feature omitted for that kind. In each
    # case the count was still drawn, and left standing it would sit in
    # prompt_json as a quantity of nothing -- resolved, unvoiced, and believed
    # by every consumer downstream.
    for name, spec in pack.entity_fields.items():
        if spec.renders_with is not None and result.get(spec.renders_with) is None:
            result[name] = None

    # A head-phrase modifier -- ``scale``, ``condition`` -- is two words in
    # front of the noun, not a clause of its own. Pricing it like a component
    # is why the two cheapest, highest-value words used to appear and vanish at
    # random. It is drawn every render and folded into the head phrase, so it
    # never spends the allowance; and because it is no longer priced, the cap
    # comes down by however many the archetype can actually draw, which keeps
    # the total clause count where it was.
    head = _head_phrase_for(pack, result.get(KIND_FIELD), archetype)
    modifiers = set(head.modifiers) if head is not None else set()
    exempted = modifiers - set(omits)

    # An archetype's cap is a floor on the caller's allowance, applied after the
    # orphan pass and before the early exit so that ``budget=None`` still means
    # "as much as this kind of thing speaks" rather than "everything".
    if archetype is not None and archetype.detail_cap is not None:
        cap = max(0, archetype.detail_cap - len(exempted))
        budget = cap if budget is None else min(budget, cap)

    if budget is None:
        return result


    heads = [
        name
        for name in _clause_heads(pack)
        if name != KIND_FIELD
        and name not in modifiers
        and result.get(name) is not None
    ]

    # A locked count protects the noun it counts: rule 1 says a locked field is
    # always rendered, and a count with no noun cannot be rendered at all.
    protected = set(locked)
    for name in locked:
        spec = pack.entity_fields.get(name)
        if spec is not None and spec.renders_with is not None:
            protected.add(spec.renders_with)

    keep = {name for name in heads if name in protected}
    allowance = max(0, budget - len(keep))
    # Rule 3 then rule 4: the fields this slot actually shows a widget for, in
    # priority order, then everything else in the same order. ``visible`` empty
    # means "every field is visible" -- the wired slot and the Scene Entity node,
    # where the distinction does not arise.
    priority = _priority(pack, archetype)
    if visible:
        shown = [n for n in priority if n in visible]
        hidden = [n for n in priority if n not in visible]
        priority = tuple(shown + hidden)
    # Rule 5b: a full-depth slot rotates its tail, a brief supporting slot does
    # not. "Full depth" is a slot that shows every clause head, so rule 3's
    # reorder above is a no-op -- the hero slot, a wired slot, the Entity node.
    # A supporting slot shows four dropdowns and keeps the fixed order, because
    # its allowance belongs to the silhouette rather than to a random detail.
    rotation = dict(archetype.detail_rotation) if archetype is not None else {}
    slots = archetype.detail_rotation_slots if archetype is not None else 0
    full_depth = not visible or set(heads) <= set(visible)
    if rng is not None and rotation and slots > 0 and full_depth:
        reserved = min(slots, allowance)
        core_allowance = allowance - reserved
        for name in priority:
            if core_allowance <= 0:
                break
            if name in rotation:
                continue
            if name in heads and name not in keep:
                keep.add(name)
                core_allowance -= 1
                allowance -= 1
        # A reserved slot is a count, not a share of whatever allowance the
        # fixed head left unspent: an under-full head (a wreck that omitted
        # ``condition``) used to let surplus allowance keep drawing rotation
        # candidates one at a time until the whole budget was rotation, which
        # is how a courier grew three greeble fields against
        # ``detail_rotation_slots=1``. Bound the draw at ``reserved`` picks;
        # any allowance rotation could not spend still falls through to the
        # core-order pass below, unchanged.
        candidates = [n for n in rotation if n in heads and n not in keep]
        picked = 0
        while picked < reserved and allowance > 0 and candidates:
            pick = rng.choices(
                candidates, weights=[rotation[n] for n in candidates], k=1
            )[0]
            keep.add(pick)
            candidates.remove(pick)
            allowance -= 1
            picked += 1
        # A reserved slot nothing could fill falls back to the core order.
        for name in priority:
            if allowance <= 0:
                break
            if name in heads and name not in keep and name not in rotation:
                keep.add(name)
                allowance -= 1
    else:
        for name in priority:
            if allowance <= 0:
                break
            if name in heads and name not in keep:
                keep.add(name)
                allowance -= 1

    cut = set(heads) - keep
    for name in cut | _companions_of(pack, cut):
        result[name] = None
    return result
