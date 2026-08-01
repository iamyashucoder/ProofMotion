// All talk with the server. Turns (message, remake, create) run one at a
// time; quick operations run through a FIFO queue with one in flight,
// applied optimistically so the page answers the hand before the wire does.
// While a turn holds the project, operations wait and a chip says so.

import state, { patch, commitSnapshot, applyLocalOp } from './state.js';
import { toast } from './log.js';

async function request(path, options = {}) {
  const response = await fetch(path, options);
  let body = null;
  try { body = await response.json(); } catch { /* not JSON */ }
  if (!response.ok) {
    throw new Error((body && body.error) || `${response.status} ${response.statusText}`);
  }
  return body;
}

const post = (path, payload) => request(path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
});

const put = (path, payload) => request(path, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
});

// Posters are content-addressed: the digest rides the URL, so an unchanged
// slide keeps its cached image forever and a changed one gets a new URL.
export function posterUrl(slideId) {
  return `/api/projects/${state.projectId}/poster/${slideId}.png?d=${state.posters[slideId] || ''}`;
}

export function videoUrl() {
  return `/api/projects/${state.projectId}/video?r=${state.revision}`;
}

// ---- reading ----------------------------------------------------------

export async function fetchSchemas() {
  const body = await request('/api/schemas');
  patch({ schemas: (body && body.schemas) || {} });
}

export async function fetchStyles() {
  // Feature-detected: an older backend without /api/styles just leaves the
  // list empty and the Style button hidden.
  try {
    const body = await request('/api/styles');
    patch({ styles: (body && body.styles) || [], qualities: (body && body.qualities) || {} });
  } catch {
    patch({ styles: [], qualities: {} });
  }
}

export async function refreshProjects() {
  const body = await request('/api/projects');
  patch({ projects: (body && body.projects) || [] });
  return state.projects;
}

export async function loadProject(projectId) {
  patch({ status: `Opening ${projectId}…` });
  const snap = await request(`/api/projects/${projectId}`);
  // Pending composer attachments belong to the project they were uploaded
  // to; they do not follow the person to another one.
  patch({ projectId, attachments: [] });
  if (!absorb(snap)) throw new Error('the server answered with an unusable snapshot');
  patch({ transcript: Array.isArray(snap.transcript) ? snap.transcript : [] });
}

export async function resync() {
  if (!state.projectId) return;
  try {
    const snap = await request(`/api/projects/${state.projectId}`);
    if (absorb(snap) && Array.isArray(snap.transcript)) patch({ transcript: snap.transcript });
  } catch (error) {
    toast(`Could not reload the project: ${error.message || error}`);
  }
}

// ---- snapshots --------------------------------------------------------

// The single door for server answers. `commit: false` keeps the optimistic
// deck while more operations wait, taking only the cheap projection fields.
function absorb(snap, { commit = true } = {}) {
  if (!snap || !Array.isArray(snap.slides)) {
    toast('The server answered with an unusable snapshot; keeping the current deck.');
    return false;
  }
  if (snap.project_id && state.projectId && snap.project_id !== state.projectId) {
    // The answer belongs to a project no longer on screen.
    toast(`A change finished in project ${snap.project_id}.`, 'info');
    return false;
  }
  if (commit) {
    commitSnapshot(snap);
  } else {
    patch({
      posters: snap.posters || {}, errors: snap.errors || {},
      status: snap.status || state.status, partial: !!snap.partial,
      video: !!snap.video, revision: snap.revision ?? state.revision,
    });
  }
  for (const refusal of snap.refused || []) toast(refusal.problem || 'operation refused', 'warn');
  if (snap.error) toast(snap.error);
  return true;
}

function say(who, text, operations, attachments) {
  patch({ transcript: [...state.transcript, {
    who, text, operations: operations || [], attachments: attachments || [],
  }] });
}

// ---- turns: one at a time --------------------------------------------

async function turn(label, work) {
  patch({ turnRunning: true, status: label });
  try {
    const snap = await work();
    if (absorb(snap)) {
      if (snap.reply) say('bot', snap.reply, snap.operations);
      refreshProjects().catch(() => {});
    }
  } catch (error) {
    toast(String(error.message || error));
  } finally {
    patch({ turnRunning: false });
    pumpOps();
  }
}

