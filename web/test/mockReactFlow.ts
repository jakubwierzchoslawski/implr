/** A ResizeObserver entry needs a contentRect: @xyflow/system reads
 *  entry.contentRect.width when it observes the translate extent, and an entry
 *  carrying only `target` throws there as an unhandled error — which fails the
 *  run even while every assertion passes. */
function entryFor(target: Element): ResizeObserverEntry {
  const el = target as HTMLElement;
  const width = parseFloat(el.style?.width) || 800;
  const height = parseFloat(el.style?.height) || 600;
  const rect = {
    x: 0, y: 0, width, height,
    top: 0, left: 0, right: width, bottom: height,
    toJSON() { return this; },
  };
  return {
    target,
    contentRect: rect as DOMRectReadOnly,
    borderBoxSize: [{ inlineSize: width, blockSize: height }],
    contentBoxSize: [{ inlineSize: width, blockSize: height }],
    devicePixelContentBoxSize: [{ inlineSize: width, blockSize: height }],
  } as ResizeObserverEntry;
}

class ResizeObserverMock {
  callback: ResizeObserverCallback;
  constructor(callback: ResizeObserverCallback) { this.callback = callback; }
  observe(target: Element) {
    setTimeout(() => {
      this.callback([entryFor(target)], this as unknown as ResizeObserver);
    }, 0);
  }
  unobserve() {}
  disconnect() {}
}

class DOMMatrixReadOnlyMock {
  m22: number;
  constructor(transform: string) {
    const scale = transform?.match(/scale\(([1-9.])\)/)?.[1];
    this.m22 = scale !== undefined ? +scale : 1;
  }
}

let initialised = false;

export const mockReactFlow = () => {
  if (initialised) return;
  initialised = true;

  global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;
  global.DOMMatrixReadOnly = DOMMatrixReadOnlyMock as unknown as typeof DOMMatrixReadOnly;

  Object.defineProperties(global.HTMLElement.prototype, {
    offsetHeight: { get() { return parseFloat(this.style.height) || 1; } },
    offsetWidth: { get() { return parseFloat(this.style.width) || 1; } },
  });

  (global.SVGElement as unknown as { prototype: { getBBox: () => object } }).prototype.getBBox =
    () => ({ x: 0, y: 0, width: 0, height: 0 });
};
