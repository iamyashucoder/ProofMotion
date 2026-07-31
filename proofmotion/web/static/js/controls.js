// Schema-driven parameter rows, one shape per JSON type — the same
// derivation the old page used, so a slider still cannot leave its declared
// range and an enum can only ever hold one of its options.

import { el } from './util.js';

export function parameterRows(slide, schema, onchange) {
  return Object.entries(schema || {})
    .filter(([name]) => name in (slide.parameters || {}))
    .map(([name, spec]) => row(slide, name, spec, onchange));
}

function row(slide, name, spec, onchange) {
  const current = slide.parameters[name];
  const readout = el('span', { class: 'meta readout' }, display(current));
  let input;

  if (spec.enum) {
    input = el('select', { class: 'tool' }, spec.enum.map((option) =>
      el('option', { value: String(option) }, String(option))));
    input.value = String(current);
  } else if (spec.type === 'number' || spec.type === 'integer') {
    const lo = spec.minimum ?? spec.exclusiveMinimum;
    const hi = spec.maximum ?? spec.exclusiveMaximum;
    if (lo !== undefined && hi !== undefined) {
      input = el('input', {
        type: 'range', min: lo, max: hi,
        step: spec.type === 'integer' ? 1 : (hi - lo) / 100,
        value: current,
      });
    } else {
      input = el('input', { type: 'number', value: current });
    }
  } else if (spec.type === 'boolean') {
    input = el('input', { type: 'checkbox', checked: !!current });
  } else {
    input = el('input', { type: 'text', value: current ?? '' });
  }

  input.addEventListener('input', () => { readout.textContent = display(read(input)); });
  input.addEventListener('change', () => {
    let value = read(input);
    if (spec.type === 'number') value = parseFloat(value);
    if (spec.type === 'integer') value = parseInt(value, 10);
    if ((spec.type === 'number' || spec.type === 'integer') && Number.isNaN(value)) return;
    onchange(name, value);
  });

  return el('div', { class: 'row' }, el('label', {}, name), input, readout);
}

function read(input) {
  return input.type === 'checkbox' ? input.checked : input.value;
}

function display(value) {
  return typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value ?? '');
}
