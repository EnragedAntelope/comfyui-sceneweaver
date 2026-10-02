# comfyui-sceneweaver - agent guide

A ComfyUI V3 custom node pack that generates whole scenes - an environment, one
entity by default and up to four, and the pairwise relationships between them -
from lockable dropdowns, as natural-language prose plus structured JSON. Three
genres ship, sci-fi, fantasy and horror; the data layer is a genre contract, so a
genre is a data module and two registration lines.

## Current state

_Last verified: 2026-10-02_

- **Status:** live at v0.5.1 on the ComfyUI Registry (0.6.0 is versioned on the branch, unmerged); `main` carries all three
  genres on one coherence engine. Branch `tmp/sceneweaver-0.5.2` holds the
  unreleased work: user_options keys, a working recreate, the speedup and gates,
  and a content round (places, subjects, relations and colours in all three
  packs). It passes every gate below on a clean checkout and is not yet pushed,
  versioned or released. The repo is public at `EnragedAntelope/comfyui-sceneweaver`;
  the full pre-release history stays local (a git bundle outside the repo, and
  the `coherence-round-*` branches).
- **Works:** both node classes per genre register through the V3
  `comfy_entrypoint`; the output is prose built from genre-authored sentences;
  coherence is declared (affordances, needs, traits, stances, cardinality, tiers)
  and enforced while drawing; a wired Scene Entity of any genre is spoken, placed
  and given an act by its own pack. A saved workflow's `widgets_values` is a
  compatibility surface: `tests/test_widget_order_frozen.py` freezes the shipped
  order and validates both example workflows. Every gate under "Build and test"
  is green. The mechanisms and every round's decisions and measurements are in
  `docs/architecture.md` ("Round XV" to "Round XXVI" are the render-test rounds).
- **In progress:** releasing the branch above (version bump, PR, GitHub release,
  Registry check). The new content has had no render test; round XXVI also still
  awaits the maintainer's. Not built: a headless horseman, carrion crows, an
  exorcist and a mortician (the last two would only reskin the village priest).
