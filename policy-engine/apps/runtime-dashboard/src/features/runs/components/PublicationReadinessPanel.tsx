import type { SignedPublicDecisionPacket } from "@/features/runs/domain/publicationPacket";

import { PublicationPacketPanel } from "./PublicationPacketPanel";

export function PublicationReadinessPanel({
  packet,
}: {
  packet: SignedPublicDecisionPacket;
}) {
  return <PublicationPacketPanel packet={packet} />;
}
