import type { RunDeckSnapshot } from "@/features/runs/domain/compare";
import { AtlasBrand } from "@/shared/brand/AtlasBrand";
import { Quantity } from "@/shared/ui/quantity";
import { Badge, Button } from "@polisyos/atlas-ui";

export type AtlasRunDeckSlideId =
  | "cover"
  | "verdict"
  | "metrics"
  | "tradeoff"
  | "evidence"
  | "closing";

export type AtlasRunDeckCopy = {
  blockerState: string;
  closingEyebrow: string;
  closingTitle: string;
  confidence: string;
  decisionContextEyebrow?: string;
  dependencies: string;
  evidenceEyebrow: string;
  exportSlide: string;
  metricsEyebrow: string;
  ownerDecision?: string;
  ownerDecisionEyebrow?: string;
  ownerDecisionTitle?: string;
  reviewContext?: string;
  supportingOwnerEvidence?: string;
  [presentationKey: string]: string | undefined;
};

export const DEFAULT_ATLAS_RUN_DECK_COPY: AtlasRunDeckCopy = {
  blockerState: "Blocker state",
  closingEyebrow: "Action window",
  closingTitle: "Next action and comment window",
  confidence: "Confidence",
  decisionContextEyebrow: "Decision context",
  dependencies: "Downstream dependencies",
  evidenceEyebrow: "Evidence and dissent",
  exportSlide: "Slide PNG",
  metricsEyebrow: "Real runtime metrics",
  ownerDecision: "Owner decision",
  ownerDecisionEyebrow: "Owner decision",
  ownerDecisionTitle: "Decision label supplied by the owner",
  reviewContext: "Review context",
  supportingOwnerEvidence: "Supporting owner evidence",
};

