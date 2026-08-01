// The shell's knobs: splitter widths, collapsed panels, which side the chat
// sits on, whether the deck is folded — and the theme, because every
// preference lives in the same localStorage blob and the next visit opens
// the room exactly as it was left.

import { $, clamp } from './util.js';

const KEY = 'pm.layout';
const DEFAULTS = {
  railW: 212, chatW: 380,
  railCollapsed: false, chatCollapsed: false,
  chatSide: 'left', deckFolded: false,
  theme: '',           // '' = follow the OS
};
let prefs = { ...DEFAULTS };

export function pref(name) {
  return prefs[name];
}

export function setPref(name, value) {
  prefs[name] = value;
  save();
  apply();
}

function save() {
  try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch { /* storage denied */ }
}

export function initLayout() {
  try {
    prefs = { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) || '{}') };
  } catch {
    prefs = { ...DEFAULTS };
  }

  splitter($('#split-rail'), 'railW', 140, 420, () => false);
  splitter($('#split-chat'), 'chatW', 260, 720, () => prefs.chatSide === 'right');

  $('#rail-collapse').addEventListener('click', () => setPref('railCollapsed', true));
  $('#rail-expand').addEventListener('click', () => setPref('railCollapsed', false));
  $('#chat-collapse').addEventListener('click', () => setPref('chatCollapsed', true));
  $('#chat-expand').addEventListener('click', () => setPref('chatCollapsed', false));
  $('#sidebtn').addEventListener('click', () =>
    setPref('chatSide', prefs.chatSide === 'left' ? 'right' : 'left'));
  $('#deckhead').addEventListener('click', () => setPref('deckFolded', !prefs.deckFolded));
  overflowMenu();
  measureScrollbar();

  apply();
}

// How wide this browser's scrollbars are. The transcript scrolls and the
// composer does not, so the scrollbar comes out of the message column alone —
// the composer has to pad by the same amount or the two can never line up.
// It cannot be hard-coded: it is ~15px on Windows, ~12px here, and 0 wherever
// scrollbars overlay the content.
function measureScrollbar() {
  const probe = document.createElement('div');
  probe.style.cssText =
    'position:absolute;top:-9999px;width:100px;height:100px;overflow:scroll';
  document.body.appendChild(probe);
  const width = probe.offsetWidth - probe.clientWidth;
  probe.remove();
  document.documentElement.style.setProperty('--sbw', `${width}px`);
}

// The "…" menu holding the settings you choose once. Every row in it is a
// one-shot preference, so a click closes the menu as well as acting — leaving
// it open would only be something else to dismiss.
function overflowMenu() {
  const button = $('#morebtn');
  const pop = $('#morepop');
  button.addEventListener('click', (e) => {
    e.stopPropagation();
    pop.hidden = !pop.hidden;
  });
  pop.addEventListener('click', () => { pop.hidden = true; });
  document.addEventListener('click', (e) => {
    if (!pop.hidden && !pop.contains(e.target) && e.target !== button) pop.hidden = true;
  });
}

function apply() {
  const app = $('#app');
  app.style.setProperty('--rail-w', `${prefs.railW}px`);
  app.style.setProperty('--chat-w', `${prefs.chatW}px`);
  app.dataset.chatSide = prefs.chatSide;
  app.classList.toggle('rail-collapsed', prefs.railCollapsed);
  app.classList.toggle('chat-collapsed', prefs.chatCollapsed);
  app.classList.toggle('deck-folded', prefs.deckFolded);
  $('#deck-chevron').textContent = prefs.deckFolded ? '▸' : '▾';
}

function splitter(node, key, lo, hi, inverted) {
  node.addEventListener('pointerdown', (e) => {
    node.setPointerCapture(e.pointerId);
    node.classList.add('dragging');
    const startX = e.clientX;
    const startW = prefs[key];
    const move = (ev) => {
      const delta = ev.clientX - startX;
      prefs[key] = clamp(Math.round(startW + (inverted() ? -delta : delta)), lo, hi);
      apply();
    };
    const up = () => {
      node.classList.remove('dragging');
      node.removeEventListener('pointermove', move);
      node.removeEventListener('pointerup', up);
      node.removeEventListener('pointercancel', up);
      save();
    };
    node.addEventListener('pointermove', move);
    node.addEventListener('pointerup', up);
    node.addEventListener('pointercancel', up);
  });
  node.addEventListener('dblclick', () => setPref(key, DEFAULTS[key]));
}
