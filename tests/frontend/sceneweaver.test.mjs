/**
 * The four frontend behaviours, plus the invariant that governs all of them.
 *
 * THE INVARIANT: labels and values may change; the widget ARRAY may not.
 * `widgets_values` is positional, so a reorder silently reassigns every value
 * after the moved widget in every workflow anyone has saved -- Identity Forge
 * measured 60 of 85 widgets landing one or more slots out from exactly this.
 *
 * `assertWidgetOrder` compares against the order the fixture DECLARES, not a
 * snapshot taken after setup ran. That distinction is not pedantry: the first
 * version of this file snapshotted after setup, and a planted
 * `node.widgets.reverse()` passed all 33 tests, because the snapshot had been
 * taken from the already-reversed array.
 */
import test from "node:test";
import assert from "node:assert/strict";

import { installDom, resetDom, recordingContext } from "./dom.mjs";
import {
  ENTITY_NODE,
  SCENE_NODE,
  assertWidgetOrder,
  clickAt,
  createNode,
  createNodeTwice,
  driveBeforeRegisterNodeDef,
  makeFakeNode,
  modernWidgets,
  specFor,
  widget,
} from "./fake_node.mjs";

installDom();

const { app, __getExtension, __resetApp } = await import("../../js/sceneweaver.js")
  .then(async () => import("./stubs/app.js"));
const { __resetApi, __setFetchApiHandler } = await import("./stubs/api.js");
const sw = await import("../../js/sceneweaver.js");

const EXTENSION = __getExtension("sceneweaver.ui");

test.beforeEach(() => {
  resetDom();
  __resetApi();
  sw.__resetFieldData();
});

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

test("the extension registers itself with app", () => {
  assert.ok(EXTENSION, "sceneweaver.ui was never registered");
  assert.equal(typeof EXTENSION.beforeRegisterNodeDef, "function");
  assert.ok(app);
});

test("setup leaves the widget array exactly as define_schema declared it", async () => {
  for (const nodeId of [SCENE_NODE, ENTITY_NODE]) {
    const node = await createNode(EXTENSION, nodeId);
    assertWidgetOrder(assert, node, nodeId);
  }
});

test("a node the payload does not describe is left completely alone", async () => {
  const FakeType = await driveBeforeRegisterNodeDef(EXTENSION, "SomeOtherNode");
  assert.equal(FakeType.prototype.onNodeCreated, undefined);
  assert.equal(FakeType.prototype.onExecuted, undefined);
  assert.equal(FakeType.prototype.onDrawForeground, undefined);
});

test("an unreachable data route degrades instead of breaking the node", async () => {
  __setFetchApiHandler(() => {
    throw new Error("route down");
  });
  const errors = [];
  const original = console.error;
  console.error = (...args) => errors.push(args);
  try {
    const FakeType = await driveBeforeRegisterNodeDef(EXTENSION, SCENE_NODE);
    // Nothing is installed, so the node is exactly the node ComfyUI built:
    // generic labels, full option lists, and every widget still working.
    assert.equal(FakeType.prototype.onNodeCreated, undefined);
    assert.ok(errors.length, "the failure must be reported, not swallowed");
  } finally {
    console.error = original;
  }
});

// ---------------------------------------------------------------------------
// (b) Kind-scoped relabelling
// ---------------------------------------------------------------------------

test("changing a slot's kind relabels that slot and reorders nothing", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  assertWidgetOrder(assert, node);
  const spec = specFor(SCENE_NODE);

  const kind = widget(node, "entity1_kind");
  kind.value = "vessel";
  kind.callback("vessel");

  assert.equal(widget(node, "entity1_form").label, "Hull silhouette 1");
  assert.equal(widget(node, "entity1_emitter_count").label, "Engine count 1");

  kind.value = "creature";
  kind.callback("creature");
  assert.equal(widget(node, "entity1_form").label, "Body plan 1");
  assert.equal(widget(node, "entity1_emitter_count").label, "Eye count 1");

  assertWidgetOrder(assert, node);
  assert.equal(widget(node, "entity1_form").name, "entity1_form", "name is the save key");
  assert.equal(node.widgets.length, spec.order.length);
});

