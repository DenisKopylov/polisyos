import { useEffect } from "react";

import { useTemporalRange } from "@/api/hooks/useTemporalRange";
import { TemporalScrubber, useMaybeTemporalCursor } from "@/shared/ui/temporal";

type ConnectedTemporalScrubberProps = {
  className?: string;
  runId: string | null;
};

export function ConnectedTemporalScrubber({
  className,
  runId,
}: ConnectedTemporalScrubberProps) {
  const cursor = useMaybeTemporalCursor();
  if (!cursor) {
    return null;
  }
  return (
    <ConnectedTemporalScrubberInner
      className={className}
      cursor={cursor}
      runId={runId}
    />
  );
}

function ConnectedTemporalScrubberInner({
  className,
  cursor,
  runId,
}: ConnectedTemporalScrubberProps & {
  cursor: NonNullable<ReturnType<typeof useMaybeTemporalCursor>>;
}) {
  const query = useTemporalRange(runId, Boolean(runId));

  useEffect(() => {
    if (query.data) {
      cursor.setTemporalCapabilities(query.data);
    }
  }, [cursor, query.data]);

  return <TemporalScrubber className={className} />;
}
