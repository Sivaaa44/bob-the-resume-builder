// Small display helpers shared by pages.

// "Built in **Python**" → Built in <strong>Python</strong>
export function Bold({ text }) {
  const parts = (text || '').split('**')
  if (parts.length % 2 === 0) return text
  return parts.map((p, i) => (i % 2 ? <strong key={i}>{p}</strong> : p))
}

export const pct = (x) => `${Math.round((x || 0) * 100)}%`

export function shortDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

export function roleLabel(title, company) {
  return [title || 'Untitled role', company].filter(Boolean).join(' · ')
}

// Hash routing: #/new, #/runs/<id>, #/history
export function navigate(path) {
  window.location.hash = path
}
