import { JSDOM } from "jsdom";

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost:3000' });
for (const name of ['window', 'document', 'navigator', 'HTMLElement', 'Element', 'Node', 'SVGElement', 'HTMLInputElement', 'HTMLButtonElement', 'MutationObserver', 'getComputedStyle']) {
  Object.defineProperty(globalThis, name, { value: (dom.window as unknown as Record<string, unknown>)[name], configurable: true, writable: true });
}
class ResizeObserverStub { observe() {} unobserve() {} disconnect() {} }
Object.defineProperty(globalThis, 'ResizeObserver', { value: ResizeObserverStub, configurable: true });
Object.defineProperty(globalThis, 'requestAnimationFrame', { value: (callback: () => void) => setTimeout(callback, 0), configurable: true });
Object.defineProperty(globalThis, 'cancelAnimationFrame', { value: clearTimeout, configurable: true });
