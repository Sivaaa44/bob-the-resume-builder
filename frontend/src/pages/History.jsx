import { useEffect, useState } from 'react'
import { api } from '../api'
import { pct, shortDate } from '../lib/format'

export default function History() {
  const [runs, setRuns] = useState(null)
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.runs().then(setRuns).catch((err) => setError(err.message))
    api.stats().then(setStats).catch(() => {})
  }, [])

  if (error) return <div className="notice notice-error">{error}</div>
  if (!runs) return <p className="muted">Loading…</p>

  return (
    <section className="card">
      <div className="section-head">
        <h1>Applications</h1>
        <a className="btn btn-primary" href="#/new">New application</a>
      </div>
      {stats?.runs > 0 && (
        <dl className="stats stats-wide" title="Kept = accepted or edited, out of the proposals you decided on">
          <div><dt>{stats.runs}</dt><dd>applications</dd></div>
          <div><dt>{stats.finalized}</dt><dd>PDFs built</dd></div>
          <div><dt>{stats.acceptance_rate == null ? '—' : pct(stats.acceptance_rate)}</dt><dd>suggestions kept</dd></div>
          <div><dt>{stats.avg_tokens_per_run == null ? '—' : `${(stats.avg_tokens_per_run / 1000).toFixed(1)}k`}</dt><dd>tokens / run</dd></div>
        </dl>
      )}
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
