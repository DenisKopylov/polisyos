import { PDFDocument } from "pdf-lib";

export type PdfPageGeometry = {
  cropBox: { height: number; width: number; x: number; y: number };
  mediaBox: { height: number; width: number; x: number; y: number };
  pageNumber: number;
};

export async function readPdfPageGeometry(
  bytes: Uint8Array,
): Promise<PdfPageGeometry[]> {
  const document = await PDFDocument.load(bytes);
  const pages = document.getPages();
  if (pages.length === 0) {
    throw new Error("governed run paper PDF contains no pages");
  }
  return pages.map((page, index) => ({
    cropBox: page.getCropBox(),
    mediaBox: page.getMediaBox(),
    pageNumber: index + 1,
  }));
}
