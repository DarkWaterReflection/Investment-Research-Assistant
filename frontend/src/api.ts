// Typed client for the FastAPI backend. All paths are relative: the Vite dev
// server proxies them to :8000, and in production the frontend is served
// behind the same origin as the API.

import type { JobCreated, JobStatus, ReportContext, ResearchInput } from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // non-JSON error body; keep the status line
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export async function startResearch(input: ResearchInput): Promise<JobCreated> {
  const body: Record<string, string> = { company: input.company };
  if (input.website) body.website = input.website;
  if (input.ticker) body.ticker = input.ticker;
  const response = await fetch("/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handle<JobCreated>(response);
}

export async function getStatus(jobId: string): Promise<JobStatus> {
  return handle<JobStatus>(await fetch(`/status/${jobId}`));
}

export async function getReport(jobId: string): Promise<ReportContext> {
  return handle<ReportContext>(await fetch(`/report/${jobId}?format=json`));
}

export const markdownUrl = (jobId: string): string => `/report/${jobId}?format=markdown`;
export const pdfUrl = (jobId: string): string => `/report/${jobId}/pdf`;
