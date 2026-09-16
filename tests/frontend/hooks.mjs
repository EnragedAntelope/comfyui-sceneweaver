/**
 * Entry point for `node --import ./tests/frontend/hooks.mjs --test ...`.
 *
 * `js/sceneweaver.js` imports ComfyUI's own frontend modules by a fixed
 * relative path -- `import { app } from "../../scripts/app.js"` -- because that
 * is where they genuinely live once ComfyUI serves this pack's WEB_DIRECTORY.
 * Outside a running ComfyUI that path resolves to nothing, so Node's default
 * resolution would ENOENT on the very first import.
 *
 * `registerHooks` intercepts exactly those two specifiers, by suffix rather
 * than exact string so it survives a js/ file sitting at a different relative
 * depth, and redirects them to ./stubs/. Everything else passes through
 * untouched: this stubs ComfyUI's frontend API, not the module system, so the
 * real js/sceneweaver.js runs completely unmodified. Testing a copy of the
 * shipped file would prove nothing about the shipped file.
 *
 * `registerHooks` rather than the deprecated `module.register` because it runs
 * synchronously in this thread instead of a separate loader worker.
 */

import { registerHooks } from "node:module";

const STUB_DIR = new URL("./stubs/", import.meta.url);

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.endsWith("/scripts/app.js")) {
      return { url: new URL("app.js", STUB_DIR).href, shortCircuit: true };
    }
    if (specifier.endsWith("/scripts/api.js")) {
      return { url: new URL("api.js", STUB_DIR).href, shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
});
