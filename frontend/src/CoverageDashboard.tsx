import { useEffect, useState } from 'react'

type LoadStatus = 'loading' | 'ready' | 'disabled' | 'error'

type CoverageMetrics = {
  posting_count: number
  location_present: number
  first_published_at_present: number
  source_updated_at_present: number
  location_coverage_pct: number | null
  published_date_coverage_pct: number | null
  source_update_coverage_pct: number | null
}

type SourceCoverage = {
  platform: string
  board_token: string
  employer: string
  metrics: CoverageMetrics
  latest_observed_at: string | null
}

type CoverageResponse = {
  data_scope: 'synthetic_only'
  counting_rule: 'distinct_source_postings'
  total_sources: number
  total_employers: number
  totals: CoverageMetrics
  latest_observed_at: string | null
  limit: number
  offset: number
  next_offset: number | null
  sources: SourceCoverage[]
}

type Props = {
  apiBaseUrl: string
  employer: string
  refreshKey: number
  onFilterEmployer: (name: string) => void
}

const SOURCE_PAGE_SIZE = 5

function isMetrics(value: unknown): value is CoverageMetrics {
  if (!value || typeof value !== 'object') return false
  const m = value as Record<string, unknown>
  return ['posting_count', 'location_present', 'first_published_at_present', 'source_updated_at_present']
    .every((field) => typeof m[field] === 'number' && Number.isInteger(m[field]) && (m[field] as number) >= 0)
    && ['location_coverage_pct', 'published_date_coverage_pct', 'source_update_coverage_pct']
      .every((field) => m[field] === null || (typeof m[field] === 'number' && Number.isFinite(m[field]) && (m[field] as number) >= 0 && (m[field] as number) <= 100))
}

function isCoverageResponse(value: unknown): value is CoverageResponse {
  if (!value || typeof value !== 'object') return false
  const page = value as Record<string, unknown>
  return page.data_scope === 'synthetic_only'
    && page.counting_rule === 'distinct_source_postings'
    && typeof page.total_sources === 'number'
    && Number.isInteger(page.total_sources) && page.total_sources >= 0
    && typeof page.total_employers === 'number'
    && Number.isInteger(page.total_employers) && page.total_employers >= 0
    && typeof page.limit === 'number'
    && typeof page.offset === 'number'
    && (page.next_offset === null || typeof page.next_offset === 'number')
    && (page.latest_observed_at === null || typeof page.latest_observed_at === 'string')
    && isMetrics(page.totals)
    && Array.isArray(page.sources)
    && page.sources.every((item: unknown) => {
      if (!item || typeof item !== 'object') return false
      const source = item as Record<string, unknown>
      return typeof source.platform === 'string'
        && typeof source.board_token === 'string'
        && typeof source.employer === 'string'
        && (source.latest_observed_at === null || typeof source.latest_observed_at === 'string')
        && isMetrics(source.metrics)
    })
}

function formatPercent(value: number | null): string {
  return value === null ? 'N/A' : `${value.toFixed(1)}%`
}

function formatSeen(value: string | null): string {
  if (!value) return 'Not yet observed'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Unrecognized date'
    : date.toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })
}

function CompletenessBar({ name, percent, count, total }: {
  name: string
  percent: number | null
  count: number
  total: number
}) {
  return (
    <div className="dq-completeness">
      <div className="dq-completeness-top">
        <span className="dq-completeness-label">{name}</span>
        <strong className="dq-completeness-value">{formatPercent(percent)}</strong>
      </div>
      <div className="dq-bar-track" aria-hidden="true">
        <span className="dq-bar-fill" style={{ width: `${percent ?? 0}%` }} />
      </div>
      <span className="dq-completeness-detail">
        {total > 0 ? `${count.toLocaleString()} of ${total.toLocaleString()} records` : 'No records for calculation'}
      </span>
    </div>
  )
}

