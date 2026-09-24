import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

/*
 * SceneWeaver frontend.
 *
 * Four things the Python side cannot do, and one rule that governs all of them.
 *
 *   (a) Searchable dropdowns. A field's pool runs to hundreds of values; a
 *       scrolling context menu is not a way to find one.
 *   (b) Kind-scoped relabelling. `emitter_count` is "Engine count" on a vessel
 *       and "Eye count" on a creature. A widget's label is fixed when ComfyUI
 *       registers the node and the kind is not, so the schema ships the generic
 *       label and this rewrites it.
 *   (c) An honest `set_all_fields`. Python cannot write to another widget, so a
 *       backend-only implementation would leave every dropdown still reading
 *       "Random" while the node quietly behaved otherwise.
 *   (d) A two-line readout on the node face, of the scene that was actually
 *       generated -- sent by the node in its `ui` payload, because only the
 *       backend knows what "Random" resolved to. A third line carries the
 *       first warning's own words when there is one; the strip grows to fit.
 *
 * THE RULE: change widget LABELS and VALUES, never widget ORDER, and never add
 * or remove a widget. `widgets_values` is a positional array that ComfyUI
 * restores 1:1 against `node.widgets` -- including widgets a frontend inserted,
 * and regardless of `serialize: false`, which is honoured when writing and not
 * when reading. Identity Forge learned that the expensive way: 60 of 85 widgets
 * restored one or more slots out, and every affected node had to be recreated.
 * Nothing here appends a widget; the readout is drawn on the canvas instead.
 *
 * Everything degrades. Every entry point is wrapped, and if the data route is
 * unreachable the node keeps working with generic labels and unnarrowed lists.
 */

const ROUTE = "/sceneweaver/fields";
const LOG_PREFIX = "[SceneWeaver]";

// ---------------------------------------------------------------------------
// The data route
// ---------------------------------------------------------------------------

let _payload = null;

/**
 * Fetch the per-node field data once per session.
 *
 * The promise itself is cached, not just its result: `beforeRegisterNodeDef`
 * runs once per node class and both would otherwise race a request each.
 */
export function loadFieldData() {
  if (_payload === null) {
    _payload = (async () => {
      try {
        const response = await api.fetchApi(ROUTE);
        if (!response || !response.ok) throw new Error(`HTTP ${response?.status}`);
        return await response.json();
      } catch (err) {
        console.error(`${LOG_PREFIX} field data unavailable; falling back to generic labels:`, err);
        return null;
      }
    })();
  }
  return _payload;
}

/** Test seam: drop the cached payload so the next load refetches. */
export function __resetFieldData() {
  _payload = null;
}

// ---------------------------------------------------------------------------
// Widget helpers
// ---------------------------------------------------------------------------

/**
 * Set a widget's value through whichever setter this frontend version has.
 *
 * `setValue` (current) fires the callback and marks the canvas dirty; older
 * builds only have the bare property plus a `callback`. Doing both would fire
 * the callback twice, so it is one or the other.
 */
export function setWidgetValue(node, widget, value) {
  if (!widget) return;
  if (typeof widget.setValue === "function") {
    widget.setValue(value, { node, canvas: app.canvas });
    return;
  }
  widget.value = value;
  if (typeof widget.callback === "function") {
    try {
      widget.callback(value, app.canvas, node);
    } catch (err) {
      console.error(`${LOG_PREFIX} widget callback failed for ${widget.name}:`, err);
    }
  }
}

/** A widget holding a literal is a lock. "Random" and "None" are not. */
export function isLocked(widget, spec) {
  return widget && widget.value !== spec.random && widget.value !== spec.none;
}

function widgetMap(node) {
  const map = new Map();
  for (const widget of node.widgets || []) map.set(widget.name, widget);
  return map;
}

/** A field descriptor by its base name, or null. */
function fieldFor(spec, base) {
  for (const field of Object.values(spec.fields ?? {})) {
    if (field.base === base) return field;
  }
  return null;
}

/**
 * The scope-keyed pool for a field, walking the chain to the pack default.
 *
 * ``scopeValues`` maps each control field to its current value (null when the
 * control is Random or None). The walk is raw value first, then that value's
 * declared group, then the next control -- the same order the engine uses, so a
 * value the engine could never draw is never offered here.
 */
