import type { JobStatus } from "../types";

const STAGE_LABELS: Record<string, string> = {
  collecting: "Collecting evidence",
  validating: "Validating & scoring",
  analyzing: "Analyzing",
  generating: "Generating memo",
};

export default function JobProgress({ status }: { status: JobStatus }) {
  return (
    <section className="progress" aria-live="polite">
      <div className="progress-head">
        <span className={`badge badge-${status.status}`}>{status.status}</span>
        <span className="company">{status.company}</span>
        {status.total_cost_usd > 0 && (
          <span className="cost">${status.total_cost_usd.toFixed(2)}</span>
        )}
      </div>
      {status.stages.length > 0 && (
        <ol className="stages">
          {status.stages.map((stage) => (
            <li key={stage.stage}>
              {STAGE_LABELS[stage.stage] ?? stage.stage}
              <span className="duration"> {stage.duration_seconds.toFixed(1)}s</span>
            </li>
          ))}
        </ol>
      )}
      {status.error !== null && <p className="error-banner">{status.error}</p>}
      {status.warnings.length > 0 && (
        <details className="warnings">
          <summary>{status.warnings.length} warning(s)</summary>
          <ul>
            {status.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
