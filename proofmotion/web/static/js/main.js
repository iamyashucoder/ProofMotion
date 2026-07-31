// Boot and routing. The URL names the project (/p/{id}); the page follows
// it, and the event stream follows the page — one subscriber on projectId
// keeps the SSE connection pointed at whatever is on screen.

import state, { subscribe } from './state.js';
import { fetchSchemas, fetchStyles, refreshProjects } from './api.js';
import { follow } from './sse.js';
import { initLog, toast } from './log.js';
import { initLayout } from './layout.js';
import { initTheme } from './theme.js';
import { initProjects, openProject, showDraft } from './projects.js';
import { initChat } from './chat.js';
import { initStage } from './stage.js';
import { initFilmstrip } from './filmstrip.js';
import { initDeck } from './deck.js';
import { initExports } from './exports.js';
import { initStyle } from './style.js';

async function boot() {
  initLayout();
  initTheme();
  initLog();
  initProjects();
  initChat();
  initStage();
  initFilmstrip();
  initDeck();
  initExports();
  initStyle();

  subscribe('projectId', (projectId) => follow(projectId));

  try {
    // fetchStyles catches its own failure: styles are optional, schemas and
    // the project listing are not.
    await Promise.all([fetchSchemas(), refreshProjects(), fetchStyles()]);
  } catch (error) {
    toast(`Could not reach the studio server: ${error.message || error}`);
  }

  route({ fromHistory: false });
  window.addEventListener('popstate', () => route({ fromHistory: true }));
}

function route({ fromHistory }) {
  const match = location.pathname.match(/^\/p\/([^/]+)$/);
  if (match) {
    openProject(decodeURIComponent(match[1]), { push: false });
    return;
  }
  if (!fromHistory) {
    // Landing on "/": reopen the last project if it still exists.
    const last = localStorage.getItem('pm.lastProject');
    if (last && state.projects.some((p) => p.id === last)) {
      openProject(last, { push: false });
      return;
    }
  }
  showDraft({ push: false });
}

boot();
