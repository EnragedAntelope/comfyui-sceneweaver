# comfyui-sceneweaver - agent guide

A ComfyUI V3 custom node pack that generates whole scenes - an environment, one
entity by default and up to four, and the pairwise relationships between them -
from lockable dropdowns, as natural-language prose plus structured JSON. Three
genres ship, sci-fi, fantasy and horror; the data layer is a genre contract, so a
genre is a data module and two registration lines.

## Current state

_Last verified: 2026-09-17_

- **Status:** **public beta.** `main` is v0.4.0 (coherence round XIV, published
  to the ComfyUI Registry). **v0.5.0 is on `tmp/sceneweaver-fantasy`**, awaiting
  the maintainer's ComfyUI render test before a squashed PR: the fantasy pack,
  **round XV** (the 0916-evening sci-fi and 0917 fantasy batches, decisions R1-R9
  in `docs/architecture.md`) and **the horror pack** (`data/horror.py`, H1-H5).
  Round XV added contract pieces, each genre-agnostic: validator checks 32
  (`FALLTHROUGH`) and 33 (`CARRYPART`), `place_stance_blocks`, a `require` rule
  that fills an empty target, genre filter labels (`scene_filter_labels`), the
  scene filter reaching a wired entity's drawn values, and a readout cut to the
  node width. The
  repo is public at `EnragedAntelope/comfyui-sceneweaver`; the full pre-release
  history stays local only, in the `coherence-round-*` and `tmp/*` branches.
  Round XIV: a dead ship is the `wreck` kind and is dead (closed dormant-act
  list, no lit emitters, no cables), no open fire or uncaused machine breakage,
  a small or indoor creature takes no craft, one thrust source, context
  sentences carry no stance verb, and render-trap renames (patch, sail, loader,
  boom, neon). The sweep went from 50.0% to 5.4% of wired scenes with variety
  measured against `main` and kept by adding values.
  Saved-workflow compatibility was deliberately dropped before 0.3.0 and is
  now a real constraint -- the pack is distributed, so widget_order is a
  compatibility surface from here on.
