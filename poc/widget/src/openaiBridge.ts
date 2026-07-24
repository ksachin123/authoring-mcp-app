export interface OpenAiBridge {
  callTool(name: string, args: Record<string, unknown>): Promise<unknown>;
  widgetState: Record<string, unknown>;
  setWidgetState(state: Record<string, unknown>): void;
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
