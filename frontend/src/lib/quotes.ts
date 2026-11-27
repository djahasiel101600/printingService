import type {
  ColorAnalysis,
  EstimateFile,
  PrintColorMode,
  PrintSpecification,
} from "./types";

export interface QuoteFileInput {
  page_count: number;
  label: string;
  media_size: string;
  media_type: string;
  color_mode: PrintColorMode;
  color_analysis: ColorAnalysis;
  print_quality: PrintSpecification["print_quality"];
  sides: PrintSpecification["sides"];
  copies: number;
}

/** Carry server-side page analysis into live Auto-mode quotes. */
export function quoteFilesFromEstimate(
  spec: PrintSpecification,
  files: EstimateFile[],
): QuoteFileInput[] {
  return files.map((file) => ({
    page_count: file.page_count,
    label: file.name,
    media_size: spec.media_size,
    media_type: spec.media_type,
    color_mode: spec.color_mode,
    color_analysis: file.color_analysis,
    print_quality: spec.print_quality,
    sides: spec.sides,
    copies: spec.copies,
  }));
}
