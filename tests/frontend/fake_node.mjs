/**
 * A LiteGraph-shaped fake node built from tests/frontend/fixtures/nodes.json,
 * plus a driver for the extension's registration lifecycle.
 *
 * `js/sceneweaver.js` hooks `beforeRegisterNodeDef`, which is `async` and
 * receives `(nodeType, nodeData)` -- a *class* with a real `.prototype`, not a
 * node instance. It wraps three prototype methods (`onNodeCreated`,
 * `onExecuted`, `onDrawForeground`), so driving it needs the class as well as
 * the instance.
 *
 * The widget objects mirror the two frontend generations this pack has to work
 * on: `value` as a plain property with a `callback` (older), and a `setValue`
 * method that assigns and then fires the callback (current). `makeFakeNode`
 * builds the older shape and `modernWidgets` upgrades a node to the newer one,
 * so `setWidgetValue` is exercised down both paths rather than only the one
 * this machine happens to have.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const FIXTURES = JSON.parse(
  readFileSync(fileURLToPath(new URL("./fixtures/nodes.json", import.meta.url)), "utf-8"),
);

export const SCENE_NODE = "SceneWeaverFixture";
export const ENTITY_NODE = "SceneEntityFixture";

/** The raw fixture spec for a node id -- what the route would have served. */
export function specFor(nodeId) {
  return FIXTURES.nodes[nodeId];
}

export function widgetsFor(nodeId) {
  const spec = FIXTURES.widgets[nodeId];
  if (!spec) throw new Error(`No widget fixture for ${JSON.stringify(nodeId)}`);
  return spec;
}

function makeWidget(spec) {
  return {
    name: spec.name,
    type: spec.type,
    value: spec.default,
    callback: null,
    width: 200,
    options: spec.type === "combo" ? { values: [...(spec.options ?? [])] } : {},
  };
}

export function makeFakeNode(nodeId) {
  return {
    comfyClass: nodeId,
    type: nodeId,
    widgets: widgetsFor(nodeId).map(makeWidget),
    size: [300, 400],
    pos: [10, 20],
    flags: {},
    title: null,
    dirtied: 0,
    setSize(sz) {
      this.size = sz;
    },
    computeSize() {
      return [300, 24 * this.widgets.length];
    },
    setDirtyCanvas() {
      this.dirtied += 1;
    },
  };
}

/**
 * Swap a node's widgets to the current frontend's shape: `setValue(value, ctx)`
 * assigns and then fires the callback, exactly as the real ComboWidget does.
 */
export function modernWidgets(node) {
  for (const widget of node.widgets) {
    widget.setValue = function (value, ctx) {
      this.value = value;
      this.callback?.(value, ctx?.canvas, ctx?.node);
    };
  }
  return node;
}

/** The widget with this name, or undefined. */
export function widget(node, name) {
  return node.widgets.find((w) => w.name === name);
}

/** Names in array order -- the thing that must never change. */
export function widgetNames(node) {
  return node.widgets.map((w) => w.name);
}

/**
 * Assert the widget array still matches what `define_schema` declared.
 *
 * Compared against the FIXTURE's declared order, never against a snapshot taken
 * after setup ran -- a snapshot of an already-reordered array matches itself,
 * and a planted `node.widgets.reverse()` sailed through a whole suite of
 * snapshot comparisons before this existed. The declared order is the only
 * thing a saved `widgets_values` was written against, so it is the only honest
 * thing to compare to.
 */
export function assertWidgetOrder(assert, node, nodeId = node.type) {
  assert.deepEqual(
    widgetNames(node),
    specFor(nodeId).order,
    "widget order changed: every saved workflow's widgets_values would be reassigned",
  );
}

/**
 * Register the extension against a fake nodeType for `nodeId` and return the
 * class. Passing an id the fixture does not define exercises the extension's
 * own early return, which is the "not our node" path.
 */
export async function driveBeforeRegisterNodeDef(ext, nodeId) {
  class FakeNodeType {}
  await ext.beforeRegisterNodeDef(FakeNodeType, { name: nodeId });
  return FakeNodeType;
}

/** End to end: build a node, register the hooks, run `onNodeCreated`. */
export async function createNode(ext, nodeId) {
  const node = makeFakeNode(nodeId);
  const FakeNodeType = await driveBeforeRegisterNodeDef(ext, nodeId);
  FakeNodeType.prototype.onNodeCreated?.call(node);
  node.__type = FakeNodeType;
  return node;
}

/**
 * Fires `onNodeCreated` TWICE on the same node, which ComfyUI genuinely does on
 * some paths. Single creation cannot see a double-wrapping bug, because there
 * is nothing to double on the first pass -- which is how Identity Forge shipped
 * four setups without a re-entry guard.
 */
export async function createNodeTwice(ext, nodeId) {
  const node = makeFakeNode(nodeId);
  const FakeNodeType = await driveBeforeRegisterNodeDef(ext, nodeId);
  FakeNodeType.prototype.onNodeCreated?.call(node);
  FakeNodeType.prototype.onNodeCreated?.call(node);
  node.__type = FakeNodeType;
  return node;
}

/** A pointer event shaped like the one LiteGraph hands a widget's onClick. */
export function clickAt(node, offsetX) {
  return { type: "pointerdown", canvasX: node.pos[0] + offsetX, canvasY: 0 };
}
