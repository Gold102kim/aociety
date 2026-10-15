const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { stripTypeScriptTypes } = require('node:module');
const three = require('three');

// Exercise the production effect, including resource disposal, without a GPU.
const source = fs.readFileSync(path.join(__dirname, '../src/AvatarViewport.tsx'), 'utf8');
const effectSource = source.slice(0, source.indexOf('  return (\n    <div ref={hostRef}'))
  .replace(/^import .*;\r?\n/gm, '')
  .replace('import.meta.env.BASE_URL', "'./'")
  .replace('export function AvatarViewport', 'function AvatarViewport');
assert.ok(effectSource.length < source.length && effectSource.includes('new GLTFLoader(loadingManager).load('));
const executable = stripTypeScriptTypes(`${effectSource}\n}\nAvatarViewport({variant: 'preview', onRetry() {}});`);

function mount({ unsupported = false } = {}) {
  const timers = new Map();
  const statuses = [];
  const listeners = new Set();
  let timerId = 0;
  let cleanup;
  let load;
  let aborted = 0;
  let hook = 0;
  const renderer = { setPixelRatio() {}, setClearColor() {}, setSize() {}, render() {}, setAnimationLoop() {},
    renderLists: { dispose() {} }, dispose() { renderer.disposed = true; }, forceContextLoss() {},
    domElement: { setAttribute() {}, remove() { renderer.removed = true; } } };
  const host = { clientWidth: 640, clientHeight: 390, appendChild() {} };
  class Observer { observe() {} disconnect() {} }
  class Controls { constructor() { this.target = new three.Vector3(); } update() {} addEventListener() {} removeEventListener() {} dispose() {} }
  vm.runInNewContext(executable, {
    THREE: { ...three, LoadingManager: class { abort() { aborted++; } }, WebGLRenderer: function () { if (unsupported) throw new Error('No WebGL'); return renderer; } },
    GLTFLoader: class { load(_url, success, progress, error) { load = { success, progress, error }; } },
    OrbitControls: Controls,
    createRenderScheduler: () => ({ request() {}, pause() {}, dispose() {} }),
    useRef: () => ({ current: host }),
    useState: (initial) => { const index = hook++; return [initial, (value) => { if (index === 0) statuses.push(value); }]; },
    useEffect: (callback) => { const result = callback(); if (result) cleanup = result; },
    ResizeObserver: Observer, IntersectionObserver: Observer, performance: { now: () => 0 },
    document: { hidden: false, addEventListener: (_type, callback) => listeners.add(callback), removeEventListener: (_type, callback) => listeners.delete(callback) },
    window: { devicePixelRatio: 1, matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
      setTimeout: (callback, delay) => { timers.set(++timerId, { callback, delay }); return timerId; },
      clearTimeout: (id) => timers.delete(id), requestAnimationFrame() {}, cancelAnimationFrame() {} },
  });
  return { statuses, timers, renderer, listeners, load, get aborted() { return aborted; },
    expire() { for (const [id, timer] of timers) { assert.equal(timer.delay, 20_000); timers.delete(id); timer.callback(); } },
    unmount() { cleanup?.(); } };
}
function model() {
  const scene = new three.Group();
  const geometry = new three.BoxGeometry();
  const material = new three.MeshBasicMaterial();
  let disposed = 0;
  geometry.addEventListener('dispose', () => { disposed++; });
  material.addEventListener('dispose', () => { disposed++; });
  scene.add(new three.Mesh(geometry, material));
  return { gltf: { scene, scenes: [scene] }, get disposed() { return disposed; } };
}

const success = mount();
assert.equal(success.statuses.at(-1), 'loading');
const valid = model();
success.load.success(valid.gltf);
assert.equal(success.statuses.at(-1), 'ready');
assert.equal(success.timers.size, 0, 'Success cancels the load deadline.');
success.unmount();
assert.equal(valid.disposed, 2);
assert.equal(success.renderer.disposed, true);
assert.equal(success.renderer.removed, true);
assert.equal(success.listeners.size, 0);

const failure = mount();
failure.load.error(new Error('Missing model'));
assert.equal(failure.statuses.at(-1), 'error');
assert.equal(failure.timers.size, 0);
failure.unmount();

const empty = mount();
const emptyScene = new three.Group();
empty.load.success({ scene: emptyScene, scenes: [emptyScene] });
assert.equal(empty.statuses.at(-1), 'error', 'An empty model must not appear loaded.');
empty.unmount();

const timedOut = mount();
timedOut.expire();
assert.equal(timedOut.statuses.at(-1), 'error');
assert.equal(timedOut.aborted, 1, 'Deadline aborts only this preview loading manager.');
const late = model();
timedOut.load.success(late.gltf);
assert.equal(timedOut.statuses.at(-1), 'error', 'Late success cannot revive an expired preview.');
assert.equal(late.disposed, 2, 'Late resources must still be disposed.');
timedOut.unmount();

const unmounted = mount();
unmounted.unmount();
assert.equal(unmounted.timers.size, 0);
assert.equal(unmounted.aborted, 1);
const afterUnmount = model();
unmounted.load.success(afterUnmount.gltf);
unmounted.load.error(new Error('Late failure'));
assert.equal(afterUnmount.disposed, 2);
assert.deepEqual(unmounted.statuses, ['loading'], 'Unmounted loaders cannot update UI.');

const unsupported = mount({ unsupported: true });
assert.equal(unsupported.statuses.at(-1), 'error');
assert.equal(unsupported.timers.size, 0);
assert.equal(unsupported.load, undefined);
console.log('Avatar lifecycle passed: valid/empty/missing model, WebGL unavailable, deadline, late completion, resource cleanup and unmount. No external model assets.');