test("a field with no per-kind label keeps its generic one, qualifier and all", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const kind = widget(node, "entity1_kind");
  kind.value = "vessel";
  kind.callback("vessel");
  assert.equal(widget(node, "entity1_situation").label, "Situation 1");
  assert.equal(widget(node, "environment").label, undefined, "not a slot field");
});

test("relabelling one slot leaves the others alone", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const kind1 = widget(node, "entity1_kind");
  kind1.value = "creature";
  kind1.callback("creature");
  assert.equal(widget(node, "entity1_form").label, "Body plan 1");
  assert.equal(widget(node, "entity2_situation").label, "Situation 2");
});

test("a kind of Random or None falls back to the generic labels", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const kind = widget(node, "entity1_kind");
  kind.value = "vessel";
  kind.callback("vessel");
  assert.equal(widget(node, "entity1_form").label, "Hull silhouette 1");
  kind.value = "Random";
  kind.callback("Random");
  assert.equal(widget(node, "entity1_form").label, "Form 1");
});

test("the option list narrows to the kind but always keeps the current value", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const form = widget(node, "entity1_form");
  const kind = widget(node, "entity1_kind");

  kind.value = "vessel";
  kind.callback("vessel");
  assert.deepEqual(form.options.values, ["Random", "needle hull", "saucer", "None"]);

  // Lock a vessel silhouette, then switch to a creature. The value is out of
  // scope now, and it must survive: a locked value is a statement of intent and
  // the backend honours it, so the widget must not quietly show something else.
  form.value = "saucer";
  kind.value = "creature";
  kind.callback("creature");
  assert.equal(form.value, "saucer");
  assert.ok(form.options.values.includes("saucer"));
  assert.ok(form.options.values.includes("hexapodal frame"));
});

test("changing a slot's Type narrows that slot's Form and leaves every other slot alone", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const subkind = widget(node, "entity1_subkind");
  const form = widget(node, "entity1_form");
  const slot2 = widget(node, "entity2_situation");

  subkind.value = "heavy freighter";
  subkind.callback("heavy freighter");
  assert.deepEqual(form.options.values, ["Random", "saucer", "None"]);
  // Slot 2 is untouched: its widgets are scoped by its own kind, not slot 1's.
  assert.deepEqual(slot2.options.values, ["Random", "docking at a station", "stalking prey", "drifting", "None"]);
  assertWidgetOrder(assert, node);
});

test("a Type of Random or None leaves Form at the full registered list", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const subkind = widget(node, "entity1_subkind");
  const form = widget(node, "entity1_form");
  const full = ["Random", "needle hull", "saucer", "hexapodal frame", "serpentine", "None"];

  subkind.value = "None";
  subkind.callback("None");
  assert.deepEqual(form.options.values, full);
  subkind.value = "Random";
  subkind.callback("Random");
  assert.deepEqual(form.options.values, full);
});

test("the search overlay is scoped by the whole chain, not just by kind", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  widget(node, "entity1_kind").value = "vessel";
  widget(node, "entity1_kind").callback("vessel");
  widget(node, "entity1_subkind").value = "courier";
  widget(node, "entity1_subkind").callback("courier");

  widget(node, "entity1_form").onClick({ e: clickAt(node, 100), node, canvas: null });
  assert.deepEqual(items(), ["Random", "needle hull", "None"]);
});

test("narrowing keeps the current value even when the new chain excludes it", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const form = widget(node, "entity1_form");
  const subkind = widget(node, "entity1_subkind");

  form.value = "saucer";
  subkind.value = "courier";
  subkind.callback("courier");
  assert.equal(form.value, "saucer");
  assert.ok(form.options.values.includes("saucer"));
  assert.ok(form.options.values.includes("needle hull"));
});

test("the entity node relabels off its bare kind widget", async () => {
  const node = await createNode(EXTENSION, ENTITY_NODE);
  assertWidgetOrder(assert, node);
  const kind = widget(node, "kind");
  kind.value = "creature";
  kind.callback("creature");
  assert.equal(widget(node, "form").label, "Body plan", "no slot qualifier on a lone entity");
  assert.equal(widget(node, "emitter_count").label, "Eye count");
  assertWidgetOrder(assert, node);
});

