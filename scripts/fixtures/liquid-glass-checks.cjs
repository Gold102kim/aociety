// Isolated optical/UI smoke checks. This fixture is never loaded by the product.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { expect } = require('playwright/test');

async function checkLiquidGlass({ page, application, screenshots }) {
  const fixture = '#liquid-glass-optics-fixture';
  const surface = `${fixture} .page-tabs`;
  const definitions = 'svg[data-liquid-glass-definitions]';
  const composer = page.getByRole('textbox', { name: '发送给数字分身的消息' });
  const originalDraft = await composer.inputValue();
  let displacedFilterId;
  let originalScale;
  let manuallyReduced = false;
  const settle = async () => {
    await page.waitForTimeout(180);
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  };
  const pointer = () => page.locator(surface).evaluate((element) => {
    const style = getComputedStyle(element);
    return [style.getPropertyValue('--liquid-pointer-x'), style.getPropertyValue('--liquid-pointer-y')];
  });
  const screenshot = async (name, rect) => {
    const capture = () => application.evaluate(async (_electron, rectangle) => {
      const image = await global.__representativeWindow.webContents.capturePage(rectangle, { stayHidden: true, stayAwake: true });
      if (image.isEmpty()) throw new Error('Liquid-glass capture was empty.');
      return { png: image.toPNG().toString('base64'), bitmap: image.toBitmap().toString('base64'), size: image.getSize() };
    }, rect);
    const result = await capture().catch(async (error) => {
      if (!String(error).includes('UnknownVizError')) throw error;
      await page.waitForTimeout(100);
      return capture();
    });
    fs.writeFileSync(path.join(screenshots, `${name}.png`), Buffer.from(result.png, 'base64'));
    return { bitmap: Buffer.from(result.bitmap, 'base64'), size: result.size };
  };

  try {
    await expect(page.locator(definitions)).toHaveCount(1);
    for (const selector of ['.sidebar', '.chat-workspaces nav', '.chat-composer']) {
      await expect(page.locator(selector)).toHaveAttribute('data-liquid-glass', /\S+/);
    }
    await page.evaluate(() => {
      const host = document.createElement('section');
      host.id = 'liquid-glass-optics-fixture';
      host.setAttribute('aria-label', '隔离光学诊断，不是真实用户内容');
      host.style.cssText = 'position:fixed;left:280px;top:160px;width:600px;height:184px;z-index:2147483000;background:repeating-linear-gradient(45deg,#fafafa 0 10px,#141414 10px 20px,#55c5ee 20px 30px,#e393df 30px 40px);';
      const nav = document.createElement('nav');
      nav.className = 'page-tabs';
      nav.style.cssText = 'position:absolute;left:40px;top:36px;width:520px;height:112px;box-sizing:border-box;display:grid;place-items:center;margin:0;';
      const label = document.createElement('span');
      label.textContent = '生产材质 · 隔离折射诊断';
      nav.append(label);
      host.append(nav);
      document.querySelector('.app').append(host);
    });
    await expect(page.locator(surface)).toHaveAttribute('data-liquid-glass', /\S+/);
    await settle();

    const filters = await page.evaluate(async () => Promise.all([...document.querySelectorAll('[data-liquid-glass]')].map(async (element) => {
      const id = element.getAttribute('data-liquid-glass');
      const filter = document.getElementById(id);
      const image = filter?.querySelector('feImage');
      const href = image?.getAttribute('href') || image?.getAttributeNS('http://www.w3.org/1999/xlink', 'href') || '';
      const dimensions = await new Promise((resolve, reject) => {
        const bitmap = new Image();
        bitmap.onload = () => resolve([bitmap.naturalWidth, bitmap.naturalHeight]);
        bitmap.onerror = () => reject(new Error('The production displacement map is not a decodable local image.'));
        bitmap.src = href;
      });
      return { id, units: filter?.getAttribute('filterUnits'), href: href.slice(0, 22), dimensions,
        scales: [...filter.querySelectorAll('feDisplacementMap')].map((node) => Number(node.getAttribute('scale'))),
        variable: getComputedStyle(element).getPropertyValue('--liquid-filter'),
        before: getComputedStyle(element, '::before').backdropFilter,
        ownFilter: getComputedStyle(element).filter };
    })));
    assert.ok(filters.length >= 4, 'Visible production surfaces own independent optical filters.');
    assert.equal(new Set(filters.map(({ id }) => id)).size, filters.length, 'Filters must not leak between differently sized surfaces.');
    for (const filter of filters) {
      assert.equal(filter.units, 'userSpaceOnUse');
      assert.ok(filter.href.startsWith('data:image/png;base64,'), 'Displacement data remains a local PNG, not a remote resource.');
      assert.ok(filter.dimensions.every((dimension) => dimension > 0 && dimension <= 512), 'Displacement maps are bounded to 512 px per side.');
      assert.ok(filter.scales.length > 0 && filter.scales.every((scale) => Number.isFinite(scale) && scale > 0 && scale <= 8));
      assert.ok(filter.variable.includes(filter.id) && filter.before.includes(filter.id), 'The production pseudo-element really uses its SVG filter.');
      assert.equal(filter.ownFilter, 'none', 'The material must not filter foreground text or controls.');
    }

    const bounds = await page.locator(surface).boundingBox();
    await page.mouse.move(bounds.x + 80, bounds.y + 40);
    await settle();
    const firstPointer = await pointer();
    await page.mouse.move(bounds.x + bounds.width - 80, bounds.y + bounds.height - 30);
    await settle();
    assert.notDeepEqual(await pointer(), firstPointer, 'Pointer light updates on interaction.');
    await page.mouse.move(4, 100);
    await settle();

    const rectangle = { x: Math.floor(bounds.x), y: Math.floor(bounds.y), width: Math.ceil(bounds.width), height: Math.ceil(bounds.height) };
    const refracted = await screenshot('30-liquid-refraction', rectangle);
    const filter = await page.locator(surface).evaluate((element) => {
      const id = element.getAttribute('data-liquid-glass');
      const node = document.getElementById(id).querySelector('feDisplacementMap');
      const scale = node.getAttribute('scale');
      node.setAttribute('scale', '0');
      return { id, scale };
    });
    displacedFilterId = filter.id;
    originalScale = filter.scale;
    await settle();
    const flat = await screenshot('31-liquid-no-refraction', rectangle);
    assert.deepEqual(refracted.size, flat.size);
    const { width, height } = refracted.size;
    assert.equal(refracted.bitmap.length, width * height * 4);
    assert.equal(flat.bitmap.length, refracted.bitmap.length);
    const edge = { sum: 0, changed: 0, count: 0 };
    const center = { sum: 0, changed: 0, count: 0 };
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const cssX = x * rectangle.width / width;
        const cssY = y * rectangle.height / height;
        const isEdge = (cssX >= 3 && cssX <= 23 || cssX >= rectangle.width - 23 && cssX <= rectangle.width - 3) && cssY > 24 && cssY < rectangle.height - 24;
        const isCenter = cssX > rectangle.width * .3 && cssX < rectangle.width * .7 && cssY > rectangle.height * .35 && cssY < rectangle.height * .65;
        if (!isEdge && !isCenter) continue;
        const offset = (y * width + x) * 4;
        const difference = (Math.abs(refracted.bitmap[offset] - flat.bitmap[offset]) + Math.abs(refracted.bitmap[offset + 1] - flat.bitmap[offset + 1]) + Math.abs(refracted.bitmap[offset + 2] - flat.bitmap[offset + 2])) / 3;
        const zone = isEdge ? edge : center;
        zone.sum += difference;
        zone.changed += difference > 8 ? 1 : 0;
        zone.count++;
      }
    }
    const optics = { edgeMean: edge.sum / edge.count, edgeChangedFraction: edge.changed / edge.count, centerMean: center.sum / center.count };
    assert.ok(optics.edgeMean > 1 && optics.edgeChangedFraction > .08, `Real backdrop edge pixels must refract, not just declare CSS: ${JSON.stringify(optics)}`);
    assert.ok(optics.centerMean < .6 && optics.centerMean < optics.edgeMean * .25, `Neutral interior must stay stable: ${JSON.stringify(optics)}`);
    await page.evaluate(({ id, scale }) => document.getElementById(id).querySelector('feDisplacementMap').setAttribute('scale', scale), filter);
    displacedFilterId = undefined;

    const fingerprint = () => page.locator(surface).evaluate((element) => {
      const filter = document.getElementById(element.getAttribute('data-liquid-glass'));
      return { width: filter.getAttribute('width'), image: filter.querySelector('feImage').getAttribute('href') };
    });
    const beforeResize = await fingerprint();
    await page.locator(surface).evaluate((element) => { element.style.width = '444px'; });
    await expect.poll(fingerprint).not.toEqual(beforeResize);
    await page.locator(surface).evaluate((element) => { element.style.width = '520px'; });
    await settle();

    await composer.fill('输入与键盘保持原生：Liquid Glass 123。');
    await composer.press('End');
    await composer.press('ArrowLeft');
    await composer.press('ArrowRight');
    assert.equal(await composer.inputValue(), '输入与键盘保持原生：Liquid Glass 123。');
    assert.ok(await composer.evaluate((element) => {
      for (let node = element; node && !node.classList.contains('app'); node = node.parentElement) {
        if (getComputedStyle(node).filter !== 'none') return false;
      }
      return true;
    }), 'Input and reading layers are outside the displacement filter.');
    await composer.fill(originalDraft);

    await page.getByRole('button', { name: '减少透明效果', exact: true }).click();
    manuallyReduced = true;
    await expect(page.locator('[data-liquid-glass]')).toHaveCount(0);
    assert.equal(await page.locator(surface).evaluate((element) => getComputedStyle(element, '::before').backdropFilter), 'none');
    assert.equal(await page.locator(`${definitions} filter`).count(), 0, 'Clear mode releases optical maps.');
    await screenshot('32-liquid-clear-mode');
    await page.getByRole('button', { name: '减少透明效果', exact: true }).click();
    manuallyReduced = false;
    await expect(page.locator(surface)).toHaveAttribute('data-liquid-glass', /\S+/);

    await page.emulateMedia({ reducedMotion: 'reduce', forcedColors: 'none' });
    await settle();
    await expect(page.locator(surface)).toHaveAttribute('data-liquid-glass', /\S+/);
    const reducedPointer = await pointer();
    await page.mouse.move(bounds.x + 100, bounds.y + 35);
    await settle();
    await page.mouse.move(bounds.x + 400, bounds.y + 70);
    await settle();
    assert.deepEqual(await pointer(), reducedPointer, 'Reduced motion keeps static optics but stops pointer tracking.');
    await page.emulateMedia({ reducedMotion: 'no-preference', forcedColors: 'active' });
    await expect(page.locator('[data-liquid-glass]')).toHaveCount(0);
    assert.equal(await page.locator(surface).evaluate((element) => getComputedStyle(element, '::before').backdropFilter), 'none');
    assert.equal(await page.locator(`${definitions} filter`).count(), 0);
    await page.emulateMedia({ reducedMotion: 'no-preference', forcedColors: 'none' });
    await expect(page.locator(surface)).toHaveAttribute('data-liquid-glass', /\S+/);

    const frameIntervals = await page.evaluate(() => new Promise((resolve) => {
      const intervals = [];
      let previous;
      function sample(now) {
        if (previous !== undefined) intervals.push(now - previous);
        previous = now;
        if (intervals.length === 30) resolve(intervals);
        else requestAnimationFrame(sample);
      }
      requestAnimationFrame(sample);
    }));
    frameIntervals.sort((a, b) => a - b);
    const frameTiming = { samples: frameIntervals.length, medianMs: frameIntervals[15], p95Ms: frameIntervals[28], scope: 'isolated idle sample, not interaction or cross-GPU FPS certification' };

    const removedFilterId = await page.locator(surface).getAttribute('data-liquid-glass');
    await page.locator(fixture).evaluate((element) => element.remove());
    await expect.poll(() => page.evaluate((id) => document.getElementById(id) === null, removedFilterId)).toBe(true);
    return { optics, frameTiming, checks: ['bounded-local-maps', 'actual-backdrop-refraction', 'neutral-center', 'pointer-feedback', 'resize', 'native-input', 'clear-mode', 'reduced-motion', 'forced-colors', 'filter-disposal'] };
  } finally {
    if (displacedFilterId) await page.evaluate(({ id, scale }) => document.getElementById(id)?.querySelector('feDisplacementMap')?.setAttribute('scale', scale), { id: displacedFilterId, scale: originalScale });
    await page.locator(fixture).evaluateAll((elements) => elements.forEach((element) => element.remove()));
    if (manuallyReduced) await page.getByRole('button', { name: '减少透明效果', exact: true }).click();
    await page.emulateMedia({ reducedMotion: 'no-preference', forcedColors: 'none' });
    await composer.fill(originalDraft);
    await page.mouse.move(4, 100);
  }
}

module.exports = { checkLiquidGlass };
