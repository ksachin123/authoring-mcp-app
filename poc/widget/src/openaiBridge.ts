export interface OpenAiBridge {
  callTool(name: string, args: Record<string, unknown>): Promise<unknown>;
  widgetState: Record<string, unknown>;
  setWidgetState(state: Record<string, unknown>): void;
  // Confirmed present on window.openai via a live bridge-keys dump, but
  // previously unused -- without reporting real content size, the host
  // apparently sizes the iframe incorrectly, producing overlapping/clipped
  // content (confirmed live: distorted, not fully visible widget).
  notifyIntrinsicHeight?(height: number): void;
  notifyIntrinsicWidth?(width: number): void;
}

declare global {
  interface Window {
    openai?: OpenAiBridge;
  }
}

export function getOpenAiBridge(): OpenAiBridge {
  if (!window.openai) {
    throw new Error('window.openai bridge is not present — this widget must run inside ChatGPT');
  }
  return window.openai;
}

// This script now runs inline (see server.py's report_workspace_widget()),
// executing the instant the HTML parser reaches it -- there's no guarantee
// ChatGPT has finished injecting window.openai into the iframe by then.
// Poll briefly instead of assuming it's synchronously available.
export function waitForOpenAiBridge(timeoutMs = 3000, intervalMs = 25): Promise<OpenAiBridge> {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const tick = () => {
      if (window.openai) {
        resolve(window.openai);
        return;
      }
      if (Date.now() - start >= timeoutMs) {
        reject(new Error(`window.openai bridge never appeared after ${timeoutMs}ms`));
        return;
      }
      setTimeout(tick, intervalMs);
    };
    tick();
  });
}
