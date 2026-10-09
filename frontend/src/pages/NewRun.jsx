import { useEffect, useState } from 'react'
import { api } from '../api'
import { navigate, pct, roleLabel, shortDate } from '../lib/format'

const STEPS = [
  'Reading the job description…',
  'Matching requirements to your facts…',
  'Drafting bullet changes…',
  'Checking every claim against your facts…',
]

export default function NewRun() {
  const [jd, setJd] = useState('')
  const [strict, setStrict] = useState(false)
  const [busy, setBusy] = useState(false)
  const [step, setStep] = useState(0)
  const [error, setError] = useState(null)
  const [recent, setRecent] = useState([])

  useEffect(() => {
    api.runs().then((r) => setRecent(r.slice(0, 5))).catch(() => {})
  }, [])

  useEffect(() => {
    if (!busy) return
    setStep(0)
    const t = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 4000)
    return () => clearInterval(t)
  }, [busy])

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const run = await api.startRun(jd, strict)
      navigate(`/runs/${run.id}`)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <div className="new-run">
      <form className="card jd-form" onSubmit={submit}>
        <h1>Tailor your resume to a job</h1>
        <p className="muted">
          Paste the job description. Bob suggests changes backed by your facts, and you approve each one.
        </p>
        <textarea
          value={jd}
          onChange={(e) => setJd(e.target.value)}
          placeholder="Paste the full job description here…"
          rows={16}
          disabled={busy}
          autoFocus
        />
        <div className="form-row">
          <label className="checkbox" title="Ask the model to fact-check each proposal too. Slower, stricter.">
            <input type="checkbox" checked={strict} onChange={(e) => setStrict(e.target.checked)} disabled={busy} />
            Strict mode: double-check every claim with the model
          </label>
          <button className="btn btn-primary" disabled={busy || jd.trim().length < 40}>
            {busy ? 'Working…' : 'Tailor resume'}
          </button>
        </div>
        {busy && (
          <div className="progress" role="status">
            <span className="spinner" /> {STEPS[step]}
          </div>
        )}
        {error && <div className="notice notice-error">{error}</div>}
      </form>

      {recent.length > 0 && (
        <aside className="card recent">
          <h2>Recent</h2>
          <ul>
            {recent.map((r) => (
              <li key={r.id}>
                <a href={`#/runs/${r.id}`}>{roleLabel(r.title, r.company)}</a>
                <span className="muted small">
                  {shortDate(r.created_at)} · {pct(r.score)} covered · {r.status.replace('_', ' ')}
                </span>
              </li>
            ))}
          </ul>
        </aside>
      )}
    </div>
  )
}
