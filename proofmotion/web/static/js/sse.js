// One EventSource per open project. The stream is filtered server-side, so
// everything that arrives is about the project on screen. Reconnects back
// off exponentially; the status-bar dot says which of the three worlds the
// connection is in.

import state, { patch } from './state.js';
import { addLog } from './log.js';
import { tick } from './chat.js';

let source = null;
let timer = null;
let current = null;
let backoff = 1000;

export function follow(projectId) {
  if (projectId === current && source) return;
  current = projectId;
  close();
  if (!current) {
    patch({ connection: 'off' });
    return;
  }
  backoff = 1000;
  open();
}

function close() {
  if (timer) { clearTimeout(timer); timer = null; }
  if (source) { source.close(); source = null; }
}

function open() {
  const wanted = current;
  source = new EventSource(`/api/projects/${wanted}/events`);
  source.onopen = () => {
    backoff = 1000;
    patch({ connection: 'on' });
  };
  source.onmessage = (e) => {
    let event;
    try { event = JSON.parse(e.data); } catch { return; }
    handle(event);
  };
  source.onerror = () => {
    patch({ connection: 'wait' });
    close();
    if (current !== wanted) return;
    timer = setTimeout(open, backoff);
    backoff = Math.min(backoff * 2, 15000);
  };
}

function handle(event) {
  const data = event.data || {};
  if (event.kind === 'headline') {
    patch({ status: data.text || '' });
    addLog(data.kind || 'info', data.text || '');
    // Progress reads as work only while a turn is actually running.
    if (state.turnRunning) tick(data.text || '');
  } else if (event.kind === 'tool') {
    patch({ status: `· ${data.name || ''}` });
    addLog('tool', data.name || '');
  } else {
    addLog(event.kind, summarise(data));
  }
}

function summarise(data) {
  return Object.entries(data)
    .filter(([key]) => key !== 'project')
    .map(([key, value]) => `${key}=${typeof value === 'object' ? JSON.stringify(value) : value}`)
    .join(' ') || '—';
}
