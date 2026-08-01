// The stage: the selected slide's poster, or the whole video. Dragging on
// the poster moves the chosen element (figure, title, caption) and sends a
// cumulative nudge in scene units on release — the drag itself only moves a
// translucent ghost, because the real answer is the server's re-render.

import state, { subscribe, patch, slideById, slideIndex } from './state.js';
import { queueOps, posterUrl, videoUrl } from './api.js';
import { el, $, isTyping, clamp } from './util.js';

let watching = false;
let lastVideoKey = '';

export function initStage() {
  const stage = $('#stage');
  const poster = $('#poster');
  const grab = $('#grab');

  for (const key of ['selected', 'slides', 'posters', 'projectId', 'video', 'revision']) {
    subscribe(key, update);
  }

  $('#prevbtn').addEventListener('click', () => step(-1));
  $('#nextbtn').addEventListener('click', () => step(1));
  $('#modebtn').addEventListener('click', toggleMode);

  document.addEventListener('keydown', (e) => {
    if (isTyping() || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === 'ArrowLeft') step(-1);
    else if (e.key === 'ArrowRight') step(1);
    else if (e.key === 'v' || e.key === 'V') toggleMode();
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

function toggleMode() {
  if (!watching && !state.video) return;   // nothing to watch yet
  watching = !watching;
  update();
}

function update() {
  const poster = $('#poster');
  const video = $('#video');
  const empty = $('#stage-empty');
  const where = $('#where');
  const mode = $('#modebtn');

  const slide = state.selected ? slideById(state.selected) : null;
  const index = slide ? slideIndex(slide.id) : -1;
  where.textContent = slide
    ? `${index + 1} / ${state.slides.length} · ${slide.title || slide.id}`
    : 'no slides';
  mode.textContent = watching ? 'back to slides' : 'watch video';
  mode.disabled = !state.video && !watching;
  mode.title = state.video ? '' : 'no full render yet';
  // Dragging targets the poster, so the picker means nothing over the video
  // or over an empty stage. Showing it there was two controls of pure noise.
  $('#grabgroup').hidden = watching || !slide;

  if (watching && state.video) {
    poster.hidden = true;
    empty.hidden = true;
    video.hidden = false;
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
  if (watching) watching = false;   // the video went away underneath us
  video.hidden = true;
  if (!video.paused) video.pause();

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
