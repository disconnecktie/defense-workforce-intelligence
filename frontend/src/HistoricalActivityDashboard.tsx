import { useEffect, useMemo, useState, type FormEvent } from 'react'

type LoadStatus = 'loading' | 'ready' | 'disabled' | 'error'

type IngestionRun = {
  run_id: number
  employer: string
  platform: string
  board_token: string
  started_at: string
  finished_at: string | null
  status: string
  fetched: number
  inserted: number
  updated: number
  unchanged: number
  rejected: number
  errors: number
  duration_ms: number | null
}

type HistoryPage = {
  data_scope: 'synthetic_only'
  counting_rule: 'ingestion_runs_not_vacancies'
  total: number
  limit: number
  offset: number
  next_offset: number | null
  items: IngestionRun[]
}

type Props = {
  apiBaseUrl: string
  employer: string
  refreshKey: number
  onFilterEmployer: (name: string) => void
}

const PAGE_SIZE = 10

function isNonnegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}

function isHistoryPage(value: unknown): value is HistoryPage {
  if (!value || typeof value !== 'object') return false
  const page = value as Record<string, unknown>
  return page.data_scope === 'synthetic_only'
    && page.counting_rule === 'ingestion_runs_not_vacancies'
    && isNonnegativeInteger(page.total)
    && isNonnegativeInteger(page.offset)
    && isNonnegativeInteger(page.limit) && page.limit >= 1 && page.limit <= 100
    && (page.next_offset === null || isNonnegativeInteger(page.next_offset))
    && Array.isArray(page.items)
    && page.items.length <= page.limit
    && page.items.every((entry: unknown) => {
      if (!entry || typeof entry !== 'object') return false
      const run = entry as Record<string, unknown>
      return isNonnegativeInteger(run.run_id)
        && typeof run.employer === 'string'
        && typeof run.platform === 'string'
        && typeof run.board_token === 'string'
        && typeof run.started_at === 'string'
        && (run.finished_at === null || typeof run.finished_at === 'string')
        && typeof run.status === 'string'
        && ['fetched', 'inserted', 'updated', 'unchanged', 'rejected', 'errors']
          .every((field) => isNonnegativeInteger(run[field]))
        && (run.duration_ms === null || isNonnegativeInteger(run.duration_ms))
    })
}

