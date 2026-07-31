// The conversation: transcript bubbles, operation chips under the bot's
// answers, transient tick lines while a turn runs, and the composer. The
// transcript renders by extension — api.js only ever appends to the same
// array, so an unchanged prefix is never rebuilt.

import state, { subscribe } from './state.js';
import { createProject, sendMessage } from './api.js';
import { el, $ } from './util.js';

let box = null;
let shown = [];     // the entries currently in the DOM, by reference
let ticks = [];

export function initChat() {
  box = $('#transcript');
  const textarea = $('#composer-text');
  const send = $('#composer-send');

  subscribe('transcript', renderTranscript);
  subscribe('projectId', updateHint);
  subscribe('turnRunning', (running) => {
    send.disabled = running;
    if (!running) clearTicks();
  });

  const submit = () => {
    const text = textarea.value.trim();
    if (!text || state.turnRunning) return;
    textarea.value = '';
    if (state.projectId) sendMessage(text, state.attachments.slice());
    else createProject(text);
  };
  send.addEventListener('click', submit);
  textarea.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  });

  renderTranscript(state.transcript);
}

function bubble(entry) {
  const operations = entry.operations || [];
  return el('div', { class: `msg ${entry.who === 'you' ? 'you' : 'bot'}` },
    el('div', { class: 'bubble' }, entry.text || ''),
    operations.length
      ? el('div', { class: 'ops' }, operations.map((op) =>
          el('span', { class: 'opchip' },
            el('code', {}, op.kind || 'op'),
            op.reason ? ` ${op.reason}` : '')))
      : null);
}

function renderTranscript(list) {
  const stick = atBottom();
  const extension = list.length >= shown.length && shown.every((entry, i) => list[i] === entry);
  if (!extension) {
    for (const node of box.querySelectorAll('.msg:not(.tick)')) node.remove();
    shown = [];
  }
  for (const entry of list.slice(shown.length)) {
    // New messages land above any tick lines, which stay at the bottom.
    box.insertBefore(bubble(entry), box.querySelector('.msg.tick'));
  }
  shown = list.slice();
  updateHint();
  if (stick || !extension) box.scrollTop = box.scrollHeight;
}

export function tick(text) {
  if (!box) return;
  const stick = atBottom();
  const node = el('div', { class: 'msg tick' }, el('div', { class: 'bubble' }, text));
  box.appendChild(node);
  ticks.push(node);
  if (stick) box.scrollTop = box.scrollHeight;
}

function clearTicks() {
  for (const node of ticks) node.remove();
  ticks = [];
}

function updateHint() {
  const hint = $('#chat-hint');
  hint.hidden = state.transcript.length > 0;
  hint.textContent = state.projectId
    ? 'No messages yet.'
    : 'Describe what to explain — the first message creates the project and derives its first slides. That can take a few minutes.';
}

function atBottom() {
  return box.scrollTop + box.clientHeight >= box.scrollHeight - 48;
}
