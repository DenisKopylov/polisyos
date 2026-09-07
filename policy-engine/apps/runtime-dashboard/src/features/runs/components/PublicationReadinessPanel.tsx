import type { PublicDecisionPacket } from "@/features/runs/domain/publicationPacket";

import { PublicationPacketPanel } from "./PublicationPacketPanel";

export function PublicationReadinessPanel({
  packet,
}: {
  packet: PublicDecisionPacket;
}) {
  return <PublicationPacketPanel packet={packet} />;
}
