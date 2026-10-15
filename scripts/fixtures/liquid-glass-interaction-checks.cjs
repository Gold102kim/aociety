// Isolated production-surface interaction checks; never loaded by the product.
const assert = require('node:assert/strict');

async function checkLiquidGlassInteraction({ page, application, enforce = true }) {
  const composer = page.getByRole('textbox', { name: '发送给数字分身的消息' });
  const originalInput = await composer.evaluate((element) => ({
    value: element.value, start: element.selectionStart, end: element.selectionEnd, direction: element.selectionDirection,
  }));
  const originalFocus = await page.evaluateHandle(() => document.activeElement);
  const requestCount = () => application.evaluate(() => global.__representativeRequests?.length ?? null);
  const requestsBefore = await requestCount();
  const frames = (count) => page.evaluate((total) => new Promise((resolve) => {
    let remaining = total;
    const sample = () => --remaining > 0 ? requestAnimationFrame(sample) : resolve();
    requestAnimationFrame(sample);
  }), count);

  try {
    await page.locator('.sidebar[data-liquid-glass]').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#liquid-glass-optics-fixture').count(), 0, 'The optics diagnostic must be removed first.');
    await frames(3);

    const interactions = await page.evaluate(async () => {
      const surface = document.querySelector('.sidebar[data-liquid-glass]');
      const root = document.querySelector('[data-liquid-glass-definitions]')?.parentElement;
      if (!surface || !root || !root.contains(surface)) throw new Error('A stable production sidebar is required.');
      if (matchMedia('(prefers-reduced-motion: reduce)').matches || !matchMedia('(any-pointer: fine)').matches) {
        throw new Error('Interaction checks require normal motion and a fine pointer.');
      }
      const waitFrames = (count) => new Promise((resolve) => {
        const next = () => --count > 0 ? requestAnimationFrame(next) : resolve();
        requestAnimationFrame(next);
      });
      const pointerProperties = ['--liquid-pointer-x', '--liquid-pointer-y'];
      const targetStyle = surface.style;
      const nativeBounds = surface.getBoundingClientRect;
      const boundsDescriptor = Object.getOwnPropertyDescriptor(surface, 'getBoundingClientRect');
      const stylePrototype = CSSStyleDeclaration.prototype;
      const setDescriptor = Object.getOwnPropertyDescriptor(stylePrototype, 'setProperty');
      const canvasPrototype = HTMLCanvasElement.prototype;
      const encodeDescriptor = Object.getOwnPropertyDescriptor(canvasPrototype, 'toDataURL');
      const rectangle = nativeBounds.call(surface);
      let counters;
      const reset = () => { counters = { layoutReads: 0, pointerWrites: 0, mapEncodes: 0 }; };
      const position = () => ({ x: targetStyle.getPropertyValue(pointerProperties[0]), y: targetStyle.getPropertyValue(pointerProperties[1]) });
      const snapshot = () => ({ ...counters, lastPointer: position() });
      const move = (pointerType = 'mouse', clientX = rectangle.left + 30, clientY = rectangle.top + 100) => {
        surface.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, pointerType, clientX, clientY }));
      };
      const leave = () => root.dispatchEvent(new PointerEvent('pointerleave', { pointerType: 'mouse' }));
      const cleanupEvents = {
        pointerleave: leave,
        pointercancel: () => surface.dispatchEvent(new PointerEvent('pointercancel', { bubbles: true, pointerType: 'mouse' })),
        touch: () => move('touch'),
        touchdown: () => surface.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerType: 'touch' })),
        scroll: () => surface.dispatchEvent(new Event('scroll')),
        resize: () => window.dispatchEvent(new Event('resize')),
        blur: () => window.dispatchEvent(new Event('blur')),
      };

      reset();
      try {
        Object.defineProperty(surface, 'getBoundingClientRect', { configurable: true, value: function () {
          counters.layoutReads++;
          return nativeBounds.call(this);
        } });
        Object.defineProperty(stylePrototype, 'setProperty', { ...setDescriptor, value: function (name, ...args) {
          if (this === targetStyle && pointerProperties.includes(name)) counters.pointerWrites++;
          return setDescriptor.value.call(this, name, ...args);
        } });
        Object.defineProperty(canvasPrototype, 'toDataURL', { ...encodeDescriptor, value: function (...args) {
          if (!this.isConnected) counters.mapEncodes++;
          return encodeDescriptor.value.apply(this, args);
        } });

        leave();
        await waitFrames(2);
        reset();
        let expectedPointer;
        for (let index = 0; index < 240; index++) {
          const fraction = index / 239;
          const x = rectangle.left + 8 + (rectangle.width - 16) * fraction;
          const y = rectangle.top + 8 + (rectangle.height - 16) * (1 - fraction * .5);
          move('mouse', x, y);
          expectedPointer = { x: `${(x - rectangle.left).toFixed(1)}px`, y: `${(y - rectangle.top).toFixed(1)}px` };
        }
        await waitFrames(3);
        const burst = { events: 240, ...snapshot(), expectedPointer };
        const clearing = {};
        for (const [name, cleanup] of Object.entries(cleanupEvents)) {
          leave();
          await waitFrames(2);
          reset();
          move();
          cleanup();
          await waitFrames(2);
          const pending = snapshot();

          leave();
          await waitFrames(2);
          move();
          await waitFrames(2);
          const lit = position();
          if (!lit.x || !lit.y) throw new Error(`The ${name} check never established a mouse highlight.`);
          reset();
          cleanup();
          await waitFrames(2);
          clearing[name] = { pending, active: snapshot() };
        }
        leave();
        await waitFrames(2);
        const targetRaces = {};
        const originalTransform = { value: targetStyle.getPropertyValue('transform'), priority: targetStyle.getPropertyPriority('transform') };
        try {
          const beforeMove = nativeBounds.call(surface);
          const transform = getComputedStyle(surface).transform;
          reset();
          move('mouse', beforeMove.left + 30, beforeMove.top + 100);
          targetStyle.setProperty('transform', `translateX(4px)${transform === 'none' ? '' : ` ${transform}`}`, 'important');
          const translated = nativeBounds.call(surface);
          await waitFrames(2);
          targetRaces.translated = {
            ...snapshot(), shiftX: translated.left - beforeMove.left,
            expectedPointer: { x: '26.0px', y: '100.0px' },
          };
        } finally {
          if (originalTransform.value) targetStyle.setProperty('transform', originalTransform.value, originalTransform.priority);
          else targetStyle.removeProperty('transform');
          leave();
          await waitFrames(3);
        }

        const originalFilterId = surface.getAttribute('data-liquid-glass');
        if (!originalFilterId) throw new Error('The sidebar filter must be restored before target-race checks.');
        try {
          reset();
          move();
          surface.removeAttribute('data-liquid-glass');
          await waitFrames(2);
          targetRaces.missingFilter = snapshot();
        } finally {
          surface.setAttribute('data-liquid-glass', originalFilterId);
          leave();
          await waitFrames(2);
        }

        const originalDisplay = { value: targetStyle.getPropertyValue('display'), priority: targetStyle.getPropertyPriority('display') };
        try {
          reset();
          move();
          targetStyle.setProperty('display', 'none', 'important');
          await waitFrames(3);
          targetRaces.hidden = snapshot();
        } finally {
          if (originalDisplay.value) targetStyle.setProperty('display', originalDisplay.value, originalDisplay.priority);
          else targetStyle.removeProperty('display');
          leave();
          let restored = false;
          for (let frame = 0; frame < 12; frame++) {
            await waitFrames(1);
            const id = surface.getAttribute('data-liquid-glass');
            if (id && document.getElementById(id) && nativeBounds.call(surface).width > 0) { restored = true; break; }
          }
          if (!restored) throw new Error('The sidebar optical filter did not recover after restoring display.');
        }

        await waitFrames(2);
        reset();
        await waitFrames(12);
        const idle = { frames: 12, ...snapshot() };
        return { burst, clearing, targetRaces, idle };
      } finally {
        leave();
        if (boundsDescriptor) Object.defineProperty(surface, 'getBoundingClientRect', boundsDescriptor);
        else delete surface.getBoundingClientRect;
        Object.defineProperty(stylePrototype, 'setProperty', setDescriptor);
        Object.defineProperty(canvasPrototype, 'toDataURL', encodeDescriptor);
      }
    });

    if (enforce) {
      assert.ok(interactions.burst.layoutReads <= 1, `One geometry read per burst: ${JSON.stringify(interactions.burst)}`);
      assert.equal(interactions.burst.pointerWrites, 2, 'A burst commits only its final x/y values.');
      assert.equal(interactions.burst.mapEncodes, 0, 'Pointer movement does not re-encode displacement maps.');
      assert.deepEqual(interactions.burst.lastPointer, interactions.burst.expectedPointer, 'The latest pointer sample wins.');
      for (const [name, phases] of Object.entries(interactions.clearing)) {
        for (const [phase, result] of Object.entries(phases)) {
          assert.deepEqual(result.lastPointer, { x: '', y: '' }, `${name} clears ${phase} highlight state.`);
          assert.equal(result.pointerWrites, 0, `${name} does not leave queued pointer writes.`);
          assert.equal(result.mapEncodes, 0, `${name} does not rebuild optical maps.`);
        }
      }
      assert.equal(interactions.targetRaces.translated.shiftX, 4, 'The race fixture shifts the actual surface by four CSS pixels.');
      assert.deepEqual(interactions.targetRaces.translated.lastPointer, interactions.targetRaces.translated.expectedPointer, 'The queued pointer uses current, not pre-RAF, bounds.');
      for (const name of ['missingFilter', 'hidden']) {
        assert.equal(interactions.targetRaces[name].pointerWrites, 0, `${name} cancels pending pointer writes.`);
        assert.deepEqual(interactions.targetRaces[name].lastPointer, { x: '', y: '' }, `${name} leaves no pointer highlight.`);
      }
      assert.equal(interactions.idle.pointerWrites, 0, 'Stable idle frames never write pointer styles.');
      assert.equal(interactions.idle.mapEncodes, 0, 'Stable idle frames never re-encode maps.');
    }

    const bounds = await page.locator('.sidebar').boundingBox();
    assert.ok(bounds, 'Sidebar bounds remain available after interaction checks.');
    const [frameIntervals] = await Promise.all([
      page.evaluate(() => new Promise((resolve) => {
        const intervals = [];
        let previous;
        const sample = (now) => {
          if (previous !== undefined) intervals.push(now - previous);
          previous = now;
          if (intervals.length === 60) resolve(intervals);
          else requestAnimationFrame(sample);
        };
        requestAnimationFrame(sample);
      })),
      (async () => {
        for (let index = 0; index < 8; index++) {
          await page.mouse.move(bounds.x + bounds.width * (index % 2 ? .8 : .2), bounds.y + bounds.height * (.2 + index / 12), { steps: 8 });
        }
      })(),
    ]);
    frameIntervals.sort((a, b) => a - b);
    const frameTiming = {
      samples: frameIntervals.length, medianMs: frameIntervals[30], p95Ms: frameIntervals[56],
      scope: '60 requestAnimationFrame intervals overlapping real mouse movement in this isolated run; not cross-device FPS certification',
    };

    const input = '原生输入与键盘选择保持不变：Liquid Glass 123。';
    await composer.fill(input);
    await composer.press('Control+End');
    for (let index = 0; index < 3; index++) await composer.press('Shift+ArrowLeft');
    const selection = await composer.evaluate((element) => ({ value: element.value, start: element.selectionStart, end: element.selectionEnd }));
    assert.deepEqual(selection, { value: input, start: input.length - 3, end: input.length }, 'Native keyboard selection preserves the draft and caret.');
    await composer.press('ArrowLeft');
    await composer.press('Shift+ArrowRight');
    const narrowed = await composer.evaluate((element) => ({ value: element.value, start: element.selectionStart, end: element.selectionEnd }));
    assert.deepEqual(narrowed, { value: input, start: input.length - 3, end: input.length - 2 }, 'Keyboard navigation still uses native selection semantics.');
    assert.equal(await requestCount(), requestsBefore, 'Optical and keyboard tests never send model requests.');
    return { ...interactions, nativeInput: { valuePreserved: true, selectionLength: 3, narrowedSelectionLength: 1 }, frameTiming, enforced: enforce };
  } finally {
    await composer.fill(originalInput.value);
    await composer.evaluate((element, input) => element.setSelectionRange(input.start, input.end, input.direction), originalInput);
    await originalFocus.evaluate((element) => { if (element?.isConnected && typeof element.focus === 'function') element.focus(); });
    await originalFocus.dispose();
    await page.mouse.move(4, 100);
    await page.evaluate(() => document.querySelector('[data-liquid-glass-definitions]')?.parentElement?.dispatchEvent(new PointerEvent('pointerleave', { pointerType: 'mouse' })));
  }
}

module.exports = { checkLiquidGlassInteraction };
