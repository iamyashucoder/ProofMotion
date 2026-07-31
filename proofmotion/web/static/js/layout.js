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

  apply();
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
