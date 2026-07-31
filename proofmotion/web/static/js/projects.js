// The projects rail. "New chat" is purely client-side: it clears the page
// to an empty draft, and nothing exists on the server until the first
// message creates the project — an abandoned draft leaves nothing behind.

import state, { subscribe, patch } from './state.js';
import { loadProject } from './api.js';
import { toast } from './log.js';
import { el, $ } from './util.js';

export function initProjects() {
  $('#newbtn').addEventListener('click', () => showDraft());
  subscribe('projects', render);
  subscribe('projectId', render);
  render();
}

function render() {
  const host = $('#projects');
  host.replaceChildren(...state.projects.map((project) =>
    el('div', {
      class: `proj${project.id === state.projectId ? ' on' : ''}`,
      onclick: () => { if (project.id !== state.projectId) openProject(project.id); },
    },
    el('div', { class: 'proj-title' }, project.title || 'Untitled'),
    el('small', {}, `${project.slides} slide${project.slides === 1 ? '' : 's'} · ${project.when}`))));
  $('#rail-empty').hidden = state.projects.length > 0;
}

export async function openProject(projectId, { push = true } = {}) {
  try {
    await loadProject(projectId);
  } catch (error) {
    toast(`Could not open ${projectId}: ${error.message || error}`);
    return;
  }
  localStorage.setItem('pm.lastProject', projectId);
  if (push) history.pushState({}, '', `/p/${projectId}`);
  else history.replaceState({}, '', `/p/${projectId}`);
}

export function showDraft({ push = true } = {}) {
  patch({
    projectId: null, revision: 0, slides: [], posters: {}, errors: {},
    transcript: [], selected: null, status: 'New project. Ask a question.',
    partial: false, video: false, style: '', quality: '',
  });
  if (push) history.pushState({}, '', '/');
  const composer = $('#composer-text');
  if (composer) composer.focus();
}
