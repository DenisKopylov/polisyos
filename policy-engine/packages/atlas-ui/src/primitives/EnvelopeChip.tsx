import { Badge } from "./Badge";
import {
  governedAuthorityPurposePresentation,
  type GovernedAuthorityPurpose,
} from "./evidenceTypes";

export type EnvelopeChipProps = {
  /** Owner-supplied purpose, preserved opaquely without grade inference. */
  authorityPurpose: GovernedAuthorityPurpose;
  id?: string;
  title?: string;
};

/** Displays an envelope purpose as neutral context, never as a decision grade. */
export function EnvelopeChip({
  authorityPurpose,
  id,
  title,
}: EnvelopeChipProps) {
  const { fixtureAuthority, value: purpose } =
    governedAuthorityPurposePresentation(authorityPurpose);
  return (
    <Badge
      data-authority-purpose={purpose}
      data-fixture-authority={fixtureAuthority}
      data-presentation-tone="neutral"
      kind="outline"
      id={id}
      title={title}
    >
      {fixtureAuthority ? <span>Fixture only · </span> : null}
      {purpose}
    </Badge>
  );
}
