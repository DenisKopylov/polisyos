import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

type LivePoliteness = "assertive" | "polite";

type LiveAnnouncerContextValue = {
  announce: (message: string, politeness?: LivePoliteness) => void;
};

const LiveAnnouncerContext = createContext<LiveAnnouncerContextValue | null>(
  null,
);

export function LiveAnnouncerProvider({ children }: PropsWithChildren) {
  const [politeMessage, setPoliteMessage] = useState("");
  const [assertiveMessage, setAssertiveMessage] = useState("");
  const timeoutRef = useRef<ReturnType<typeof globalThis.setTimeout> | null>(
    null,
  );

  useEffect(
    () => () => {
      if (timeoutRef.current) {
        globalThis.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    },
    [],
  );

  const announce = useCallback(
    (message: string, politeness: LivePoliteness = "polite") => {
      const normalized = message.trim();
      if (!normalized) {
        return;
      }
      const setMessage =
        politeness === "assertive" ? setAssertiveMessage : setPoliteMessage;
      setMessage("");
      if (timeoutRef.current) {
        globalThis.clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = globalThis.setTimeout(() => {
        setMessage(normalized);
      }, 10);
    },
    [],
  );

  return (
    <LiveAnnouncerContext.Provider value={{ announce }}>
      {children}
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {politeMessage}
      </div>
      <div className="sr-only" aria-live="assertive" aria-atomic="true">
        {assertiveMessage}
      </div>
    </LiveAnnouncerContext.Provider>
  );
}

export function useLiveAnnouncer() {
  const context = useContext(LiveAnnouncerContext);
  if (!context) {
    throw new Error(
      "useLiveAnnouncer must be used within LiveAnnouncerProvider",
    );
  }
  return context;
}
