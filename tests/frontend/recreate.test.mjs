/**
 * "Fix node (recreate)" and the face re-derivation that follows a load.
 *
 * ComfyUI-Manager's recreate adds the new node, throws while reconnecting, and
 * leaves a duplicate (Comfy-Org/ComfyUI-Manager#3126). This pack installs its own
 * and removes any other pack's entry from the menu of its own nodes. Recreate is
 * LiteGraph mechanics (nodes, sockets, links), so the graph and socket layer lives
 * in this file rather than the shared driver; the layer mirrors the real one in
 * the two ways the original bug depended on: `connect` resolves a node OBJECT
 * (a bare id throws), and removing a node unlinks both of its ends.
 */
import test from "node:test";
import assert from "node:assert/strict";

import { installDom, resetDom } from "./dom.mjs";
import {
  SCENE_NODE,
  driveBeforeRegisterNodeDef,
  makeFakeNode,
  widget,
} from "./fake_node.mjs";

installDom();

await import("../../js/sceneweaver.js");
const { __getExtension } = await import("./stubs/app.js");
const { __resetApi } = await import("./stubs/api.js");
const sw = await import("../../js/sceneweaver.js");

const EXTENSION = __getExtension("sceneweaver.ui");

test.beforeEach(() => {
  resetDom();
  __resetApi();
  sw.__resetFieldData();
});

// -- fake LiteGraph graph + socket layer -------------------------------------

function makeGraph() {
  let nextNodeId = 1;
  let nextLinkId = 1;
  const nodes = new Map();
  const links = new Map();
  const graph = {
    log: [],
    lastAdded: null,
    add(node) {
      graph.lastAdded = node;
      if (node.id == null) node.id = nextNodeId++;
      node.graph = graph;
      nodes.set(node.id, node);
      graph.log.push(["add", node.id]);
    },
    remove(node) {
      graph.log.push(["remove", node.id]);
      for (const input of node.inputs || []) {
        const link = links.get(input.link);
        if (link) {
          const origin = nodes.get(link.origin_id);
          const out = origin?.outputs[link.origin_slot];
          if (out) out.links = out.links.filter((id) => id !== input.link);
          links.delete(input.link);
        }
        input.link = null;
      }
      for (const output of node.outputs || []) {
        for (const linkId of output.links || []) {
          const link = links.get(linkId);
          if (link) {
            const target = nodes.get(link.target_id);
            if (target?.inputs[link.target_slot]) target.inputs[link.target_slot].link = null;
            links.delete(linkId);
          }
        }
        output.links = [];
      }
      nodes.delete(node.id);
    },
    has(node) {
      return nodes.get(node.id) === node;
    },
    count(type) {
      return [...nodes.values()].filter((n) => n.comfyClass === type).length;
    },
    getNodeById(id) {
      return nodes.get(id) ?? null;
    },
    getLink(id) {
      return links.get(id) ?? null;
    },
    afterChange() {},
    __addLink(origin, originSlot, target, targetSlot) {
      const id = nextLinkId++;
      links.set(id, {
        id,
        origin_id: origin.id,
        origin_slot: originSlot,
        target_id: target.id,
        target_slot: targetSlot,
      });
      return id;
    },
  };
  return graph;
}

function withSockets(node, { inputs = [], outputs = [] }) {
  node.inputs = inputs.map((name) => ({ name, link: null }));
  node.outputs = outputs.map((name) => ({ name, links: [] }));
  node.findInputSlot = function (name) {
    return this.inputs.findIndex((i) => i.name === name);
  };
  node.findOutputSlot = function (name) {
    return this.outputs.findIndex((o) => o.name === name);
  };
  // Mirrors real LiteGraph: only a node OBJECT is resolved. A bare id throws,
  // which is how this test catches rule 1.
  node.connect = function (originSlot, target, targetSlotOrName) {
    const index =
      typeof targetSlotOrName === "number" ? targetSlotOrName : target.findInputSlot(targetSlotOrName);
    if (index < 0) return null;
    const linkId = this.graph.__addLink(this, originSlot, target, index);
    this.outputs[originSlot].links.push(linkId);
    target.inputs[index].link = linkId;
    return linkId;
  };
  return node;
}

