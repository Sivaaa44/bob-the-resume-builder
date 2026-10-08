import { useState } from 'react'
import { api } from '../api'

export default function BuildPanel({ run, onRun }) {
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [version, setVersion] = useState(0) // bumps after each build so the preview reloads

  const count = (s) => run.proposals.filter((p) => p.status === s).length
  const accepted = count('accepted') + count('edited')
  const pending = count('pending')
  const blocked = count('blocked')
  const result = run.result
  const stale = result && run.status !== 'finalized'

  async function go(name, fn) {
    setBusy(name)
    setError(null)
    try {
      onRun(await fn())
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(null)
    }
  }

  if (run.status === 'aborted') {
    return <aside className="card build"><p className="muted">This application was abandoned.</p></aside>
  }

  return (
    <aside className="card build">
      <h2>Your resume</h2>
      <dl className="stats">
        <div><dt>{accepted}</dt><dd>going in</dd></div>
        <div><dt>{pending}</dt><dd>undecided</dd></div>
        <div><dt>{blocked}</dt><dd>blocked</dd></div>
      </dl>

      {run.skills_added.length > 0 && (
        <label className="checkbox">
          <input
            type="checkbox"
            checked={run.include_skill_additions}
            disabled={!!busy}
            onChange={(e) => go('skills', () => api.setSkillAdditions(run.id, e.target.checked))}
          />
          Add to skills from your profile: <strong>{run.skills_added.join(', ')}</strong>
        </label>
      )}

      <div className="build-actions">
        {pending > 0 && (
          <button className="btn" disabled={!!busy} onClick={() => go('all', () => api.acceptAll(run.id))}>
            Accept all {pending} that passed checks
          </button>
        )}
        <button className="btn btn-primary btn-wide" disabled={!!busy}
          onClick={() => go('build', () => api.finalize(run.id)).then(() => setVersion((v) => v + 1))}>
          {busy === 'build' ? 'Building PDF…' : result ? 'Rebuild PDF' : 'Build PDF'}
        </button>
        {pending > 0 && <p className="small muted">Undecided proposals are left out.</p>}
      </div>

      {error && <div className="notice notice-error small">{error}</div>}

      {result && (
        <div className="result">
          {stale && <div className="notice small">You changed decisions since the last build. Rebuild to update the PDF.</div>}
          <p className={result.fits ? 'ok' : 'warn'}>
            {result.pages} page{result.pages === 1 ? '' : 's'}{result.fits ? ', fits' : ', over the page budget'}
          </p>
          {result.dropped.length > 0 && (
            <details>
              <summary>{result.dropped.length} bullet{result.dropped.length === 1 ? '' : 's'} cut to fit</summary>
              <ul className="small">{result.dropped.map((d) => <li key={d.id}>{d.text}</li>)}</ul>
            </details>
          )}
          <div className="downloads">
            <a className="btn" href={api.pdfUrl(run.id, version)} download>Download PDF</a>
            <a className="btn btn-ghost" href={api.texUrl(run.id)} download>.tex</a>
          </div>
          <iframe className="pdf" title="Tailored resume" src={api.pdfUrl(run.id, version)} />
        </div>
      )}

      {run.status !== 'finalized' && !result && (
        <button className="btn btn-ghost btn-small" disabled={!!busy}
          onClick={() => window.confirm('Abandon this application?') && go('abort', () => api.abort(run.id))}>
          Abandon this application
        </button>
      )}
    </aside>
  )
}
