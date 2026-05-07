import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

export type LivePoliteness = "assertive" | "polite";

type LiveMessageState = {
  nonce: number;
  text: string;
};

type LiveAnnouncerContextValue = {
  announce: (message: string, politeness?: LivePoliteness) => void;
  clearAnnouncements: () => void;
};

const EMPTY_MESSAGE: LiveMessageState = {
  nonce: 0,
  text: "",
};

const LiveAnnouncerContext = createContext<LiveAnnouncerContextValue | null>(
  null,
);

export function LiveAnnouncerProvider({ children }: PropsWithChildren) {
  const [politeMessage, setPoliteMessage] = useState(EMPTY_MESSAGE);
  const [assertiveMessage, setAssertiveMessage] = useState(EMPTY_MESSAGE);
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

  const clearAnnouncements = useCallback(() => {
    setPoliteMessage(EMPTY_MESSAGE);
    setAssertiveMessage(EMPTY_MESSAGE);
  }, []);

  const announce = useCallback(
    (message: string, politeness: LivePoliteness = "polite") => {
      const normalized = message.replace(/\s+/g, " ").trim();
      if (!normalized) {
        return;
      }

      const setMessage =
        politeness === "assertive" ? setAssertiveMessage : setPoliteMessage;

      setMessage((current) => ({
        nonce: current.nonce + 1,
        text: "",
      }));

      if (timeoutRef.current) {
        globalThis.clearTimeout(timeoutRef.current);
      }

      timeoutRef.current = globalThis.setTimeout(() => {
        setMessage((current) => ({
          nonce: current.nonce + 1,
          text: normalized,
        }));
      }, 10);
    },
    [],
  );

  return (
    <LiveAnnouncerContext.Provider value={{ announce, clearAnnouncements }}>
      {children}
      <div
        aria-atomic="true"
        aria-live="polite"
        className="sr-only"
        data-testid="live-announcer-polite"
        role="status"
      >
        {politeMessage.nonce > 0 ? politeMessage.text : ""}
      </div>
      <div
        aria-atomic="true"
        aria-live="assertive"
        className="sr-only"
        data-testid="live-announcer-assertive"
        role="alert"
      >
        {assertiveMessage.nonce > 0 ? assertiveMessage.text : ""}
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
