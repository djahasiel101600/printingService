import { describe, expect, it } from "vitest";

import { DEFAULT_SPEC } from "@/components/SpecFields";
import { quoteFilesFromEstimate } from "@/lib/quotes";
import type { ColorAnalysis, EstimateFile } from "@/lib/types";

const analysis: ColorAnalysis = {
  version: 1,
  pages: [
    { page: 1, mode: "mono", analyzed: true, color_ratio: 0, max_chroma: 0, confidence: "high" },
    { page: 2, mode: "color", analyzed: true, color_ratio: 0.2, max_chroma: 180, confidence: "high" },
  ],
  complete: true,
  warning: "",
};

const estimateFile: EstimateFile = {
  name: "mixed.pdf",
  file_type: "pdf",
  page_count: 2,
  size: 1234,
  print_ready: true,
  color_analysis: analysis,
};

describe("quoteFilesFromEstimate", () => {
  it("forwards page analysis so Auto quotes price mono and color pages separately", () => {
    const spec = { ...DEFAULT_SPEC, color_mode: "auto" as const, copies: 2, sides: "long" as const };

    expect(quoteFilesFromEstimate(spec, [estimateFile])).toEqual([{
      page_count: 2,
      label: "mixed.pdf",
      media_size: spec.media_size,
      media_type: spec.media_type,
      color_mode: "auto",
      color_analysis: analysis,
      print_quality: spec.print_quality,
      sides: "long",
      copies: 2,
    }]);
  });
});
