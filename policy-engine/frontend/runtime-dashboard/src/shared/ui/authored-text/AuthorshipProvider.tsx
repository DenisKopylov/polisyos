import {
  createContext,
  startTransition,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";

import { cn } from "@/shared/lib/utils";

import { AuthorBadge } from "./AuthorBadge";
import {
  excerptText,
  type AuthoredTextAuthor,
  type AuthorshipHighlightMode,
} from "./author-registry";

type TimelineRegistration = {
  id: string;
  author: AuthoredTextAuthor;
  authorAgentVersion?: string;
  confidence?: number;
  reviewedByHuman?: boolean;
  sourceHref?: string;
  sourceRef?: string;
  text: string;
  timestamp?: string;
};

type TimelineEntry = TimelineRegistration & {
  order: number;
};

type AuthorshipContextValue = {
  highlightMode: AuthorshipHighlightMode;
  registerBlock: (entry: TimelineRegistration) => void;
  setHighlightMode: (mode: AuthorshipHighlightMode) => void;
  timelineEntries: TimelineRegistration[];
  unregisterBlock: (id: string) => void;
};

const noop = () => undefined;

const DEFAULT_CONTEXT: AuthorshipContextValue = {
  highlightMode: "subtle",
  registerBlock: noop,
  setHighlightMode: noop,
  timelineEntries: [],
  unregisterBlock: noop,
};

const AuthorshipContext =
  createContext<AuthorshipContextValue>(DEFAULT_CONTEXT);

type AuthorshipProviderProps = PropsWithChildren<{
  defaultHighlightMode?: AuthorshipHighlightMode;
  highlightMode?: AuthorshipHighlightMode;
  onHighlightModeChange?: (mode: AuthorshipHighlightMode) => void;
}>;

export function AuthorshipProvider({
  children,
  defaultHighlightMode = "subtle",
  highlightMode,
  onHighlightModeChange,
}: AuthorshipProviderProps) {
  const [internalMode, setInternalMode] =
    useState<AuthorshipHighlightMode>(defaultHighlightMode);
  const [entries, setEntries] = useState<Record<string, TimelineEntry>>({});
  const orderRef = useRef(0);

  const resolvedHighlightMode = highlightMode ?? internalMode;

  const registerBlock = useCallback((entry: TimelineRegistration) => {
    setEntries((current) => {
      const existing = current[entry.id];
      const nextOrder = existing?.order ?? orderRef.current++;
      const nextEntry = {
        ...entry,
        order: nextOrder,
      } satisfies TimelineEntry;

      if (existing && JSON.stringify(existing) === JSON.stringify(nextEntry)) {
        return current;
      }

      return {
        ...current,
        [entry.id]: nextEntry,
      };
    });
  }, []);

  const unregisterBlock = useCallback((id: string) => {
    setEntries((current) => {
      if (!(id in current)) {
        return current;
      }
      const { [id]: _removed, ...next } = current;
      return next;
    });
  }, []);

  const setHighlightMode = useCallback(
    (mode: AuthorshipHighlightMode) => {
      onHighlightModeChange?.(mode);
      if (highlightMode == null) {
        startTransition(() => setInternalMode(mode));
      }
    },
    [highlightMode, onHighlightModeChange],
  );

  const timelineEntries = useMemo(
    () =>
      Object.values(entries)
        .sort((left, right) => {
          if (left.timestamp && right.timestamp) {
            return left.timestamp.localeCompare(right.timestamp);
          }
          if (left.timestamp) {
            return -1;
          }
          if (right.timestamp) {
            return 1;
          }
          return left.order - right.order;
        })
        .map(({ order: _order, ...entry }) => entry),
    [entries],
  );

  const value = useMemo<AuthorshipContextValue>(
    () => ({
      highlightMode: resolvedHighlightMode,
      registerBlock,
      setHighlightMode,
      timelineEntries,
      unregisterBlock,
    }),
    [
      registerBlock,
      resolvedHighlightMode,
      setHighlightMode,
      timelineEntries,
      unregisterBlock,
    ],
  );

  return (
    <AuthorshipContext.Provider value={value}>
      {children}
    </AuthorshipContext.Provider>
  );
}

export function useAuthorship() {
  return useContext(AuthorshipContext);
}

function formatTimelineTimestamp(timestamp?: string) {
  if (!timestamp) {
    return null;
  }

  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

const AUTHORSHIP_TIMELINE_TITLE = "Authorship timeline";
const AUTHORSHIP_TIMELINE_HEADING = "Trace operator and AI prose";

type AuthorshipTimelineProps = {
  className?: string;
};

export function AuthorshipTimeline({ className }: AuthorshipTimelineProps) {
  const { highlightMode, timelineEntries } = useAuthorship();

  if (highlightMode !== "prominent" || timelineEntries.length === 0) {
    return null;
  }

  return (
    <aside
      className={cn(
        "border-line bg-panel/90 sticky top-20 hidden w-80 self-start rounded-[28px] border p-4 xl:block",
        className,
      )}
      aria-label={AUTHORSHIP_TIMELINE_TITLE}
      data-testid="authorship-timeline"
    >
      <div className="space-y-4">
        <div>
          <p className="eyebrow">{AUTHORSHIP_TIMELINE_TITLE}</p>
          <h4 className="text-lg font-semibold">
            {AUTHORSHIP_TIMELINE_HEADING}
          </h4>
        </div>
        <ol className="space-y-3">
          {timelineEntries.map((entry) => {
            const formattedTimestamp = formatTimelineTimestamp(entry.timestamp);

            return (
              <li
                key={entry.id}
                className="bg-surface/75 border-line rounded-2xl border p-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <AuthorBadge
                    author={entry.author}
                    authorAgentVersion={entry.authorAgentVersion}
                    reviewedByHuman={entry.reviewedByHuman}
                    sourceHref={entry.sourceHref}
                    sourceRef={entry.sourceRef}
                  />
                  {formattedTimestamp ? (
                    <span className="text-muted text-[11px] font-medium tracking-[0.12em] uppercase">
                      {formattedTimestamp}
                    </span>
                  ) : null}
                </div>
                <p className="mt-3 text-sm leading-relaxed">
                  {excerptText(entry.text)}
                </p>
              </li>
            );
          })}
        </ol>
      </div>
    </aside>
  );
}
