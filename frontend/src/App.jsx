import { useEffect, useState } from 'react'
import { api } from './api'
import NewRun from './pages/NewRun'
import RunView from './pages/RunView'
import History from './pages/History'
import SetupNotice from './components/SetupNotice'

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

export default function App() {
  const { page, id } = useHashRoute()
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setError('Can’t reach the Bob API. Start it with: uvicorn bob.api:app --reload'))
  }, [])

  let body
  if (error) body = <div className="notice notice-error">{error}</div>
  else if (!health) body = <p className="muted">Connecting…</p>
  else if (!health.workspace_ready) body = <SetupNotice />
  else if (page === 'runs' && id) body = <RunView key={id} runId={id} />
  else if (page === 'history') body = <History />
  else body = <NewRun />

  return (
    <div className="app">
      <header className="topbar">
        <a className="brand" href="#/new">
          <span className="brand-mark">B</span> Bob <span className="brand-sub">resume tailor</span>
        </a>
        <nav>
          <a className={page === 'new' ? 'active' : ''} href="#/new">New application</a>
          <a className={page === 'history' ? 'active' : ''} href="#/history">History</a>
        </nav>
      </header>
      <main>{body}</main>
    </div>
  )
}
