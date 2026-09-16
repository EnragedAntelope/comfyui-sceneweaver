/**
 * Minimal jsdom bootstrap shared by every frontend test.
 *
 * Honest limits: jsdom has no layout engine, so `clientWidth`/`clientHeight`
 * read 0 and anything depending on real layout (CSS, pixel positions, actual
 * canvas painting) cannot be exercised here. What this catches is wiring,
 * value and label logic, filtering and event handling -- the class of bug that
 * ships. It does not replace opening the page in a real browser before a
 * release, which is what Todo 25's live QA is for.
 */

import { JSDOM } from "jsdom";

let dom = null;

export function installDom() {
  dom = new JSDOM("<!doctype html><html><body></body></html>", {
    url: "http://localhost/",
  });
  const { window } = dom;
  globalThis.window = window;
  globalThis.document = window.document;
  globalThis.HTMLElement = window.HTMLElement;
  globalThis.Node = window.Node;
  globalThis.CustomEvent = window.CustomEvent;
  globalThis.KeyboardEvent = window.KeyboardEvent;
  // Node defines a read-only `navigator` getter (since Node 21), so a plain
  // assignment throws. Redefine the property instead.
  Object.defineProperty(globalThis, "navigator", {
    value: window.navigator,
    configurable: true,
    writable: true,
  });
  globalThis.requestAnimationFrame = (callback) => setTimeout(callback, 0);
  return dom;
}

export function resetDom() {
  if (document?.body) document.body.replaceChildren();
}

/**
 * A canvas 2D context that records instead of painting.
 *
 * The readout is drawn, not built from DOM nodes, so this is the only way to
 * assert what it says. Recording `fillText` calls is enough: what matters is
 * which lines reach the canvas and where, not how they look.
 */
export function recordingContext() {
  return {
    calls: [],
    font: "",
    fillStyle: "",
    strokeStyle: "",
    textAlign: "",
    lineWidth: 1,
    save() {
      this.calls.push(["save"]);
    },
    restore() {
      this.calls.push(["restore"]);
    },
    fillText(text, x, y) {
      this.calls.push(["fillText", text, x, y]);
    },
    // The painter draws a separator rule above the footer. A double that threw
    // on these would be caught by the extension's own try/catch and the test
    // would see *no* text at all -- a stub gap reported as a drawing bug.
    beginPath() {
      this.calls.push(["beginPath"]);
    },
    moveTo(x, y) {
      this.calls.push(["moveTo", x, y]);
    },
    lineTo(x, y) {
      this.calls.push(["lineTo", x, y]);
    },
    stroke() {
      this.calls.push(["stroke"]);
    },
    get texts() {
      return this.calls.filter((c) => c[0] === "fillText").map((c) => c[1]);
    },
  };
}
