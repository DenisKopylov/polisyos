import { cn } from "@/shared/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@polisyos/atlas-ui";

export type MethodologyKey = string;

type MethodologyInfo = {
  short: string;
  full: string;
  description: string;
};

const METHODOLOGY_MAP: Record<string, MethodologyInfo> = {
  did: {
    short: "DiD",
    full: "Difference-in-Differences",
    description:
      "Compares treated vs control groups before and after an intervention, relying on parallel trends assumption.",
  },
  sc: {
    short: "SC",
    full: "Synthetic Control",
    description:
      "Constructs a weighted combination of untreated units to approximate the counterfactual for the treated unit.",
  },
  tmle: {
    short: "TMLE",
    full: "Targeted Maximum Likelihood Estimation",
    description:
      "Doubly robust estimator combining outcome modeling and propensity scoring for causal effect estimation.",
  },
  dml: {
    short: "DML",
    full: "Double Machine Learning",
    description:
      "Uses ML for nuisance parameter estimation with cross-fitting to achieve valid causal inference.",
  },
  iv: {
    short: "IV",
    full: "Instrumental Variables",
    description:
      "Exploits an exogenous instrument correlated with treatment but not directly with outcome to identify causal effects.",
  },
  rdd: {
    short: "RDD",
    full: "Regression Discontinuity Design",
    description:
      "Compares outcomes just above and below a treatment threshold, leveraging quasi-random assignment near the cutoff.",
  },
  bsts: {
    short: "BSTS",
    full: "Bayesian Structural Time Series",
    description:
      "Builds a Bayesian time-series model of the counterfactual to estimate the causal impact of an intervention.",
  },
  meta_learner: {
    short: "Meta-L",
    full: "Meta-Learner (HTE)",
    description:
      "Estimates heterogeneous treatment effects across subgroups using S/T/X-learner architectures.",
  },
  ols: {
    short: "OLS",
    full: "Ordinary Least Squares",
    description:
      "Standard linear regression; only causal under strict exogeneity and correct functional form assumptions.",
  },
};

type MethodologyBadgeProps = {
  methodology: MethodologyKey;
  className?: string;
};

export function MethodologyBadge({
  methodology,
  className,
}: MethodologyBadgeProps) {
  const info = METHODOLOGY_MAP[methodology.toLowerCase()] ?? {
    short: methodology,
    full: methodology,
    description: "",
  };

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={cn(
              "border-border bg-surface inline-flex cursor-help items-center rounded-lg border px-2 py-1 font-mono text-xs font-semibold tracking-wide",
              className,
            )}
          >
            {info.short}
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-72">
          <p className="font-semibold">{info.full}</p>
          {info.description && (
            <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
              {info.description}
            </p>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
