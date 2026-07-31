// One flat store. patch() shallow-merges and notifies per changed key —
// values are all set before any subscriber runs, so a listener on `slides`
// can already read the new `projectId`. commitSnapshot() is the only door
// server state comes through, and it refuses to blank the deck on a
// malformed answer.

import { clamp } from './util.js';

const state = {
  projectId: null,          // null = an empty, unsaved draft
  revision: 0,
  slides: [],
  posters: {},              // slide id -> content digest
  errors: {},               // slide id -> render problem
  transcript: [],           // {who, text, operations}
  selected: null,           // slide id
  turnRunning: false,
  queue: 0,                 // operations waiting behind a turn or each other
  status: 'Ready.',
  partial: false,
  video: false,
  projects: [],
  schemas: {},
  styles: [],               // presets from /api/styles; empty = endpoint absent
  qualities: {},            // quality name -> {px_w, px_h, fps}
  style: '',                // this project's current preset
  quality: '',
  resolution: { px_w: 854, px_h: 480, frame_w: 14.222, frame_h: 8.0 },
  connection: 'off',        // off | wait | on
  log: [],                  // {time, kind, text}, capped at 500
};

export default state;

const subscribers = new Map();

export function subscribe(key, fn) {
  if (!subscribers.has(key)) subscribers.set(key, new Set());
  subscribers.get(key).add(fn);
  return () => subscribers.get(key).delete(fn);
}

export function patch(partial) {
  const changed = Object.keys(partial);
  for (const key of changed) state[key] = partial[key];
  for (const key of changed) {
    for (const fn of subscribers.get(key) || []) fn(state[key]);
  }
}

export function slideById(id) {
  return state.slides.find((s) => s.id === id) || null;
}

export function slideIndex(id) {
  return state.slides.findIndex((s) => s.id === id);
}

export function commitSnapshot(snap) {
  if (!snap || !Array.isArray(snap.slides)) return false;
  const previousIndex = state.selected != null ? slideIndex(state.selected) : -1;
  const next = {
    projectId: snap.project_id ?? state.projectId,
    revision: snap.revision ?? state.revision,
    slides: snap.slides,
    posters: snap.posters || {},
    errors: snap.errors || {},
    status: snap.status || state.status,
    partial: !!snap.partial,
    video: !!snap.video,
  };
  if (snap.resolution) next.resolution = snap.resolution;
  if (typeof snap.style === 'string') next.style = snap.style;
  if (typeof snap.quality === 'string') next.quality = snap.quality;
  // Keep the selection on the same slide, or the same seat if it is gone.
  const ids = snap.slides.map((s) => s.id);
  if (state.selected && ids.includes(state.selected)) next.selected = state.selected;
  else if (ids.length) next.selected = ids[clamp(Math.max(previousIndex, 0), 0, ids.length - 1)];
  else next.selected = null;
  patch(next);
  return true;
}

// Optimistic mirror of the server's apply(): just enough to keep the page
// honest while an operation is on the wire. The next snapshot is
// authoritative and replaces all of this.
export function applyLocalOp(op) {
  const slides = state.slides.slice();
  const extra = {};
  const i = slides.findIndex((s) => s.id === op.slide_id);
  const found = i >= 0 ? { ...slides[i] } : null;

  if (op.kind === 'delete') {
    if (!found) return;
    slides.splice(i, 1);
    if (state.selected === op.slide_id) {
      extra.selected = slides.length ? slides[Math.min(i, slides.length - 1)].id : null;
    }
  } else if (op.kind === 'reorder') {
    // Same semantics as the server: `before` wins, then `after`, empty = end.
    if (!found) return;
    slides.splice(i, 1);
    let at = slides.length;
    if (op.before) {
      const j = slides.findIndex((s) => s.id === op.before);
      if (j >= 0) at = j;
    } else if (op.after) {
      const j = slides.findIndex((s) => s.id === op.after);
      if (j >= 0) at = j + 1;
    }
    slides.splice(at, 0, found);
  } else if (op.kind === 'lock') {
    if (!found) return;
    found.locked = op.locked;
    slides[i] = found;
  } else if (op.kind === 'edit') {
    if (!found) return;
    for (const field of ['title', 'caption', 'seconds', 'bridge', 'narration']) {
      if (op[field] != null) found[field] = op[field];
    }
    slides[i] = found;
  } else if (op.kind === 'set_parameter') {
    if (!found) return;
    found.parameters = { ...found.parameters, [op.name]: op.value };
    slides[i] = found;
  } else if (op.kind === 'nudge') {
    if (!found) return;
    const overrides = { ...found.overrides };
    for (const axis of ['shift', 'scale']) {
      if (op.value && axis in op.value) {
        overrides[axis] = { ...(overrides[axis] || {}), [op.name]: op.value[axis] };
      }
    }
    found.overrides = overrides;
    slides[i] = found;
  } else if (op.kind === 'add') {
    // The real id is the document's to give; a placeholder holds the seat.
    const slide = {
      id: `pending-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      title: op.title || '', component: op.component ?? null,
      parameters: op.parameters || {}, caption: op.caption || '',
      seconds: op.seconds || 6, overrides: {}, bridge: op.bridge || '',
      code: '', origin: 'human', locked: false, pending: true,
    };
    const at = op.after ? slides.findIndex((s) => s.id === op.after) + 1 : slides.length;
    slides.splice(at < 1 ? slides.length : at, 0, slide);
  } else {
    return;
  }
  patch({ slides, ...extra });
}