- **Works:** everything the pack advertises, plus the coherence overhaul. Both
  node classes register through the V3 `comfy_entrypoint`. The output is
  **prose**: a genre declares whole English sentences with named holes
  (`data.genre.Sentence`) and the renderer fills them, so the connector, the
  verb and the possessive are genre data and a nebula is never "clad in"
  anything. A pattern fires only when every slot outside a bracketed segment
  resolves, and a field spoken once is consumed, so a fallback ladder fires
  exactly one rung. An **apposition closes itself** (", a starship,") and the
  tidy pass absorbs its comma; a promoted subject **keeps its modifiers**. How
  it is *worded* and **how much** is spoken both come from the **archetype**:
  `detail_cap` and `detail_priority` give a creature its whole component list
  and a station, wreck, world or artifact only its silhouette. Every shipped
  pack declares a `POOL_DEFAULT_KEY` archetype, so a foreign-genre entity wired
  into a sci-fi scene is spoken through declared stranger grammar. Environment
  **bands** tie the subject and the action to the place, the environment
  *chooses* the kinds and respects a wired kind, and **deposit conditions**
  (`ice-encrusted`, `dust-caked`, `overgrown`) are gated to places that could
  deposit them. A field resolves through an ordered **scope chain** of control
  tokens (`subkind`, then `kind`), keyed by declared groups - the situation and
  the six component fields walk it too, and the surface-vehicle and small-drone
  **Declarative vocabularies** replace the hand lists: a place declares what it
  *affords* (`place_affordances`), a value declares what it *needs* of the
  place (`value_needs`), what it *is* (`value_traits` / `trait_conflicts`) and
  what a kind *can do* (`kind_capabilities` / `relation_roles`);
  `GenrePack.all_constraints` expands them into ordinary rules, so `engine/`
  stays genre-blind. A value also declares how it is *said* (`spoken`), so a
  subject is one noun phrase. Counts are never nulled -- a collision is
  re-drawn. Situations are restricted to what one still frame can show.
  An `Entities` control (1-4) reveals and fills slots; every occupied slot is
  described, never merely named. The readout is drawn inside the node with a
  token count, and a third line carries the first warning's own words.
  `prompt_json` records each entity's resolved archetype (`schema_version` 2).
  `GenrePack.motifs` declares cross-field word families and the distribution
  sweep gates their share, with a per-motif ceiling for the ring family. A
  **dramatic-weight axis** prices the interesting end: `value_tiers` /
  `tier_weights` tier a field's values (every value of a tiered field must
  carry one), `FieldSpec.omission_weight` lets a head modifier go unsaid,
  `KIND_WEIGHTS` weights the subjects, and a `context` scene field names what
  else is in the shot once per scene. The context field is spoken through
  `prose.context_sentences`: whole sentences with `{context}`, `{a_context}`
  and `{pronoun_object}` (a person is "them", never "it"), one of which is
  drawn at random per scene and whose index is recorded in
  `prompt_json._meta.context_sentence_index` so a document round-trips. The
  **affordance lint is live**: `affordance_keywords`, `affordance_lint_fields`
  and `affordance_allowlist` are populated, so the word-boundary scan in
  `tests/validate_data.py` fails a situation, context or subkind that names a
  place it declares no need for. A pool key carries its own needs
  (`default_needs`), so a key is classified once; a value's needs are its own
  `value_needs` entry if present (even empty), else the union of the
  `default_needs` of every key it is authored under, and the needs-free
  situation cores stay place-neutral by design. A second **stance axis**
  separates a place from a body: `value_stances` says what a form can do and
  `place_stances` says what a place supports, so a form is excluded from a
  place that supports none of its stances and a situation from a form it
  cannot share. `submerged` and `shoreline` split out of `water`, a validator
  check forbids a place granting both `submerged` and `sky` or both
  `open-space` and `ground`, and `celestial body` left the `orbit` band.
  keeps an event floor. Round XII added three more declared mechanisms: a place
  that floats stages its setting sentence (`prose.environment_staging`), a part
  that names a body structure is drawn only by a body that has it
  (`part_keywords` / `part_lint_fields`, check 29 `PARTFIT`), and a value nobody
  draws is dead (`scripts/reach_audit.py --gate`). A world rotates its tail like
  every other archetype, a non-combat machine carries no weapon, humanoid alien
  people are a `spacefarer` subkind group, and a secondary actor is a machine
  rather than a crowd. Round XIII added the **cardinality** axis
  (`value_cardinality` / `cardinality_counts`): a count noun declares how many
  of it there can be, `GenrePack` expands that into the noun field's pool groups,
  and check 30 `CARD` fails an unclassified count noun. It also added a
  **thermal**, a **state** and a **medium** axis over the existing
  `trait_conflicts` (`heat-scarred`/`frost-bound`, `inactive`/`powered-act`,
  `pristine-state`/`destruction-act`, `aqueous`/`combustion`), a `Sentence.needs`
  frozenset so a framing that claims depth is only drawn where the place has it,
  and a carried/worn split on the `figure` archetype. Two engine defects were
  fixed: the head-noun repeat guard nulled the field it was re-drawing when the
  re-draw pool came back empty, and `_apply_constraints` left a field None when
  the scope that emptied its pool was itself re-drawn later in the same fixed
  point -- which is how a subject arrived with no silhouette at all. The Python
  suites, the jsdom suite, the data validator, the distribution sweep, the
  coherence audit, the coherence sweep and `ruff` are green; the reach audit is
  not (see Known gaps). Round XIV's decisions D16-D24 and its measurements are
  in `docs/architecture.md` ("Concern audit (round XIV)").
- **In progress:** round XV's fixes and the horror pack are **not yet rendered**;
  the maintainer's render test decides the next round. `time_of_day` (fantasy and
  horror) and the fantasy Tone filter are designed in `docs/genre-roadmap.md` and
  not built. Round XIII was driven by a measured gap rather than
  by a report: on the 2026-09-15 batch `scripts/concern_audit.py` read **0.0%
  flagged** while 44 of 101 rendered images -- 43.6% -- were bad enough that the
  user pulled them out by hand. Every previous round had driven its own frozen
  flag list to zero and generalised nothing, so the round's first deliverable is
  `scripts/coherence_sweep.py`: classes shaped as *kinds* of incoherence, reading
  the pack's own declarations where they exist. It measured **37.3%** of 3000
  scenes at the start of the round and **5.2%** at the end, every class inside
  its ceiling. `scripts/concern_audit.py` still reports 0.0% on both paths and
  `scripts/reach_audit.py --gate` still reports every non-exempt value drawn.
