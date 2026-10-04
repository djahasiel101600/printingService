import { describe, expect, it } from "vitest";

import {
  ATTENTION_STATUSES,
  formatBytes,
  formatPageRange,
  parsePageRange,
  printJobStatusLabel,
} from "@/lib/constants";
import { formatDateTime, formatPeso } from "@/lib/utils";

/**
 * Characterisation tests. These pin the CURRENT behaviour of the pure
 * helpers so later refactors (the order-flow consolidation, the admin workbench)
 * cannot silently change page-range parsing or money formatting.
 */

describe("formatPeso", () => {
  it("always shows two decimals", () => {
    expect(formatPeso(5)).toBe("₱5.00");
    expect(formatPeso(0)).toBe("₱0.00");
  });

  it("groups thousands — the reason pages must stop using toFixed(2)", () => {
    expect(formatPeso(1234)).toBe("₱1,234.00");
    expect(formatPeso(1234.5)).toBe("₱1,234.50");
  });
});

describe("formatDateTime", () => {
  it("falls back to an em dash for missing values", () => {
    expect(formatDateTime(null)).toBe("—");
    expect(formatDateTime(undefined)).toBe("—");
    expect(formatDateTime("")).toBe("—");
  });
});

describe("formatPageRange", () => {
  it("collapses runs and keeps single pages", () => {
    expect(formatPageRange([1, 2, 3, 7])).toBe("1-3, 7");
    expect(formatPageRange([5])).toBe("5");
  });

  it("sorts, dedupes and handles empty input", () => {
    expect(formatPageRange([7, 1, 3, 2])).toBe("1-3, 7");
    expect(formatPageRange([2, 2, 2])).toBe("2");
    expect(formatPageRange([])).toBe("");
  });
});

describe("parsePageRange", () => {
  it("expands ranges, commas and loose spacing", () => {
    expect(parsePageRange("1-3, 5", 10)).toEqual([1, 2, 3, 5]);
    expect(parsePageRange(" 2 - 4 ", 10)).toEqual([2, 3, 4]);
  });

  it("treats an empty input as no pages, not an error", () => {
    expect(parsePageRange("", 10)).toEqual([]);
    expect(parsePageRange("   ", 10)).toEqual([]);
  });

  it("rejects malformed and out-of-range input with null", () => {
    expect(parsePageRange("abc", 10)).toBeNull();
    expect(parsePageRange("1,,2", 10)).toBeNull();
    expect(parsePageRange("3-1", 10)).toBeNull();
    expect(parsePageRange("0", 10)).toBeNull();
    expect(parsePageRange("1-99", 10)).toBeNull();
  });

  it("guards against an accidentally enormous pasted range", () => {
    expect(parsePageRange("1-5000", 99999)).toBeNull();
  });
});

describe("formatBytes", () => {
  it("scales units and keeps 0 B exact", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(1024)).toBe("1.0 KB");
    expect(formatBytes(1024 * 1024 * 5)).toBe("5.0 MB");
  });
});

describe("ATTENTION_STATUSES", () => {
  it("lists exactly the statuses that need a human decision", () => {
    expect(ATTENTION_STATUSES).toEqual([
      "pending_review",
      "revision_requested",
      "on_hold",
      "print_cancelled",
    ]);
  });
});

describe("printJobStatusLabel", () => {
  it("prefers the human label over the raw printer state", () => {
    expect(printJobStatusLabel({ status: "printing" })).toBe("Printing");
    expect(printJobStatusLabel({ status: "printing", status_display: "Ink low" })).toBe("Ink low");
  });

  it("always names a printer-side cancel rather than passing it through", () => {
    expect(printJobStatusLabel({ status: "canceled" })).toBe("Cancelled at printer");
  });
});