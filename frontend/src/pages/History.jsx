import { useEffect, useState } from 'react'
import { api } from '../api'
import { pct, shortDate } from '../lib/format'

export default function History() {
  const [runs, setRuns] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.runs().then(setRuns).catch((err) => setError(err.message))
  }, [])

  if (error) return <div className="notice notice-error">{error}</div>
  if (!runs) return <p className="muted">Loading…</p>

  return (
    <section className="card">
      <div className="section-head">
        <h1>Applications</h1>
        <a className="btn btn-primary" href="#/new">New application</a>
      </div>
      {runs.length === 0 ? (
        <p className="muted">Nothing yet. Tailor your first one from “New application”.</p>
      ) : (
        <table className="history">
          <thead>
            <tr><th>Date</th><th>Role</th><th>Company</th><th>Coverage</th><th>Status</th></tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id} onClick={() => (window.location.hash = `/runs/${r.id}`)}>
                <td>{shortDate(r.created_at)}</td>
                <td><a href={`#/runs/${r.id}`}>{r.title || 'Untitled role'}</a></td>
                <td>{r.company || '—'}</td>
                <td>{pct(r.score)}</td>
                <td><span className={`pill pill-run-${r.status}`}>{r.status.replace('_', ' ')}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
