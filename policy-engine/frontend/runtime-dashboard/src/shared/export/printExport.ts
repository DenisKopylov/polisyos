/**
 * Print and PDF export utility.
 *
 * Provides two strategies:
 * 1. Browser print dialog (window.print) with print-optimized CSS
 * 2. Client-side PDF generation using the browser's print-to-PDF capability
 *
 * For more advanced PDF generation (custom headers, charts as images),
 * a future iteration can integrate jspdf + html2canvas.
 */

import { formatDate } from "@/lib/utils";
import { trackExportTriggered } from "@/shared/telemetry/extendedEvents";

export type PrintOptions = {
  /** Title for the printed document. */
  title?: string;
  /** CSS selector for the content to print. If omitted, prints the full page. */
  contentSelector?: string;
  /** Whether to include a timestamp in the header. */
  includeTimestamp?: boolean;
  /** Callback before print (e.g., expand collapsed sections). */
  onBeforePrint?: () => void;
  /** Callback after print. */
  onAfterPrint?: () => void;
};

/**
 * Trigger the browser's print dialog with print-optimized styles.
 *
 * The CSS @media print rules in styles.css handle layout cleanup:
 * - Hides sidebar, nav, actions
 * - Removes borders, shadows, backgrounds
 * - Shows link URLs inline
 */
export function triggerPrint(options?: PrintOptions): void {
  trackExportTriggered("pdf");

  const originalTitle = document.title;

  if (options?.title) {
    document.title = options.title;
  }

  if (options?.includeTimestamp) {
    const timestamp = formatDate(Date.now());
    const meta = document.createElement("meta");
    meta.name = "print-timestamp";
    meta.content = timestamp;
    document.head.appendChild(meta);
  }

  options?.onBeforePrint?.();

  // If a content selector is specified, temporarily hide everything else
  let hiddenElements: HTMLElement[] = [];
  if (options?.contentSelector) {
    const content = document.querySelector(options.contentSelector);
    if (content) {
      hiddenElements = Array.from(
        document.body.children,
      ).filter(
        (el): el is HTMLElement =>
          el instanceof HTMLElement && !el.contains(content) && el !== content,
      );
      hiddenElements.forEach((el) => {
        el.dataset.printHidden = el.style.display;
        el.style.display = "none";
      });
    }
  }

  window.print();

  // Restore hidden elements
  hiddenElements.forEach((el) => {
    el.style.display = el.dataset.printHidden ?? "";
    delete el.dataset.printHidden;
  });

  if (options?.title) {
    document.title = originalTitle;
  }

  options?.onAfterPrint?.();
}

/**
 * Export a DOM element's content as a downloadable PNG screenshot.
 *
 * Uses the Canvas API to render HTML content.
 * For complex layouts, html2canvas can be added as a dependency.
 */
export function exportElementAsImage(
  element: HTMLElement,
  filename = "export.png",
): Promise<void> {
  trackExportTriggered("png");

  const { width, height } = element.getBoundingClientRect();
  if (width <= 0 || height <= 0) {
    return Promise.reject(new Error("Cannot export an element with zero size"));
  }

  const clone = element.cloneNode(true) as HTMLElement;
  const pixelRatio =
    typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
      <foreignObject width="100%" height="100%">
        <div
          xmlns="http://www.w3.org/1999/xhtml"
          style="width:${width}px;height:${height}px;overflow:hidden;"
        >
          ${clone.outerHTML}
        </div>
      </foreignObject>
    </svg>
  `;

  const svgBlob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
  const svgUrl = URL.createObjectURL(svgBlob);

  const image = new Image();
  image.decoding = "async";

  const canvas = document.createElement("canvas");
  canvas.width = Math.ceil(width * pixelRatio);
  canvas.height = Math.ceil(height * pixelRatio);
  const context = canvas.getContext("2d");
  if (!context) {
    URL.revokeObjectURL(svgUrl);
    return Promise.reject(new Error("Canvas 2D context is unavailable"));
  }

  context.scale(pixelRatio, pixelRatio);

  return new Promise<void>((resolve, reject) => {
    image.onload = () => {
      try {
        context.clearRect(0, 0, width, height);
        context.drawImage(image, 0, 0, width, height);
        canvas.toBlob((blob) => {
          URL.revokeObjectURL(svgUrl);
          if (!blob) {
            reject(new Error("PNG rasterization failed"));
            return;
          }

          const pngUrl = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.download = filename;
          link.href = pngUrl;
          link.click();
          URL.revokeObjectURL(pngUrl);
          resolve();
        }, "image/png");
      } catch (error) {
        URL.revokeObjectURL(svgUrl);
        reject(
          error instanceof Error
            ? error
            : new Error("PNG export failed while drawing the canvas"),
        );
      }
    };
    image.onerror = () => {
      URL.revokeObjectURL(svgUrl);
      reject(new Error("PNG rasterization failed"));
    };
    image.src = svgUrl;
  });
}
