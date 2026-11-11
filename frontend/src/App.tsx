import { useEffect, useState, type FormEvent } from 'react'
import CoverageDashboard from './CoverageDashboard'
import TitleSignalsDashboard from './TitleSignalsDashboard'
import HistoricalActivityDashboard from './HistoricalActivityDashboard'
import './styles.css'

type ApiStatus = 'checking' | 'online' | 'offline'
type PostingsStatus = 'loading' | 'ready' | 'disabled' | 'error'

type Posting = {
  id: number
  employer: { id: number; name: string }
  title: string
  location_raw: string | null
  source: {
    platform: string
    board_token: string
    external_posting_id: string
    url: string
  }
  first_published_at: string | null
  source_updated_at: string | null
  first_seen_at: string
  last_seen_at: string
}

type PostingsPage = {
  data_scope: 'synthetic_only'
  counting_rule: 'distinct_source_postings'
  total: number
  limit: number
  offset: number
  next_offset: number | null
  latest_observed_at: string | null
  page_sources: { platform: string; board_token: string; employer: string }[]
  items: Posting[]
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

function isPostingsPage(value: unknown): value is PostingsPage {
  if (!value || typeof value !== 'object') return false
  const page = value as Record<string, unknown>
  return page.data_scope === 'synthetic_only'
    && page.counting_rule === 'distinct_source_postings'
    && typeof page.total === 'number'
    && Number.isInteger(page.total)
    && typeof page.limit === 'number'
    && typeof page.offset === 'number'
    && (page.next_offset === null || typeof page.next_offset === 'number')
    && (page.latest_observed_at === null || typeof page.latest_observed_at === 'string')
    && Array.isArray(page.page_sources)
    && Array.isArray(page.items)
    && page.items.every((item) => {
      if (!item || typeof item !== 'object') return false
      const record = item as Record<string, unknown>
      return typeof record.id === 'number'
        && typeof record.title === 'string'
        && typeof record.last_seen_at === 'string'
        && !!record.employer
        && typeof record.employer === 'object'
        && typeof (record.employer as Record<string, unknown>).name === 'string'
        && !!record.source
        && typeof record.source === 'object'
        && typeof (record.source as Record<string, unknown>).board_token === 'string'
        && typeof (record.source as Record<string, unknown>).url === 'string'
    })
}

function formatTimestamp(value: string | null): string {
  if (!value) return 'Not supplied'
  const timestamp = new Date(value)
  if (Number.isNaN(timestamp.getTime())) return 'Invalid timestamp'
  return timestamp.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  })
}

