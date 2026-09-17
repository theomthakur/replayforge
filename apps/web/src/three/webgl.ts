let cached: boolean | null = null;

/** Probe once per page: creating WebGL contexts is expensive and browsers cap how many can exist. */
export function hasWebGL(): boolean {
  if (cached !== null) return cached;
  try {
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("webgl2") || canvas.getContext("webgl");
    cached = Boolean(window.WebGLRenderingContext && context);
    (context as WebGLRenderingContext | null)?.getExtension("WEBGL_lose_context")?.loseContext();
  } catch {
    cached = false;
  }
  return cached;
}
