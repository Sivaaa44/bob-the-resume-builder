import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import NewRun from './pages/NewRun'
import RunView from './pages/RunView'
import History from './pages/History'
import Setup from './pages/Setup'
import Facts from './pages/Facts'
import Settings from './pages/Settings'

function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash || '#/new')
  useEffect(() => {
    const onChange = () => setHash(window.location.hash || '#/new')
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  const [, page, id] = hash.replace(/^#/, '').split('/')
  return { page: page || 'new', id }
}

const NAV = [
  ['new', 'New application'],
  ['history', 'History'],
  ['facts', 'Your facts'],
  ['settings', 'Settings'],
]

export default function App() {
  const { page, id } = useHashRoute()
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

  // pages call this after setup/settings changes so the shell knows what's configured
  const refresh = useCallback(
    () => api.health().then(setHealth).catch(() => setError('Can’t reach the Bob API. Start it with: uvicorn bob.api:app --reload')),
    [],
  )
  useEffect(() => { refresh() }, [refresh])

  let body
  if (error) body = <div className="notice notice-error">{error}</div>
  else if (!health) body = <p className="muted">Connecting…</p>
  else if (page === 'settings') body = <Settings onSaved={refresh} />
  else if (page === 'setup' || !health.workspace_ready) body = <Setup ready={health.workspace_ready} onImported={refresh} />
  else if (page === 'facts') body = <Facts />
  else if (page === 'runs' && id) body = <RunView key={id} runId={id} />
  else if (page === 'history') body = <History />
  else body = <NewRun hasKey={health.has_llm_key} />

  return (
    <div className="app">
      <header className="topbar">
        <a className="brand" href="#/new">
          <span className="brand-mark">B</span> Bob <span className="brand-sub">resume tailor</span>
        </a>
        <nav>
          {NAV.map(([key, label]) => (
            <a key={key} className={page === key || (key === 'history' && page === 'runs') ? 'active' : ''} href={`#/${key}`}>
              {label}
            </a>
          ))}
        </nav>
      </header>
      <main>{body}</main>
    </div>
  )
}