// ---------------------------------------------------------------------------
// (c) An honest set_all_fields
// ---------------------------------------------------------------------------

test("Clear all rewrites every Random widget and snaps back to Off", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  assertWidgetOrder(assert, node);
  const control = widget(node, "set_all_fields");

  control.value = "Clear all";
  control.callback("Clear all");

  assert.equal(widget(node, "environment").value, "None");
  assert.equal(widget(node, "entity1_kind").value, "None");
  assert.equal(widget(node, "entity1_form").value, "None");
  assert.equal(control.value, "Off", "it is an action, not a mode");
  // Controls are not fields and must be untouched.
  assert.equal(widget(node, "entity_count").value, "1");
  assert.equal(widget(node, "scene_filter").value, "Any");
  assert.equal(widget(node, "seed").value, 0);
  assertWidgetOrder(assert, node);
});

test("set_all_fields leaves a locked widget exactly as it was", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  widget(node, "entity1_form").value = "needle hull";
  widget(node, "entity1_kind").value = "vessel";

  const control = widget(node, "set_all_fields");
  control.value = "Clear all";
  control.callback("Clear all");

  assert.equal(widget(node, "entity1_form").value, "needle hull");
  assert.equal(widget(node, "entity1_kind").value, "vessel");
  assert.equal(widget(node, "environment").value, "None");
});

test("Randomize all undoes Clear all, and still skips the locks", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  widget(node, "entity1_form").value = "saucer";
  const control = widget(node, "set_all_fields");

  control.value = "Clear all";
  control.callback("Clear all");
  assert.equal(widget(node, "environment").value, "None");

  control.value = "Randomize all";
  control.callback("Randomize all");
  assert.equal(widget(node, "environment").value, "Random");
  assert.equal(widget(node, "entity1_kind").value, "Random");
  assert.equal(widget(node, "entity1_form").value, "saucer");
  assert.equal(control.value, "Off");
});

test("a relation left at its None default is picked back up by Randomize all", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  assert.equal(widget(node, "relation_1_2").value, "None");
  const control = widget(node, "set_all_fields");
  control.value = "Randomize all";
  control.callback("Randomize all");
  assert.equal(widget(node, "relation_1_2").value, "Random");
});

test("set_all_fields works through the current frontend's setValue too", async () => {
  const node = modernWidgets(await createNode(EXTENSION, SCENE_NODE));
  const control = widget(node, "set_all_fields");
  control.setValue("Clear all", { node });
  assert.equal(widget(node, "environment").value, "None");
  assert.equal(control.value, "Off");
});

test("the entity node has no bulk control and applySetAll is a no-op there", async () => {
  const node = await createNode(EXTENSION, ENTITY_NODE);
  assert.equal(widget(node, "set_all_fields"), undefined);
  assert.equal(sw.applySetAll(node, specFor(ENTITY_NODE), "Clear all"), 0);
  assert.equal(widget(node, "form").value, "Random");
});

// ---------------------------------------------------------------------------
// (a) Searchable dropdowns
// ---------------------------------------------------------------------------

function overlay() {
  return document.querySelector(".sceneweaver-search");
}
function items() {
  return Array.from(document.querySelectorAll(".sceneweaver-search-list li")).map(
    (li) => li.textContent,
  );
}

test("clicking a field widget opens a filterable list of its values", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const form = widget(node, "entity1_form");

  form.onClick({ e: clickAt(node, 100), node, canvas: null });

  assert.ok(overlay(), "no search overlay opened");
  assert.deepEqual(items(), [
    "Random", "needle hull", "saucer", "hexapodal frame", "serpentine", "None",
  ]);
});

test("typing filters the list, case-insensitively and on substrings", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  widget(node, "entity1_form").onClick({ e: clickAt(node, 100), node, canvas: null });

  const input = overlay().querySelector("input");
  input.value = "HULL";
  input.dispatchEvent(new window.Event("input"));
  assert.deepEqual(items(), ["needle hull"]);

  input.value = "zzz";
  input.dispatchEvent(new window.Event("input"));
  assert.deepEqual(items(), []);
});

