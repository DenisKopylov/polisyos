/// <reference lib="webworker" />

/**
 * Web Worker for parsing large JSON payloads off the main thread.
 *
 * Large artifact responses (10MB+) can block the main thread for 50-200ms.
 * This worker moves the parse cost to a background thread.
 */

type ParseRequest = {
  id: string;
  raw: string;
  type: "parse";
};

type ParseResponse =
  | { id: string; parsed: unknown; type: "parse.result" }
  | { error: string; id: string; type: "parse.error" };

self.addEventListener("message", (event: MessageEvent<ParseRequest>) => {
  const { data } = event;
  if (data.type !== "parse") return;

  try {
    const parsed = JSON.parse(data.raw);
    const response: ParseResponse = {
      id: data.id,
      parsed,
      type: "parse.result",
    };
    self.postMessage(response);
  } catch (err) {
    const response: ParseResponse = {
      id: data.id,
      error: err instanceof Error ? err.message : "Parse error",
      type: "parse.error",
    };
    self.postMessage(response);
  }
});