- **Known gaps:**
  - `scripts/reach_audit.py --gate` **fails on `main` (0.3.0) and on round XIV**
    with a handful of never-drawn situations that are feasible but confined to a
    rare place and a rare kind (a drone at a trench vent). It samples; it is a
    maintainer instrument and CI does not run it. Round XIII's note calling it
    green was measured on a different seed.
  - Round XIV renamed or removed dropdown values; a saved workflow that locked
    one reports "value not in list". Release notes live in commit messages,
    never in the README (maintainer's rule).
  - Not fixed in round XIV (no clean fix yet): a generation ship can still be
    drawn landed on a surface, and "lunar far-side orbit" can render as the
    lunar surface despite the open-space staging suffix.
  - There is **no core-nodes-only example workflow.** The two graphs in
    `example_workflows/` are the maintainer's real Krea2 graphs, saved from a
    running ComfyUI, so they are known-good wiring but need a specific
    checkpoint/VAE/CLIP and two third-party packs. The previous hand-built
    `scene-weaver-minimal.json` was deleted rather than shipped: it had never
    been opened in ComfyUI and its positional `widgets_values` were one short
    of the live `widget_order`. A replacement must be **exported from a running
    instance**, never hand-written.
  - Cross-genre trait conflicts still fail open: a wired foreign entity carries
    no traits into the host scene (the roadmap proposes carrying them in the
    payload). A relation is not checked against an entity's state either, so an
    opt-in relation can have a petrified or slumbering entity "hunting" another.
  - The fantasy Tone filter (Any / Whimsical / Heroic / Grim) is designed but not
    built: it needs named content-tag axes in the contract. Horror's gore filter
    did not: it relabels the existing axis.
  - A wired Scene Entity's *kind and type* are never masked by the scene filter
    (a conflict-tagged sci-fi warship wired into a Peaceful scene stays); only its
    other drawn tag-scoped values are re-drawn (R6).
  - The horror pack has not been render-tested, and `reach_audit.py --pack horror`
    still lists a few rare-place situations as never drawn.
  - There is no fantasy or horror example workflow; swap the node in a sci-fi graph.
  - A world as **scenery** behind a ground-level scene has no placement concept,
    so `celestial body` is excluded from the `planetary surface` kind pool, and
    a world is no longer the subject in `orbit` either: with the camera already
    at a world, "a planet in an orbital debris belt" read as a planet set on the
    ground. A moon can only be the subject in deep space or a cloud layer.
    Recorded in `docs/architecture.md` as a decision, not an omission.
  - There are no section headings on the node face. Both approaches were tried
    and removed; `js/sceneweaver.js` records why.
  - `pytest tests` requires the pack directory to be named
    `comfyui-sceneweaver`. Documented, not fixed - see `docs/architecture.md`.
    `unittest discover` is unaffected and is the CI entry point.
  - `markings` deliberately ships no readable-text values; see the decision
    recorded in `docs/architecture.md`.
- **Deep docs:** `docs/architecture.md` - the genre seam (with a how-to-add-
  fantasy checklist), the generation pipeline, **the scope chain**,
  **archetypes** (including `detail_cap` / `detail_priority`), **trait
  conflicts**, the **sentence grammar** (including the closing apposition and
  the promoted subject), **environment staging**, **the part lint**, the
  **environment bands**, the two denylists, the tag vocabulary, the allowance
  table and token ceiling, the wired-entity precedence, the **reach audit**
  (round XII), and the measured distribution and motif baseline.

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
| `scripts/` | Maintainer tools: the distribution sweep, the pool lister. Not imported by the pack. |
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
python scripts/reach_audit.py --pack fantasy --seeds 12000
python scripts/reach_audit.py --pack horror --seeds 12000
python scripts/sample_distribution.py --seeds 1000
python scripts/coherence_audit.py --seeds 2000
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
- **A drawn wired value obeys the scene filter.** The Entity node has no filter; a
  scene that promises "No gore" must mask what the wire drew.
