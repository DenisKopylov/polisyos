import type { ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";

import { cn } from "@/lib/utils";
import { fadeInUp } from "@/shared/ui/motion";

export type ChapterStatus = "pending" | "active" | "completed";

type NarrativeChapterProps = {
  id: string;
  number: number;
  title: string;
  subtitle?: string;
  status?: ChapterStatus;
  children: ReactNode;
  className?: string;
};

const STATUS_ICON: Record<ChapterStatus, string> = {
  pending: "\u25CB",
  active: "\u25D4",
  completed: "\u2713",
};

export function NarrativeChapter({
  id,
  number,
  title,
  subtitle,
  status = "completed",
  children,
  className,
}: NarrativeChapterProps) {
  return (
    <section
      id={id}
      className={cn("scroll-mt-20", className)}
      aria-label={`Chapter ${number}: ${title}`}
    >
      <AnimatePresence>
        <motion.div
          variants={fadeInUp}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-60px" }}
          className="space-y-4"
        >
          {/* Chapter header */}
          <div className="flex items-start gap-4">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-full border-2 border-[var(--chart-primary)] text-sm font-bold text-[var(--chart-primary)]">
              {number}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold">{title}</h2>
                <span
                  className="text-muted text-sm"
                  aria-label={`Status: ${status}`}
                >
                  {STATUS_ICON[status]}
                </span>
              </div>
              {subtitle && (
                <p className="text-muted mt-0.5 text-sm">{subtitle}</p>
              )}
            </div>
          </div>

          {/* Chapter body */}
          <div className="ps-14">{children}</div>
        </motion.div>
      </AnimatePresence>
    </section>
  );
}
