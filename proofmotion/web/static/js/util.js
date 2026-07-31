// Tiny DOM and misc helpers. Every piece of user-visible data goes through
// textContent — snapshots carry model-written text, so innerHTML is never
// used with data anywhere in this codebase.

export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value == null) continue;
    if (key === 'class') node.className = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key === 'style' && typeof value === 'object') Object.assign(node.style, value);
    else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
    else if (key in node) node[key] = value;
    else node.setAttribute(key, value);
  }
  append(node, children);
  return node;
}

function append(node, children) {
  for (const child of children) {
    if (child == null || child === false) continue;
    if (Array.isArray(child)) append(node, child);
    else node.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

export const $ = (selector, root = document) => root.querySelector(selector);

export function isTyping() {
  const active = document.activeElement;
  return !!active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA'
    || active.tagName === 'SELECT' || active.isContentEditable);
}

export function clamp(value, lo, hi) {
  return Math.min(hi, Math.max(lo, value));
}

export function timeStamp(date = new Date()) {
  return date.toTimeString().slice(0, 8);
}

// Swap a static element for an input in place: Enter or blur commits,
// Escape walks away. The element itself stays in the DOM, only hidden, so
// the card's keyed update never loses track of it. Multiline gets a
// textarea where Shift+Enter breaks the line and Enter still commits.
export function inlineEdit(target, current, commit, { multiline = false } = {}) {
  const input = multiline
    ? el('textarea', { class: 'inline-edit', rows: 3 })
    : el('input', { class: 'inline-edit', type: 'text', value: current });
  if (multiline) input.value = current;
  let done = false;
  const finish = (save) => {
    if (done) return;
    done = true;
    target.hidden = false;
    input.remove();
    const value = input.value.trim();
    if (save && value !== current) commit(value);
  };
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !(multiline && e.shiftKey)) { e.preventDefault(); finish(true); }
    else if (e.key === 'Escape') finish(false);
  });
  input.addEventListener('blur', () => finish(true));
  target.hidden = true;
  target.after(input);
  input.focus();
  input.select();
}