test("choosing a value sets the widget and closes the overlay", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const form = widget(node, "entity1_form");
  assertWidgetOrder(assert, node);
  form.onClick({ e: clickAt(node, 100), node, canvas: null });

  const chosen = Array.from(document.querySelectorAll(".sceneweaver-search-list li")).find(
    (li) => li.textContent === "saucer",
  );
  chosen.dispatchEvent(new window.Event("click"));

  assert.equal(form.value, "saucer");
  assert.equal(overlay(), null);
  assertWidgetOrder(assert, node);
});

test("the search list is scoped to the slot's kind", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const kind = widget(node, "entity1_kind");
  kind.value = "creature";
  kind.callback("creature");

  widget(node, "entity1_form").onClick({ e: clickAt(node, 100), node, canvas: null });
  assert.deepEqual(items(), ["Random", "hexapodal frame", "serpentine", "None"]);
});

test("Escape closes and Enter takes the first match", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const form = widget(node, "entity1_form");

  form.onClick({ e: clickAt(node, 100), node, canvas: null });
  let input = overlay().querySelector("input");
  input.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape" }));
  assert.equal(overlay(), null);

  form.onClick({ e: clickAt(node, 100), node, canvas: null });
  input = overlay().querySelector("input");
  input.value = "serp";
  input.dispatchEvent(new window.Event("input"));
  input.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Enter" }));
  assert.equal(form.value, "serpentine");
  assert.equal(overlay(), null);
});

test("the stepper zones at each end still reach the original handler", async () => {
  const node = makeFakeNode(SCENE_NODE);
  const form = node.widgets.find((w) => w.name === "entity1_form");
  let stepped = 0;
  form.onClick = () => {
    stepped += 1;
  };
  const FakeType = await driveBeforeRegisterNodeDef(EXTENSION, SCENE_NODE);
  FakeType.prototype.onNodeCreated.call(node);

  form.onClick({ e: clickAt(node, 5), node, canvas: null }); // left arrow
  form.onClick({ e: clickAt(node, 195), node, canvas: null }); // right arrow
  assert.equal(stepped, 2);
  assert.equal(overlay(), null, "a stepper click must not open the search");

  form.onClick({ e: clickAt(node, 100), node, canvas: null });
  assert.ok(overlay());
  assert.equal(stepped, 2);
});

test("only one overlay is ever open", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  widget(node, "entity1_form").onClick({ e: clickAt(node, 100), node, canvas: null });
  widget(node, "entity1_situation").onClick({ e: clickAt(node, 100), node, canvas: null });
  assert.equal(document.querySelectorAll(".sceneweaver-search").length, 1);
});

test("the legacy widget.mouse hook opens the same overlay", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const form = widget(node, "entity1_form");
  assert.equal(form.mouse(clickAt(node, 100), [100, 0], node), true);
  assert.ok(overlay());
  // A move is not a click; only a press opens it.
  sw.closeSearch();
  form.mouse({ type: "pointermove", canvasX: 110 }, [100, 0], node);
  assert.equal(overlay(), null);
});

test("a control widget is not searchable -- it has no pool", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  assert.equal(widget(node, "entity_count").__sceneweaverSearch, undefined);
  assert.equal(widget(node, "scene_filter").__sceneweaverSearch, undefined);
});

test("the overlay is fixed-positioned above the canvas at the click", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  widget(node, "entity1_form").onClick({
    e: { ...clickAt(node, 100), clientX: 320, clientY: 140 },
    node,
    canvas: null,
  });
  const el = overlay();
  assert.ok(el, "no overlay opened");
  assert.equal(el.style.position, "fixed");
  assert.equal(el.style.zIndex, "10000");
  assert.equal(el.style.left, "320px");
  assert.equal(el.style.top, "140px");
});

test("a pointerdown outside the overlay closes it", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  widget(node, "entity1_form").onClick({ e: clickAt(node, 100), node, canvas: null });
  assert.ok(overlay());
  document.body.dispatchEvent(new window.Event("pointerdown", { bubbles: true }));
  assert.equal(overlay(), null);
});