function formatDate(value: string | null): string {
  if (!value) return 'Not supplied'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Invalid timestamp'
    : date.toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

function dayLabel(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Unrecognized date' : date.toISOString().slice(0, 10)
}

function formatDuration(value: number | null): string {
  return value === null ? 'Not supplied' : `${value.toLocaleString()} ms`
}

export default function HistoricalActivityDashboard({ apiBaseUrl, employer, refreshKey, onFilterEmployer }: Props) {
  const [status, setStatus] = useState<LoadStatus>('loading')
  const [page, setPage] = useState<HistoryPage | null>(null)
  const [offset, setOffset] = useState(0)
  const [errorMessage, setErrorMessage] = useState('')
  const [requestKey, setRequestKey] = useState(0)
  const [draftEmployer, setDraftEmployer] = useState(employer)

  useEffect(() => {
    setDraftEmployer(employer)
    setOffset(0)
  }, [employer])

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      setStatus('loading')
      setPage(null)
      setErrorMessage('')
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) })
      if (employer) params.set('employer', employer)
      try {
        const response = await fetch(`${apiBaseUrl}/api/v1/ingestion-history?${params}`, { signal: controller.signal })
        if (controller.signal.aborted) return
        if (response.status === 503) {
          setStatus('disabled')
          return
        }
        if (!response.ok) throw new Error(`Ingestion history endpoint returned HTTP ${response.status}`)
        const payload: unknown = await response.json()
        if (!isHistoryPage(payload)) throw new Error('Unexpected ingestion history response from the API.')
        if (!controller.signal.aborted) {
          setPage(payload)
          setStatus('ready')
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setErrorMessage(error instanceof Error ? error.message : 'Unable to retrieve ingestion history.')
          setStatus('error')
        }
      }
    }
    void load()
    return () => controller.abort()
  }, [apiBaseUrl, employer, offset, refreshKey, requestKey])

  const metrics = useMemo(() => {
    const rows = page?.items ?? []
    const total = (key: 'fetched' | 'inserted' | 'updated' | 'unchanged' | 'rejected' | 'errors') =>
      rows.reduce((sum, run) => sum + run[key], 0)
    const days = new Map<string, number>()
    for (const run of rows) {
      const day = dayLabel(run.started_at)
      days.set(day, (days.get(day) ?? 0) + 1)
    }
    return {
      completed: rows.filter((run) => run.status === 'succeeded').length,
      failed: rows.filter((run) => run.status !== 'succeeded').length,
      fetched: total('fetched'),
      inserted: total('inserted'),
      updated: total('updated'),
      unchanged: total('unchanged'),
      rejected: total('rejected'),
      errors: total('errors'),
      days: Array.from(days, ([day, count]) => ({ day, count })).sort((a, b) => a.day.localeCompare(b.day)),
    }
  }, [page])

  const maxDayCount = Math.max(1, ...metrics.days.map((day) => day.count))
  const start = page && page.total ? page.offset + 1 : 0
  const end = page ? Math.min(page.offset + page.items.length, page.total) : 0

  function applyEmployer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const next = draftEmployer.trim()
    onFilterEmployer(next)
    if (next === employer) {
      setOffset(0)
      setRequestKey((key) => key + 1)
    }
  }

  return (
    <section className="ha-section" aria-labelledby="ha-heading">
      <div className="section-topline">
        <div>
          <p className="eyebrow section-eyebrow">INGESTION OPERATIONS / V1</p>
          <h2 id="ha-heading">Historical activity</h2>
          <p className="section-description">
            Synthetic ingestion execution history. Run counts are processing events, not vacancies or hiring demand.
          </p>
          {employer && <span className="ha-filter-note">Exact employer filter: {employer}</span>}
        </div>
        <button className="refresh-button" type="button" disabled={status === 'loading'} onClick={() => setRequestKey((key) => key + 1)}>
          Refresh activity
        </button>
      </div>

      <div className="ha-overview" aria-label="Ingestion history overview">
        <div className="ha-stat">
          <span>Matching runs (all pages)</span>
          <strong>{page ? page.total.toLocaleString() : '—'}</strong>
          <small>API-reported matching ingestion runs</small>
        </div>
        <div className="ha-stat">
          <span>Succeeded (current page)</span>
          <strong>{page ? metrics.completed : '—'}</strong>
          <small>Out of {page?.items.length ?? '—'} runs loaded</small>
        </div>
        <div className="ha-stat">
          <span>Other statuses (current page)</span>
          <strong>{page ? metrics.failed : '—'}</strong>
          <small>Inspect statuses in the table below</small>
        </div>
      </div>

      <form className="filters" onSubmit={applyEmployer}>
        <label className="field" htmlFor="ha-employer">
          <span>Employer (exact name)</span>
          <input id="ha-employer" type="text" maxLength={200} value={draftEmployer}
            onChange={(event) => setDraftEmployer(event.target.value)}
            placeholder="Synthetic CI Employer…" />
        </label>
        <button className="primary-button" type="submit">Apply filter</button>
        <button className="secondary-button" type="button"
          disabled={!draftEmployer && !employer}
          onClick={() => { setDraftEmployer(''); onFilterEmployer(''); setOffset(0); setRequestKey((key) => key + 1) }}>
          Clear
        </button>
      </form>

      {status === 'loading' && <div className="message-panel" role="status">Retrieving synthetic ingestion run history…</div>}
      {status === 'disabled' && (
        <div className="message-panel message-warning" role="status">
          <strong>Ingestion history API is disabled.</strong>
          <p>For isolated local synthetic testing only, set <code>DWI_POSTINGS_API_ENABLED=1</code> and restart FastAPI. Never enable publicly.</p>
        </div>
      )}
      {status === 'error' && (
        <div className="message-panel message-error" role="alert">
          <strong>Could not load ingestion history.</strong>
          <p>{errorMessage}</p>
        </div>
      )}
      {status === 'ready' && page && (
        <>
          <div className="ha-summary">
            <h3>Processing counters — current page only</h3>
            <div className="ha-counter-grid">
              {([
                ['Fetched', metrics.fetched], ['Inserted', metrics.inserted], ['Updated', metrics.updated],
                ['Unchanged', metrics.unchanged], ['Rejected', metrics.rejected], ['Errors', metrics.errors],
              ] as const).map(([label, count]) => (
                <div className="ha-counter" key={label}><span>{label}</span><strong>{count.toLocaleString()}</strong></div>
              ))}
            </div>
            <h3>Ingestion runs by UTC date — current page only</h3>
            {metrics.days.length ? (
              <div className="ha-timeline" role="list" aria-label="Page-level ingestion run counts by UTC date">
                {metrics.days.map(({ day, count }) => (
                  <div className="ha-day" key={day} role="listitem">
                    <span>{day}</span>
                    <div className="ha-bar-track" aria-hidden="true"><span style={{ width: `${100 * count / maxDayCount}%` }} /></div>
                    <strong>{count} {count === 1 ? 'run' : 'runs'}</strong>
                  </div>
                ))}
              </div>
            ) : <p className="ha-muted">No runs on this page.</p>}
          </div>

          {page.items.length === 0 ? (
            <div className="message-panel" role="status">
              <strong>No matching synthetic ingestion runs.</strong>
              <p>{page.total > 0 ? 'This page is beyond the available results.' : 'Check the exact employer name or seed the isolated synthetic test database.'}</p>
            </div>
          ) : (
            <div className="table-scroll" role="region" aria-label="Synthetic ingestion history" tabIndex={0}>
              <table className="ha-table">
                <thead><tr>
                  <th scope="col">Run / source</th><th scope="col">Status</th><th scope="col">Started / finished</th>
                  <th scope="col">Duration</th><th scope="col">Fetched</th><th scope="col">Inserted</th>
                  <th scope="col">Updated</th><th scope="col">Unchanged</th><th scope="col">Rejected</th><th scope="col">Errors</th>
                </tr></thead>
                <tbody>
                  {page.items.map((run) => (
                    <tr key={run.run_id}>
                      <td>
                        <strong>Run #{run.run_id}</strong>
                        <button className="employer-button ha-employer-button" type="button"
                          onClick={() => { setDraftEmployer(run.employer); onFilterEmployer(run.employer); setOffset(0) }}>
                          {run.employer}
                        </button>
                        <span className="source-token">{run.platform} / {run.board_token}</span>
                      </td>
                      <td><span className="ha-status">{run.status}</span></td>
                      <td className="muted-cell">{formatDate(run.started_at)}<span className="ha-finished">Finished: {formatDate(run.finished_at)}</span></td>
                      <td>{formatDuration(run.duration_ms)}</td>
                      <td>{run.fetched}</td><td>{run.inserted}</td><td>{run.updated}</td>
                      <td>{run.unchanged}</td><td>{run.rejected}</td><td>{run.errors}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="pagination">
            <span className="pagination-details" aria-live="polite">Showing {start}–{end} of {page.total.toLocaleString()} matching ingestion runs</span>
            <div className="pagination-actions">
              <button className="secondary-button" type="button" disabled={page.offset === 0}
                onClick={() => setOffset(Math.max(0, page.offset - PAGE_SIZE))}>Previous</button>
              <button className="secondary-button" type="button" disabled={page.next_offset === null}
                onClick={() => { if (page.next_offset !== null) setOffset(page.next_offset) }}>Next</button>
            </div>
          </div>
        </>
      )}
      <div className="ha-disclaimer">
        <strong>Synthetic operations only.</strong> Execution records measure ingestion processing events,
        not unique jobs, active vacancies, job closures, hires, or market demand. Charts and processing counters
        represent only the current fetched page unless explicitly labeled otherwise. Source permissions remain unresolved.
      </div>
    </section>
  )
}
