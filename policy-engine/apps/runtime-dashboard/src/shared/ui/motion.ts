import type { Transition, Variants } from "motion/react";
import { motionDurations } from "@polisyos/atlas-ui";

import {
  motionGeometry,
  type MotionGeometry,
} from "@/shared/lib/domain/nonAuthorityNumeric";

type MotionCurve = readonly [
  MotionGeometry,
  MotionGeometry,
  MotionGeometry,
  MotionGeometry,
];

const standardEasing: MotionCurve = [
  motionGeometry(0.2),
  motionGeometry(0),
  motionGeometry(0),
  motionGeometry(1),
];
const decelerateEasing: MotionCurve = [
  motionGeometry(0),
  motionGeometry(0),
  motionGeometry(0),
  motionGeometry(1),
];
const accelerateEasing: MotionCurve = [
  motionGeometry(0.3),
  motionGeometry(0),
  motionGeometry(1),
  motionGeometry(1),
];

/* ── Duration presets (align with CSS tokens) ── */

export const duration = {
  fast: motionDurations.helper.fastMs / 1000,
  moderate: motionDurations.helper.moderateMs / 1000,
  slow: motionDurations.helper.slowMs / 1000,
  emphasis: motionDurations.helper.emphasisMs / 1000,
} as const;

/* ── Easing presets ── */

export const easing = {
  standard: standardEasing,
  decelerate: decelerateEasing,
  accelerate: accelerateEasing,
  spring: { type: "spring", stiffness: 500, damping: 30 } as const,
  springGentle: { type: "spring", stiffness: 300, damping: 25 } as const,
  springBouncy: { type: "spring", stiffness: 600, damping: 20 } as const,
} as const;

/* ── Default transitions ── */

export const transition: Record<string, Transition> = {
  fast: { duration: duration.fast, ease: easing.standard },
  moderate: { duration: duration.moderate, ease: easing.standard },
  slow: { duration: duration.slow, ease: easing.standard },
  spring: easing.spring,
  springGentle: easing.springGentle,
  springBouncy: easing.springBouncy,
};

/* ── Reusable animation variants ── */

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: transition.moderate },
  exit: { opacity: 0, transition: transition.fast },
};

export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: transition.moderate },
  exit: { opacity: 0, y: -4, transition: transition.fast },
};

export const fadeInDown: Variants = {
  hidden: { opacity: 0, y: -8 },
  visible: { opacity: 1, y: 0, transition: transition.moderate },
  exit: { opacity: 0, y: 4, transition: transition.fast },
};

export const fadeInScale: Variants = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: { opacity: 1, scale: 1, transition: transition.moderate },
  exit: { opacity: 0, scale: 0.95, transition: transition.fast },
};

export const slideInRight: Variants = {
  hidden: { opacity: 0, x: 20 },
  visible: { opacity: 1, x: 0, transition: transition.moderate },
  exit: { opacity: 0, x: 20, transition: transition.fast },
};

export const slideInLeft: Variants = {
  hidden: { opacity: 0, x: -20 },
  visible: { opacity: 1, x: 0, transition: transition.moderate },
  exit: { opacity: 0, x: -20, transition: transition.fast },
};

export const expandHeight: Variants = {
  hidden: { opacity: 0, height: 0 },
  visible: {
    opacity: 1,
    height: "auto",
    transition: { ...transition.moderate, height: { duration: duration.slow } },
  },
  exit: {
    opacity: 0,
    height: 0,
    transition: { ...transition.fast, height: { duration: duration.moderate } },
  },
};

/* ── Stagger container ── */

export function staggerContainer(stagger = 0.04): Variants {
  return {
    hidden: {},
    visible: {
      transition: {
        staggerChildren: stagger,
        delayChildren: 0.02,
      },
    },
    exit: {
      transition: {
        staggerChildren: stagger / 2,
        staggerDirection: -1,
      },
    },
  };
}

/* ── Reduced-motion safe wrapper ── */

export function reducedMotion<T extends Variants>(
  variants: T,
): T & { visible: object } {
  const visibleVariant = variants.visible;
  const resolvedVisible =
    typeof visibleVariant === "object" && visibleVariant !== null
      ? visibleVariant
      : {};

  return {
    ...variants,
    visible: {
      ...resolvedVisible,
      transition: { duration: 0 },
    },
  };
}