test("the native menu is preserved as a fallback when search cannot open", async () => {
  // A field the payload does not describe has no spec, so openFieldSearch
  // returns null and the original onClick must run -- the native combo menu.
  const node = await createNode(EXTENSION, SCENE_NODE);
  const form = widget(node, "entity1_form");
  let native = 0;
  const original = form.onClick;
  form.onClick = () => {
    native += 1;
  };
  sw.openFieldSearch(node, form, { fields: {}, random: "Random", none: "None", default_key: "_default" });
  assert.equal(overlay(), null, "a fieldless widget must not open the overlay");
  // The wrapper (installed by setup) still chains to the original handler.
  form.onClick({ e: clickAt(node, 100), node, canvas: null });
  assert.ok(native >= 1, "the original onClick must still run");
  form.onClick = original;
});

test("no separator widgets remain, and no group headers are drawn", async () => {
  // Both approaches to section headings are gone. Separator widgets took a
  // `widgets_values` slot each; canvas headers were painted under the widget
  // pill by the current frontend and rendered as a single clipped letter.
  // The slot number in each label is what carries the structure now.
  const node = await createNode(EXTENSION, SCENE_NODE);
  for (const w of node.widgets) {
    assert.ok(!w.name.startsWith("sep_"), `separator widget ${w.name} must be gone`);
  }
  assertWidgetOrder(assert, node);
  assert.equal(sw.groupHeaderPlan, undefined);
  assert.equal(sw.drawGroupHeaders, undefined);

  node.__type.prototype.onExecuted.call(node, { text: ["a", "b"] });
  const ctx = recordingContext();
  node.__type.prototype.onDrawForeground.call(node, ctx);
  assert.deepEqual(ctx.texts, ["a", "b"], "only the readout is painted");
});

// ---------------------------------------------------------------------------
// (d) The node-face readout
// ---------------------------------------------------------------------------

test("a run's two lines are stored and drawn inside the node footer", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const type = node.__type;

  type.prototype.onExecuted.call(node, {
    text: ["deep space | strike carrier", "Any | 1 entity | 0 relations | 94 tok"],
  });

  const ctx = recordingContext();
  type.prototype.onDrawForeground.call(node, ctx);
  assert.deepEqual(ctx.texts, [
    "deep space | strike carrier",
    "Any | 1 entity | 0 relations | 94 tok",
  ]);
  // Inside the node, in the strip computeSize reserved for it. It used to be
  // painted below the body, where it floated over the canvas and belonged to
  // nothing; the whole point of the change is that these are now < size[1].
  const ys = ctx.calls.filter((c) => c[0] === "fillText").map((c) => c[3]);
  assert.ok(ys.length > 0);
  assert.ok(
    ys.every((y) => y > 0 && y <= node.size[1]),
    `expected every line inside 0..${node.size[1]}, got ${JSON.stringify(ys)}`,
  );
});

test("the node reserves footer height only once a run has reported", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const type = node.__type;

  const bare = type.prototype.computeSize.call(node)[1];
  type.prototype.onExecuted.call(node, { text: ["one", "two"] });
  const withFooter = type.prototype.computeSize.call(node)[1];

  assert.ok(
    withFooter > bare,
    `expected the footer to add height: ${bare} -> ${withFooter}`,
  );
  // Stable, not cumulative: computeSize is called on every layout pass.
  assert.equal(type.prototype.computeSize.call(node)[1], withFooter);
});

test("nothing is drawn before the first run, or while collapsed", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const type = node.__type;

  let ctx = recordingContext();
  type.prototype.onDrawForeground.call(node, ctx);
  assert.deepEqual(ctx.texts, []);

  type.prototype.onExecuted.call(node, { text: ["a", "b"] });
  node.flags.collapsed = true;
  ctx = recordingContext();
  type.prototype.onDrawForeground.call(node, ctx);
  assert.deepEqual(ctx.texts, []);
});

