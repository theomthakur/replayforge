import "@testing-library/jest-dom/vitest";

// jsdom intentionally has no canvas implementation. The product must take its accessible
// no-WebGL path in component tests without writing noisy not-implemented errors to stderr.
Object.defineProperty(HTMLCanvasElement.prototype, "getContext", {
  configurable: true,
  value: () => null,
});
