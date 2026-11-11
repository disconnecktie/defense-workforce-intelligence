import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { useState } from 'react'
import HistoricalActivityDashboard from './HistoricalActivityDashboard'

type Run = {
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

const employer = 'Synthetic CI Employer Alpha'
const alpha = (id: number, overrides: Partial<Run> = {}): Run => ({
  run_id: id,
  employer,
  platform: 'greenhouse',
  board_token: 'synthetic_alpha',
  started_at: '2026-11-09T01:00:00Z',
  finished_at: '2026-11-09T01:00:01Z',
  status: 'succeeded',
  fetched: 3,
  inserted: 1,
  updated: 1,
  unchanged: 0,
  rejected: 1,
  errors: 0,
  duration_ms: 1000,
  ...overrides,
})

function historyPage(items: Run[], props: { total?: number; offset?: number; next_offset?: number | null } = {}) {
  return {
    data_scope: 'synthetic_only' as const,
    counting_rule: 'ingestion_runs_not_vacancies' as const,
    total: props.total ?? items.length,
    limit: 10,
    offset: props.offset ?? 0,
    next_offset: props.next_offset ?? null,
    items,
  }
}

function httpResponse(payload: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => payload }
}

function Harness({ initialEmployer = '' }: { initialEmployer?: string }) {
  const [selectedEmployer, setSelectedEmployer] = useState(initialEmployer)
  return (
    <HistoricalActivityDashboard
      apiBaseUrl="http://127.0.0.1:8000"
      employer={selectedEmployer}
      refreshKey={0}
      onFilterEmployer={setSelectedEmployer}
    />
  )
}

beforeEach(() => {
  vi.restoreAllMocks()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('HistoricalActivityDashboard', () => {
  it('shows globally matching runs but scopes processing metrics and UTC timeline to the fetched page', async () => {
    const fetchMock = vi.fn().mockResolvedValue(httpResponse(historyPage([
      alpha(22),
      alpha(21, {
        status: 'failed', fetched: 2, inserted: 0, updated: 0,
        unchanged: 0, rejected: 1, errors: 1, finished_at: null, duration_ms: null,
        started_at: '2026-11-08T12:00:00Z',
      }),
    ], { total: 20, next_offset: 10 })))
    vi.stubGlobal('fetch', fetchMock)
    render(<Harness />)

    expect(await screen.findByText('20')).toBeTruthy()
    expect(screen.getByText('Succeeded (current page)')).toBeTruthy()
    expect(screen.getByText('Other statuses (current page)')).toBeTruthy()

    const counters = document.querySelector('.ha-counter-grid')
    expect(counters).not.toBeNull()
    expect(within(counters as HTMLElement).getByText('Fetched').nextElementSibling?.textContent).toBe('5')
    expect(within(counters as HTMLElement).getByText('Inserted').nextElementSibling?.textContent).toBe('1')
    expect(within(counters as HTMLElement).getByText('Errors').nextElementSibling?.textContent).toBe('1')

    expect(screen.getByText('2026-11-08')).toBeTruthy()
    expect(screen.getByText('2026-11-09')).toBeTruthy()
    expect(screen.getByText('Run #22')).toBeTruthy()
    expect(screen.getByText('Run #21')).toBeTruthy()
    expect(screen.getAllByText('Not supplied').length).toBeGreaterThan(0)
    expect(screen.getByText('Showing 1–2 of 20 matching ingestion runs')).toBeTruthy()
    expect(document.body.textContent).toContain('processing events')
    expect(document.body.textContent).toContain('not vacancies or hiring demand')
  })

  it('uses server-side pagination rather than calculating a full-population history locally', async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string) => {
      const offset = Number(new URL(url).searchParams.get('offset'))
      return httpResponse(offset === 0
        ? historyPage([alpha(22)], { total: 12, next_offset: 10 })
        : historyPage([alpha(12)], { total: 12, offset: 10, next_offset: null }))
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<Harness />)
    expect(await screen.findByText('Run #22')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Run #12')).toBeTruthy()
    expect(screen.queryByText('Run #22')).toBeNull()
    expect(screen.getByText('Showing 11–11 of 12 matching ingestion runs')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Next' }).hasAttribute('disabled')).toBe(true)
    expect(fetchMock.mock.calls.some(([url]) => new URL(url).searchParams.get('offset') === '10')).toBe(true)
  })

  it('sends an exact employer query and resets pagination when the filter changes', async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string) => {
      const query = new URL(url).searchParams
      const selected = query.get('employer')
      return httpResponse(historyPage(selected ? [alpha(4)] : [alpha(22)], { total: selected ? 1 : 20 }))
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<Harness />)
    expect(await screen.findByText('Run #22')).toBeTruthy()

    fireEvent.change(screen.getByRole('textbox', { name: 'Employer (exact name)' }), { target: { value: employer } })
    fireEvent.click(screen.getByRole('button', { name: 'Apply filter' }))
    expect(await screen.findByText('Run #4')).toBeTruthy()
    expect(fetchMock.mock.calls.some(([url]) => {
      const query = new URL(url).searchParams
      return query.get('employer') === employer && query.get('offset') === '0'
    })).toBe(true)

    fireEvent.click(screen.getByRole('button', { name: 'Clear' }))
    await waitFor(() => expect(screen.getByText('Run #22')).toBeTruthy())
  })

  it('provides a safe disabled notice on HTTP 503', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(httpResponse(null, 503)))
    render(<Harness />)
    expect(await screen.findByText('Ingestion history API is disabled.')).toBeTruthy()
    expect(screen.getByText(/Never enable publicly/)).toBeTruthy()
    expect(screen.queryByText('Run #22')).toBeNull()
  })

  it('reports HTTP failures and rejects malformed API responses instead of displaying invented metrics', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(httpResponse(null, 500))
      .mockResolvedValueOnce(httpResponse({ ...historyPage([alpha(1)]), data_scope: 'live' }))
    vi.stubGlobal('fetch', fetchMock)
    render(<Harness />)
    expect(await screen.findByText('Could not load ingestion history.')).toBeTruthy()
    expect(screen.getByText(/HTTP 500/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Refresh activity' }))
    await waitFor(() => expect(screen.getByText('Unexpected ingestion history response from the API.')).toBeTruthy())
    expect(screen.queryByText('Run #1')).toBeNull()
  })

  it('handles empty results without presenting a fictional time series', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(httpResponse(historyPage([]))))
    render(<Harness />)
    expect(await screen.findByText('No matching synthetic ingestion runs.')).toBeTruthy()
    expect(screen.getByText('No runs on this page.')).toBeTruthy()
    expect(screen.queryByText('2026-11-09')).toBeNull()
  })
})