export function poolFor(spec, base, scopeValues) {
  const pools = spec.pools?.[base];
  if (!pools) return null;
  const field = fieldFor(spec, base);
  for (const control of field?.scope ?? []) {
    const value = scopeValues?.[control];
    if (value == null) continue;
    if (Object.prototype.hasOwnProperty.call(pools, value)) return pools[value];
    const groups = spec.pool_groups?.[control] ?? {};
    for (const [groupName, members] of Object.entries(groups)) {
      if ((members ?? []).includes(value) && Object.prototype.hasOwnProperty.call(pools, groupName)) {
        return pools[groupName];
      }
    }
  }
  return pools[spec.default_key] ?? null;
}

/**
 * The control values that scope one widget, read from the widgets themselves.
 */
function scopeValuesFor(spec, node, key) {
  const widgets = widgetMap(node);
  const scopeValues = {};
  for (const [controlKey, dependents] of Object.entries(spec.scope_widgets ?? {})) {
    if (!(dependents ?? []).includes(key)) continue;
    const controlBase = spec.fields?.[controlKey]?.base ?? controlKey;
    const controlWidget = widgets.get(controlKey);
    scopeValues[controlBase] =
      controlWidget && isLocked(controlWidget, spec) ? controlWidget.value : null;
  }
  return scopeValues;
}

/**
 * What a widget should offer given the current values of its scope chain.
 *
 * The registered option list is the union across every scope, because ComfyUI
 * fixes a combo's options when the node is registered. This narrows what is
 * *shown* -- and always keeps the current value, so a value locked under one
 * scope stays selectable and visible after the scope changes rather than being
 * silently swapped for something else.
 */
export function scopedChoices(spec, key, scopeValues) {
  const field = spec.fields?.[key];
  if (!field) return null;
  const registered = spec.choices?.[field.base] ?? [];
  const scope = field.scope ?? [];
  if (!scope.length) return registered.slice();
  const anyLocked = scope.some((control) => scopeValues?.[control] != null);
  if (!anyLocked) return registered.slice();
  const pool = poolFor(spec, field.base, scopeValues);
  if (pool === null) return registered.slice();
  const choices = [];
  if (registered.includes(spec.random)) choices.push(spec.random);
  choices.push(...pool);
  if (registered.includes(spec.none)) choices.push(spec.none);
  return choices;
}

// ---------------------------------------------------------------------------
// (b) Kind-scoped relabelling
// ---------------------------------------------------------------------------

/**
 * Rewrite the labels (and narrow the option lists) of everything one `kind`
 * widget scopes.
 *
 * `widget.label` is what the frontend displays (`label ?? localized_name ??
 * name`); `widget.name` is the serialization key and is never touched. The
 * widget array is not reordered and nothing is inserted or removed, so a
 * workflow saved under any kind reloads under any other unchanged.
 */
export function applyKindScope(node, spec, kindKey) {
  const widgets = widgetMap(node);
  const kindWidget = widgets.get(kindKey);
  if (!kindWidget) return;
  const kind = isLocked(kindWidget, spec) ? kindWidget.value : null;

  for (const key of spec.kind_widgets?.[kindKey] ?? []) {
    const widget = widgets.get(key);
    const field = spec.fields?.[key];
    if (!widget || !field) continue;

    const perKind = spec.labels?.[field.base];
    const label = (kind && perKind?.[kind]) || field.label;
    // Label swapped, qualifier kept: "Engine count 2" stays on slot 2.
    widget.label = `${label}${field.qualifier ?? ""}`;
  }
  node.setDirtyCanvas?.(true, true);
}

/**
 * Narrow the option lists of everything one scope control narrows.
 *
 * ``applyKindScope`` swaps labels; this swaps options, and for every control
 * in the chain -- kind, subkind, the count nouns, environment -- not just kind.
 * The current value is always kept, so a locked value stays visible when the
 * chain moves away from it.
 */
