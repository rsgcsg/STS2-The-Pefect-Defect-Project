import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.value = ''; }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  get options() { return this.children; }
}
function setup() {
  const nodes = new Map(['account-actions', 'device-scope', 'content', 'notice'].map(k => [k, new Element('div')]));
  const calls = [];
  const context = vm.createContext({
    document: {body: {dataset: {mode: 'local'}}, getElementById: key => nodes.get(key),
      createElement: tag => new Element(tag)}, window: {},
    location: {assign() {}}, history: {pushState() {}}, Date, URLSearchParams, AbortSignal,
    setTimeout, clearTimeout,
    fetch: (url, options) => new Promise(resolve => calls.push({url, options,
      answer: body => resolve({ok:true, json: async () => body})})),
  });
  vm.runInContext(readFileSync(new URL('../stpd/console/identity.js', import.meta.url), 'utf8'), context);
  return {ui: context.window.SpireIdentity, nodes, calls};
}
const person = (subject = 'one') => ({status: 'signed_in', csrf_token: 'csrf',
  principal: {subject, email: subject + '@example.test'}, devices: [{device_id: 'pc', name: 'Laptop'}]});

test('account logout rejects an already in-flight identity response and retains local scope', async () => {
  const {ui, nodes, calls} = setup();
  const initial = ui.refresh(true); calls.shift().answer(person()); await initial;
  const pending = ui.refresh(true), old = calls.shift();
  const logout = nodes.get('account-actions').children.find(x => x.tag === 'button');
  const exiting = logout.onclick();
  assert.equal(nodes.get('account-actions').children.some(x => x.textContent === 'one@example.test'), false);
  old.answer(person()); await pending;
  assert.equal(nodes.get('account-actions').children.some(x => x.textContent === 'one@example.test'), false);
  calls.shift().answer({remote_revoked: true});
  await new Promise(resolve => setImmediate(resolve));
  calls.shift().answer({status:'signed_out', csrf_token:'csrf'});
  await exiting;
  assert.equal(ui.isLocal(), true);
  assert.match(ui.context(), /anonymous/);
});

test('device selection changes request scope and invalidates prior response context', async () => {
  const {ui, nodes, calls} = setup();
  const initial = ui.refresh(true); calls.shift().answer(person()); await initial;
  let reset = false; ui.connect(value => {reset = value;});
  const before = ui.context(), select = nodes.get('device-scope');
  select.value = 'pc'; select.onchange();
  assert.equal(reset, true);
  assert.notEqual(ui.context(), before);
  assert.equal(ui.isLocal(), false);
  assert.equal(ui.api('collections', '?limit=25'), '/api/project/collections?limit=25&device=pc');
});
