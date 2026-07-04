// Renders the ReportContext JSON as the interactive memo. Citations link to
// the numbered source register; basis and confidence are always visible so
// facts and inferences never blur.

import { markdownUrl, pdfUrl } from "../api";
import type { CitedFinding, ReportContext } from "../types";

function Citations({ numbers }: { numbers: number[] }) {
  if (numbers.length === 0) return null;
  return (
    <sup className="citations">
      {numbers.map((n) => (
        <a key={n} href={`#source-${n}`}>
          [{n}]
        </a>
      ))}
    </sup>
  );
}

function Findings({ findings }: { findings: CitedFinding[] }) {
  if (findings.length === 0) return null;
  return (
    <ul className="findings">
      {findings.map((finding) => (
        <li key={finding.claim}>
          {finding.claim}
          <Citations numbers={finding.citations} />{" "}
          <span className={`basis basis-${finding.basis}`}>
            {finding.basis}, {finding.confidence} confidence
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function Report({ report, jobId }: { report: ReportContext; jobId: string }) {
  const { stats } = report;
  return (
    <article className="report">
      <div className="report-head">
        <h2>Investment Memo — {report.company}</h2>
        <div className="report-actions">
          <a href={markdownUrl(jobId)} download={`${report.company}_memo.md`}>
            Download Markdown
          </a>
          <a href={pdfUrl(jobId)}>Download PDF</a>
        </div>
      </div>
      <p className="meta">
        Status: {stats.stage} · {stats.evidence_count} evidence items · Analysis cost: $
        {stats.total_cost_usd.toFixed(2)}
      </p>

      {report.executive_summary !== null && (
        <section>
          <h3>Executive Summary</h3>
          <p>{report.executive_summary}</p>
        </section>
      )}
      {report.investment_thesis !== null && (
        <section>
          <h3>Investment Thesis</h3>
          <p>{report.investment_thesis}</p>
        </section>
      )}
      {report.strengths.length > 0 && (
        <section>
          <h4>Key Strengths</h4>
          <Findings findings={report.strengths} />
        </section>
      )}
      {report.concerns.length > 0 && (
        <section>
          <h4>Key Concerns</h4>
          <Findings findings={report.concerns} />
        </section>
      )}
      {report.open_questions.length > 0 && (
        <section>
          <h4>Open Questions</h4>
          <ul>
            {report.open_questions.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        </section>
      )}

      {report.sections.map((section) => (
        <section key={section.title}>
          <h3>{section.title}</h3>
          <p>{section.summary}</p>
          <Findings findings={section.findings} />
        </section>
      ))}

      <section>
        <h3>Data Quality</h3>
        <ul>
          <li>
            {stats.evidence_count} evidence item(s) analyzed; {stats.merged_count} duplicate(s)
            merged; {stats.quarantined_count} item(s) quarantined as possibly off-target.
          </li>
          <li>{stats.conflict_count} unresolved conflict(s) between sources.</li>
        </ul>
        {report.conflicts.length > 0 && (
          <>
            <h4>Unresolved Conflicts</h4>
            <ul className="conflicts">
              {report.conflicts.map((conflict) => (
                <li key={conflict}>{conflict}</li>
              ))}
            </ul>
          </>
        )}
      </section>

      {report.timeline.length > 0 && (
        <section>
          <h3>Timeline</h3>
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Event</th>
                <th>Category</th>
              </tr>
            </thead>
            <tbody>
              {report.timeline.map((row) => (
                <tr key={`${row.date}-${row.title}`}>
                  <td>{row.date}</td>
                  <td>{row.title}</td>
                  <td>{row.category}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {report.sources.length > 0 && (
        <section>
          <h3>Sources</h3>
          <ol className="sources">
            {report.sources.map((source) => (
              <li key={source.number} id={`source-${source.number}`} value={source.number}>
                <a href={source.url} target="_blank" rel="noreferrer">
                  {source.title}
                </a>{" "}
                — {source.collector}
                {source.published !== null && `, published ${source.published}`}
              </li>
            ))}
          </ol>
        </section>
      )}

      {report.warnings.length > 0 && (
        <section className="diagnostics">
          <h3>Diagnostics</h3>
          <ul>
            {report.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}
