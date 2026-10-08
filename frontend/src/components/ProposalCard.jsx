import { useState } from 'react'
import { Bold } from '../lib/format'

const STATUS = {
  pending: 'Needs your call',
  accepted: 'Accepted',
  edited: 'Accepted with your edit',
  rejected: 'Rejected',
  blocked: 'Blocked by checks',
}

export default function ProposalCard({ proposal: p, entryTitle, facts, requirements, onAction }) {
  const [mode, setMode] = useState(null) // null | 'edit' | 'regen'
  const [text, setText] = useState('')
  const [feedback, setFeedback] = useState('')
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)

  async function act(action, extra) {
    setBusy(action)
    setError(null)
    try {
      await onAction(p.id, action, extra)
      setMode(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(null)
    }
  }

  const decided = ['accepted', 'edited', 'rejected'].includes(p.status)
  const shown = p.status === 'edited' && p.user_text ? p.user_text : p.new_text

  return (
    <article className={`card proposal status-${p.status}`}>
      <header className="proposal-head">
        <span className="tag">{p.kind === 'add' ? 'New bullet' : 'Rewrite'}</span>
        <span className="proposal-entry">{entryTitle}</span>
        <span className={`pill pill-${p.status}`}>{STATUS[p.status]}</span>
      </header>

      <div className="diff">
        {p.kind === 'rewrite' && (
          <div className="diff-row diff-old">
            <span className="diff-label">Now</span>
            <p>{p.original_text}</p>
          </div>
        )}
        <div className="diff-row diff-new">
          <span className="diff-label">{p.kind === 'add' ? 'Add' : 'Then'}</span>
          <p><Bold text={shown} /></p>
        </div>
        {p.status === 'edited' && (
          <div className="small muted">Bob suggested: <Bold text={p.new_text} /></div>
        )}
      </div>

      {p.checks.length > 0 && (
        <ul className="checks">
          {p.checks.map((c, i) => (
            <li key={i} className={`check check-${c.level}`}>
              <strong>{c.level === 'error' ? 'Blocked' : 'Heads up'}:</strong> {c.message}
            </li>
          ))}
        </ul>
      )}

      <details className="evidence">
        <summary>
          Evidence: {p.fact_ids.length ? p.fact_ids.join(', ') : 'none'}
          {p.requirement_ids.some((r) => requirements[r]) && (
            <> · targets {p.requirement_ids.filter((r) => requirements[r]).map((r) => requirements[r].text).join(', ')}</>
          )}
        </summary>
        <ul>
          {p.fact_ids.map((f) => (
            <li key={f}><span className="fact-ref">{f}</span> {facts[f]?.text || 'unknown fact'}</li>
          ))}
        </ul>
        {p.rationale && <p className="small muted">Why: {p.rationale}</p>}
      </details>

      {mode === 'edit' && (
        <div className="inline-form">
          <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} autoFocus />
          <p className="small muted">Your words go on the resume as written. Bob still checks them and shows any warnings. Use **double asterisks** for bold.</p>
          <div className="actions">
            <button className="btn btn-primary" disabled={!text.trim() || busy} onClick={() => act('edit', { text })}>
              {busy === 'edit' ? 'Saving…' : 'Save edit'}
            </button>
            <button className="btn" onClick={() => setMode(null)}>Cancel</button>
          </div>
        </div>
      )}

      {mode === 'regen' && (
        <div className="inline-form">
          <input
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="What should change? e.g. shorter, lead with the 40% result, drop Kubernetes"
            autoFocus
          />
          <div className="actions">
            <button className="btn btn-primary" disabled={!feedback.trim() || busy} onClick={() => act('regenerate', { feedback })}>
              {busy === 'regenerate' ? 'Rewriting…' : 'Try again'}
            </button>
            <button className="btn" onClick={() => setMode(null)}>Cancel</button>
          </div>
        </div>
      )}

      {!mode && (
        <div className="actions">
          {!decided && (
            <>
              <button
                className="btn btn-primary"
                disabled={p.status === 'blocked' || !!busy}
                title={p.status === 'blocked' ? 'Edit it or add the missing fact to profile.yaml' : ''}
                onClick={() => act('accept')}
              >
                {busy === 'accept' ? '…' : 'Accept'}
              </button>
              <button className="btn" disabled={!!busy} onClick={() => act('reject')}>Reject</button>
            </>
          )}
          <button className="btn btn-ghost" disabled={!!busy} onClick={() => { setText(shown); setMode('edit') }}>Edit</button>
          <button className="btn btn-ghost" disabled={!!busy} onClick={() => setMode('regen')}>Try again…</button>
          {decided && <button className="btn btn-ghost" disabled={!!busy} onClick={() => act('reset')}>Undo</button>}
        </div>
      )}
      {error && <div className="notice notice-error small">{error}</div>}
    </article>
  )
}
