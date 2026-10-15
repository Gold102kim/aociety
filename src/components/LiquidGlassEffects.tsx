import { useEffect, useId, useRef } from 'react';
import { createGlassDisplacement } from '../liquidGlassOptics';

const surfaceSelector = '.sidebar, .page-tabs, .chat-workspaces nav, .chat-composer';
const svgNamespace = 'http://www.w3.org/2000/svg';

/** Local optical chrome only. Never captures content, filters text or reads account data. */
export function LiquidGlassEffects({ disabled }: { disabled: boolean }) {
  const definitions = useRef<SVGSVGElement>(null);
  const instanceId = useId().replace(/[^a-zA-Z0-9_-]/g, '');

  useEffect(() => {
    const svg = definitions.current;
    const root = svg?.parentElement;
    if (disabled || !svg || !root || !CSS.supports('backdrop-filter', 'url("#glass")')) return;

    const records = new Map<HTMLElement, { filter: SVGFilterElement | null; geometry: string }>();
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const finePointer = window.matchMedia('(any-pointer: fine)');
    let serial = 0;
    let layoutFrame = 0;
    let lightFrame = 0;
    let lightTarget: HTMLElement | null = null;
    let lightPosition: { x: number; y: number } | null = null;
    let disposed = false;

    const clearLight = () => {
      cancelAnimationFrame(lightFrame);
      lightFrame = 0;
      lightTarget?.style.removeProperty('--liquid-pointer-x');
      lightTarget?.style.removeProperty('--liquid-pointer-y');
      lightTarget = null;
      lightPosition = null;
    };
    const release = (element: HTMLElement) => {
      if (lightTarget === element) clearLight();
      records.get(element)?.filter?.remove();
      element.removeAttribute('data-liquid-glass');
      element.style.removeProperty('--liquid-filter');
    };
    const makeNode = (name: string, attributes: Record<string, string>) => {
      const node = document.createElementNS(svgNamespace, name);
      for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
      return node;
    };
    const updateSurface = (element: HTMLElement, width: number, height: number, radius: number) => {
      const record = records.get(element)!;
      if (width < 1 || height < 1) {
        release(element);
        record.filter = null;
        record.geometry = '';
        return;
      }
      const geometry = `${width.toFixed(2)}:${height.toFixed(2)}:${radius}`;
      if (record.geometry === geometry) return;

      try {
        const map = createGlassDisplacement(width, height, radius);
        // This detached, bounded canvas encodes geometry; it never draws page content.
        const canvas = document.createElement('canvas');
        canvas.width = map.width;
        canvas.height = map.height;
        const context = canvas.getContext('2d');
        if (!context) throw new Error('No displacement encoder available.');
        context.putImageData(new ImageData(new Uint8ClampedArray(map.pixels), map.width, map.height), 0, 0);
        const image = canvas.toDataURL('image/png');
        const id = record.filter?.id || `aociety-glass-${instanceId}-${++serial}`;
        const filter = makeNode('filter', {
          id, x: '0', y: '0', width: String(width), height: String(height),
          filterUnits: 'userSpaceOnUse', primitiveUnits: 'userSpaceOnUse',
          'color-interpolation-filters': 'sRGB',
        }) as SVGFilterElement;
        const correction = makeNode('feComponentTransfer', { in: 'map', result: 'displacement' });
        // Eight-bit neutral 128 must become exactly .5, not shift the entire background.
        for (const channel of ['feFuncR', 'feFuncG']) {
          correction.append(makeNode(channel, { type: 'linear', slope: '1', intercept: '-0.00196078431372549' }));
        }
        filter.append(
          makeNode('feImage', { href: image, x: '0', y: '0', width: String(width), height: String(height), preserveAspectRatio: 'none', result: 'map' }),
          correction,
          makeNode('feDisplacementMap', { in: 'SourceGraphic', in2: 'displacement', scale: String(map.scale), xChannelSelector: 'R', yChannelSelector: 'G' }),
        );
        record.filter?.remove();
        svg.append(filter);
        record.filter = filter;
        record.geometry = geometry;
        element.style.setProperty('--liquid-filter', `url("#${id}")`);
        element.setAttribute('data-liquid-glass', id);
        canvas.width = canvas.height = 0;
      } catch {
        // Unsupported encoders/filters keep the existing frosted material usable.
        release(element);
        record.filter = null;
        record.geometry = geometry;
      }
    };
    const synchronize = () => {
      layoutFrame = 0;
      if (disposed) return;
      const surfaces = new Set(root.querySelectorAll<HTMLElement>(surfaceSelector));
      // Read all geometry before SVG/style writes to avoid read/write layout thrashing.
      const measurements = [...surfaces].map((element) => {
        const { width, height } = element.getBoundingClientRect();
        const radius = width >= 1 && height >= 1 ? Number.parseFloat(getComputedStyle(element).borderTopLeftRadius) || 0 : 0;
        return { element, width, height, radius };
      });
      for (const element of records.keys()) {
        if (surfaces.has(element)) continue;
        release(element);
        resize.unobserve(element);
        records.delete(element);
      }
      for (const { element, width, height, radius } of measurements) {
        if (!records.has(element)) {
          records.set(element, { filter: null, geometry: '' });
          resize.observe(element);
        }
        updateSurface(element, width, height, radius);
      }
    };
    const scheduleLayout = () => {
      if (!disposed && !layoutFrame) layoutFrame = requestAnimationFrame(synchronize);
    };
    const resize = new ResizeObserver(scheduleLayout);
    const mutations = new MutationObserver((changes) => {
      if (changes.some((change) => !svg.contains(change.target))) scheduleLayout();
    });
    mutations.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden', 'class'] });

    const moveLight = (event: PointerEvent) => {
      if (motion.matches || !finePointer.matches || event.pointerType === 'touch') { clearLight(); return; }
      const element = event.target instanceof Element ? event.target.closest<HTMLElement>('[data-liquid-glass]') : null;
      if (!element || !records.has(element)) { clearLight(); return; }
      if (element !== lightTarget) { clearLight(); lightTarget = element; }
      lightPosition = { x: event.clientX, y: event.clientY };
      if (!lightFrame) lightFrame = requestAnimationFrame(() => {
        lightFrame = 0;
        const target = lightTarget;
        const position = lightPosition;
        const filter = target && records.get(target)?.filter;
        if (disposed || !target || !position || !filter || !target.isConnected || !root.contains(target)
          || target.getAttribute('data-liquid-glass') !== filter.id || motion.matches || !finePointer.matches) { clearLight(); return; }
        // High-frequency pointer samples share one current geometry read per frame.
        const bounds = target.getBoundingClientRect();
        if (bounds.width < 1 || bounds.height < 1 || position.x < bounds.left || position.x > bounds.right
          || position.y < bounds.top || position.y > bounds.bottom) { clearLight(); return; }
        target.style.setProperty('--liquid-pointer-x', `${(position.x - bounds.left).toFixed(1)}px`);
        target.style.setProperty('--liquid-pointer-y', `${(position.y - bounds.top).toFixed(1)}px`);
      });
    };
    const beginPointer = (event: PointerEvent) => { if (event.pointerType === 'touch') clearLight(); };
    root.addEventListener('pointermove', moveLight, { passive: true });
    root.addEventListener('pointerleave', clearLight, { passive: true });
    root.addEventListener('pointercancel', clearLight, { passive: true });
    root.addEventListener('pointerdown', beginPointer, { passive: true });
    root.addEventListener('scroll', clearLight, { capture: true, passive: true });
    window.addEventListener('blur', clearLight);
    window.addEventListener('resize', clearLight, { passive: true });
    motion.addEventListener('change', clearLight);
    finePointer.addEventListener('change', clearLight);
    synchronize();

    return () => {
      disposed = true;
      cancelAnimationFrame(layoutFrame);
      clearLight();
      mutations.disconnect();
      resize.disconnect();
      root.removeEventListener('pointermove', moveLight);
      root.removeEventListener('pointerleave', clearLight);
      root.removeEventListener('pointercancel', clearLight);
      root.removeEventListener('pointerdown', beginPointer);
      root.removeEventListener('scroll', clearLight, true);
      window.removeEventListener('blur', clearLight);
      window.removeEventListener('resize', clearLight);
      motion.removeEventListener('change', clearLight);
      finePointer.removeEventListener('change', clearLight);
      for (const element of records.keys()) release(element);
      records.clear();
      svg.replaceChildren();
    };
  }, [disabled, instanceId]);

  return <svg ref={definitions} className="liquid-glass-definitions" data-liquid-glass-definitions="" width="0" height="0" aria-hidden="true" focusable="false"/>;
}
