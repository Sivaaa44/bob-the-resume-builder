import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'

// Editable copy of profile.yaml. Skills are edited as comma-separated text and split on save.
let nextKey = 1
const toRow = (f) => ({ ...f, _key: nextKey++, skillsText: (f.skills || []).join(', ') })
const splitList = (text) => text.split(',').map((s) => s.trim()).filter(Boolean)

export default function Facts() {
  const [entries, setEntries] = useState([])
  const [rows, setRows] = useState(null)
  const [skills, setSkills] = useState([]) // [{ category, itemsText }]
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.resume(), api.profile()])
      .then(([resume, profile]) => {
        setEntries(resume.sections.flatMap((s) => s.entries.map((e) => ({ ...e, section: s.title }))))
        setRows(profile.facts.map(toRow))
        setSkills(Object.entries(profile.skills).map(([category, items]) => ({ category, itemsText: items.join(', ') })))
      })
      .catch((err) => setError(err.message))
  }, [])

  useEffect(() => {
    if (!dirty) return
    const warn = (e) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  const byEntry = useMemo(() => {
    const groups = {}
    for (const r of rows || []) (groups[r.entry || ''] ||= []).push(r)
    return groups
  }, [rows])

  const touch = () => { setDirty(true); setSaved(false) }
  const update = (key, patch) => { setRows((rs) => rs.map((r) => (r._key === key ? { ...r, ...patch } : r))); touch() }
  const remove = (key) => { setRows((rs) => rs.filter((r) => r._key !== key)); touch() }
  const add = (entry) => {
    setRows((rs) => [...rs, toRow({ id: null, text: '', entry: entry || null, skills: [], source: 'user' })])
    touch()
  }

  async function save() {
    setSaving(true)
    setError(null)
    try {
      const profile = {
        facts: rows.map(({ _key, skillsText, ...f }) => ({ ...f, skills: splitList(skillsText) })),
        skills: Object.fromEntries(skills.filter((s) => s.category.trim()).map((s) => [s.category.trim(), splitList(s.itemsText)])),
      }
      const fresh = await api.saveProfile(profile)
      setRows(fresh.facts.map(toRow))
      setDirty(false)
      setSaved(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (error && !rows) return <div className="notice notice-error">{error}</div>
  if (!rows) return <p className="muted">Loading…</p>

  const total = rows.filter((r) => r.text.trim()).length
  const added = rows.filter((r) => r.source === 'user' && r.text.trim()).length

  return (
    <div className="facts">
      <header className="run-head">
        <div>
          <h1>Your facts</h1>
          <p className="muted small">
            {total} facts · {added} added by you. Bob may only claim what’s written here, and only under the job it belongs to.
          </p>
        </div>
      </header>

      <div className="notice small tip">
        <strong>Tip:</strong> add the work that didn’t fit on your resume, real numbers, and the tools you used. In
        “skills”, list the names a job post might use (e.g. <em>Pinecone, vector databases, RAG</em>), but only ones
        you’d happily explain in an interview.
      </div>

      {entries.map((e) => (
        <section key={e.id} className="card fact-group">
          <div className="section-head">
            <h2>{e.title}{e.subtitle && <span className="muted"> · {e.subtitle}</span>}</h2>
            <span className="muted small">{e.section}</span>
          </div>
          <FactRows rows={byEntry[e.id] || []} update={update} remove={remove} />
          <button className="btn btn-ghost" onClick={() => add(e.id)}>+ Add a fact</button>
        </section>
      ))}

      <section className="card fact-group">
        <div className="section-head">
          <h2>General</h2>
          <span className="muted small">Certifications, languages, coursework: usable under any entry</span>
        </div>
        <FactRows rows={byEntry[''] || []} update={update} remove={remove} />
        <button className="btn btn-ghost" onClick={() => add(null)}>+ Add a fact</button>
      </section>

      <section className="card fact-group">
        <div className="section-head">
          <h2>Skills you can list</h2>
          <span className="muted small">Bob adds these to your skills section when a job asks for them</span>
        </div>
        {skills.map((s, i) => (
          <div key={i} className="skill-row">
            <input
              value={s.category}
              placeholder="Category"
              onChange={(e) => { setSkills((ss) => ss.map((x, j) => (j === i ? { ...x, category: e.target.value } : x))); touch() }}
            />
            <input
              value={s.itemsText}
              placeholder="Python, SQL, …"
              onChange={(e) => { setSkills((ss) => ss.map((x, j) => (j === i ? { ...x, itemsText: e.target.value } : x))); touch() }}
            />
          </div>
        ))}
        <button className="btn btn-ghost" onClick={() => { setSkills((ss) => [...ss, { category: '', itemsText: '' }]); touch() }}>
          + Add a category
        </button>
      </section>

      <div className="savebar">
        {error && <span className="notice-error small savebar-msg">{error}</span>}
        {saved && !dirty && <span className="ok small savebar-msg">Saved</span>}
        {dirty && <span className="muted small savebar-msg">Unsaved changes</span>}
        <button className="btn btn-primary" disabled={!dirty || saving} onClick={save}>
          {saving ? 'Saving…' : 'Save facts'}
        </button>
      </div>
    </div>
  )
}

function FactRows({ rows, update, remove }) {
  if (rows.length === 0) return <p className="muted small">No facts yet.</p>
  return (
    <ul className="fact-rows">
      {rows.map((r) => (
        <li key={r._key} className="fact-row">
          <div className="fact-main">
            <textarea
              rows={2}
              value={r.text}
              placeholder="Something true you did, e.g. Cut API latency 40% by adding Redis caching"
              onChange={(e) => update(r._key, { text: e.target.value })}
            />
            <input
              value={r.skillsText}
              placeholder="skills / tools this proves, comma-separated"
              onChange={(e) => update(r._key, { skillsText: e.target.value })}
            />
          </div>
          <div className="fact-side">
            <span className="tag">{r.source === 'resume' ? 'from resume' : 'added by you'}</span>
            <button className="btn btn-ghost btn-small" onClick={() => remove(r._key)} aria-label="Delete fact">Delete</button>
          </div>
        </li>
      ))}
    </ul>
  )
}