function wire(graph, origin, outputName, target, inputName) {
  const originSlot = origin.outputs.findIndex((o) => o.name === outputName);
  const targetSlot = target.inputs.findIndex((i) => i.name === inputName);
  assert.ok(originSlot >= 0 && targetSlot >= 0, "wire: named socket missing from the fixture");
  const id = graph.__addLink(origin, originSlot, target, targetSlot);
  origin.outputs[originSlot].links.push(id);
  target.inputs[targetSlot].link = id;
}

const SCENE_SOCKETS = {
  inputs: ["entity_1_in", "entity_2_in"],
  outputs: ["prompt_text", "prompt_json"],
};

/** Install a synchronous LiteGraph.createNode that builds a fully set-up node. */
async function installLiteGraph(type) {
  const FakeType = await driveBeforeRegisterNodeDef(EXTENSION, type);
  window.LiteGraph = {
    createNode(requested) {
      const node = makeFakeNode(requested);
      withSockets(node, SCENE_SOCKETS);
      node.pos = [0, 0];
      FakeType.prototype.onNodeCreated.call(node);
      return node;
    },
  };
  return FakeType;
}

async function sceneNodeInGraph() {
  const graph = makeGraph();
  await installLiteGraph(SCENE_NODE);
  const node = window.LiteGraph.createNode(SCENE_NODE);
  graph.add(node);
  return { graph, node };
}

function menu(node, preexisting = []) {
  const options = [...preexisting];
  node.getExtraMenuOptions(null, options);
  return options;
}

const recreateEntries = (options) =>
  options.filter((o) => typeof o?.content === "string" && /recreate/i.test(o.content));

async function quiet(fn) {
  const original = [console.warn, console.error];
  const seen = [];
  console.warn = (...args) => seen.push(args.join(" "));
  console.error = (...args) => seen.push(args.join(" "));
  try {
    await fn();
  } finally {
    [console.warn, console.error] = original;
  }
  return seen;
}

// -- the menu -----------------------------------------------------------------

test("the menu carries exactly one recreate entry, and it is ours", async () => {
  const { node } = await sceneNodeInGraph();
  const managers = { content: "Fix node (recreate)", callback: () => {} };
  const renamed = { content: "Recreate node (fixed)", callback: () => {} };

  for (const preexisting of [[], [managers], [renamed], [managers, renamed]]) {
    const entries = recreateEntries(menu(node, preexisting));
    assert.equal(entries.length, 1, "one recreate entry, however many other packs add one");
    assert.equal(entries[0].content, "Fix node (recreate)");
    assert.ok(!preexisting.includes(entries[0]), "must be this pack's callback, not Manager's");
  }
});

test("a node the pack did not build is left alone", async () => {
  const FakeType = await driveBeforeRegisterNodeDef(EXTENSION, "SomeOtherNode");
  assert.equal(FakeType.prototype.onNodeCreated, undefined);
});

// -- the recreate itself ---------------------------------------------------------