export async function ensureProject() {
  // Attaching a picture is a first act too: it needs a project to land in
  // before the first message is ever sent.
  if (state.projectId) return state.projectId;
  const snap = await post('/api/projects/new', {});
  commitSnapshot(snap);
  patch({ projectId: snap.project_id, transcript: [] });
  localStorage.setItem('pm.lastProject', snap.project_id);
  history.pushState({}, '', `/p/${snap.project_id}`);
  refreshProjects().catch(() => {});
  return snap.project_id;
}

export function createProject(message) {
  if (state.turnRunning) return;
  say('you', message);
  turn('Starting a new project…', async () => {
    const snap = await post('/api/projects', { message });
    if (snap && snap.project_id) {
      patch({ projectId: snap.project_id });
      localStorage.setItem('pm.lastProject', snap.project_id);
      history.pushState({}, '', `/p/${snap.project_id}`);
    }
    return snap;
  });
}

export function sendMessage(message, attachments = []) {
  if (state.turnRunning || !state.projectId) return;
  const pid = state.projectId;
  // The pictures move into the message the moment it is sent — the bubble
  // shows them, the composer lets go of them. A failed send hands them back.
  say('you', message, null, attachments);
  patch({ attachments: state.attachments.filter((ref) => !attachments.includes(ref)) });
  turn('Thinking…', async () => {
    const body = { message };
    if (attachments.length) body.attachments = attachments;
    try {
      return await post(`/api/projects/${pid}/message`, body);
    } catch (error) {
      patch({ attachments: [...new Set([...attachments, ...state.attachments])] });
      throw error;
    }
  });
}

export function remakeSlide(slideId, instruction) {
  if (state.turnRunning || !state.projectId) return;
  const pid = state.projectId;
  say('you', `↻ ${slideId}: ${instruction}`);
  turn(`Remaking ${slideId}…`, () =>
    post(`/api/projects/${pid}/remake`, { slide_id: slideId, instruction }));
}

// Style and quality change every slide's pixels and re-render the whole
// deck, so both run through the same one-at-a-time gate as a turn.
export function setStyle(name) {
  if (state.turnRunning || !state.projectId) return;
  const pid = state.projectId;
  turn(`Restyling the deck as ${name}…`, () => put(`/api/projects/${pid}/style`, { style: name }));
}

export function setQuality(quality) {
  if (state.turnRunning || !state.projectId) return;
  const pid = state.projectId;
  turn(`Re-rendering the deck at quality ${quality}…`, () => put(`/api/projects/${pid}/quality`, { quality }));
}

// Narration audio for one slide. Not a snapshot — the answer is a URL to
// play. A 400 carries the remedy (missing TTS engine or voice) for a toast.
export function speak(slideId) {
  return post(`/api/projects/${state.projectId}/slides/${slideId}/speak`, {});
}

// Attachments go up as raw bytes, named by header — no multipart. The
// answer's kind decides what the composer does with it: image → chip,
// video → one chip per sampled frame, audio → transcript into the textarea.
export function uploadAttachment(blob, filename) {
  return request(`/api/projects/${state.projectId}/attachments`, {
    method: 'POST',
    headers: { 'X-Filename': filename },
    body: blob,
  });
}

export function attachmentUrl(ref) {
  return `/api/projects/${state.projectId}/attachments/${ref}`;
}

// ---- quick operations: FIFO, one in flight ---------------------------

const opQueue = [];   // {pid, operations}
let opInFlight = false;

function queuedCount() {
  return opQueue.reduce((n, batch) => n + batch.operations.length, 0);
}

export function queueOps(operations) {
  if (!state.projectId) {
    toast('No project yet — the first message creates one.', 'info');
    return;
  }
  operations.forEach(applyLocalOp);
  opQueue.push({ pid: state.projectId, operations });
  patch({ queue: queuedCount() });
  pumpOps();
}

export async function pumpOps() {
  if (opInFlight || state.turnRunning || !opQueue.length) return;
  opInFlight = true;
  const batch = opQueue.shift();
  patch({ queue: queuedCount() });
  try {
    const snap = await post(`/api/projects/${batch.pid}/operations`, { operations: batch.operations });
    absorb(snap, { commit: opQueue.length === 0 });
  } catch (error) {
    toast(String(error.message || error));
    await resync();
  } finally {
    opInFlight = false;
    pumpOps();
  }
}

export function rerender(slideId) {
  if (!state.projectId) return;
  patch({ status: `Re-rendering ${slideId}…` });
  post(`/api/projects/${state.projectId}/rerender`, { slide_id: slideId })
    .then((snap) => absorb(snap))
    .catch((error) => toast(String(error.message || error)));
}
