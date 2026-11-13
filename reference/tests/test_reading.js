// Behavior checks without browser automation: persistence, limits, reset, storage failures.
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../deploy/oml/static/reading.js'), 'utf8');
function screen(saved, unavailable = false) {
  let ready;
  const elements = Object.fromEntries(['font-smaller', 'font-larger', 'font-reset', 'font-size-value'].map(id => [id, {
    addEventListener(event, callback) { this.click = callback; }
  }]));
  const document = {documentElement: {dataset: {}}, getElementById: id => elements[id],
    addEventListener: (event, callback) => { ready = callback; }};
  const store = {value: saved};
  vm.runInNewContext(source, {document, localStorage: {
    getItem() { if (unavailable) throw Error('disabled'); return store.value; },
    setItem(key, value) { if (unavailable) throw Error('disabled'); store.value = value; }
  }});
  ready();
  return {elements, document, store};
}
test('default, adjustment, navigation persistence and reset', () => {
  const first = screen(null);
  assert.equal(first.document.documentElement.dataset.fontSize, '22');
  first.elements['font-larger'].click();
  assert.equal(first.elements['font-size-value'].textContent, '24px');
  const next = screen(first.store.value);
  assert.equal(next.document.documentElement.dataset.fontSize, '24');
  next.elements['font-reset'].click();
  assert.equal(next.store.value, '22');
});
test('limits, corrupt preferences and unavailable storage', () => {
  const page = screen('unexpected');
  for (let i = 0; i < 20; i++) page.elements['font-larger'].click();
  assert.equal(page.store.value, '30');
  assert.equal(page.elements['font-larger'].disabled, true);
  for (let i = 0; i < 20; i++) page.elements['font-smaller'].click();
  assert.equal(page.store.value, '18');
  assert.equal(page.elements['font-smaller'].disabled, true);
  const privatePage = screen(null, true);
  privatePage.elements['font-larger'].click();
  assert.equal(privatePage.document.documentElement.dataset.fontSize, '24');
});
