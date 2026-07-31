// Deck-wide look: style presets and render quality. Either change touches
// every slide's pixels and re-renders the whole deck, so both ask first and
// run through the same one-at-a-time gate as a turn. The button only exists
// when the server offers /api/styles.

import state, { subscribe } from './state.js';
import { setStyle, setQuality } from './api.js';
import { el, $ } from './util.js';

const QUALITY_LABELS = { l: '480p', m: '720p', h: '1080p' };

export function initStyle() {
  const button = $('#stylebtn');
  const pop = $('#stylepop');

  button.addEventListener('click', (e) => {
    e.stopPropagation();
    if (pop.hidden) {
      render(pop);
      pop.hidden = false;
    } else {
      pop.hidden = true;
    }
  });
  document.addEventListener('click', (e) => {
    if (!pop.hidden && !pop.contains(e.target) && e.target !== button) pop.hidden = true;
  });

  const refresh = () => {
    button.hidden = !state.styles.length;
    button.disabled = !state.projectId;
    if (!pop.hidden) render(pop);
  };
  for (const key of ['styles', 'projectId', 'style', 'quality', 'turnRunning']) {
    subscribe(key, refresh);
  }
  refresh();
}

function pick(kind, value, pop) {
  if (state.turnRunning) return;
  const ok = confirm(
    `Switch ${kind} to ${value}? This changes every slide's look; the whole deck re-renders, which can take a while.`);
  if (!ok) return;
  pop.hidden = true;
  if (kind === 'style') setStyle(value);
  else setQuality(value);
}

function render(pop) {
  const busy = state.turnRunning;
  const cards = state.styles.map((style) =>
    el('button', {
      class: `style-card${style.name === state.style ? ' on' : ''}`,
      disabled: busy,
      onclick: () => pick('style', style.name, pop),
    },
    el('span', { class: 'style-name' }, `${style.name === state.style ? '✓ ' : ''}${style.name}`),
    el('span', { class: 'swatches' },
      el('span', { class: 'swatch', style: { background: style.background }, title: 'background' }),
      el('span', { class: 'swatch', style: { background: style.ink }, title: 'ink' }),
      (style.colors || []).map((color) =>
        el('span', { class: 'swatch', style: { background: color } })))));

  const qualities = Object.keys(state.qualities).map((quality) =>
    el('button', {
      class: `pill${quality === state.quality ? ' on' : ''}`,
      disabled: busy,
      title: qualityTitle(quality),
      onclick: () => pick('quality', quality, pop),
    }, QUALITY_LABELS[quality] || quality));

  pop.replaceChildren(
    el('div', { class: 'pop-title' }, 'style'),
    ...cards,
    el('div', { class: 'pop-title' }, 'quality'),
    el('div', { class: 'row quality-row' }, qualities));
}

function qualityTitle(quality) {
  const spec = state.qualities[quality];
  return spec ? `${spec.px_w}×${spec.px_h} @ ${spec.fps}fps` : '';
}