export function applyScopeNarrowing(node, spec, controlKey) {
  const widgets = widgetMap(node);
  for (const key of spec.scope_widgets?.[controlKey] ?? []) {
    const widget = widgets.get(key);
    const field = spec.fields?.[key];
    if (!widget || !field) continue;

    const scopeValues = scopeValuesFor(spec, node, key);
    const choices = scopedChoices(spec, key, scopeValues);
    if (choices && widget.options) {
      if (!choices.includes(widget.value)) choices.push(widget.value);
      widget.options.values = choices;
    }
  }
}
// Options are read lazily when a dropdown opens, so narrowing needs no redraw;
// the label swap in applyKindScope is what dirties the canvas.

function applyEveryScopeNarrowing(node, spec) {
  for (const controlKey of Object.keys(spec.scope_widgets ?? {})) {
    applyScopeNarrowing(node, spec, controlKey);
  }
}

function applyEveryKindScope(node, spec) {
  for (const kindKey of Object.keys(spec.kind_widgets ?? {})) {
    applyKindScope(node, spec, kindKey);
  }
}

// ---------------------------------------------------------------------------
// (c) An honest set_all_fields
// ---------------------------------------------------------------------------

/**
 * Apply the bulk edit to the widgets themselves, then snap the control back.
 *
 * Mirrors `engine.scene._apply_set_all` exactly, in both directions: "Clear
 * all" rewrites every widget that says "Random", "Randomize all" every widget
 * that says "None", and neither touches a widget holding a literal value --
 * that is a lock, and a bulk control must not silently undo a deliberate
 * choice. Snapping back to "Off" is what keeps it an action rather than a mode:
 * left set, it would re-run on every load and overwrite the values it had just
 * written.
 */
export function applySetAll(node, spec, mode) {
  const setAll = spec.set_all;
  if (!setAll || mode === setAll.off) return 0;

  // Direction comes from the payload's explicit keys, never from an option
  // index: the option order is display order, and reordering it would silently
  // reverse the bulk edit.
  let from;
  let to;
  if (mode === setAll.clear) {
    [from, to] = [spec.random, spec.none];
  } else if (mode === setAll.randomize) {
    [from, to] = [spec.none, spec.random];
  } else {
    return 0;
  }

  let changed = 0;
  for (const widget of node.widgets || []) {
    if (!spec.fields?.[widget.name]) continue; // controls are not fields
    if (widget.value !== from) continue; // a lock, or already the target
    setWidgetValue(node, widget, to);
    changed += 1;
  }

  const control = widgetMap(node).get(setAll.key);
  if (control) {
    // Assigned directly rather than through setWidgetValue: routing it through
    // the callback would re-enter this function on the value we just wrote.
    control.value = setAll.off;
  }
  applyEveryKindScope(node, spec);
  node.setDirtyCanvas?.(true, true);
  return changed;
}

// ---------------------------------------------------------------------------
// (d) The compact face -- entities 2-4 and relations hidden until used
// ---------------------------------------------------------------------------

/**
 * Whether a Scene Entity socket is wired. The socket carries no widget, so it
 * is the only sign a slot is occupied when its own kind widget is still None.
 */
function isSlotWired(node, slot) {
  const name = `entity_${slot}_in`;
  const input = (node.inputs || []).find((i) => i && i.name === name);
  return Boolean(input && input.link != null);
}

/**
 * The entity slots this scene occupies, by the same three rules the engine
 * uses: the first `entity_count`, plus any wired socket, plus any slot whose
 * kind widget holds a literal.
 *
 * Mirroring the engine matters more here than anywhere else in this file. The
 * node face is the only account of the scene the user gets before they run it,
 * and a face that reveals four slots for a scene the engine will build with two
 * is worse than no face at all.
 */
export function activeEntitySlots(node, spec) {
  const widgets = widgetMap(node);
  const countWidget = spec.entity_count_key ? widgets.get(spec.entity_count_key) : null;
  const wanted = Number.parseInt(countWidget?.value, 10);
  const active = new Set();
  for (const [key, field] of Object.entries(spec.fields ?? {})) {
    if (field.base !== spec.kind_field) continue;
    const w = widgets.get(key);
    const locked = w && w.value !== spec.none && w.value !== spec.random;
    if (
      (Number.isFinite(wanted) && field.slot <= wanted) ||
      isSlotWired(node, field.slot) ||
      locked
    ) {
      active.add(field.slot);
    }
  }
  // No count widget at all (an older payload, or a pack without one): fall back
  // to the previous rule rather than hiding every slot.
  if (!Number.isFinite(wanted)) {
    for (const [key, field] of Object.entries(spec.fields ?? {})) {
      if (field.base !== spec.kind_field) continue;
      const w = widgets.get(key);
      if (w && w.value !== spec.none) active.add(field.slot);
    }
  }
  return active;
}

