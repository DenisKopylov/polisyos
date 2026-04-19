import type { RunDeckSnapshot } from "@/features/runs/domain/compare";
import { AtlasBrand } from "@/shared/brand/AtlasBrand";
import { Badge, Button } from "@/shared/ui";

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
  dependencies: string;
  evidenceEyebrow: string;
  exportSlide: string;
  holdForReview: string;
  metricsEyebrow: string;
  ratifyNow: string;
  recommendation: string;
  tradeoffEyebrow: string;
  verdictEyebrow: string;
  verdictTitle: string;
};

export const DEFAULT_ATLAS_RUN_DECK_COPY: AtlasRunDeckCopy = {
  blockerState: "Blocker state",
  closingEyebrow: "Action window",
  closingTitle: "Next action and comment window",
  confidence: "Confidence",
  dependencies: "Downstream dependencies",
  evidenceEyebrow: "Evidence and dissent",
  exportSlide: "Slide PNG",
  holdForReview: "Hold for review",
  metricsEyebrow: "Real runtime metrics",
  ratifyNow: "Ratify now",
  recommendation: "Recommendation",
  tradeoffEyebrow: "Ratify versus hold",
  verdictEyebrow: "Verdict and recommendation",
  verdictTitle: "Recommendation for the current run",
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
  function renderExportAction(id: AtlasRunDeckSlideId) {
    if (!onExportSlide) {
      return null;
    }
    return (
      <Button
        size="sm"
        type="button"
        variant="ghost"
        onClick={() => void onExportSlide(id)}
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
            <Badge kind="neutral">{deck.verdict.status}</Badge>
            <Badge kind={deck.report.blockerCount === 0 ? "ok" : "warn"}>
              {deck.verdict.blockers}
            </Badge>
          </div>
        </div>
      </DeckSlide>

      <DeckSlide
        action={renderExportAction("verdict")}
        eyebrow={copy.verdictEyebrow}
        id="verdict"
        title={copy.verdictTitle}
      >
        <div className="atlas-deck-grid atlas-deck-grid--two">
          <div className="atlas-deck-spotlight">
            <span>{copy.recommendation}</span>
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
              <strong>{card.value}</strong>
              <Badge kind={card.tone}>{card.tone}</Badge>
            </div>
          ))}
        </div>
      </DeckSlide>

      <DeckSlide
        action={renderExportAction("tradeoff")}
        eyebrow={copy.tradeoffEyebrow}
        id="tradeoff"
        title={deck.tradeoff.title}
      >
        <div className="atlas-deck-grid atlas-deck-grid--two">
          <div className="atlas-deck-lane">
            <p className="eyebrow">{copy.ratifyNow}</p>
            {deck.tradeoff.ratify.map((item) => (
              <p key={item}>{item}</p>
            ))}
          </div>
          <div className="atlas-deck-lane atlas-deck-lane--warn">
            <p className="eyebrow">{copy.holdForReview}</p>
            {deck.tradeoff.hold.map((item) => (
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
