// Composer attachments: pick, drop, paste, or speak. Everything funnels
// through one upload path — the server names files by content, so the same
// picture twice is the same id and the chip row dedupes to match. Only
// image refs ride a message; audio comes back as words and goes straight
// into the textarea, a video comes back as sampled frames.

import state, { subscribe, patch } from './state.js';
import { uploadAttachment, attachmentUrl, ensureProject } from './api.js';
import { toast } from './log.js';
import { el, $ } from './util.js';

const MAX_ATTACHMENTS = 8;

let micSupported = false;
let recorder = null;
let recStream = null;
let recTimer = null;
let recStart = 0;

export function initAttach() {
  const attachBtn = $('#attachbtn');
  const micBtn = $('#micbtn');
  const fileInput = $('#fileinput');
  const composer = $('#composer');
  const textarea = $('#composer-text');

  subscribe('attachments', renderChips);
  subscribe('turnRunning', updateButtons);
  subscribe('projectId', updateButtons);

  attachBtn.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    uploadAll([...fileInput.files]);
    fileInput.value = '';
  });

  // Drag-drop and paste feed the same flow as the picker.
  composer.addEventListener('dragover', (e) => {
    if (![...e.dataTransfer.types].includes('Files')) return;
    e.preventDefault();
    composer.classList.add('drop');
  });
  composer.addEventListener('dragleave', () => composer.classList.remove('drop'));
  composer.addEventListener('drop', (e) => {
    e.preventDefault();
    composer.classList.remove('drop');
    uploadAll([...e.dataTransfer.files]);
  });
  textarea.addEventListener('paste', (e) => {
    const files = [...((e.clipboardData && e.clipboardData.files) || [])];
    if (files.length) {
      e.preventDefault();
      uploadAll(files);
    }
  });

  // getUserMedia only exists in a secure context — localhost is fine,
  // plain http over the LAN is not. Detect, and say which problem it is.
  micSupported = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  if (!micSupported) {
    micBtn.disabled = true;
    micBtn.title = window.isSecureContext
      ? 'voice recording is not supported by this browser'
      : 'voice needs localhost or https';
  } else {
    micBtn.addEventListener('click', toggleRecording);
  }

  updateButtons();
  renderChips(state.attachments);
}

function updateButtons() {
  const attachBtn = $('#attachbtn');
  const micBtn = $('#micbtn');
  // A picture belongs with the FIRST message most of all — attaching on a
  // fresh draft quietly creates the project it lands in.
  const gate = state.turnRunning;
  attachBtn.disabled = gate;
  attachBtn.title = 'attach images, audio, or video';
  if (!micSupported) return;
  micBtn.disabled = gate && !recorder;   // a running recording may always be stopped
  if (!recorder) micBtn.title = 'record a voice note';
}

// ---- uploads -----------------------------------------------------------

function uploadAll(files) {
  if (!files.length) return;
  if (state.turnRunning) {
    toast('Wait for the current turn to finish before attaching.', 'info');
    return;
  }
  // Sequential on purpose: transcription and frame sampling are slow, and a
  // calm queue beats six spinners racing.
  (async () => {
    try {
      await ensureProject();
    } catch (error) {
      toast(String(error.message || error), 'error');
      return;
    }
    for (const file of files) await uploadOne(file, file.name || 'attachment');
  })();
}

async function uploadOne(blob, name) {
  const host = $('#chips');
  const ghost = el('span', { class: 'chip-attach ghost' },
    el('span', { class: 'spinner' }),
    el('span', { class: 'gname' }, name));
  host.appendChild(ghost);
  syncChipRow();
  try {
    const out = await uploadAttachment(blob, name);
    if (out.kind === 'image') {
      addRef(out.id);
    } else if (out.kind === 'video') {
      const frames = out.frames || [];
      frames.forEach(addRef);
      toast(`Clip sampled into ${frames.length} frame${frames.length === 1 ? '' : 's'}.`, 'info');
    } else if (out.kind === 'audio') {
      insertTranscript(out.transcript || '');
      toast('Voice note transcribed.', 'info');
    }
  } catch (error) {
    toast(String(error.message || error));
  } finally {
    ghost.remove();
    syncChipRow();
  }
}

// Refs are used verbatim, exactly as the server hands them out — the same
// string names the thumbnail and rides the message body.
function addRef(ref) {
  if (!ref || state.attachments.includes(ref)) return;
  if (state.attachments.length >= MAX_ATTACHMENTS) {
    toast(`At most ${MAX_ATTACHMENTS} attachments per message.`, 'warn');
    return;
  }
  patch({ attachments: [...state.attachments, ref] });
}

function insertTranscript(text) {
  if (!text) return;
  const textarea = $('#composer-text');
  const value = textarea.value;
  const start = textarea.selectionStart ?? value.length;
  const end = textarea.selectionEnd ?? value.length;
  const before = value.slice(0, start);
  const glue = before && !/\s$/.test(before) ? ' ' : '';
  textarea.value = before + glue + text + value.slice(end);
  const caret = (before + glue + text).length;
  textarea.setSelectionRange(caret, caret);
  textarea.focus();
}

// ---- chips -------------------------------------------------------------

function renderChips(list) {
  const host = $('#chips');
  const existing = new Map(
    [...host.querySelectorAll('.chip-attach:not(.ghost)')].map((node) => [node.dataset.ref, node]));
  for (const [ref, node] of existing) {
    if (!list.includes(ref)) node.remove();
  }
  for (const ref of list) {
    if (!existing.has(ref)) host.appendChild(chip(ref));
  }
  syncChipRow();
}

function chip(ref) {
  return el('span', { class: 'chip-attach', dataset: { ref } },
    el('img', { src: attachmentUrl(ref), alt: '' }),
    el('button', {
      class: 'chip-x', title: 'remove',
      onclick: () => patch({ attachments: state.attachments.filter((r) => r !== ref) }),
    }, '×'));
}

function syncChipRow() {
  const host = $('#chips');
  host.hidden = !host.children.length;
}

// ---- voice -------------------------------------------------------------

async function toggleRecording() {
  const micBtn = $('#micbtn');
  if (recorder) {
    recorder.stop();
    return;
  }
  if (state.turnRunning) return;
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (error) {
    toast(`Microphone unavailable: ${error.message || error}`);
    return;
  }
  const parts = [];
  recStream = stream;
  recorder = new MediaRecorder(stream);
  recorder.ondataavailable = (e) => { if (e.data && e.data.size) parts.push(e.data); };
  recorder.onstop = async () => {
    clearInterval(recTimer);
    recTimer = null;
    recStream.getTracks().forEach((track) => track.stop());
    recStream = null;
    const blob = new Blob(parts, { type: recorder.mimeType || 'audio/webm' });
    recorder = null;
    micBtn.classList.remove('rec');
    micBtn.textContent = '🎤';
    updateButtons();
    if (blob.size) {
      try {
        await ensureProject();
      } catch (error) {
        toast(String(error.message || error), 'error');
        return;
      }
      await uploadOne(blob, 'voice-note.webm');
    }
  };
  recStart = Date.now();
  micBtn.classList.add('rec');
  micBtn.title = 'stop recording';
  micBtn.textContent = '■ 0s';
  recTimer = setInterval(() => {
    micBtn.textContent = `■ ${Math.round((Date.now() - recStart) / 1000)}s`;
  }, 250);
  recorder.start();
}
