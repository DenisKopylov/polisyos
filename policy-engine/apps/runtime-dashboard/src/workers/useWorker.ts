import { useCallback, useEffect, useRef } from "react";

/**
 * Generic hook for communicating with a Web Worker.
 *
 * Uses Vite's built-in worker support:
 * ```ts
 * const worker = new Worker(
 *   new URL("./dagLayout.worker.ts", import.meta.url),
 *   { type: "module" },
 * );
 * ```
 */
type TypedWorker<TRequest, TResponse> = Omit<
  Worker,
  "onmessage" | "postMessage"
> & {
  onmessage: ((event: MessageEvent<TResponse>) => void) | null;
  postMessage: (message: TRequest, transfer?: Transferable[]) => void;
};

export function useWorker<TRequest, TResponse>(
  createWorker: () => TypedWorker<TRequest, TResponse>,
  onMessage: (response: TResponse) => void,
): {
  post: (request: TRequest) => void;
  terminate: () => void;
} {
  const workerRef = useRef<TypedWorker<TRequest, TResponse> | null>(null);
  const callbackRef = useRef(onMessage);

  useEffect(() => {
    callbackRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    const worker = createWorker();
    workerRef.current = worker;

    worker.onmessage = (event: MessageEvent<TResponse>) => {
      callbackRef.current(event.data);
    };

    worker.onerror = (err) => {
      console.error("[worker] Error:", err.message);
    };

    return () => {
      worker.terminate();
      workerRef.current = null;
    };
  }, [createWorker]);

  const post = useCallback((request: TRequest) => {
    workerRef.current?.postMessage(request);
  }, []);

  const terminate = useCallback(() => {
    workerRef.current?.terminate();
    workerRef.current = null;
  }, []);

  return { post, terminate };
}