test("recreate removes the original before reconnecting, by name, with values intact", async () => {
  const { graph, node } = await sceneNodeInGraph();
  const upstream = withSockets({ comfyClass: "Upstream", widgets: [] }, { outputs: ["entity"] });
  const downstream = withSockets({ comfyClass: "Downstream", widgets: [] }, { inputs: ["text"] });
  graph.add(upstream);
  graph.add(downstream);
  wire(graph, upstream, "entity", node, "entity_2_in");
  wire(graph, node, "prompt_text", downstream, "text");

  widget(node, "entity1_kind").value = "vessel";
  const situation = widget(node, "entity1_situation").options.values.find(
    (v) => v !== "Random" && v !== "None",
  );
  widget(node, "entity1_situation").value = situation;
  node.title = "My weaver";
  node.pos = [40, 80];
  graph.log.length = 0;

  assert.equal(sw.recreateNode(node), true);

  assert.equal(graph.count(SCENE_NODE), 1, "exactly one node survives a recreate");
  assert.ok(!graph.has(node), "the original is gone");
  const freshNode = graph.lastAdded;
  assert.deepEqual(graph.log.map((e) => e[0]), ["add", "remove"], "added, then the original removed");
  assert.equal(widget(freshNode, "entity1_kind").value, "vessel");
  assert.equal(widget(freshNode, "entity1_situation").value, situation);
  assert.equal(freshNode.title, "My weaver");
  assert.deepEqual(freshNode.pos, [40, 80]);
  assert.ok(freshNode.inputs[freshNode.findInputSlot("entity_2_in")].link != null, "input relinked by name");
  assert.ok(downstream.inputs[0].link != null, "output relinked by name");
});

test("recreate re-derives the per-kind labels and narrowed lists from the restored values", async () => {
  const { graph, node } = await sceneNodeInGraph();
  widget(node, "entity1_kind").value = "vessel";
  sw.syncFace(node, node.__sceneweaver);
  assert.equal(widget(node, "entity1_emitter_count").label, "Engine count 1");

  sw.recreateNode(node);
  assert.equal(widget(graph.lastAdded, "entity1_emitter_count").label, "Engine count 1");
});

test("a value the fresh node no longer offers is dropped and named, not forced", async () => {
  const { graph, node } = await sceneNodeInGraph();
  widget(node, "entity1_situation").value = "a value from an older release";
  const seen = await quiet(() => sw.recreateNode(node));
  const fresh = graph.lastAdded;
  assert.notEqual(widget(fresh, "entity1_situation").value, "a value from an older release");
  assert.ok(seen.some((line) => line.includes("entity1_situation")), "the dropped widget is named");
});

test("a failure before the original is removed leaves the graph as it was", async () => {
  const { graph, node } = await sceneNodeInGraph();
  window.LiteGraph.createNode = (type) => {
    const fresh = makeFakeNode(type);
    withSockets(fresh, SCENE_SOCKETS);
    fresh.pos = [0, 0];
    fresh.size = null; // the sizing step cannot read this, after the node was added
    return fresh;
  };
  await quiet(() => assert.throws(() => sw.recreateNode(node)));
  assert.ok(graph.has(node), "the original is still on the canvas");
  assert.equal(graph.count(SCENE_NODE), 1, "no duplicate was left behind");
});

// -- a loaded node gets its face back ---------------------------------------------

test("onConfigure relabels and narrows a node whose values were restored without callbacks", async () => {
  const FakeType = await driveBeforeRegisterNodeDef(EXTENSION, SCENE_NODE);
  const node = makeFakeNode(SCENE_NODE);
  FakeType.prototype.onNodeCreated.call(node);
  assert.equal(widget(node, "entity1_emitter_count").label, "Emitter count 1", "generic until a kind is set");

  // What a workflow load does: assign values, fire no callback, then onConfigure.
  widget(node, "entity1_kind").value = "vessel";
  FakeType.prototype.onConfigure.call(node);
  assert.equal(widget(node, "entity1_emitter_count").label, "Engine count 1");
});

test("a connection change re-derives the face too", async () => {
  const FakeType = await driveBeforeRegisterNodeDef(EXTENSION, SCENE_NODE);
  const node = makeFakeNode(SCENE_NODE);
  FakeType.prototype.onNodeCreated.call(node);
  widget(node, "entity1_kind").value = "vessel";
  FakeType.prototype.onConnectionsChange.call(node, 1, 0, true, null);
  assert.equal(widget(node, "entity1_emitter_count").label, "Engine count 1");
});