test("a run that reports nothing usable leaves the last readout standing", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const type = node.__type;
  type.prototype.onExecuted.call(node, { text: ["first", "second"] });
  type.prototype.onExecuted.call(node, {});
  type.prototype.onExecuted.call(node, { text: [] });

  const ctx = recordingContext();
  type.prototype.onDrawForeground.call(node, ctx);
  assert.deepEqual(ctx.texts, ["first", "second"]);
});

test("the readout never adds a widget", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  node.__type.prototype.onExecuted.call(node, { text: ["a", "b"] });
  node.__type.prototype.onDrawForeground.call(node, recordingContext());
  assertWidgetOrder(assert, node);
});

// ---------------------------------------------------------------------------
// The re-entry guard
// ---------------------------------------------------------------------------

test("onNodeCreated firing twice wraps nothing twice and adds nothing", async () => {
  const node = await createNodeTwice(EXTENSION, SCENE_NODE);
  assertWidgetOrder(assert, node);

  // If set_all's callback had been wrapped twice the bulk edit would run twice.
  // It is idempotent, so count the relabel instead: a doubly-wrapped kind
  // callback dirties the canvas twice per change.
  const kind = widget(node, "entity1_kind");
  node.dirtied = 0;
  kind.value = "vessel";
  kind.callback("vessel");
  assert.equal(node.dirtied, 1);
});

test("a second setup call on the same node reports that it did nothing", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  assert.equal(sw.setupNode(node, specFor(SCENE_NODE)), false);
});

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

test("poolFor falls through to the pack default", () => {
  const spec = specFor(SCENE_NODE);
  assert.deepEqual(sw.poolFor(spec, "form", { kind: "vessel" }), ["needle hull", "saucer"]);
  assert.deepEqual(sw.poolFor(spec, "situation", { kind: "nonesuch" }), ["drifting"]);
  assert.equal(sw.poolFor(spec, "not_a_field", { kind: "vessel" }), null);
});

test("scopedChoices keeps the sentinels the registered list actually has", () => {
  const spec = specFor(SCENE_NODE);
  assert.deepEqual(sw.scopedChoices(spec, "entity1_form", { kind: "vessel" }), [
    "Random", "needle hull", "saucer", "None",
  ]);
  // Not kind-scoped: the registered list, untouched.
  assert.deepEqual(sw.scopedChoices(spec, "entity1_emitter_count", { kind: "vessel" }), [
    "Random", "a single", "a pair of", "None",
  ]);
  assert.equal(sw.scopedChoices(spec, "no_such_widget", { kind: "vessel" }), null);
});

test("isLocked is exactly 'not one of the two sentinels'", () => {
  const spec = specFor(SCENE_NODE);
  assert.equal(sw.isLocked({ value: "Random" }, spec), false);
  assert.equal(sw.isLocked({ value: "None" }, spec), false);
  assert.equal(sw.isLocked({ value: "saucer" }, spec), true);
});

test("a pointerdown on the overlay itself does not close it", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  widget(node, "entity1_form").onClick({ e: clickAt(node, 100), node, canvas: null });
  const el = overlay();
  assert.ok(el, "overlay did not open");
  el.dispatchEvent(new window.Event("pointerdown", { bubbles: true }));
  assert.equal(overlay(), el, "overlay closed on its own pointerdown");
});

test("the compact face hides entity slots 2+ and relations until used", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  assert.ok(!widget(node, "entity1_kind").hidden, "entity 1 must stay visible");
  assert.equal(widget(node, "entity2_kind").hidden, true);
  assert.equal(widget(node, "entity2_situation").hidden, true);
  assert.equal(widget(node, "relation_1_2").hidden, true);
});

test("setting a slot's kind reveals it, and None hides it again", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const kind = widget(node, "entity2_kind");
  kind.value = "vessel";
  kind.callback("vessel");
  assert.equal(widget(node, "entity2_situation").hidden, false);
  assert.equal(widget(node, "relation_1_2").hidden, false, "two entities reveal relations");
  kind.value = "None";
  kind.callback("None");
  assert.equal(widget(node, "entity2_situation").hidden, true);
  assert.equal(widget(node, "relation_1_2").hidden, true);
});

