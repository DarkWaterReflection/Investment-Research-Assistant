// Mirrors of the backend API schemas (api/schemas.py and reports/context.py).

export interface JobCreated {
  job_id: string;
  status: string;
  status_url: string;
  report_url: string;
}

export interface StageInfo {
  stage: string;
  duration_seconds: number;
}

export interface JobStatus {
  job_id: string;
  company: string;
  status: "queued" | "running" | "complete" | "partial" | "failed";
  created_at: string;
  stages: StageInfo[];
  warnings: string[];
  total_cost_usd: number;
  report_available: boolean;
  error: string | null;
}

export interface CitedFinding {
  claim: string;
  basis: "sourced" | "inferred" | "assumption";
  confidence: "high" | "medium" | "low";
  citations: number[];
}

export interface ReportSection {
  title: string;
  summary: string;
  findings: CitedFinding[];
  warnings: string[];
}

export interface SourceRef {
  number: number;
  evidence_id: string;
  title: string;
  url: string;
  collector: string;
  published: string | null;
}

export interface TimelineRow {
  date: string;
  title: string;
  category: string;
}

export interface ReportStats {
  stage: string;
  evidence_count: number;
  quarantined_count: number;
  merged_count: number;
  conflict_count: number;
  total_cost_usd: number;
}

export interface ReportContext {
  company: string;
  generated_at: string;
  stats: ReportStats;
  executive_summary: string | null;
  investment_thesis: string | null;
  strengths: CitedFinding[];
  concerns: CitedFinding[];
  open_questions: string[];
  sections: ReportSection[];
  conflicts: string[];
  timeline: TimelineRow[];
  sources: SourceRef[];
  warnings: string[];
}

export interface ResearchInput {
  company: string;
  website?: string;
  ticker?: string;
}
