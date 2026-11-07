import { useEffect, useState } from 'react'
import './styles.css'

type ApiStatus = 'checking' | 'online' | 'offline'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking')

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
  }, [])

  const statusLabel: Record<ApiStatus, string> = {
    checking: 'Checking API',
    online: 'API online',
    offline: 'API unavailable',
  }

  return (
    <main className="page">
      <header className="header">
        <div className="wordmark">DWI <span>/</span> ANALYTICS</div>
        <span className="release-tag">FOUNDATION · TKT-001</span>
      </header>
      <section className="hero" aria-labelledby="hero-heading">
        <p className="eyebrow">DEFENSE WORKFORCE INTELLIGENCE</p>
        <h1 id="hero-heading">Make workforce signals actionable.</h1>
        <p className="intro">
          A source-attributed platform for tracking advertised technical skills,
          employer demand, geography, and compensation across the defense sector.
        </p>
        <div className="status-panel">
          <div className="status-heading">Local environment</div>
          <div className="status-line">
            <span className={`status-dot ${apiStatus}`} aria-hidden="true" />
            <span role="status">{statusLabel[apiStatus]}</span>
          </div>
          <p>
            This is a development scaffold. No workforce dataset or analytics have
            been ingested yet; database connectivity is not checked by API liveness.
          </p>
        </div>
      </section>
      <footer>
        Public-data intelligence · Independent portfolio project · Future Telaryn integration
      </footer>
    </main>
  )
}
