// The stage shows one of three things: the selected slide's poster (deck),
// the rendered film (film), or the step-through reveal.js presentation the
// server builds from the whole deck (slides). Dragging on the poster moves
// the chosen element and sends a cumulative nudge in scene units on release
// — the drag itself only moves a translucent ghost, because the real answer
// is the server's re-render.

import state, { subscribe, patch, slideById, slideIndex } from './state.js';
import { queueOps, posterUrl, videoUrl } from './api.js';
import { el, $, isTyping, clamp } from './util.js';

let mode = 'deck';          // deck | film | slides
let lastVideoKey = '';
let lastSlidesKey = '';
let slidesLoading = '';
let hintSeen = false;

export function initStage() {
  const stage = $('#stage');
  const poster = $('#poster');
  const grab = $('#grab');

  for (const key of ['selected', 'slides', 'posters', 'projectId', 'video', 'revision']) {
    subscribe(key, update);
  }

  $('#prevbtn').addEventListener('click', () => step(-1));
  $('#nextbtn').addEventListener('click', () => step(1));
  for (const button of document.querySelectorAll('#modeseg .pill')) {
    button.addEventListener('click', () => setMode(button.dataset.mode));
  }

  document.addEventListener('keydown', (e) => {
    if (isTyping() || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === 'ArrowLeft') step(-1);
    else if (e.key === 'ArrowRight') step(1);
    else if (e.key === 'v' || e.key === 'V') setMode(mode === 'film' ? 'deck' : 'film');
  });

  initDrag(stage, poster, grab);
  update();
}

function step(delta) {
  if (!state.slides.length) return;
  const index = state.selected ? slideIndex(state.selected) : -1;
  const next = clamp(index + delta, 0, state.slides.length - 1);
  if (state.slides[next]) patch({ selected: state.slides[next].id });
}

function setMode(next) {
  if (next === mode) return;
  if (next === 'film' && !state.video) return;
  if (next === 'slides' && !state.projectId) return;
  mode = next;
  update();
}

function update() {
  const poster = $('#poster');
  const video = $('#video');
  const frame = $('#slidesframe');
  const empty = $('#stage-empty');
  const where = $('#where');
  const hint = $('#slideshint');

  // Fall back when the current mode's content went away underneath us.
  if (mode === 'film' && !state.video) mode = 'deck';
  if (mode === 'slides' && !state.projectId) mode = 'deck';

  for (const button of document.querySelectorAll('#modeseg .pill')) {
    const wants = button.dataset.mode;
    button.classList.toggle('on', wants === mode);
    if (wants === 'film') {
      button.disabled = !state.video;
      button.title = state.video ? 'the rendered film' : 'no full render yet';
    } else if (wants === 'slides') {
      button.disabled = !state.projectId;
      button.title = 'step-through presentation';
    }
  }

  const slide = state.selected ? slideById(state.selected) : null;
  const index = slide ? slideIndex(slide.id) : -1;
  where.textContent = slide
    ? `${index + 1} / ${state.slides.length} · ${slide.title || slide.id}`
    : 'no slides';
  // Dragging targets the poster, so the picker means nothing over the film
  // or the presentation. Showing it there was two controls of pure noise.
  $('#grabgroup').hidden = mode !== 'deck' || !slide;

  if (mode !== 'film' && !video.paused) video.pause();
  video.hidden = mode !== 'film';
  if (mode !== 'slides') {
    // A hidden reveal deck would keep speaking its narration; unload it.
    if (frame.src) frame.removeAttribute('src');
    lastSlidesKey = '';
    frame.hidden = true;
    $('#stage-spinner').hidden = true;
    hint.hidden = true;
  }

  if (mode === 'film') {
    poster.hidden = true;
    empty.hidden = true;
    $('#narration').hidden = true;
    const key = `${state.projectId}:${state.revision}`;
    if (key !== lastVideoKey) {
      const at = video.currentTime;   // survive a re-render mid-watch
      lastVideoKey = key;
      video.src = videoUrl();
      video.load();
      video.onloadedmetadata = () => {
        if (at && at < video.duration) video.currentTime = at;
      };
    }
    return;
  }

  if (mode === 'slides') {
    poster.hidden = true;
    $('#narration').hidden = true;
    loadSlides();
    return;
  }

  // deck mode: the selected slide's poster, or an honest placeholder.
  const digest = slide ? state.posters[slide.id] : '';
  if (slide && digest) {
    empty.hidden = true;
    poster.hidden = false;
    const url = posterUrl(slide.id);
    if (poster.dataset.url !== url) {
      poster.src = url;
      poster.dataset.url = url;
    }
  } else {
    poster.hidden = true;
    poster.removeAttribute('src');
    poster.dataset.url = '';
    empty.hidden = false;
    empty.textContent = slide
      ? `${slide.title || slide.id} — ${slide.pending ? 'being added…' : 'no poster yet'}`
      : (state.projectId ? 'No slides yet.' : 'Ask a question to start a project.');
  }

  // Narration strip: what will be spoken over this slide, never drawn on it.
  const strip = $('#narration');
  const spoken = slide && typeof slide.narration === 'string' ? slide.narration : '';
  strip.hidden = !spoken;
  strip.textContent = spoken;
}

