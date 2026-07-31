// The filmstrip: one thumbnail per slide, keyed by slide id, in slide
// order. Click selects; dragging a thumbnail reorders, with a single accent
// mark showing the gap it will land in. Poster URLs are content-addressed,
// so an unchanged slide never re-fetches its image.

import state, { subscribe, patch, slideIndex } from './state.js';
import { queueOps, posterUrl } from './api.js';
import { el, $ } from './util.js';

const thumbs = new Map();   // slide id -> {node, img, empty, num, badge}
let host = null;
let mark = null;

export function initFilmstrip() {
  host = $('#film');
  mark = el('div', { class: 'dropmark', hidden: true });
  host.insertBefore(mark, host.firstChild);
  for (const key of ['slides', 'posters', 'errors', 'selected', 'projectId']) {
    subscribe(key, render);
  }
  host.addEventListener('dragover', onDragOver);
  host.addEventListener('dragleave', () => { mark.hidden = true; });
  host.addEventListener('drop', onDrop);
  render();
}

function makeThumb(id) {
  const img = el('img', { alt: '', draggable: false, hidden: true });
  const empty = el('div', { class: 'thumb-empty', hidden: true });
  const badge = el('div', { class: 'thumb-badge', title: 'this slide failed to render', hidden: true }, '!');
  const num = el('div', { class: 'num' });
  const node = el('div', { class: 'thumb', draggable: true },
    el('div', { class: 'thumb-box' }, img, empty, badge), num);
  node.addEventListener('click', () => patch({ selected: id }));
  node.addEventListener('dragstart', (e) => {
    e.dataTransfer.setData('text/plain', id);
    e.dataTransfer.effectAllowed = 'move';
    node.classList.add('drag-src');
  });
  node.addEventListener('dragend', () => {
    node.classList.remove('drag-src');
    mark.hidden = true;
  });
  return { node, img, empty, num, badge };
}

function render() {
  const seen = new Set();
  state.slides.forEach((slide, index) => {
    seen.add(slide.id);
    let t = thumbs.get(slide.id);
    if (!t) {
      t = makeThumb(slide.id);
      thumbs.set(slide.id, t);
    }
    const digest = state.posters[slide.id] || '';
    if (digest) {
      const url = posterUrl(slide.id);
      if (t.img.dataset.url !== url) {
        t.img.src = url;
        t.img.dataset.url = url;
      }
      t.img.hidden = false;
      t.empty.hidden = true;
    } else {
      t.img.hidden = true;
      t.img.removeAttribute('src');
      t.img.dataset.url = '';
      t.empty.hidden = false;
      t.empty.textContent = slide.title || slide.id;
    }
    t.node.title = slide.title || slide.id;
    t.num.textContent = `${index + 1}${slide.locked ? ' 🔒' : ''}`;
    t.badge.hidden = !state.errors[slide.id];
    t.node.classList.toggle('on', slide.id === state.selected);
  });
  for (const [id, t] of thumbs) {
    if (!seen.has(id)) {
      t.node.remove();
      thumbs.delete(id);
    }
  }
  // Order reconcile: thumbs follow the (absolute-positioned) drop mark.
  let cursor = mark;
  for (const slide of state.slides) {
    const node = thumbs.get(slide.id).node;
    if (cursor.nextElementSibling !== node) host.insertBefore(node, cursor.nextElementSibling);
    cursor = node;
  }
  $('#film-empty').hidden = state.slides.length > 0;
}

// The insertion gap under the pointer, from thumbnail midpoints.
function gapAt(clientX) {
  const nodes = state.slides.map((s) => thumbs.get(s.id).node);
  for (let i = 0; i < nodes.length; i++) {
    const rect = nodes[i].getBoundingClientRect();
    if (clientX < rect.left + rect.width / 2) {
      return { index: i, x: nodes[i].offsetLeft - 4 };
    }
  }
  const last = nodes[nodes.length - 1];
  return { index: nodes.length, x: last ? last.offsetLeft + last.offsetWidth + 2 : 4 };
}

function onDragOver(e) {
  if (!e.dataTransfer.types.includes('text/plain') || !state.slides.length) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  mark.style.left = `${gapAt(e.clientX).x}px`;
  mark.hidden = false;
}

function onDrop(e) {
  e.preventDefault();
  mark.hidden = true;
  const id = e.dataTransfer.getData('text/plain');
  const from = slideIndex(id);
  if (from < 0) return;
  const { index } = gapAt(e.clientX);
  if (index === from || index === from + 1) return;   // same seat
  // Name the slide currently sitting at the gap and land before it; a drop
  // past the last thumb sends neither field, which means the end.
  const target = state.slides[index];                 // never the dragged one: index !== from
  const op = { kind: 'reorder', slide_id: id };
  if (target) op.before = target.id;
  queueOps([op]);
  // The server re-renders whatever the move touched on its own.
  patch({ status: 'Reordered — affected clips re-render automatically.' });
}