/**
 * Hide entity slots 2-4 and the relation/position widgets until they are used.
 *
 * Hiding only flips `widget.hidden`; nothing is removed from the widget array,
 * so `widgets_values` keeps its positional order across a save/reload.
 */
export function applyCompactFace(node, spec) {
  const widgets = widgetMap(node);
  const active = activeEntitySlots(node, spec);
  let changed = false;
  for (const [key, field] of Object.entries(spec.fields ?? {})) {
    const w = widgets.get(key);
    if (!w) continue;
    let hidden;
    if (typeof field.slot === "number") {
      // A wired slot is described by the node plugged into it. Its own
      // descriptive widgets are overridden -- the engine says so and reports it
      // in _meta -- so showing them invites the user to set a value that will
      // be thrown away. What the scene still owns for that slot is the
      // situation, and that stays visible.
      if (isSlotWired(node, field.slot) && field.base !== spec.situation_field) {
        hidden = true;
      } else if (field.slot >= 2) {
        hidden = !active.has(field.slot);
      } else {
        hidden = false;
      }
    } else if (field.endpoints != null) {
      hidden = active.size < 2;
    } else {
      continue;
    }
    if (w.hidden !== hidden) {
      w.hidden = hidden;
      changed = true;
    }
  }
  if (changed) {
    node.setSize?.(node.computeSize?.());
    node.setDirtyCanvas?.(true, true);
  }
  return changed;
}

// ---------------------------------------------------------------------------
// (d2) Why there are no canvas group headers
// ---------------------------------------------------------------------------
//
// There were, briefly, and they could not work. The plan was to paint "Scene",
// "Entity 1", "Relations" just above the widget that starts each section --
// non-interactive text, so nothing was added to `node.widgets` and
// `widgets_values` stayed untouched. That constraint was met and the feature
// still failed, for a reason only a browser shows: the current frontend lays
// widgets out contiguously and its widget pill spans nearly the full node
// width, so text drawn at the left margin lands *underneath* the pill. On a
// live node each header rendered as a single clipped letter -- an "S" and an
// "E" beside the wrong rows.
//
// The section structure is carried by the widget labels instead, which already
// do it: "Kind 1", "Type 1" ... "Situation 1", then the relation widgets. If a
// future frontend gives a row a top margin to draw into, this is the place to
// put them back.

// ---------------------------------------------------------------------------
// (a) Searchable dropdowns
// ---------------------------------------------------------------------------

const OVERLAY_CLASS = "sceneweaver-search";
const STYLE_ID = "sceneweaver-styles";

/** Remove any open search overlay. Safe to call when none is open. */
export function closeSearch() {
  for (const node of Array.from(document.querySelectorAll(`.${OVERLAY_CLASS}`))) {
    node.remove();
  }
}

/**
 * Open a filterable list of a field's values.
 *
 * A plain DOM overlay rather than LiteGraph's context menu: the menu has no
 * text input, and these pools are long enough that scrolling one is the problem
 * this is here to solve.
 */
export function openFieldSearch(node, widget, spec, anchor) {
  closeSearch();
  const field = spec.fields?.[widget.name];
  if (!field) return null;

  const scopeValues = scopeValuesFor(spec, node, widget.name);
  const values = scopedChoices(spec, widget.name, scopeValues) ?? [];

  const overlay = document.createElement("div");
  overlay.className = OVERLAY_CLASS;
  // Fixed to the viewport, above the canvas, at the click that opened it.
  overlay.style.position = "fixed";
  overlay.style.zIndex = "10000";
  if (anchor && typeof anchor.x === "number" && typeof anchor.y === "number") {
    overlay.style.left = `${anchor.x}px`;
    overlay.style.top = `${anchor.y}px`;
  }
  const input = document.createElement("input");
  input.type = "text";
  input.className = `${OVERLAY_CLASS}-input`;
  input.placeholder = widget.label || widget.name;
  const list = document.createElement("ul");
  list.className = `${OVERLAY_CLASS}-list`;
  overlay.append(input, list);

  const render = () => {
    const needle = input.value.trim().toLowerCase();
    list.replaceChildren();
    for (const value of values) {
      if (needle && !String(value).toLowerCase().includes(needle)) continue;
      const item = document.createElement("li");
      item.textContent = String(value);
      item.dataset.value = String(value);
      if (value === widget.value) item.classList.add("is-current");
      item.addEventListener("click", () => {
        setWidgetValue(node, widget, value);
        closeSearch();
      });
      list.append(item);
    }
  };

  input.addEventListener("input", render);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSearch();
    if (event.key === "Enter") list.firstElementChild?.click();
  });

  render();
  document.body.append(overlay);
  input.focus();
  return overlay;
}


