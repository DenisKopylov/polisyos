import type { AnchorHTMLAttributes } from "react";

import { cn } from "../lib/cn";
import { fixtureAuthorityValue, type FixtureProvenance } from "./evidenceTypes";

type CommonEvidenceLinkProps = {
  /** Opaque producer reference; its presence makes no verification claim. */
  evidenceRef: string;
  fixtureProvenance?: FixtureProvenance;
  id?: string;
  label?: string;
  title?: string;
};

type LinkedEvidenceProps = CommonEvidenceLinkProps & {
  anchorProps?: Pick<
    AnchorHTMLAttributes<HTMLAnchorElement>,
    "download" | "referrerPolicy" | "rel" | "target"
  >;
  href: string;
};

type UnlinkedEvidenceProps = CommonEvidenceLinkProps & {
  anchorProps?: never;
  href?: never;
};

export type EvidenceLinkProps = LinkedEvidenceProps | UnlinkedEvidenceProps;

/** Renders a producer evidence reference without inferring verification. */
export function EvidenceLink(props: EvidenceLinkProps) {
  const {
    anchorProps,
    evidenceRef,
    fixtureProvenance,
    href,
    id,
    label,
    title,
  } = props;
  const fixtureAuthority = fixtureProvenance
    ? fixtureAuthorityValue(fixtureProvenance)
    : undefined;
  const content = (
    <>
      {fixtureAuthority ? <span>Fixture only · </span> : null}
      {label ? <>{label} </> : null}
      <span data-evidence-ref-value={evidenceRef}>{evidenceRef}</span>
    </>
  );
  const shared = {
    "data-evidence-claim": "reference-only",
    "data-evidence-ref": evidenceRef,
    "data-fixture-authority": fixtureAuthority,
  } as const;

  if (href !== undefined) {
    return (
      <a
        {...anchorProps}
        {...shared}
        className={cn(
          "font-mono text-xs break-all underline decoration-dotted underline-offset-2",
        )}
        href={href}
        id={id}
        title={title}
      >
        {content}
      </a>
    );
  }

  return (
    <span
      {...shared}
      className={cn("font-mono text-xs break-all")}
      id={id}
      title={title}
    >
      {content}
    </span>
  );
}
