// Dark or light. The attribute on <html> is the override; when no
// preference was ever saved, the OS decides through prefers-color-scheme
// and the attribute stays off.

import { pref, setPref } from './layout.js';
import { $ } from './util.js';

export function initTheme() {
  applyTheme(pref('theme'));
  $('#themebtn').addEventListener('click', () => {
    const next = effective() === 'dark' ? 'light' : 'dark';
    setPref('theme', next);
    applyTheme(next);
  });
}

function effective() {
  const chosen = document.documentElement.dataset.theme;
  if (chosen) return chosen;
  return matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

function applyTheme(theme) {
  if (theme) document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;
  // The button names the theme a click would take you to.
  $('#themebtn').textContent = effective() === 'dark' ? 'light' : 'dark';
}
