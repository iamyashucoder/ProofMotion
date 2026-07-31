// The page's voice for everything that is not a slide: the status bar, the
// log drawer of recent events, and toasts for things that went wrong.

import state, { subscribe, patch } from './state.js';
import { el, $, timeStamp } from './util.js';

const DOT_TITLES = { on: 'event stream: live', wait: 'event stream: reconnecting…', off: 'event stream: no project open' };

export function initLog() {
  const text = $('#statustext');
  const dot = $('#dot');
  const spinner = $('#spinner');
  const queued = $('#queued');
  const partial = $('#partial');
  const drawer = $('#logdrawer');
  const button = $('#logbtn');

  subscribe('status', (value) => { text.textContent = value; });
  subscribe('turnRunning', (running) => { spinner.hidden = !running; });
  subscribe('queue', (count) => {
    queued.hidden = !count;
    queued.textContent = `${count} queued`;
  });
  subscribe('partial', (value) => { partial.hidden = !value; });
  subscribe('connection', (value) => {
    dot.dataset.state = value;
    dot.title = DOT_TITLES[value] || value;
  });
  subscribe('log', () => { if (!drawer.hidden) renderDrawer(drawer); });

  button.addEventListener('click', () => {
    drawer.hidden = !drawer.hidden;
    button.classList.toggle('on', !drawer.hidden);
    if (!drawer.hidden) {
      renderDrawer(drawer);
      drawer.scrollTop = drawer.scrollHeight;
    }
  });

  text.textContent = state.status;
}

function renderDrawer(drawer) {
  const stick = drawer.scrollTop + drawer.clientHeight >= drawer.scrollHeight - 8;
  drawer.replaceChildren(...state.log.map((entry) =>
    el('div', { class: 'logline' },
      el('span', { class: 'logtime' }, entry.time),
      el('span', { class: `logkind k-${entry.kind}` }, entry.kind),
      el('span', { class: 'logtext' }, entry.text))));
  if (stick) drawer.scrollTop = drawer.scrollHeight;
}

export function addLog(kind, text) {
  const entry = { time: timeStamp(), kind: kind || 'event', text: text || '' };
  patch({ log: [...state.log, entry].slice(-500) });
}

// Toasts sit top-right, dismiss themselves after six seconds; a click pins
// one that deserves reading, and the × takes it away.
export function toast(message, kind = 'error') {
  const host = $('#toasts');
  if (!host) return;
  const item = el('div', { class: `toast ${kind}`, role: 'status' },
    el('span', { class: 'toast-text' }, message),
    el('button', {
      class: 'toast-x', title: 'dismiss',
      onclick: (e) => { e.stopPropagation(); item.remove(); },
    }, '×'));
  const timer = setTimeout(() => item.remove(), 6000);
  item.addEventListener('click', () => {
    clearTimeout(timer);
    item.classList.add('pinned');
  });
  host.appendChild(item);
}
