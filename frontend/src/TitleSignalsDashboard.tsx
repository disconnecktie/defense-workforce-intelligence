import { useEffect, useState } from 'react'

type LoadStatus = 'loading' | 'ready' | 'disabled' | 'error'

type TitleExample = {
  posting_id: number
  platform: string
  board_token: string
  external_posting_id: string
  title: string
  evidence: string
  match_start: number
  match_end: number
}

type TermSignal = {
  term: string
  postings_with_title_mention: number
  examples: TitleExample[]
}

type TitleSignalsReport = {
  data_scope: 'synthetic_only'
  counting_rule: 'distinct_source_postings'
  source_field: 'title_raw'
  interpretation: 'explicit_title_mentions_not_verified_skill_requirements'
  method_version: 'title_keywords_v1'
  postings_scanned: number
  postings_with_any_term: number
  postings_without_any_term: number
  title_mention_rate_pct: number | null
  latest_observed_at: string | null
  terms: TermSignal[]
}

type Props = {
  apiBaseUrl: string
  employer: string
  refreshKey: number
}

const CANONICAL_TERMS = ['Python', 'Kubernetes', 'AWS', 'Azure', 'Docker', 'PostgreSQL', 'React']

function isNonnegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
}

function isExample(value: unknown): value is TitleExample {
  if (!value || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  return isNonnegativeInteger(item.posting_id)
    && typeof item.platform === 'string'
    && typeof item.board_token === 'string'
    && typeof item.external_posting_id === 'string'
    && typeof item.title === 'string'
    && typeof item.evidence === 'string'
    && isNonnegativeInteger(item.match_start)
    && isNonnegativeInteger(item.match_end)
    && item.match_start < item.match_end
    && item.match_end <= item.title.length
    && item.title.slice(item.match_start, item.match_end) === item.evidence
}

function isTitleSignalsReport(value: unknown): value is TitleSignalsReport {
  if (!value || typeof value !== 'object') return false
  const report = value as Record<string, unknown>
  if (report.data_scope !== 'synthetic_only'
    || report.counting_rule !== 'distinct_source_postings'
    || report.source_field !== 'title_raw'
    || report.interpretation !== 'explicit_title_mentions_not_verified_skill_requirements'
    || report.method_version !== 'title_keywords_v1'
    || !isNonnegativeInteger(report.postings_scanned)
    || !isNonnegativeInteger(report.postings_with_any_term)
    || !isNonnegativeInteger(report.postings_without_any_term)
    || report.postings_with_any_term + report.postings_without_any_term !== report.postings_scanned
    || !(report.title_mention_rate_pct === null || (
      typeof report.title_mention_rate_pct === 'number'
      && Number.isFinite(report.title_mention_rate_pct)
      && report.title_mention_rate_pct >= 0
      && report.title_mention_rate_pct <= 100
    ))
    || (report.latest_observed_at !== null && typeof report.latest_observed_at !== 'string')
    || !Array.isArray(report.terms)
    || report.terms.length !== CANONICAL_TERMS.length
  ) return false

  const terms = report.terms as unknown[]
  // Capture validated primitive before entering the callback; mutable object
  // properties are not narrowed across function boundaries by TypeScript.
  const scannedCount = report.postings_scanned as number
  return CANONICAL_TERMS.every((canonical) => terms.some((value) => {
    if (!value || typeof value !== 'object') return false
    const item = value as Record<string, unknown>
    return item.term === canonical
      && isNonnegativeInteger(item.postings_with_title_mention)
      && item.postings_with_title_mention <= scannedCount
      && Array.isArray(item.examples)
      && item.examples.length <= 3
      && item.examples.every(isExample)
  }))
}

function formatPercent(value: number | null): string {
  return value === null ? 'N/A' : value.toFixed(1) + '%'
}

function formatObserved(value: string | null): string {
  if (!value) return 'No observations yet'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Unrecognized timestamp'
    : date.toLocaleString(undefined, {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
      })
}

function EvidenceRow({ example }: { example: TitleExample }) {
  const before = example.title.slice(0, example.match_start)
  const match = example.title.slice(example.match_start, example.match_end)
  const after = example.title.slice(example.match_end)
  return (
    <li className="ts-evidence-row">
      <div className="ts-evidence-title">
        {before}<mark>{match}</mark>{after}
      </div>
      <div className="ts-evidence-meta">
        <span>{example.platform} / {example.board_token}</span>
        <span>Source posting ID: {example.external_posting_id}</span>
        <span>Title characters {example.match_start}–{example.match_end}</span>
      </div>
    </li>
  )
}

export default function TitleSignalsDashboard({ apiBaseUrl, employer, refreshKey }: Props) {
  const [status, setStatus] = useState<LoadStatus>('loading')
  const [report, setReport] = useState<TitleSignalsReport | null>(null)
  const [errorMessage, setErrorMessage] = useState('')
  const [localRefresh, setLocalRefresh] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    async function fetchSignals() {
      setStatus('loading')
      setErrorMessage('')
      setReport(null)

      const query = new URLSearchParams()
      if (employer) query.set('employer', employer)
      const suffix = query.size ? '?' + query.toString() : ''

      try {
        const response = await fetch(apiBaseUrl + '/api/v1/title-signals' + suffix, {
          signal: controller.signal,
        })
        if (controller.signal.aborted) return
        if (response.status === 503) {
          setStatus('disabled')
          return
        }
        if (!response.ok) {
          throw new Error('Technology title signals endpoint returned HTTP ' + response.status + '.')
        }

        const payload: unknown = await response.json()
        if (!isTitleSignalsReport(payload)) {
          throw new Error('Unexpected technology title signals API response.')
        }
        if (!controller.signal.aborted) {
          setReport(payload)
          setStatus('ready')
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setErrorMessage(error instanceof Error ? error.message : 'Unable to load title signals.')
          setStatus('error')
        }
      }
    }

    void fetchSignals()
    return () => controller.abort()
  }, [apiBaseUrl, employer, refreshKey, localRefresh])

  return (
    <section className="ts-section" aria-labelledby="ts-title">
      <div className="section-topline">
        <div>
          <p className="eyebrow section-eyebrow">TECHNOLOGY SIGNALS / TITLE KEYWORDS V1</p>
          <h2 id="ts-title">Technology title mentions</h2>
          <p className="section-description">
            Literal technology terms in synthetic job titles. Not verified skill requirements.
            {employer && <span className="ts-filter-note"> Filtered to: <strong>{employer}</strong></span>}
          </p>
        </div>
        <button
          type="button"
          className="refresh-button"
          disabled={status === 'loading'}
          onClick={() => setLocalRefresh((value) => value + 1)}
        >
          Refresh signals
        </button>
      </div>

      {status === 'loading' && (
        <div className="message-panel" role="status">
          <span className="loading-dot" aria-hidden="true" />
          Checking synthetic title keywords…
        </div>
      )}

      {status === 'disabled' && (
        <div className="message-panel message-warning" role="status">
          <strong>Technology title signals API is disabled.</strong>
          <p>
            Enable the backend's local synthetic-only postings API against the isolated test database.
            This development endpoint must not be enabled on a public deployment.
          </p>
        </div>
      )}

      {status === 'error' && (
        <div className="message-panel message-error" role="alert">
          <strong>Technology title signals unavailable.</strong>
          <p>{errorMessage}</p>
          <p>Confirm the local FastAPI server includes the merged title-signals endpoint.</p>
        </div>
      )}

      {status === 'ready' && report && (
        <>
          <div className="ts-overview" aria-label="Technology title matching summary">
            <div className="ts-stat">
              <span className="metric-label">Stored titles scanned</span>
              <strong>{report.postings_scanned.toLocaleString()}</strong>
              <span>Current distinct source postings</span>
            </div>
            <div className="ts-stat">
              <span className="metric-label">Titles with a term</span>
              <strong>{report.postings_with_any_term.toLocaleString()}</strong>
              <span>{report.postings_without_any_term.toLocaleString()} without a recognized term</span>
            </div>
            <div className="ts-stat">
              <span className="metric-label">Title mention rate</span>
              <strong>{formatPercent(report.title_mention_rate_pct)}</strong>
              <span>Not full job-description coverage</span>
            </div>
          </div>

          {report.postings_scanned === 0 ? (
            <div className="message-panel" role="status">
              <strong>No synthetic titles to analyze.</strong>
              <p>
                {employer
                  ? 'No postings match this exact employer. Clear the employer filter in the Postings Explorer.'
                  : 'Run the local synthetic PostgreSQL smoke test to populate sample titles.'}
              </p>
            </div>
          ) : (
            <div className="ts-breakdown">
              <div className="ts-heading">
                <h3>Recognized technology terms</h3>
                <p>
                  Each bar shows the share of scanned titles mentioning the term. A title can mention several terms,
                  so the percentages are not additive.
                </p>
              </div>
              <div className="ts-term-list" aria-label="Technology term mention counts">
                {report.terms.map((item) => {
                  const percent = report.postings_scanned > 0
                    ? 100 * item.postings_with_title_mention / report.postings_scanned : 0
                  return (
                    <div className="ts-term" key={item.term}>
                      <div className="ts-term-header">
                        <strong>{item.term}</strong>
                        <span className="ts-count">
                          {item.postings_with_title_mention} of {report.postings_scanned} titles
                          <span className="ts-percent"> {percent.toFixed(1)}%</span>
                        </span>
                      </div>
                      <div className="ts-track" aria-hidden="true">
                        <div className="ts-fill" style={{ width: percent + '%' }} />
                      </div>
                      {item.examples.length > 0 ? (
                        <details className="ts-examples">
                          <summary>
                            View {item.examples.length} source-attributed {item.examples.length === 1 ? 'example' : 'examples'}
                            {item.postings_with_title_mention > item.examples.length && ' (sample only)'}
                          </summary>
                          <ul>
                            {item.examples.map((example) => (
                              <EvidenceRow
                                key={example.platform + ':' + example.board_token + ':' + example.external_posting_id}
                                example={example}
                              />
                            ))}
                          </ul>
                        </details>
                      ) : (
                        <p className="ts-no-examples">No explicit matches in these titles.</p>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          <p className="ts-observed">
            Latest stored observation: <strong>{formatObserved(report.latest_observed_at)}</strong>
            <span className="ts-method"> Rule set: {report.method_version}; source field: {report.source_field}</span>
          </p>
        </>
      )}

      <div className="ts-disclaimer">
        <strong>Interpretation:</strong> These are explicit title keyword matches in an isolated synthetic test dataset.
        They are not verified required skills, advertised hiring demand, active openings, or representative defense labor-market trends.
        Source references show matching titles and exact evidence spans, not job descriptions.
      </div>
    </section>
  )
}