/**
 * Route a click on a combo widget into the search overlay.
 *
 * The frontend's own combo widget treats the leftmost and rightmost 40px as
 * previous/next steppers; those are preserved by delegating to the original
 * handler, so nothing that worked before this file loaded stops working.
 * `onClick` is the current hook and `mouse` the legacy one -- both are wrapped
 * because a pack that only handles one silently does nothing on the other.
 */
function installSearch(node, spec, widget) {
  if (widget.__sceneweaverSearch) return;
  widget.__sceneweaverSearch = true;

  const open = (event, hostNode) => {
    const x = (event?.canvasX ?? 0) - (hostNode?.pos?.[0] ?? 0);
    const width = widget.width || hostNode?.size?.[0] || 0;
    if (width && (x < 40 || x > width - 40)) return false; // stepper zones
    const anchor = {
      x: event?.clientX ?? event?.canvasX ?? 0,
      y: event?.clientY ?? event?.canvasY ?? 0,
    };
    openFieldSearch(hostNode, widget, spec, anchor);
    return true;
  };

  const originalClick = widget.onClick;
  widget.onClick = function (args) {
    try {
      if (open(args?.e, args?.node ?? node)) return;
    } catch (err) {
      console.error(`${LOG_PREFIX} search overlay failed:`, err);
    }
    return originalClick?.call(this, args);
  };

  const originalMouse = widget.mouse;
  widget.mouse = function (event, pos, hostNode) {
    try {
      if (event?.type === "pointerdown" || event?.type === "mousedown") {
        if (open(event, hostNode ?? node)) return true;
      }
    } catch (err) {
      console.error(`${LOG_PREFIX} search overlay failed:`, err);
    }
    return originalMouse?.call(this, event, pos, hostNode) ?? false;
  };
}

// ---------------------------------------------------------------------------
// (d) The node-face readout
// ---------------------------------------------------------------------------

const READOUT_LINE_HEIGHT = 13;
// The most lines the face will draw. The strip is sized from the lines a run
// actually reported, so the common two-line case gains no dead space and a
// warning earns a third line.
const READOUT_LINES = 3;
const READOUT_PAD = 5;

/**
 * The height the footer needs, or 0 before a run has reported anything.
 *
 * Read by the `computeSize` wrapper as well as by the painter, so the strip the
 * node reserves and the strip it draws into are the same number.
 */
export function readoutHeight(node) {
  const lines = node?.__sceneweaverReadout;
  if (!lines || !lines.length) return 0;
  return READOUT_PAD * 2 + READOUT_LINE_HEIGHT * lines.length;
}

/** Store the lines a run reported, grow the node to fit them, and repaint. */
export function receiveReadout(node, message) {
  const lines = message?.text;
  if (!Array.isArray(lines) || !lines.length) return;
  const first = !node.__sceneweaverReadout;
  node.__sceneweaverReadout = lines.slice(0, READOUT_LINES).map(String);
  if (first) {
    // Only on the first run, and only ever grows: re-fitting on every run
    // would undo a height the user chose by dragging.
    const wanted = node.computeSize?.();
    if (wanted && node.size && node.size[1] < wanted[1]) node.setSize?.(wanted);
  }
  node.setDirtyCanvas?.(true, true);
}

