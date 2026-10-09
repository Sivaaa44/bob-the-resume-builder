import { useEffect, useState } from 'react'
import { api } from '../api'
import BuildPanel from '../components/BuildPanel'
import CoveragePanel from '../components/CoveragePanel'
import ProposalCard from '../components/ProposalCard'
import { pct, shortDate } from '../lib/format'

const ORDER = { pending: 0, blocked: 1, edited: 2, accepted: 2, rejected: 3 }

export default function RunView({ runId }) {
  const [run, setRun] = useState(null)
  const [facts, setFacts] = useState({})
  const [entries, setEntries] = useState({})
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.run(runId), api.profile(), api.resume()])
      .then(([r, profile, resume]) => {
        setRun(r)
        setFacts(Object.fromEntries(profile.facts.map((f) => [f.id, f])))
        setEntries(Object.fromEntries(resume.sections.flatMap((s) => s.entries).map((e) => [e.id, e])))
      })
      .catch((err) => setError(err.message))
  }, [runId])

  if (error) return <div className="notice notice-error">{error}</div>
  if (!run) return <p className="muted">Loading…</p>

  const a = run.analysis
  const counts = { direct: 0, adjacent: 0, none: 0 }
  run.coverage.forEach((c) => (counts[c.strength] += 1))
  // only requirements with evidence can be "targeted" (an edit may have dropped the claim)
  const supported = new Set(run.coverage.filter((c) => c.strength !== 'none').map((c) => c.requirement_id))
  const requirements = Object.fromEntries(a.requirements.filter((r) => supported.has(r.id)).map((r) => [r.id, r]))
  // keep the original order but float undecided cards to the top so the next action is obvious
  const proposals = [...run.proposals].sort((x, y) => ORDER[x.status] - ORDER[y.status])

  const onAction = async (proposalId, action, extra) => setRun(await api.decide(run.id, proposalId, action, extra))

  return (
    <div className="run">
      <header className="run-head">
        <div>
          <h1>{a.title || 'Untitled role'}{a.company && <span className="muted"> at {a.company}</span>}</h1>
          <p className="muted small">
            {shortDate(run.created_at)} · {run.status.replace('_', ' ')}
          </p>
        </div>
        <div className="score" title="Share of requirements backed by your facts (must-haves count double)">
          <div className="score-num">{pct(run.score)}</div>
          <div className="score-bar"><span style={{ width: pct(run.score) }} /></div>
          <div className="small muted">{counts.direct} covered · {counts.adjacent} partial · {counts.none} {counts.none === 1 ? 'gap' : 'gaps'}</div>
        </div>
      </header>

      <div className="run-grid">
        <div className="run-main">
          <section>
            <div className="section-head">
              <h2>Suggested changes</h2>
              <span className="muted small">Each one is checked against the facts it cites</span>
            </div>
            {proposals.length === 0 && (
              <div className="card muted">No changes suggested. Your resume already covers what your facts can support.</div>
            )}
            {proposals.map((p) => (
              <ProposalCard
                key={p.id}
                proposal={p}
                entryTitle={entries[p.entry_id]?.title || p.entry_id}
                facts={facts}
                requirements={requirements}
                onAction={onAction}
              />
            ))}
          </section>
          <CoveragePanel analysis={a} coverage={run.coverage} facts={facts} />
          <details className="card jd">
            <summary>Job description</summary>
            <pre>{run.jd_text}</pre>
          </details>
        </div>
        <BuildPanel run={run} onRun={setRun} />
      </div>
    </div>
  )
}