function DeckSlide({
  action,
  children,
  eyebrow,
  id,
  title,
}: {
  action?: React.ReactNode;
  children: React.ReactNode;
  eyebrow: string;
  id: AtlasRunDeckSlideId;
  title: string;
}) {
  return (
    <section
      className="atlas-deck-slide"
      data-testid={`run-deck-slide-${id}`}
      id={`run-deck-slide-${id}`}
    >
      <div className="atlas-deck-slide__header">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h3>{title}</h3>
        </div>
        {action ? <div className="print:hidden">{action}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function AtlasRunDeck({
  copy = DEFAULT_ATLAS_RUN_DECK_COPY,
  deck,
  deckRef,
  onExportSlide,
  rootId = "run-deck-root",
  testId = "run-deck-page",
}: {
  copy?: AtlasRunDeckCopy;
  deck: RunDeckSnapshot;
  deckRef?: React.Ref<HTMLDivElement>;
  onExportSlide?: (id: AtlasRunDeckSlideId) => void;
  rootId?: string;
  testId?: string;
}) {
  const supportingContext = deck.tradeoff.supportingContext ?? [];
  const reviewContext = deck.tradeoff.reviewContext ?? [];

  function renderExportAction(id: AtlasRunDeckSlideId) {
    if (!onExportSlide) {
      return null;
    }
    return (
      <Button
        size="sm"
        type="button"
        variant="ghost"
        onClick={() => {
          onExportSlide(id);
        }}
      >
        {copy.exportSlide}
      </Button>
    );
  }

  return (
    <div className="atlas-deck" data-testid={testId} id={rootId} ref={deckRef}>
      <DeckSlide
        action={renderExportAction("cover")}
        eyebrow={deck.cover.eyebrow}
        id="cover"
        title={deck.cover.title}
      >
        <div className="atlas-deck-cover">
          <AtlasBrand size={48} variant="mark" />
          <p className="atlas-deck-cover__subtitle">{deck.cover.subtitle}</p>
          <p className="atlas-deck-cover__headline">{deck.verdict.headline}</p>
          <div className="atlas-deck-pill-row">
            {deck.fixture_authority !== undefined ? (
              <Badge
                data-fixture-authority={deck.fixture_authority}
                data-testid="atlas-fixture-authority"
                kind="warn"
              >
                {deck.fixture_authority}
              </Badge>
            ) : null}
            <Badge kind="neutral">{deck.verdict.status}</Badge>
            <Badge kind="neutral">{deck.verdict.blockers}</Badge>
          </div>
        </div>
      </DeckSlide>

      <DeckSlide
        action={renderExportAction("verdict")}
        eyebrow={
          copy.ownerDecisionEyebrow ??
          DEFAULT_ATLAS_RUN_DECK_COPY.ownerDecisionEyebrow ??
          "Owner decision"
        }
        id="verdict"
        title={
          copy.ownerDecisionTitle ??
          DEFAULT_ATLAS_RUN_DECK_COPY.ownerDecisionTitle ??
          "Decision label supplied by the owner"
        }
      >
        <div className="atlas-deck-grid atlas-deck-grid--two">
          <div className="atlas-deck-spotlight">
            <span>
              {copy.ownerDecision ??
                DEFAULT_ATLAS_RUN_DECK_COPY.ownerDecision ??
                "Owner decision"}
            </span>
            <strong>{deck.verdict.verdict}</strong>
            <p>{deck.verdict.headline}</p>
          </div>
          <div className="atlas-deck-stack">
            <div className="compact-metric">
              <span>{copy.confidence}</span>
              <strong>{deck.verdict.confidence}</strong>
            </div>
            <div className="compact-metric">
              <span>{copy.blockerState}</span>
              <strong>{deck.verdict.blockers}</strong>
            </div>
          </div>
        </div>
      </DeckSlide>

      <DeckSlide
        action={renderExportAction("metrics")}
        eyebrow={copy.metricsEyebrow}
        id="metrics"
        title={deck.metrics.title}
      >
        <div className="atlas-deck-grid atlas-deck-grid--metrics">
          {deck.metrics.cards.map((card) => (
            <div key={card.label} className="atlas-deck-stat">
              <span>{card.label}</span>
              <strong>
                {card.kind === "quantity" ? (
                  <span data-quantity-metric-id={card.quantity.metric_id}>
                    <Quantity value={card.quantity} variant="dense" />
                  </span>
                ) : (
                  card.value
                )}
              </strong>
            </div>
          ))}
        </div>
        {deck.report.impactRows.length > 0 ? (
          <div className="atlas-deck-grid atlas-deck-grid--metrics mt-4">
            {deck.report.impactRows.map((row) => (
              <div key={row.label} className="atlas-deck-stat">
                <span>{row.label}</span>
                <strong>
                  <Quantity value={row.quantity} variant="dense" />
                </strong>
              </div>
            ))}
          </div>
        ) : null}
      </DeckSlide>

      <DeckSlide
        action={renderExportAction("tradeoff")}
        eyebrow={
          copy.decisionContextEyebrow ??
          DEFAULT_ATLAS_RUN_DECK_COPY.decisionContextEyebrow ??
          "Decision context"
        }
        id="tradeoff"
        title={deck.tradeoff.title}
      >
        <div className="atlas-deck-grid atlas-deck-grid--two">
          <div className="atlas-deck-lane">
            <p className="eyebrow">
              {copy.supportingOwnerEvidence ??
                DEFAULT_ATLAS_RUN_DECK_COPY.supportingOwnerEvidence ??
                "Supporting owner evidence"}
            </p>
            {supportingContext.map((item) => (
              <p key={item}>{item}</p>
            ))}
          </div>
          <div className="atlas-deck-lane">
            <p className="eyebrow">
              {copy.reviewContext ??
                DEFAULT_ATLAS_RUN_DECK_COPY.reviewContext ??
                "Review context"}
            </p>
            {reviewContext.map((item) => (
              <p key={item}>{item}</p>
            ))}
          </div>
        </div>
      </DeckSlide>

      <DeckSlide
        action={renderExportAction("evidence")}
        eyebrow={copy.evidenceEyebrow}
        id="evidence"
        title={deck.evidence.title}
      >
        <div className="atlas-deck-grid atlas-deck-grid--evidence">
          <blockquote className="atlas-deck-quote">
            “{deck.evidence.quote}”
          </blockquote>
          <div className="atlas-deck-stack">
            <p>{deck.evidence.body}</p>
            <Badge kind="neutral">{deck.evidence.provenance}</Badge>
          </div>
        </div>
      </DeckSlide>

      <DeckSlide
        action={renderExportAction("closing")}
        eyebrow={copy.closingEyebrow}
        id="closing"
        title={copy.closingTitle}
      >
        <div className="atlas-deck-grid atlas-deck-grid--two">
          <div className="atlas-deck-closing">
            <AtlasBrand size={48} variant="mark" />
            <p className="atlas-deck-cover__headline">
              {deck.close.nextAction}
            </p>
            <p>{deck.close.commentWindow}</p>
          </div>
          <div className="atlas-deck-lane">
            <p className="eyebrow">{copy.dependencies}</p>
            {deck.close.downstreamDependencies.map((item) => (
              <p key={item}>{item}</p>
            ))}
          </div>
        </div>
      </DeckSlide>
    </div>
  );
}
