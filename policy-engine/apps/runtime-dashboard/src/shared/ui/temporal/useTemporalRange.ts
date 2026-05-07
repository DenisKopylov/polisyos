import { useEffect } from "react";

import { useTemporalRange as useTemporalRangeQuery } from "@/api/hooks/useTemporalRange";
import { useMaybeTemporalCursor } from "@/app/providers/useTemporalCursor";

export function useTemporalRange(runId: string | null | undefined) {
  const cursor = useMaybeTemporalCursor();
  const query = useTemporalRangeQuery(runId, Boolean(cursor && runId));

  useEffect(() => {
    if (query.data) {
      cursor?.setTemporalCapabilities(query.data);
    }
  }, [cursor, query.data]);

  return {
    capabilities: query.data ?? cursor?.capabilities ?? null,
    eventPoints: cursor?.eventPoints ?? [],
    query,
    range: cursor?.range ?? null,
    txRange: cursor?.txRange ?? null,
  };
}
