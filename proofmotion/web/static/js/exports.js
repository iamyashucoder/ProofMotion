// The export popover: one row per artifact the server can hand over. The
// list is data, so a later PDF or bundle export is one more entry here and
// one more route there — no reshaping.

import state, { subscribe } from './state.js';
import { el, $ } from './util.js';

export function initExports() {
  const button = $('#exportbtn');
  const pop = $('#exportpop');

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

  subscribe('projectId', () => { button.disabled = !state.projectId; });
  subscribe('video', () => { if (!pop.hidden) render(pop); });
  button.disabled = !state.projectId;
}

function render(pop) {
  const pid = state.projectId;
  const rows = [
    {
      label: 'Video (mp4)',
      href: `/api/projects/${pid}/export/video.mp4`,
      enabled: state.video,
      why: 'no full render yet',
    },
    {
      // Posters render server-side on the first call, so this can be slow.
      label: 'Posters PDF',
      href: `/api/projects/${pid}/export/deck.pdf`,
      enabled: true,
    },
    {
      label: 'Bundle (mp4+pdf+json)',
      href: `/api/projects/${pid}/export/bundle.zip`,
      enabled: state.video,
      why: 'no full render yet — the bundle includes the mp4',
    },
    {
      label: 'Project document (json)',
      href: `/api/projects/${pid}/export/project.json`,
      enabled: true,
    },
  ];
  pop.replaceChildren(...rows.map((row) => row.enabled
    ? el('a', { class: 'export-row', href: row.href, download: '' }, row.label)
    : el('span', { class: 'export-row off', title: row.why || '' }, row.label)));
}
