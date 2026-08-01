// The deck: one editable card per slide, keyed by slide id so a snapshot
// updates cards in place instead of rebuilding — a slider mid-drag or a
// half-typed remake box must never be yanked out from under the hand.

import state, { subscribe, slideById } from './state.js';
import { queueOps, remakeSlide, rerender, speak } from './api.js';
import { parameterRows } from './controls.js';
import { toast } from './log.js';
import { el, $, inlineEdit } from './util.js';

const cards = new Map();   // slide id -> {node, refs, update}
let host = null;
let hint = null;

export function initDeck() {
  host = $('#deck');
  hint = $('#deck-hint');
  for (const key of ['slides', 'errors', 'schemas']) subscribe(key, render);
  subscribe('turnRunning', (running) => {
    for (const card of cards.values()) card.refs.remake.disabled = running;
  });
  render();
}

function render() {
  const slides = state.slides;
  const seen = new Set();
  for (const slide of slides) {
    seen.add(slide.id);
    let card = cards.get(slide.id);
    if (!card) {
      card = makeCard(slide.id);
      cards.set(slide.id, card);
    }
    card.update(slide);
  }
  for (const [id, card] of cards) {
    if (!seen.has(id)) {
      card.node.remove();
      cards.delete(id);
    }
  }
  // Order reconcile without ever emptying the container.
  let cursor = null;
  for (const slide of slides) {
    const node = cards.get(slide.id).node;
    const wanted = cursor ? cursor.nextElementSibling : host.firstElementChild;
    if (node !== wanted) host.insertBefore(node, wanted);
    cursor = node;
  }
  hint.hidden = slides.length > 0;
}

function pillButton(text, onclick) {
  return el('button', { class: 'pill', onclick }, text);
}

function duplicate(slide) {
  // overrides and hand-written code cannot ride an `add` yet, so a duplicate
  // carries everything else and starts from the layout engine's placement.
  queueOps([{
    kind: 'add', after: slide.id, title: slide.title,
    component: slide.component,
    parameters: JSON.parse(JSON.stringify(slide.parameters || {})),
    caption: slide.caption, seconds: slide.seconds, bridge: slide.bridge,
  }]);
}