- **Known gaps:**
  - A situation can disagree with the pose a model draws (a fire drake breathing
    fire instead of "snapping at a spear") with no text contradiction behind it.
    It is a model-fidelity limit; there is no wording fix.
  - Small alien creatures still name limbs, a natural weapon, senses and a mouth
    by design, so a render can show odd protrusions. Watch small creatures.
  - `scripts/reach_audit.py --gate` samples, so a low seed count lists rare
    place-and-kind combinations as never drawn; use 30000 seeds. CI does not run it.
  - Only `scripts/reach_audit.py` and `scripts/sample_distribution.py` take
    `--pack`. `concern_audit.py`, `coherence_sweep.py` and `coherence_audit.py`
    measure sci-fi only, and the frozen `concern_flags*` are sci-fi's.
  - Renaming or removing a dropdown value makes a saved workflow that locked it
    report "value not in list". Release notes live in commit messages, never in
    the README (maintainer's rule).
  - Cross-genre trait conflicts fail open: a wired foreign entity carries no
    traits into the host scene (`docs/genre-roadmap.md` proposes carrying them). A
    relation is not checked against an entity's state either.
  - A wired Scene Entity's *kind and type* are never masked by the scene filter;
    only its other drawn tag-scoped values are re-drawn.
  - A world as **scenery** behind a ground-level scene has no placement concept,
    so `celestial body` is excluded from the `planetary surface` kind pool and is
    no longer the subject in `orbit`. A decision, recorded in
    `docs/architecture.md`, not an omission.
  - The substance-adjective render-trap class ("forked tongue" draws a fork) is
    checked only for colours (`COLOURWORD`); in other fields an author catches it
    by eye.
  - Not built, and not committed to: the fantasy Tone filter (needs named
    content-tag axes) and `time_of_day` for fantasy and horror. Both are designed
    in `docs/genre-roadmap.md`; if `time_of_day` is built it defaults to unspoken.
  - The example workflows need Krea2T-Enhancer and `ShowText|pysssss`. A
    core-nodes-only graph is a very-low-priority idea; it must be exported from a
    running ComfyUI, never hand-written.
  - ComfyUI-Manager's own "Fix node (recreate)" leaves a duplicate node
    (Comfy-Org/ComfyUI-Manager#3126); `js/sceneweaver.js` replaces it on this
    pack's nodes. KJNodes' "Recreate node" submenu coexists with it.
  - There are no section headings on the node face (both approaches were tried
    and removed; `js/sceneweaver.js` records why). `markings` ships no readable
    text on purpose. `pytest tests` needs the pack directory named
    `comfyui-sceneweaver`; `unittest discover` is the CI entry point.
- **Deep docs:** `docs/architecture.md` - the genre seam, the generation
  pipeline, the scope chain, archetypes, trait conflicts, the sentence grammar,
  environment staging and bands, the part lint, the two denylists, the tag
  vocabulary, the allowance table and token ceiling, the wired-entity
  precedence, the reach audit, the measured distribution and motif baselines for
  all three packs, and one section per render-test round. `docs/genre-roadmap.md`
  - the genre content brainstorm and the decisions behind it.

## Layout

| Path | What lives there |
|---|---|
| `__init__.py` | V3 entrypoint. **The only place a concrete genre is named.** |
| `data/genre.py` | The `GenrePack` contract - genre-agnostic. |
| `data/scifi.py` | The sci-fi pack. Nothing outside `__init__.py` imports it. |
| `data/fantasy.py` | The fantasy pack. Situations are authored in buckets (tier, tag, needs, stance, liveness) and every table about them is derived from the registry. |
| `data/horror.py` | The horror pack, the same bucket shape. Gore is `conflict_only` and the node labels the filter No gore / Any / Gore only. |
| `data/user_options.py` | Merge hook for a gitignored `user_options.json`. Never run at import. |
| `engine/` | Pure generation logic. No ComfyUI imports, no genre knowledge. |
| `nodes/` | Node-class factories. **May not name a genre** (a test greps for it). |
| `js/` | Frontend widgets, served via `WEB_DIRECTORY`. |
| `scripts/` | Maintainer tools: the audits and sweeps, and `builtin_options.py`, the pool lister the README sends users to (the one script the Registry zip keeps). Not imported by the pack. |
| `tests/comfy_stub/` | Record-only `comfy_api` stand-in for machines without ComfyUI. |
| `tests/frontend/` | jsdom harness. Drives the real `js/sceneweaver.js`; only ComfyUI's own frontend modules are stubbed. |
| `docs/` | `architecture.md` and the README's images. Excluded from the Registry zip, which is why the README references images by absolute raw URL. |
| `example_workflows/` | Exported graphs. **This exact folder name** is what ComfyUI scans (`app/custom_node_manager.py`) to list them under Workflow > Browse Templates; `examples/` merely warns. |
| `.comfyignore` | What the Registry zip leaves out. Filters **only** that archive - never GitHub, never a `git clone` install. |
| `.github/workflows/publish.yml` | Publishes to the Registry when `pyproject.toml` changes on `main`. Needs the `REGISTRY_ACCESS_TOKEN` repo secret. |

## Build and test

```
python -m unittest discover -s tests -t . -v
pytest tests
python tests/validate_data.py
python scripts/reach_audit.py --pack scifi --gate --seeds 30000
python scripts/reach_audit.py --pack fantasy --gate --seeds 30000
python scripts/reach_audit.py --pack horror --gate --seeds 30000
python scripts/sample_distribution.py --seeds 1000
python scripts/sample_distribution.py --pack fantasy --seeds 1000
python scripts/sample_distribution.py --pack horror --seeds 1000
python scripts/coherence_audit.py --seeds 2000
python scripts/concern_audit.py --seeds 600 --gate
python scripts/coherence_sweep.py --gate
python scripts/coherence_sweep.py --gate --path unwired
npm ci && npm run test:frontend
python -m ruff check .
```

`-t .` is load-bearing: it makes `tests` a genuine subpackage of the repo root,
which is what guarantees `tests/__init__.py` registers the `comfy_api` stub
before any test module imports a node module. `pytest` is made correct by the
rootdir `conftest.py` plus a `ComfyExtension` export on the stub, but
`unittest discover` stays *the* command - it is what proves the pack is
dependency-free, because CI installs nothing for it. `pytest` additionally needs
the pack directory to be named `comfyui-sceneweaver`; `docs/architecture.md`
records why.

`validate_data.py` is the gate on the authoring rules a diff cannot show - adding
`no weapons` to a pool looks exactly like adding `spinal railgun`. It also prints
the live pool numbers, which is why no document in this repo states them.

Run the whole set against a **fresh clone**, not only the working tree: a check
that reads a gitignored file passes locally and fails on a clean checkout.

## Conventions

- **A gate counts the missing value.** A check that skips an entity whose field
  is None passes because of the defect it guards; round IX's stance gates did,
  and a form left at None read as "no silhouette" for 12.5% of scenes.
- **A part must fit the body it is bolted to.** A rotating tail voices pools
  nobody checked; `part_keywords` + `check_part_keywords` (check 29) fails the
  one that does not, and the trait conflicts (`legless-plan` /
  `leg-appendage`) catch what a lint cannot see. A part pool keyed by *kind*
  carries no body check, which is how a drop pod got a spare track.
- **A place that floats says so.** `ProseSpec.environment_staging` appends the
  suffix the place's affordance selects; a model grounds anything it is not
  told floats, so a station in a debris belt is drawn standing on the debris.
- **Reachable is not drawn.** `check_shadowed_values` proves a value can be
  reached; `scripts/reach_audit.py --gate` proves it is drawn. A value is
  exempt only as stranger vocabulary (`_default` alone) or when every archetype
  that reaches it lists the field in `omits`. There is no allowlist -- fix the
  scope, the need, or replace the value.
- **A secondary actor is a machine, not a crowd.** A wreck is examined by a
  hovering survey drone, not by a survey team; a small crew stays only in
  interiors and in a spacefarer's own situations.
- **Every reported concern becomes a regression row** in
  `tests/test_concern_regressions.py`, in the commit that fixes it, never
  removed. The frozen definitions live in `scripts/concern_flags.py`.
- **Replay before theorising.** `scripts/replay_batch.py` reads each image's
  `prompt` chunk and re-runs the exact scene, so a batch of images becomes a
  list of named defects instead of a guess.
- **Write files with an editor, never a shell heredoc.** A shell once turned
  `\\b` into a backspace byte and a regex check silently matched nothing;
  prove every regex check with a planted positive in a test.
- **Test the path the user actually uses.** Every coherence rule in this pack was
  measured at 0 violations with the Scene Weaver alone and 10.5% with a Scene
  Entity wired in, because a wired value was treated as a user's choice when it
  was only a random draw. A gate that is only exercised on one path is a gate for
  one path; `tests/test_coherence.py::WiredPathCoherenceTests` sweeps all three.
- **No unqualified Earth noun.** "graveyard orbit" is correct astronautics and
  renders as a cemetery; "weather balloons" renders as hot-air balloons. The
  qualifier has to be in the head noun, not in front of it, and
  `foreign_noun_fields` scans `context` and `environment` as well as the entity
  fields.
- **A word is judged by what a model draws, not by what it means.** A tether is
  a chain, a bladder-pod is a balloon, a starliner is an airliner. Correct
  English that renders as the Earth object is the same defect as an Earth noun:
  rename the value, or declare the need it has. `scripts/concern_flags_0914.py`
  is the frozen list of those classes.
- **A value no subject can draw is a dead option.** `check_shadowed_values` in
  `tests/validate_data.py` fails a value authored under a pool key no subject's
  scope chain resolves, so a subkind group key cannot silently shadow the kind
  key above it. A value under `_default` alone is stranger vocabulary, not a
  shadow.
- **A fixed detail priority is a dead widget for every field below the line.**
  The order is the same on every render, so a field under the cap is drawn,
  resolved and written into `prompt_json` and never spoken. An archetype reserves
  `detail_rotation_slots` and fills them by a weighted draw; a brief supporting
  slot keeps the fixed order, because its allowance belongs to the silhouette.

- **No counts in any doc.** Name the validator that reports the real number
  instead; a count turns every content addition into a doc chore.
- **Never negate** in prose or in data. Absence is expressed by naming what *is*
  there.
- Option values are **bare, article-less noun phrases**; the engine composes
  articles, counts and plurals.
- Data lives in **Python modules, not JSON**.
- **A rule that only ever deletes values is a scoped pool wearing a rule's
  clothes.** A scope cannot be out-iterated; prefer `scope` + `pool_groups` over
  a constraint that only subtracts.
- Widget **order** is never changed once shipped - only labels and values.
  `widgets_values` in a saved workflow is positional, so `data.genre.widget_order`
  is the single declaration of it: append only, never reorder.
- **Genre is node identity, never a wire.** `nodes/` and `engine/` may not name a
  genre; both node classes are generated from a `GenrePack` that the repo-root
  `__init__.py` supplies. `tests/test_genre_contract.py` enforces both halves.
- **A genre writes its sentences, not its clause order.** The renderer fills
  holes in English the pack authored; it owns no connector, no verb and no
  pronoun. A clause list can only attach a detail with a comma, which is why
  every field used to arrive in the same grammatical relationship to the
  subject whatever its real one was. If you find yourself wanting to join two
  clauses in `engine/prose.py`, the pattern is the place.
- **A pattern must state the real relationship between the subject and the
  part.** `{pronoun} is {form}` says the thing *is* its hull; `{pronoun} has
  {form}` says it *has* one. The possessive form is unavailable - a clause slot
  carries its article, so `{possessive} {form}` renders "Its a hull" - and a
  wreck is a hull section while a courier has a hull, so the two want different
  rungs. A genre picks per archetype, and the choice is the same question in
  any genre.
- **A subject is one noun phrase.** A made thing's category joins the head
  through `spoken` ("hospital starship"), never through an apposition a model
  reads as a second object; a creature keeps its apposition (", an alien
  creature") and the tidy pass absorbs its comma.
- **An archetype owns how much is spoken, not only how.** A category of thing a
  model builds from parts (a creature, a person) can carry its whole component
  list; one it builds from a silhouette (a station, a wreck, a world, an
  artifact) cannot, and the same clause count that reads as anatomy on one reads
  as unplaceable greebles on the other. `Archetype.detail_cap` and
  `Archetype.detail_priority` are where that is stated. Every genre must also
  declare a `POOL_DEFAULT_KEY` archetype - the grammar a kind it has never heard
  of is spoken with - or a foreign entity falls through to the bare `ProseSpec`
  and is "clad in" its own hide.
- **A situation must be legible in one still frame**, from outside the subject
  and without an actor the scene has not described; see the three tests in
  `docs/architecture.md`.
- **An object acts on something.** A cursed object, relic or artifact shows a
  witness it acts on, what it does to the place, or how it is held; an effect
  with no cause in the frame reads as noise, and "someone" draws a
  disembodied hand. Name the witness. `docs/architecture.md` ("Round XXV").
- **A situation must be the most interesting thing in the frame.** If someone
  standing there would not look up, it is `idle`. The four tests (camera, actor,
  frame, mechanism) say whether a situation can be *drawn*; `value_tiers` says
  whether it is worth drawing, and `TIER_WEIGHTS` prices it.
- **A place affords; a value needs.** A nest needs a floor, a flyer needs air;
  declare the need on the value (`value_needs`) rather than listing every place
  it is wrong, and let the affordance lint fail the value that forgets. A whole
  pool key can be classified once with `default_needs`; a value's own entry
  (even an empty one) wins over it, and a value authored under several keys
  takes the union. The needs-free situation cores stay neutral on purpose: a
  shared value cannot need every place it is drawn under at once.
- **A place says what it offers; a form says what it can do.** Neither alone is
  enough: the ring standing on its ring was a legal place and a legal shape.
  `value_stances` says which stances a body can take (rests, walks, rolls,
  flies, hovers, floats, swims, orbits) and `place_stances` says which a place
  supports, so a form is excluded from a place that supports none of its
  stances and a situation from a form it cannot share.
- **A gate that is declared but unwired is worse than no gate.** The affordance
  lint sat in `tests/validate_data.py` with an empty keyword table, so whole
  pools of situations went unclassified and nobody noticed. Any check this pack
  adds must fail on the day it lands, against real data, or it is decoration.
- **A subkind must not be a word that names an Earth vehicle unless the
  category noun beside it says otherwise.** "A warship, a starship" is safe
  because the apposition fixes it; "a ghost passenger liner, a wreck" is not,
  because "wreck" names no medium. No validator can check this, so it is a
  review rule.
- **Widget order and widget defaults are one declaration.** `data.genre.widget_order`
  is the positional contract for `widgets_values`; append, never reorder. A
  control that changes what the node *generates* (`entity_count`) must be read
  by the engine, not merely shown - a control the engine ignores is a lie on the
  node face.
- **Verify the node face in a browser.** The jsdom suite drives the real
  `js/sceneweaver.js` and still cannot see paint: canvas group headers passed
  every test and rendered as a single clipped letter on a live node.
- **Coherence is declared, not listed.** A place says what it affords, a value
  says what it needs and what it is, a kind says what it can do, and a form
  says how it holds itself up. The pack never keeps a hand list of "situations
  that need ground" -- it declares the need on the situation, and
  `tests/validate_data.py`'s affordance lint fails the one that forgets.
- **Coherence is a filter, not a goal.** Every rule in this pack can only remove
  a value. Nothing in a filter asks whether a scene is worth looking at, so
  widening a pool raises coverage and lowers the mean interest unless something
  prices the interesting end. That is what `value_tiers` is, and why every
  value of a tiered field must carry a tier.
- **Add a value with its whole card.** Pool entry, tag, spoken form, needs,
  traits, group, **cardinality class** and every rule key that names it, in the
  same edit; the checklist is in `docs/architecture.md`.
- **A noun says how many of it there can be, not its kind.** A count field's
  scope asks its noun before its kind, so an unclassified noun is counted by the
  kind -- and a kind cannot answer it, because "drive nacelle" and "luminous hull
  seam" are both `emitters` on a `starship`. "A dozen drive nacelles" draws
  engines at *both ends* of the hull. `value_cardinality` is the single
  declaration; it expands into the pool groups, so the two tables cannot drift.
- **An instrument that only knows last round's defects will read zero forever.**
  `concern_flags*.py` are regression instruments and stay frozen. Finding the
  *next* class needs a check shaped as a kind of incoherence, reading the pack's
  own tables -- `scripts/coherence_sweep.py`. When a class and the data disagree,
  suspect the class first: "ice-blue" is a colour, a gas giant's storms are real,
  and a creature in a corridor is a genre staple.
- **Re-drawn, never nulled.** Two engine passes broke this in round XIII. A
  re-draw whose pool comes back empty must leave the field standing, and a field
  a rule emptied must be re-offered once the fixed point settles -- the scope
  that emptied it is often re-drawn later in the same pass. A repeated head noun
  is ordinary English; a subject with no silhouette is a defect, and it arrived
  with no warning and nothing in `redrawn_fields`.
- **Liveness is a closed list.** `DORMANT_ACTS` names what a thing with no power,
  crew or intent can be doing; every other situation is derived `powered-act`.
  A new situation is live by default. Never go back to tagging powered acts by
  hand: two such lists missed every act nobody remembered, and a dead hull rode
  a re-entry sheath in orbit.
- **A pool is a literal.** Add values inside the pool literal (or as a named
  tuple declared before it and concatenated in it), never with
  `POOLS["key"] = POOLS["key"] + (...)` afterwards: `scripts/builtin_options.py`
  reads pools with `ast` and `tests/test_user_options.py` fails on the drift.
- **Variety is kept by adding.** A rule that removes values ships with values
  that replace them. Measure distinct values and entropy per field and per kind
  against `main` (seeded, both paths) before calling a coherence round done; a
  floor failure is fixed by authoring, never by lowering the floor.
- **A context framing names where, never how.** "A ladder crowds in close" was a
  template's verb forced onto a value; validator check 31 fails a stance verb.
- **A situation belongs to one bucket** (fantasy). A bucket is a tuple whose
  values share a tier, a filter tag, the needs, the stances and whether a
  dormant or sleeping thing can do them; `_BUCKETS` derives every table from it
  and the module refuses to import if a situation has no bucket or two
  disagreeing ones. Add a value to the right bucket, never to a derived table.
- **A form never repeats its type's head noun.** "square keep" on a "ruined keep"
  is silenced by the engine's repeat guard every time, so the form is dead.
- **An archetype's cap is the clause count plus two.** The head modifiers (scale,
  condition) are subtracted from `detail_cap`, and any field below the resulting
  line that is not in the rotation is never spoken. `reach_audit.py --pack`
  finds it.
- **Underwater affords water only.** A place that also grants `floor` lets a
  walking bear stroll the reef.
- **A table applied later wins.** `VALUE_NEEDS["subkind"].update({...})` over
  `_TYPES_NEEDING_NOTHING` runs after the per-value entries and silently
  overwrote one, so a glider needed nothing of a place and was feasible at the
  bottom of an ocean trench. Grep for a later `update` before concluding a
  declaration is live.
- **A native subject never falls through to the stranger's pool.** `_default` is
  what a foreign entity is spoken with; a native type with no key of its own gets
  it too, silently ("a shrine has a single spear"). Declare an empty pool
  and `omitted_pools` instead; validator check 32 finds the hole.
- **What a sentence says is carried must be carriable.** A carry sentence over a
  pool that holds talons, fists or arms draws a body part held in the hand; made
  things *have* their parts. Check 33.
- **A place can forbid a stance outright.** Support is a union, so a seabed with a
  floor supported rolling; `place_stance_blocks` keeps any body that has the stance
  out, even at rest. Do not remove the affordance instead -- it starves every
  legitimate act that needed it.
- **A requirement is met, not merely not violated.** A `require` rule fills an empty
  target. Use it when an act needs a state (a stone act needs "petrified") rather
  than wording the state into the act, which repeats it when the state is drawn.
- **Traits are added, never merged in a dict literal.** A later `**{...}` for the
  same key replaces the earlier entry; three sea monsters lost `inherently-vast`
  that way. Use the pack's `_add_traits`.
- **A re-drawn place keeps the scene's subjects.** A rule that re-draws the
  environment avoids the places the scene's subjects cannot stand in; a river
  barge refusing a stormy sea was put in a forge. Any new re-draw of a
  scene-level control must respect the slots it scopes.
- **A guest is placed by what it is, in one of its homes.** Kind, type, form
  and scale choose the host place, matched against one home of the guest's own
  genre; the place then masks drawn values that conflict with it. Probe the
  per-kind placement table across all six genre pairs after touching
  `engine/foreign.py`.
- **A horror act shows who it threatens.** Vermin in a crate or a clock
  cracking on its own "isn't horror"; name the victim or the menace.
- **A drawn wired value obeys the scene filter.** The Entity node has no filter; a
  scene that promises "No gore" must mask what the wire drew.
