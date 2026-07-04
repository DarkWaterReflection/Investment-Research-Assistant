// Top-level state machine: idle → running (poll /status) → done | failed.

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, getReport, getStatus, startResearch } from "./api";
import JobProgress from "./components/JobProgress";
import Report from "./components/Report";
import ResearchForm from "./components/ResearchForm";
import type { JobStatus, ReportContext, ResearchInput } from "./types";

const POLL_INTERVAL_MS = 1500;
const TERMINAL = new Set(["complete", "partial", "failed"]);

export default function App() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [report, setReport] = useState<ReportContext | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (timer.current !== null) {
      clearInterval(timer.current);
      timer.current = null;
    }
  }, []);

  const submit = useCallback(
    async (input: ResearchInput) => {
      stopPolling();
      setStatus(null);
      setReport(null);
      setError(null);
      try {
        const created = await startResearch(input);
        setJobId(created.job_id);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not reach the API.");
        setJobId(null);
      }
    },
    [stopPolling],
  );

  useEffect(() => {
    if (jobId === null) return undefined;
    const poll = async () => {
      try {
        const current = await getStatus(jobId);
        setStatus(current);
        if (TERMINAL.has(current.status)) {
          stopPolling();
          if (current.report_available) {
            setReport(await getReport(jobId));
          }
        }
      } catch (err) {
        stopPolling();
        setError(err instanceof ApiError ? err.message : "Lost contact with the API.");
      }
    };
    void poll();
    timer.current = setInterval(() => void poll(), POLL_INTERVAL_MS);
    return stopPolling;
  }, [jobId, stopPolling]);

  const running = status !== null && !TERMINAL.has(status.status);

  return (
    <main className="app">
      <header>
        <h1>Investment Research Assistant</h1>
        <p className="tagline">
          Automated company due diligence — every claim traced to its source.
        </p>
      </header>
      <ResearchForm onSubmit={submit} busy={running || (jobId !== null && status === null)} />
      {error !== null && <div className="error-banner">{error}</div>}
      {status !== null && <JobProgress status={status} />}
      {report !== null && jobId !== null && <Report report={report} jobId={jobId} />}
    </main>
  );
}
