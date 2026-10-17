import { useState } from 'react'
import { api } from '../api'

// Step 1: pick a .tex → Step 2: check how Bob read it → Step 3: import (seeds your facts)
export default function Setup({ ready, onImported }) {
  const [file, setFile] = useState(null) // { name, tex }
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)

  async function load(f) {
    if (!f) return
    setError(null)
    setResult(null)
    setPreview(null)
    if (!f.name.toLowerCase().endsWith('.tex')) {
      setError('Pick your resume’s .tex file (the LaTeX source, not the PDF).')
      return
    }
    const tex = await f.text()
    setFile({ name: f.name, tex })
    setBusy(true)
    try {
      setPreview(await api.setupPreview(tex))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function doImport() {
    setBusy(true)
    setError(null)
    try {
      setResult(await api.setupImport(file.tex))
      // stay on this page to show next steps once the app sees the workspace is ready
      if (window.location.hash !== '#/setup') window.location.hash = '/setup'
      onImported?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="setup">
      <section className="card">
        <h1>{ready ? 'Replace your base resume' : 'Set up Bob'}</h1>
        <p className="muted">
          Bob reads your LaTeX resume once. Every bullet becomes a <strong>fact</strong>: something true about you
          that Bob is allowed to use. Your file is never modified; each tailored resume is a new copy.
        </p>

        <label
          className={`dropzone ${dragging ? 'dragging' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); load(e.dataTransfer.files[0]) }}
        >
          <input type="file" accept=".tex" onChange={(e) => load(e.target.files[0])} />
          <strong>{file ? file.name : 'Drop your resume.tex here'}</strong>
          <span className="muted small">{file ? 'Pick a different file' : 'or click to choose a file'}</span>
        </label>
        {busy && !preview && <div className="progress"><span className="spinner" /> Reading your resume…</div>}
        {error && <div className="notice notice-error">{error}</div>}
      </section>

      {preview && !result && (
        <section className="card">
          <div className="section-head">
            <h2>Is this how your resume is organised?</h2>
            <span className="muted small">
              {preview.stats.entries} entries · {preview.stats.bullets} bullets · {preview.stats.skill_lines} skill lines
            </span>
          </div>
          <p className="muted small">
            Check that each job and project is its own entry with its own bullets. If two jobs are merged into one,
            Bob could mix up which work happened where.
          </p>
          {preview.warnings.length > 0 && (
            <ul className="checks">
              {preview.warnings.map((w) => <li key={w} className="check check-warning"><strong>Heads up:</strong> {w}</li>)}
            </ul>
          )}
          <Outline outline={preview.outline} />
          <div className="actions">
            <button className="btn btn-primary" disabled={busy} onClick={doImport}>
              {busy ? 'Importing…' : 'Looks right, import it'}
            </button>
            {preview.replacing && (
              <span className="small muted">Facts you added by hand are kept if their job/project still exists.</span>
            )}
          </div>
        </section>
      )}

      {result && (
        <section className="card">
          <h2>Done. {result.facts} facts ready</h2>
          <p className="muted">
            {result.stats.bullets} bullets from {result.stats.entries} entries became facts
            {result.kept > 0 && `, plus ${result.kept} you added before`}.
          </p>
          {result.orphaned.length > 0 && (
            <div className="notice small">
              These facts you added belonged to an entry that’s gone. Re-add them under the right job:
              <ul>{result.orphaned.map((f) => <li key={f.id}>{f.text}</li>)}</ul>
            </div>
          )}
          <p>
            <strong>Next:</strong> add what didn’t fit on the page: extra projects, metrics, tools. The more true facts
            Bob has, the better it can match each job.
          </p>
          <div className="actions">
            <a className="btn btn-primary" href="#/facts">Add your facts</a>
            <a className="btn" href="#/settings">Set up your AI key</a>
          </div>
        </section>
      )}
    </div>
  )
}

function Outline({ outline }) {
  return (
    <div className="outline">
      {outline.sections.map((s) => (
        <div key={s.id} className="outline-section">
          <h3>{s.title}</h3>
          {s.entries.map((e) => (
            <div key={e.id} className="outline-entry">
              <div className="outline-title">
                {e.title}
                {e.subtitle && <span className="muted"> · {e.subtitle}</span>}
                <span className="muted small"> ({e.bullets.length} {e.bullets.length === 1 ? 'bullet' : 'bullets'})</span>
              </div>
              {e.bullets.length > 0 && <ul>{e.bullets.map((b) => <li key={b.id}>{b.text}</li>)}</ul>}
            </div>
          ))}
          {s.skill_lines.map((l) => (
            <div key={l.id} className="outline-entry">
              <span className="outline-title">{l.category}:</span> {l.items.join(', ')}
            </div>
          ))}
          {s.entries.length === 0 && s.skill_lines.length === 0 && <p className="muted small">Nothing Bob can edit here.</p>}
        </div>
      ))}
    </div>
  )
}