// The reveal deck is built lazily server-side and cached by content, so the
// first look after an edit can take seconds. Probe with fetch before
// pointing the iframe at the URL — an iframe would swallow the 400's JSON
// ("render the deck first") and show garbage instead of the reason.
async function loadSlides() {
  const frame = $('#slidesframe');
  const spinner = $('#stage-spinner');
  const empty = $('#stage-empty');
  const hint = $('#slideshint');
  const key = `${state.projectId}:${state.revision}`;
  if (key === lastSlidesKey && frame.src) {
    frame.hidden = false;
    return;
  }
  if (slidesLoading === key) return;
  slidesLoading = key;
  spinner.hidden = false;
  empty.hidden = true;
  const url = `/api/projects/${state.projectId}/slides/deck.html?r=${state.revision}`;
  try {
    const probe = await fetch(url);
    if (!probe.ok) {
      let message = `${probe.status} ${probe.statusText}`;
      try { message = (await probe.json()).error || message; } catch { /* not JSON */ }
      throw new Error(message);
    }
    // The deck may have moved on while the build ran; a stale answer is
    // dropped and the newer subscription pass reloads.
    if (mode !== 'slides' || key !== `${state.projectId}:${state.revision}`) return;
    lastSlidesKey = key;
    frame.src = url;   // hits the server's content cache, not a rebuild
    frame.hidden = false;
    if (!hintSeen) {
      hintSeen = true;
      hint.hidden = false;
    }
  } catch (error) {
    if (mode !== 'slides') return;
    frame.hidden = true;
    frame.removeAttribute('src');
    lastSlidesKey = '';
    empty.hidden = false;
    empty.textContent = String(error.message || error);
  } finally {
    if (slidesLoading === key) {
      slidesLoading = '';
      spinner.hidden = true;
    }
  }
}

function targetLabel(name) {
  return name === 'built.group' ? 'figure' : name;
}

function initDrag(stage, poster, grab) {
  let drag = null;

  poster.addEventListener('pointerdown', (e) => {
    if (e.button !== 0 || !state.selected || poster.hidden) return;
    const slide = slideById(state.selected);
    if (!slide) return;
    poster.setPointerCapture(e.pointerId);
    // Scene units per screen pixel, from the poster as displayed right now —
    // the poster resizes with the panel, so this cannot be a constant.
    const units = state.resolution.frame_w / poster.clientWidth;
    const rect = poster.getBoundingClientRect();
    const room = stage.getBoundingClientRect();
    const ghost = el('div', {
      class: 'ghost',
      style: {
        left: `${rect.left - room.left}px`,
        top: `${rect.top - room.top}px`,
        width: `${rect.width}px`,
        height: `${rect.height}px`,
        backgroundImage: `url("${poster.src}")`,
      },
    });
    const hud = el('div', { class: 'draghud' }, `${targetLabel(grab.value)} Δx 0.00 Δy 0.00`);
    drag = { id: e.pointerId, slide, x: e.clientX, y: e.clientY, units, ghost, hud, dx: 0, dy: 0 };
    stage.append(ghost, hud);
    poster.classList.add('dragging');
    e.preventDefault();
  });

  poster.addEventListener('pointermove', (e) => {
    if (!drag || e.pointerId !== drag.id) return;
    drag.dx = e.clientX - drag.x;
    drag.dy = e.clientY - drag.y;
    drag.ghost.style.transform = `translate(${drag.dx}px, ${drag.dy}px)`;
    const ux = (drag.dx * drag.units).toFixed(2);
    const uy = (-drag.dy * drag.units).toFixed(2);   // screen y grows downward
    drag.hud.textContent = `${targetLabel(grab.value)} Δx ${ux} Δy ${uy}`;
  });

  const finish = (e, commit) => {
    if (!drag || e.pointerId !== drag.id) return;
    poster.classList.remove('dragging');
    drag.ghost.remove();
    drag.hud.remove();
    const { slide, dx, dy, units } = drag;
    drag = null;
    if (!commit || (Math.abs(dx) < 4 && Math.abs(dy) < 4)) return;
    const name = grab.value;
    // Cumulative: the new shift merges onto whatever this element already had.
    const now = ((slide.overrides || {}).shift || {})[name] || { dx: 0, dy: 0 };
    queueOps([{
      kind: 'nudge', slide_id: slide.id, name,
      value: { shift: {
        dx: +((+now.dx || 0) + dx * units).toFixed(2),
        dy: +((+now.dy || 0) - dy * units).toFixed(2),
      } },
    }]);
  };
  poster.addEventListener('pointerup', (e) => finish(e, true));
  poster.addEventListener('pointercancel', (e) => finish(e, false));
}
