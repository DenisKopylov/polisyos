import { useEffect, useState, type RefObject } from "react";

type ReadingProgressState = {
  activeSectionId: string | null;
  progress: number;
};

function clamp01(value: number) {
  return Math.max(0, Math.min(1, value));
}

export function useReadingProgress(rootRef: RefObject<HTMLElement | null>) {
  const [state, setState] = useState<ReadingProgressState>({
    activeSectionId: null,
    progress: 0,
  });

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    let frame = 0;

    const measure = () => {
      frame = 0;
      const root = rootRef.current;
      if (!root) {
        setState({ activeSectionId: null, progress: 0 });
        return;
      }

      const scrollTop = window.scrollY;
      const scrollable = Math.max(
        1,
        document.documentElement.scrollHeight - window.innerHeight,
      );
      const sectionNodes = Array.from(
        root.querySelectorAll<HTMLElement>("[data-reading-section-id]"),
      );

      let activeSectionId = sectionNodes[0]?.dataset.readingSectionId ?? null;
      for (const node of sectionNodes) {
        const top = node.getBoundingClientRect().top;
        if (top <= window.innerHeight * 0.28) {
          activeSectionId = node.dataset.readingSectionId ?? activeSectionId;
        }
      }

      setState({
        activeSectionId,
        progress: clamp01(scrollTop / scrollable),
      });
    };

    const requestMeasure = () => {
      if (frame !== 0) {
        return;
      }
      frame = window.requestAnimationFrame(measure);
    };

    requestMeasure();
    window.addEventListener("scroll", requestMeasure, { passive: true });
    window.addEventListener("resize", requestMeasure);

    return () => {
      if (frame !== 0) {
        window.cancelAnimationFrame(frame);
      }
      window.removeEventListener("scroll", requestMeasure);
      window.removeEventListener("resize", requestMeasure);
    };
  }, [rootRef]);

  return state;
}