test("a wired socket hides the widgets its wire overrides, and keeps the situation", async () => {
  // The wire supplies that slot's whole description and outranks a value
  // locked on these widgets -- the engine says so and reports it in _meta. So
  // showing them invites the user to set something that will be thrown away.
  // What the scene still owns for a wired slot is what the entity is *doing*.
  const node = await createNode(EXTENSION, SCENE_NODE);
  node.inputs = [{ name: "entity_2_in", link: 1 }];
  sw.applyCompactFace(node, specFor(SCENE_NODE));

  assert.equal(widget(node, "entity2_kind").hidden, true);
  assert.equal(widget(node, "entity2_situation").hidden, false);
});

test("a wired socket occupies its slot, so the relation widgets appear", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  assert.equal(widget(node, "relation_1_2").hidden, true);
  node.inputs = [{ name: "entity_2_in", link: 1 }];
  sw.applyCompactFace(node, specFor(SCENE_NODE));
  assert.equal(widget(node, "relation_1_2").hidden, false);
});

test("the entity count reveals and hides slots", async () => {
  // The control the node face was missing: slot 2's widgets were only
  // reachable by wiring a node into the socket, so there was no way to ask for
  // a second subject from the node itself.
  const node = await createNode(EXTENSION, SCENE_NODE);
  const count = widget(node, "entity_count");
  assert.equal(widget(node, "entity2_kind").hidden, true);
  assert.equal(widget(node, "relation_1_2").hidden, true);

  count.value = "2";
  count.callback("2");
  assert.equal(widget(node, "entity2_kind").hidden, false);
  assert.equal(widget(node, "entity2_situation").hidden, false);
  assert.equal(widget(node, "relation_1_2").hidden, false);

  count.value = "1";
  count.callback("1");
  assert.equal(widget(node, "entity2_kind").hidden, true);
  assert.equal(widget(node, "relation_1_2").hidden, true);
});

test("onConfigure reveals a slot with a locked kind on reload", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  widget(node, "entity2_kind").value = "vessel";
  node.__type.prototype.onConfigure.call(node);
  assert.equal(widget(node, "entity2_situation").hidden, false);
});


test("the footer grows to three lines only when a third is supplied", async () => {
  const node = await createNode(EXTENSION, SCENE_NODE);
  const type = node.__type;

  type.prototype.onExecuted.call(node, { text: ["one", "two"] });
  const two = sw.readoutHeight(node);
  type.prototype.onExecuted.call(node, { text: ["one", "two", "warn"] });
  const three = sw.readoutHeight(node);
  assert.ok(three > two, `expected a third line to grow the strip: ${two} -> ${three}`);

  // The common two-line case gains no dead space, and a fourth line is dropped.
  type.prototype.onExecuted.call(node, { text: ["one", "two", "warn", "extra"] });
  assert.equal(sw.readoutHeight(node), three);
});

test("the six component fields narrow on subkind as well as kind", () => {
  const components = [
    "appendages", "emitters", "armament", "sensors", "extras", "markings",
  ];
  const spec = {
    default_key: "_default",
    random: "Random",
    none: "None",
    fields: {},
    pools: {},
    pool_groups: { subkind: { hulls: ["heavy freighter"] } },
    choices: {},
  };
  for (const base of components) {
    spec.fields[`entity1_${base}`] = { base, scope: ["subkind", "kind"], label: base };
    spec.choices[base] = ["Random", "solid greeble", "hull fitting", "None"];
    spec.pools[base] = {
      "heavy freighter": ["hull fitting"],
      _default: ["solid greeble"],
    };
  }

  for (const base of components) {
    const key = `entity1_${base}`;
    assert.deepEqual(
      sw.scopedChoices(spec, key, { subkind: "heavy freighter" }),
      ["Random", "hull fitting", "None"],
      `${base} did not narrow on subkind`
    );
    // With nothing locked the registered list is untouched.
    assert.deepEqual(sw.scopedChoices(spec, key, {}), spec.choices[base]);
    assert.deepEqual(
      sw.poolFor(spec, base, { subkind: "heavy freighter" }),
      ["hull fitting"]
    );
  }
});
