import { useEffect, useState } from 'react'
import { api } from '../api'

const PRESETS = [
  { id: 'gemini', label: 'Google Gemini (free tier)', url: 'https://generativelanguage.googleapis.com/v1beta/openai',
    model: 'gemini-2.5-flash', keyUrl: 'https://aistudio.google.com/apikey' },
  { id: 'groq', label: 'Groq', url: 'https://api.groq.com/openai/v1', model: 'openai/gpt-oss-20b',
    keyUrl: 'https://console.groq.com/keys' },
  { id: 'openai', label: 'OpenAI', url: 'https://api.openai.com/v1', model: 'gpt-4o-mini',
    keyUrl: 'https://platform.openai.com/api-keys' },
  { id: 'openrouter', label: 'OpenRouter', url: 'https://openrouter.ai/api/v1', model: 'google/gemini-2.5-flash',
    keyUrl: 'https://openrouter.ai/keys' },
  { id: 'ollama', label: 'Ollama (runs on your computer)', url: 'http://localhost:11434/v1', model: 'llama3.1' },
]

const presetFor = (url) => PRESETS.find((p) => p.url === url)?.id || 'custom'

export default function Settings({ onSaved }) {
  const [form, setForm] = useState(null)
  const [current, setCurrent] = useState(null)
  const [status, setStatus] = useState(null) // { kind: 'ok'|'error'|'info', text }
  const [busy, setBusy] = useState(null)

  useEffect(() => {
    api.settings().then((s) => {
      setCurrent(s)
      setForm({ preset: presetFor(s.llm_base_url), llm_base_url: s.llm_base_url, llm_model: s.llm_model,
                llm_api_key: '', max_pages: s.max_pages })
    }).catch((err) => setStatus({ kind: 'error', text: err.message }))
  }, [])

  if (!form) return status ? <div className="notice notice-error">{status.text}</div> : <p className="muted">Loading…</p>

  const preset = PRESETS.find((p) => p.id === form.preset)
  const set = (patch) => { setForm((f) => ({ ...f, ...patch })); setStatus(null) }
  const choose = (id) => {
    const p = PRESETS.find((x) => x.id === id)
    set(p ? { preset: id, llm_base_url: p.url, llm_model: p.model } : { preset: 'custom' })
  }

  async function save() {
    setBusy('save')
    try {
      const { preset: _, ...values } = form
      const s = await api.saveSettings({ ...values, max_pages: Number(values.max_pages) })
      setCurrent(s)
      setForm((f) => ({ ...f, llm_api_key: '' }))
      setStatus({ kind: 'ok', text: 'Saved.' })
      onSaved?.()
    } catch (err) {
      setStatus({ kind: 'error', text: err.message })
    } finally {
      setBusy(null)
    }
  }

  async function test() {
    setBusy('test')
    setStatus({ kind: 'info', text: 'Sending a tiny test request…' })
    try {
      const r = await api.testSettings()
      setStatus({ kind: 'ok', text: `Working: ${r.model} replied.` })
    } catch (err) {
      setStatus({ kind: 'error', text: err.message })
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="card settings">
      <h1>Settings</h1>
      <p className="muted">
        Bob uses your own AI key, saved on this computer only (in <code>workspace/settings.json</code>). One tailoring
        run uses about 7–15k tokens, well within free tiers.
      </p>

      <label className="field">
        <span>AI provider</span>
        <select value={form.preset} onChange={(e) => choose(e.target.value)}>
          {PRESETS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
          <option value="custom">Custom (any OpenAI-compatible API)</option>
        </select>
      </label>

      {form.preset === 'custom' && (
        <label className="field">
          <span>API base URL</span>
          <input value={form.llm_base_url} onChange={(e) => set({ llm_base_url: e.target.value })} />
        </label>
      )}

      <label className="field">
        <span>Model</span>
        <input value={form.llm_model} onChange={(e) => set({ llm_model: e.target.value })} />
      </label>

      {form.preset !== 'ollama' && (
        <label className="field">
          <span>API key</span>
          <input
            type="password"
            autoComplete="off"
            value={form.llm_api_key}
            placeholder={current?.has_key ? `Saved (${current.key_hint}). Leave blank to keep it` : 'Paste your key'}
            onChange={(e) => set({ llm_api_key: e.target.value })}
          />
          {preset?.keyUrl && (
            <span className="small muted">
              Get one at <a href={preset.keyUrl} target="_blank" rel="noreferrer">{new URL(preset.keyUrl).host}</a>
            </span>
          )}
        </label>
      )}

      <label className="field">
        <span>Page limit</span>
        <select value={form.max_pages} onChange={(e) => set({ max_pages: e.target.value })}>
          <option value={1}>1 page</option>
          <option value={2}>2 pages</option>
        </select>
      </label>

      <div className="actions">
        <button className="btn btn-primary" disabled={!!busy} onClick={save}>{busy === 'save' ? 'Saving…' : 'Save'}</button>
        <button className="btn" disabled={!!busy || (!current?.has_key && form.preset !== 'ollama')} onClick={test}
          title="Save first, then test">
          {busy === 'test' ? 'Testing…' : 'Test connection'}
        </button>
      </div>
      {status && (
        <div className={`notice small ${status.kind === 'error' ? 'notice-error' : status.kind === 'ok' ? 'notice-ok' : ''}`}>
          {status.text}
        </div>
      )}
    </section>
  )
}