export default function CoverageDashboard({ apiBaseUrl, employer, refreshKey, onFilterEmployer }: Props) {
  const [status, setStatus] = useState<LoadStatus>('loading')
  const [report, setReport] = useState<CoverageResponse | null>(null)
  const [error, setError] = useState('')
  const [offset, setOffset] = useState(0)
  const [localRefresh, setLocalRefresh] = useState(0)

  useEffect(() => {
    setOffset(0)
  }, [employer])

  useEffect(() => {
    const controller = new AbortController()

    async function fetchCoverage() {
      setStatus('loading')
      setError('')
      setReport(null)
      const query = new URLSearchParams({
        limit: String(SOURCE_PAGE_SIZE),
        offset: String(offset),
      })
      if (employer) query.set('employer', employer)

      try {
        const response = await fetch(`${apiBaseUrl}/api/v1/coverage?${query}`, {
          signal: controller.signal,
        })
        if (controller.signal.aborted) return
        if (response.status === 503) {
          setStatus('disabled')
          return
        }
        if (!response.ok) throw new Error(`Coverage endpoint returned HTTP ${response.status}.`)
        const payload: unknown = await response.json()
        if (!isCoverageResponse(payload)) throw new Error('Unexpected data-quality API response.')
        if (!controller.signal.aborted) {
          setReport(payload)
          setStatus('ready')
        }
      } catch (cause) {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : 'Unable to load the report.')
          setStatus('error')
        }
      }
    }

    void fetchCoverage()
    return () => controller.abort()
  }, [apiBaseUrl, employer, offset, refreshKey, localRefresh])

  const first = report && report.total_sources > 0 ? report.offset + 1 : 0
  const last = report ? Math.min(report.offset + report.sources.length, report.total_sources) : 0

  return (
    <section className="dq-section" aria-labelledby="dq-title">
      <div className="section-topline">
        <div>
          <p className="eyebrow section-eyebrow">DATA QUALITY / V1</p>
          <h2 id="dq-title">Source coverage &amp; completeness</h2>
          <p className="section-description">
            Measure stored metadata completeness—not the share of defense jobs captured.
            {employer && <span className="dq-filter-note"> Filtered to: <strong>{employer}</strong></span>}
          </p>
        </div>
        <button
          className="refresh-button"
          type="button"
          disabled={status === 'loading'}
          onClick={() => setLocalRefresh((n) => n + 1)}
        >
          Refresh quality
        </button>
      </div>

      {status === 'loading' && (
        <div className="message-panel" role="status">
          <span className="loading-dot" aria-hidden="true" />
          Calculating synthetic source coverage…
        </div>
      )}

      {status === 'disabled' && (
        <div className="message-panel message-warning" role="status">
          <strong>Data Quality API is disabled.</strong>
          <p>Enable the local synthetic-only postings API and connect it to your isolated test database. This feature must not be enabled on a public deployment.</p>
        </div>
      )}

      {status === 'error' && (
        <div className="message-panel message-error" role="alert">
          <strong>Data quality metrics unavailable.</strong>
          <p>{error}</p>
          <p>Confirm the local backend is running the merged coverage API and PostgreSQL is available.</p>
        </div>
      )}

      {status === 'ready' && report && (
        <>
          <div className="dq-overview" aria-label="Filtered source coverage summary">
            <div className="dq-stat">
              <span className="metric-label">Stored postings</span>
              <strong>{report.totals.posting_count.toLocaleString()}</strong>
              <span>Distinct source-posting records</span>
            </div>
            <div className="dq-stat">
              <span className="metric-label">Synthetic sources</span>
              <strong>{report.total_sources.toLocaleString()}</strong>
              <span>Including zero-posting sources</span>
            </div>
            <div className="dq-stat">
              <span className="metric-label">Synthetic employers</span>
              <strong>{report.total_employers.toLocaleString()}</strong>
              <span>Source-specific entities</span>
            </div>
          </div>

          <div className="dq-subsection">
            <div className="dq-heading">
              <h3>Metadata completeness</h3>
              <p>Percentage of stored postings containing each field. No value is inferred.</p>
            </div>
            <div className="dq-completeness-grid">
              <CompletenessBar
                name="Raw location"
                percent={report.totals.location_coverage_pct}
                count={report.totals.location_present}
                total={report.totals.posting_count}
              />
              <CompletenessBar
                name="Source publication date"
                percent={report.totals.published_date_coverage_pct}
                count={report.totals.first_published_at_present}
                total={report.totals.posting_count}
              />
              <CompletenessBar
                name="Source updated timestamp"
                percent={report.totals.source_update_coverage_pct}
                count={report.totals.source_updated_at_present}
                total={report.totals.posting_count}
              />
            </div>
            <p className="dq-asof">
              Latest stored observation: <strong>{formatSeen(report.latest_observed_at)}</strong>.
              This does not confirm whether any posting is currently open.
            </p>
          </div>

          <div className="dq-subsection dq-sources">
            <div className="dq-heading">
              <h3>Source breakdown</h3>
              <p>Counts and completeness by synthetic board. Total metrics above include every matching source, not just this page.</p>
            </div>

            {report.sources.length === 0 ? (
              <div className="dq-empty">
                {report.total_sources === 0
                  ? 'No synthetic sources match the selected employer.'
                  : 'There are no sources on this page. Return to an earlier page.'}
              </div>
            ) : (
              <div className="table-scroll" role="region" aria-label="Source completeness breakdown" tabIndex={0}>
                <table className="dq-table">
                  <thead>
                    <tr>
                      <th scope="col">Employer / source</th>
                      <th scope="col">Postings</th>
                      <th scope="col">Location</th>
                      <th scope="col">Published</th>
                      <th scope="col">Updated</th>
                      <th scope="col">Last observed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.sources.map((source) => (
                      <tr key={`${source.platform}/${source.board_token}`}>
                        <td>
                          <button
                            className="employer-button"
                            type="button"
                            title="Filter both dashboards to this employer"
                            onClick={() => onFilterEmployer(source.employer)}
                          >
                            {source.employer}
                          </button>
                          <span className="source-token">{source.platform} / {source.board_token}</span>
                        </td>
                        <td className="dq-number">{source.metrics.posting_count}</td>
                        <td className="dq-number">{formatPercent(source.metrics.location_coverage_pct)}</td>
                        <td className="dq-number">{formatPercent(source.metrics.published_date_coverage_pct)}</td>
                        <td className="dq-number">{formatPercent(source.metrics.source_update_coverage_pct)}</td>
                        <td className="muted-cell date-cell">{formatSeen(source.latest_observed_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="pagination">
              <span className="pagination-details" aria-live="polite">
                Sources {first}–{last} of {report.total_sources.toLocaleString()}
              </span>
              <div className="pagination-actions">
                <button
                  type="button"
                  className="secondary-button"
                  disabled={offset === 0}
                  onClick={() => setOffset((value) => Math.max(0, value - SOURCE_PAGE_SIZE))}
                >
                  Previous sources
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  disabled={report.next_offset === null}
                  onClick={() => {
                    if (report.next_offset !== null) setOffset(report.next_offset)
                  }}
                >
                  Next sources
                </button>
              </div>
            </div>
          </div>
        </>
      )}
      <div className="dq-footnote">
        <strong>Interpretation:</strong> These percentages describe completeness within the synthetic test database.
        They do not measure the fraction of real workforce demand represented, and they must not be presented as real employer or market trends.
      </div>
    </section>
  )
}
