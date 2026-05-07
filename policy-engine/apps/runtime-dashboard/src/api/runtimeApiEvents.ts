export type RuntimeApiEvent = {
  status: number;
  code: string;
  detail: string;
  requestId: string | null;
  source: string;
  timestamp: number;
};

type RuntimeApiEventListener = (event: RuntimeApiEvent) => void;

const listeners = new Set<RuntimeApiEventListener>();

export function emitRuntimeApiEvent(event: RuntimeApiEvent) {
  for (const listener of listeners) {
    listener(event);
  }
}

export function subscribeRuntimeApiEvents(listener: RuntimeApiEventListener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