export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking')
  const [postingsStatus, setPostingsStatus] = useState<PostingsStatus>('loading')
  const [page, setPage] = useState<PostingsPage | null>(null)
  const [errorMessage, setErrorMessage] = useState('')
  const [draftEmployer, setDraftEmployer] = useState('')
  const [appliedEmployer, setAppliedEmployer] = useState('')
  const [pageSize, setPageSize] = useState(5)
  const [offset, setOffset] = useState(0)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    fetch(`${apiBaseUrl}/health`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`API responded with ${response.status}`)
        const payload: { status?: string } = await response.json()
        if (payload.status !== 'ok') throw new Error('API health response was invalid')
        if (!controller.signal.aborted) setApiStatus('online')
      })
      .catch(() => {
        if (!controller.signal.aborted) setApiStatus('offline')
      })

    return () => controller.abort()
  }, [refreshKey])

  useEffect(() => {
    const controller = new AbortController()

    async function loadPostings() {
      setPostingsStatus('loading')
      setPage(null)
      setErrorMessage('')

      const query = new URLSearchParams({
        limit: String(pageSize),
        offset: String(offset),
      })
      if (appliedEmployer) query.set('employer', appliedEmployer)

      try {
        const response = await fetch(`${apiBaseUrl}/api/v1/postings?${query}`, {
          signal: controller.signal,
        })

        if (controller.signal.aborted) return
        if (response.status === 503) {
          setPostingsStatus('disabled')
          return
        }
        if (!response.ok) {
          throw new Error(`Postings endpoint responded with HTTP ${response.status}`)
        }

        const result: unknown = await response.json()
        if (!isPostingsPage(result)) {
          throw new Error('The API returned an unexpected postings response.')
        }

        if (!controller.signal.aborted) {
          setPage(result)
          setPostingsStatus('ready')
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setErrorMessage(error instanceof Error ? error.message : 'Unable to fetch postings.')
          setPostingsStatus('error')
        }
      }
    }

    void loadPostings()
    return () => controller.abort()
  }, [pageSize, offset, appliedEmployer, refreshKey])

  function submitEmployer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const next = draftEmployer.trim()
    if (next === appliedEmployer) {
      setRefreshKey((key) => key + 1)
    } else {
      setAppliedEmployer(next)
    }
    setOffset(0)
  }

  function filterByEmployer(name: string) {
    setDraftEmployer(name)
    setAppliedEmployer(name)
    setOffset(0)
  }

  function clearEmployer() {
    setDraftEmployer('')
    setAppliedEmployer('')
    setOffset(0)
  }

  const statusLabel: Record<ApiStatus, string> = {
    checking: 'Checking API',
    online: 'API online',
    offline: 'API unavailable',
  }

  const pageStart = page && page.total > 0 ? page.offset + 1 : 0
  const pageEnd = page ? Math.min(page.offset + page.items.length, page.total) : 0

  return (
    <main className="page">
      <header className="header">
        <div className="wordmark">DWI <span>/</span> ANALYTICS</div>
        <div className="header-actions">
          <span className="release-tag">DEVELOPMENT PREVIEW</span>
          <span className="data-pill"><span className="data-pill-dot" /> SYNTHETIC DATA</span>
        </div>
      </header>

      <section className="hero" aria-labelledby="hero-heading">
        <p className="eyebrow">DEFENSE WORKFORCE INTELLIGENCE</p>
        <h1 id="hero-heading">Explore workforce signals.</h1>
        <p className="intro">
          A source-attributed foundation for analyzing advertised technical roles.
          This preview uses synthetic test records only—not real vacancies or hiring activity.
        </p>
        <div className="environment-bar">
          <div className="environment-heading">Local environment</div>
          <div className="status-line">
            <span className={`status-dot ${apiStatus}`} aria-hidden="true" />
            <span role="status">{statusLabel[apiStatus]}</span>
          </div>
          <span className="environment-note">API health does not confirm database readiness.</span>
        </div>
      </section>

      <section className="explorer" aria-labelledby="explorer-heading">
        <div className="section-topline">
          <div>
            <p className="eyebrow section-eyebrow">DATA EXPLORER / V1</p>
            <h2 id="explorer-heading">Postings explorer</h2>
            <p className="section-description">
              Browse stored synthetic posting observations with source-level traceability.
            </p>
          </div>
          <button
            className="refresh-button"
            type="button"
            disabled={postingsStatus === 'loading'}
            onClick={() => setRefreshKey((key) => key + 1)}
          >
            Refresh data
          </button>
        </div>

        <div className="metrics" aria-label="Posting dataset overview">
          <div className="metric">
            <span className="metric-label">Matching records</span>
            <strong className="metric-value">{page ? page.total.toLocaleString() : '—'}</strong>
            <span className="metric-subtext">Source-specific postings</span>
          </div>
          <div className="metric">
            <span className="metric-label">Sources on page</span>
            <strong className="metric-value">{page ? page.page_sources.length : '—'}</strong>
            <span className="metric-subtext">Not total source coverage</span>
          </div>
          <div className="metric metric-date">
            <span className="metric-label">Latest stored observation</span>
            <strong className="metric-value metric-value-date">{page ? formatTimestamp(page.latest_observed_at) : '—'}</strong>
            <span className="metric-subtext">Not a vacancy verification</span>
          </div>
        </div>

        <form className="filters" onSubmit={submitEmployer}>
          <label className="field" htmlFor="employer-filter">
            <span>Employer (exact name)</span>
            <input
              id="employer-filter"
              type="text"
              maxLength={200}
              value={draftEmployer}
              onChange={(event) => setDraftEmployer(event.target.value)}
              placeholder="e.g. Synthetic CI Employer…"
            />
          </label>
          <button className="primary-button" type="submit">Apply filter</button>
          <button className="secondary-button" type="button" onClick={clearEmployer} disabled={!draftEmployer && !appliedEmployer}>
            Clear
          </button>
          <label className="page-size-field" htmlFor="page-size">
            <span>Rows per page</span>
            <select
              id="page-size"
              value={pageSize}
              onChange={(event) => {
                setPageSize(Number(event.target.value))
                setOffset(0)
              }}
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={25}>25</option>
            </select>
          </label>
        </form>

        {appliedEmployer && <p className="active-filter">Filtered to: <strong>{appliedEmployer}</strong></p>}

        {postingsStatus === 'loading' && (
          <div className="message-panel" role="status">
            <span className="loading-dot" aria-hidden="true" />
            Retrieving synthetic postings from the local API…
          </div>
        )}

        {postingsStatus === 'disabled' && (
          <div className="message-panel message-warning" role="status">
            <strong>Postings API is disabled.</strong>
            <p>
              In your local FastAPI terminal, set <code>DWI_POSTINGS_API_ENABLED=1</code>,
              connect to the isolated <code>dwi_ingestion_test</code> database, and restart the API.
              Never enable this development endpoint on a public deployment.
            </p>
          </div>
        )}

        {postingsStatus === 'error' && (
          <div className="message-panel message-error" role="alert">
            <strong>Could not load postings.</strong>
            <p>{errorMessage}</p>
            <p>Confirm FastAPI is running locally and that the test database is available.</p>
          </div>
        )}

        {postingsStatus === 'ready' && page && (
          <>
            {page.items.length === 0 ? (
              <div className="message-panel" role="status">
                <strong>No matching synthetic postings.</strong>
                <p>
                  {appliedEmployer
                    ? 'Check the exact employer name or clear your filter.'
                    : page.total > 0
                      ? 'This page is beyond the end of the dataset. Return to an earlier page.'
                      : 'Run the local synthetic PostgreSQL smoke test to seed records.'}
                </p>
              </div>
            ) : (
              <div className="table-scroll" role="region" aria-label="Synthetic postings results" tabIndex={0}>
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Posting</th>
                      <th scope="col">Employer / source</th>
                      <th scope="col">Location</th>
                      <th scope="col">Last observed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {page.items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <div className="posting-title">{item.title}</div>
                          <div className="posting-id">Source ID · {item.source.external_posting_id}</div>
                          <a href={item.source.url} target="_blank" rel="noopener noreferrer" aria-label={`Open source reference for ${item.title} in a new tab`}>
                            Source reference ↗
                          </a>
                        </td>
                        <td>
                          <button
                            className="employer-button"
                            type="button"
                            title="Filter by this exact employer"
                            onClick={() => filterByEmployer(item.employer.name)}
                          >
                            {item.employer.name}
                          </button>
                          <span className="source-token">{item.source.platform} / {item.source.board_token}</span>
                        </td>
                        <td className="muted-cell">{item.location_raw ?? 'Not supplied'}</td>
                        <td className="muted-cell date-cell">{formatTimestamp(item.last_seen_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="pagination">
              <span className="pagination-details" aria-live="polite">
                Showing {pageStart}–{pageEnd} of {page.total.toLocaleString()} matching records
              </span>
              <div className="pagination-actions">
                <button
                  type="button"
                  className="secondary-button"
                  disabled={page.offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - pageSize))}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  disabled={page.next_offset === null}
                  onClick={() => {
                    if (page.next_offset !== null) setOffset(page.next_offset)
                  }}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      <CoverageDashboard
        apiBaseUrl={apiBaseUrl}
        employer={appliedEmployer}
        refreshKey={refreshKey}
        onFilterEmployer={filterByEmployer}
      />

      <TitleSignalsDashboard
        apiBaseUrl={apiBaseUrl}
        employer={appliedEmployer}
        refreshKey={refreshKey}
      />

      <HistoricalActivityDashboard
        apiBaseUrl={apiBaseUrl}
        employer={appliedEmployer}
        refreshKey={refreshKey}
        onFilterEmployer={filterByEmployer}
      />

      <aside className="disclaimer">
        <strong>Development data only.</strong> These records were generated by local integration tests.
        Counts are source-specific posting observations, not verified active vacancies, hires, or total labor-market demand.
        Third-party source-use authorization remains unresolved.
      </aside>

      <footer>
        Public-data intelligence · Independent portfolio project · Future Telaryn integration
      </footer>
    </main>
  )
}
