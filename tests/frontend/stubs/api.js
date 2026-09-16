/**
 * Stand-in for ComfyUI's `scripts/api.js`. `js/sceneweaver.js` uses exactly one
 * call -- `fetchApi("/sceneweaver/fields")` -- so this serves the fixture
 * payload by default and lets a test swap in a failure to exercise the
 * degraded path, which is the branch that decides whether an unreachable route
 * breaks the node or merely un-prettifies it.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const FIXTURE = JSON.parse(
  readFileSync(fileURLToPath(new URL("../fixtures/nodes.json", import.meta.url)), "utf-8"),
);

function defaultHandler(route) {
  if (route === "/sceneweaver/fields") {
    return { ok: true, status: 200, json: async () => ({ nodes: FIXTURE.nodes }) };
  }
  return { ok: false, status: 404, json: async () => ({}) };
}

let _handler = defaultHandler;
const _calls = [];

export const api = {
  apiURL(route) {
    return route;
  },
  async fetchApi(route, opts) {
    _calls.push({ route, opts });
    return _handler(route, opts);
  },
};

export function __setFetchApiHandler(handler) {
  _handler = handler;
}

export function __getFetchApiCalls() {
  return _calls;
}

export function __resetApi() {
  _handler = defaultHandler;
  _calls.length = 0;
}