/**
 * Draw the readout in a reserved strip at the bottom of the node body.
 *
 * It used to be painted *below* the node, on the canvas. That kept it clear of
 * the widgets, and it also meant a line of text floating over whatever happened
 * to be behind the node, moving with it, belonging to nothing -- which is
 * exactly how it read. Reserving the strip in `computeSize` costs a few pixels
 * and makes it part of the node.
 *
 * Nothing is added to `node.widgets`, so this still cannot disturb the
 * positional `widgets_values` array.
 */
export function drawReadout(node, ctx) {
  const lines = node.__sceneweaverReadout;
  if (!lines || !lines.length || node.flags?.collapsed) return;
  const top = node.size[1] - readoutHeight(node);
  ctx.save();
  ctx.strokeStyle = "#3a4551";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(8, top + 0.5);
  ctx.lineTo(Math.max(8, node.size[0] - 8), top + 0.5);
  ctx.stroke();
  ctx.font = "11px sans-serif";
  ctx.textAlign = "left";
  ctx.fillStyle = "#9bb0c0";
  const width = Math.max(0, node.size[0] - 16);
  lines.forEach((line, index) => {
    ctx.fillText(
      fitReadoutLine(ctx, line, width),
      8,
      top + READOUT_PAD + READOUT_LINE_HEIGHT * (index + 1) - 3,
    );
  });
  ctx.restore();
}

/**
 * Shorten `text` with a trailing "..." until it fits `maxWidth` on `ctx`.
 *
 * A warning line is routinely wider than the node, and canvas text is not
 * clipped by the node body: it ran straight over the node's right edge. The
 * line is cut to the width the user gave the node rather than wrapped, because
 * the footer height is reserved in `computeSize`, where no context exists to
 * measure with; widening the node shows the rest.
 */
export function fitReadoutLine(ctx, text, maxWidth) {
  if (typeof ctx.measureText !== "function") return text;
  if (ctx.measureText(text).width <= maxWidth) return text;
  const ellipsis = "...";
  let low = 0;
  let high = text.length;
  while (low < high) {
    const mid = Math.ceil((low + high) / 2);
    const candidate = text.slice(0, mid).trimEnd() + ellipsis;
    if (ctx.measureText(candidate).width <= maxWidth) low = mid;
    else high = mid - 1;
  }
  return low > 0 ? text.slice(0, low).trimEnd() + ellipsis : ellipsis;
}

// ---------------------------------------------------------------------------
// Overlay dismissal and styles
// ---------------------------------------------------------------------------

/** Close the search overlay when the user clicks anywhere outside it. */
function installDismissal() {
  if (installDismissal.__installed) return;
  installDismissal.__installed = true;
  // Capture phase on window: LiteGraph's canvas swallows pointerdown in the
  // bubble phase, so a document-level listener never sees a blank-canvas
  // click. Capture fires before any canvas handler.
  window.addEventListener("pointerdown", (event) => {
    const overlay = document.querySelector(`.${OVERLAY_CLASS}`);
    if (overlay && !overlay.contains(event.target)) closeSearch();
  }, { capture: true });
}

/**
 * Inject the stylesheet once.
 *
 * The URL is resolved relative to this module so it works whether ComfyUI
 * serves the pack under /extensions/ or a custom path. Idempotent and guarded
 * so a missing ``document.head`` (some test harnesses) degrades silently.
 */
function loadStyles() {
  if (typeof document === "undefined" || !document.head) return;
  if (document.getElementById(STYLE_ID)) return;
  const link = document.createElement("link");
  link.id = STYLE_ID;
  link.rel = "stylesheet";
  link.href = new URL("./sceneweaver.css", import.meta.url).href;
  document.head.append(link);
}
// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

/**
 * Wire one node up. Idempotent.
 *
 * The re-entry guard is not decoration: `onNodeCreated` genuinely fires twice
 * for the same node on some paths, and without it every callback below would be
 * wrapped twice and each user change would apply its handler two deep. Identity
 * Forge shipped four setups without one.
 */