function makeCard(id) {
  const current = () => slideById(id) || { parameters: {}, overrides: {} };
  const send = (op) => queueOps([{ slide_id: id, ...op }]);
  const refs = {};

  const editTitle = () => inlineEdit(refs.title, current().title || '',
    (value) => send({ kind: 'edit', title: value }));
  const editCaption = () => inlineEdit(refs.caption, current().caption || '',
    (value) => send({ kind: 'edit', caption: value }));
  const editNarration = () => inlineEdit(refs.narration, current().narration || '',
    (value) => send({ kind: 'edit', narration: value }), { multiline: true });

  refs.title = el('h4', { title: 'double-click to rename', ondblclick: editTitle });
  refs.caption = el('div', { class: 'caption', title: 'double-click to edit', ondblclick: editCaption });
  refs.narration = el('div', {
    class: 'narration',
    title: 'double-click to edit — spoken over the slide, never shown on screen',
    ondblclick: editNarration,
  });
  refs.meta = el('div', { class: 'meta' });
  refs.seconds = el('input', {
    type: 'number', min: 0.6, max: 40, step: 0.5,
    onchange: () => {
      const value = parseFloat(refs.seconds.value);
      if (!Number.isNaN(value)) send({ kind: 'edit', seconds: value });
    },
  });
  refs.bridge = el('input', {
    type: 'text', class: 'wide', placeholder: 'bridge from the previous slide',
    onchange: () => send({ kind: 'edit', bridge: refs.bridge.value.trim() }),
  });
  refs.params = el('div');
  refs.nudges = el('div');
  refs.error = el('div', { class: 'slide-error', hidden: true });
  refs.remake = el('input', {
    class: 'remake', type: 'text',
    placeholder: 'remake this slide: what should change?',
    onkeydown: (e) => {
      const text = refs.remake.value.trim();
      if (e.key === 'Enter' && text && !state.turnRunning) {
        remakeSlide(id, text);
        refs.remake.value = '';
      }
    },
  });
  refs.lock = pillButton('lock', () => send({ kind: 'lock', locked: !current().locked }));
  // Loop changes no pixels — the presentation replays this slide's motion
  // until the next step — so it rides the light edit path like lock does.
  refs.loop = pillButton('loop', () => send({ kind: 'edit', loop: !current().loop }));
  refs.loop.title = 'replay this slide’s motion until the next step in the presentation';
  refs.speak = pillButton('speak', async () => {
    refs.speak.disabled = true;
    try {
      const out = await speak(id);
      if (out && out.audio) {
        const player = $('#speaker');
        player.src = out.audio;
        player.play();
      }
    } catch (error) {
      toast(String(error.message || error));
    } finally {
      refs.speak.disabled = false;
    }
  });
  refs.speak.hidden = true;
  refs.rerender = pillButton('re-render', () => rerender(id));
  refs.rerender.hidden = true;

  const node = el('div', { class: 'slide-card' },
    el('div', { class: 'cardhead' },
      refs.title,
      el('button', { class: 'ghostbtn', title: 'rename', onclick: editTitle }, '✎')),
    refs.meta,
    refs.caption,
    el('div', { class: 'row' },
      el('label', {}, 'narration'), refs.narration),
    el('div', { class: 'row' },
      el('label', {}, 'seconds'), refs.seconds,
      el('label', {}, 'bridge'), refs.bridge),
    refs.params,
    refs.nudges,
    refs.error,
    el('div', { class: 'row' }, refs.remake),
    el('div', { class: 'row pills' },
      refs.lock,
      refs.loop,
      refs.speak,
      pillButton('duplicate', () => duplicate(current())),
      pillButton('delete', () => { if (confirm(`Delete ${id}?`)) send({ kind: 'delete' }); }),
      refs.rerender));

  let paramsKey = null;
  let nudgeKey = null;

  function update(slide) {
    node.classList.toggle('locked', !!slide.locked);
    node.classList.toggle('pending', !!slide.pending);
    if (!refs.title.hidden) refs.title.textContent = slide.title || '(untitled)';
    if (!refs.caption.hidden) refs.caption.textContent = slide.caption || '(no caption)';
    if (!refs.narration.hidden) refs.narration.textContent = slide.narration || '(no narration)';
    refs.speak.hidden = !slide.narration;
    refs.meta.textContent =
      `${slide.id} · ${slide.component || (slide.code ? 'hand-drawn' : 'text only')}`
      + ` · ${slide.seconds}s${slide.locked ? ' · locked' : ''}`
      + `${slide.origin === 'human' ? ' · yours' : ''}`;
    if (document.activeElement !== refs.seconds) refs.seconds.value = slide.seconds;
    if (document.activeElement !== refs.bridge) refs.bridge.value = slide.bridge || '';
    refs.lock.textContent = slide.locked ? 'unlock' : 'lock';
    refs.loop.classList.toggle('on', !!slide.loop);
    refs.remake.disabled = state.turnRunning;

    const nextParams = JSON.stringify([slide.component, slide.parameters]);
    if (nextParams !== paramsKey && !refs.params.contains(document.activeElement)) {
      const schema = state.schemas[slide.component] || {};
      refs.params.replaceChildren(...parameterRows(slide, schema,
        (name, value) => send({ kind: 'set_parameter', name, value })));
      paramsKey = nextParams;
    }
    const nextNudge = JSON.stringify(slide.overrides || {});
    if (nextNudge !== nudgeKey && !refs.nudges.contains(document.activeElement)) {
      refs.nudges.replaceChildren(...nudgeRows(slide, send));
      nudgeKey = nextNudge;
    }

    const problem = state.errors[slide.id];
    refs.error.hidden = !problem;
    refs.error.textContent = problem ? String(problem) : '';
    refs.rerender.hidden = !problem;
  }

  return { node, refs, update };
}

// Fine placement without the mouse: a dx/dy pair per movable thing. The
// checker can say a label overlaps; only a person can say it reads better
// slightly left — these sliders are how they say it.
function nudgeRows(slide, send) {
  return ['title', 'caption', 'built.group'].map((what) => {
    const shift = ((slide.overrides || {}).shift || {})[what] || { dx: 0, dy: 0 };
    const row = el('div', { class: 'row' },
      el('label', {}, `move ${what === 'built.group' ? 'figure' : what}`));
    for (const axis of ['dx', 'dy']) {
      const readout = el('span', { class: 'meta readout' }, `${axis} ${(+shift[axis] || 0).toFixed(2)}`);
      const input = el('input', {
        type: 'range', min: -3, max: 3, step: 0.05,
        value: +shift[axis] || 0, title: axis,
      });
      input.addEventListener('input', () => {
        readout.textContent = `${axis} ${(+input.value).toFixed(2)}`;
      });
      input.addEventListener('change', () => {
        const next = { dx: +shift.dx || 0, dy: +shift.dy || 0 };
        next[axis] = parseFloat(input.value);
        send({ kind: 'nudge', name: what, value: { shift: next } });
      });
      row.append(input, readout);
    }
    return row;
  });
}
