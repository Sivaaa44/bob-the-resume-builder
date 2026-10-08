const LABEL = { direct: 'Covered', adjacent: 'Partial', none: 'Gap' }
const ICON = { direct: '✓', adjacent: '~', none: '✕' }

export default function CoveragePanel({ analysis, coverage, facts }) {
  const byReq = Object.fromEntries(coverage.map((c) => [c.requirement_id, c]))
  return (
    <section className="card">
      <div className="section-head">
        <h2>What the job asks for</h2>
        <span className="muted small">Must-haves count double in the score</span>
      </div>
      <ul className="reqs">
        {analysis.requirements.map((r) => {
          const c = byReq[r.id] || { strength: 'none', fact_ids: [] }
          return (
            <li key={r.id} className={`req req-${c.strength}`}>
              <span className="req-icon" aria-label={LABEL[c.strength]}>{ICON[c.strength]}</span>
              <div className="req-body">
                <div className="req-line">
                  <span className="req-text">{r.text}</span>
                  <span className={`tag ${r.importance === 'must' ? 'tag-must' : ''}`}>{r.importance}</span>
                  <span className={`tag tag-${c.strength}`}>{LABEL[c.strength]}</span>
                </div>
                {c.fact_ids.length > 0 && (
                  <div className="small muted">
                    Backed by:{' '}
                    {c.fact_ids.map((f) => (
                      <span key={f} className="fact-ref" title={facts[f]?.text}>{f}</span>
                    ))}
                    {!c.literal && c.strength === 'direct' && <em> (judged by the model, worth a quick check)</em>}
                  </div>
                )}
                {c.note && <div className="small muted">{c.note}</div>}
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