export function setupNode(node, spec) {
  if (node.__sceneweaver) return false;
  node.__sceneweaver = spec;

  const widgets = widgetMap(node);

  for (const widget of node.widgets || []) {
    if (spec.fields?.[widget.name]) installSearch(node, spec, widget);
  }

  for (const kindKey of Object.keys(spec.kind_widgets ?? {})) {
    const kindWidget = widgets.get(kindKey);
    if (!kindWidget) continue;
    const previous = kindWidget.callback;
    kindWidget.callback = function (value) {
      const result = previous ? previous.apply(this, arguments) : undefined;
      try {
        applyKindScope(node, spec, kindKey);
        applyScopeNarrowing(node, spec, kindKey);
        applyCompactFace(node, spec);
      } catch (err) {
        console.error(`${LOG_PREFIX} relabelling failed for ${kindKey}:`, err);
      }
      return result;
    };
  }

  for (const controlKey of Object.keys(spec.scope_widgets ?? {})) {
    if (spec.kind_widgets?.[controlKey]) continue; // kind already handled above
    const controlWidget = widgets.get(controlKey);
    if (!controlWidget) continue;
    const previous = controlWidget.callback;
    controlWidget.callback = function (value) {
      const result = previous ? previous.apply(this, arguments) : undefined;
      try {
        applyScopeNarrowing(node, spec, controlKey);
      } catch (err) {
        console.error(`${LOG_PREFIX} narrowing failed for ${controlKey}:`, err);
      }
      return result;
    };
  }

  const countWidget = spec.entity_count_key && widgets.get(spec.entity_count_key);
  if (countWidget) {
    const previous = countWidget.callback;
    countWidget.callback = function (value) {
      const result = previous ? previous.apply(this, arguments) : undefined;
      try {
        applyCompactFace(node, spec);
      } catch (err) {
        console.error(`${LOG_PREFIX} entity count failed:`, err);
      }
      return result;
    };
  }

  const setAll = spec.set_all && widgets.get(spec.set_all.key);
  if (setAll) {
    const previous = setAll.callback;
    setAll.callback = function (value) {
      const result = previous ? previous.apply(this, arguments) : undefined;
      try {
        applySetAll(node, spec, value);
      } catch (err) {
        console.error(`${LOG_PREFIX} set_all_fields failed:`, err);
      }
      return result;
    };
    // A workflow saved mid-action would otherwise reapply it on every load.
    if (setAll.value !== spec.set_all.off) setAll.value = spec.set_all.off;
  }

  applyEveryKindScope(node, spec);
  applyEveryScopeNarrowing(node, spec);
  applyCompactFace(node, spec);
  return true;
}

app.registerExtension({
  name: "sceneweaver.ui",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    const payload = await loadFieldData();
    const spec = payload?.nodes?.[nodeData?.name];
    if (!spec) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
      try {
        setupNode(this, spec);
      } catch (err) {
        console.error(`${LOG_PREFIX} frontend setup failed:`, err);
      }
      return result;
    };

    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      const result = onExecuted ? onExecuted.apply(this, arguments) : undefined;
      try {
        receiveReadout(this, message);
      } catch (err) {
        console.error(`${LOG_PREFIX} readout failed:`, err);
      }
      return result;
    };

    // Reserve the footer strip the readout is drawn into. Wrapping rather than
    // replacing, so whatever the frontend (or another extension) computes stays
    // the base and this only ever adds to it.
    const computeSize = nodeType.prototype.computeSize;
    nodeType.prototype.computeSize = function () {
      const size = computeSize ? computeSize.apply(this, arguments) : [200, 100];
      try {
        size[1] += readoutHeight(this);
      } catch (err) {
        console.error(`${LOG_PREFIX} readout sizing failed:`, err);
      }
      return size;
    };

    const onDrawForeground = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function (ctx) {
      const result = onDrawForeground ? onDrawForeground.apply(this, arguments) : undefined;
      try {
        drawReadout(this, ctx);
      } catch (err) {
        console.error(`${LOG_PREFIX} readout draw failed:`, err);
      }
      return result;
    };

    const onConnectionsChange = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function (type, index, connected, link_info) {
      const result = onConnectionsChange ? onConnectionsChange.apply(this, arguments) : undefined;
      try {
        applyCompactFace(this, spec);
      } catch (err) {
        console.error(`${LOG_PREFIX} compact face failed:`, err);
      }
      return result;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const result = onConfigure ? onConfigure.apply(this, arguments) : undefined;
      try {
        applyCompactFace(this, spec);
      } catch (err) {
        console.error(`${LOG_PREFIX} compact face failed:`, err);
      }
      return result;
    };
  },
});

installDismissal();
loadStyles();
