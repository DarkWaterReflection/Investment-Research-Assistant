import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ReportContext } from "../types";
import Report from "./Report";

const REPORT: ReportContext = {
  company: "Acme Robotics",
  generated_at: "2026-07-04T12:00:00Z",
  stats: {
    stage: "complete",
    evidence_count: 2,
    quarantined_count: 1,
    merged_count: 1,
    conflict_count: 1,
    total_cost_usd: 0.42,
  },
  executive_summary: "Acme is a fast-growing robotics company.",
  investment_thesis: "Automation demand is durable.",
  strengths: [
    { claim: "European expansion underway", basis: "sourced", confidence: "high", citations: [1] },
  ],
  concerns: [
    { claim: "Funding figures conflict", basis: "inferred", confidence: "medium", citations: [] },
  ],
  open_questions: ["What is the real Series B size?"],
  sections: [
    {
      title: "Funding & Financials",
      summary: "Raised a contested Series B.",
      findings: [
        { claim: "Raised $40M Series B", basis: "sourced", confidence: "high", citations: [2] },
      ],
      warnings: [],
    },
  ],
  conflicts: ["Series B amount disagrees across sources."],
  timeline: [{ date: "2026-05-12", title: "Acme opens Berlin office", category: "news" }],
  sources: [
    {
      number: 1,
      evidence_id: "ev-2",
      title: "Acme opens Berlin office",
      url: "https://news.example/acme-berlin",
      collector: "serpapi",
      published: "2026-05-12",
    },
    {
      number: 2,
      evidence_id: "ev-1",
      title: "Acme raises $40M Series B",
      url: "https://news.example/acme-40m",
      collector: "serpapi",
      published: "2026-06-30",
    },
  ],
  warnings: ["serpapi: no news results"],
};

describe("Report", () => {
  it("renders the memo with citations linked to sources", () => {
    render(<Report report={REPORT} jobId="job-1" />);

    expect(screen.getByText("Investment Memo — Acme Robotics")).toBeDefined();
    expect(screen.getByText("Acme is a fast-growing robotics company.")).toBeDefined();
    expect(screen.getByText("European expansion underway")).toBeDefined();

    const citation = screen.getAllByRole("link", { name: "[1]" })[0];
    expect(citation.getAttribute("href")).toBe("#source-1");

    const source = screen.getByRole("link", { name: "Acme opens Berlin office" });
    expect(source.getAttribute("href")).toBe("https://news.example/acme-berlin");
  });

  it("labels inferred findings and shows conflicts", () => {
    render(<Report report={REPORT} jobId="job-1" />);

    expect(screen.getByText("inferred, medium confidence")).toBeDefined();
    expect(screen.getByText("Series B amount disagrees across sources.")).toBeDefined();
    expect(screen.getByText("1 unresolved conflict(s) between sources.")).toBeDefined();
  });

  it("links the export downloads to the job's report endpoints", () => {
    render(<Report report={REPORT} jobId="job-1" />);

    const markdown = screen.getByRole("link", { name: "Download Markdown" });
    expect(markdown.getAttribute("href")).toBe("/report/job-1?format=markdown");
    const pdf = screen.getByRole("link", { name: "Download PDF" });
    expect(pdf.getAttribute("href")).toBe("/report/job-1/pdf");
  });
});
