// Thin client for the Bob API (bob/api.py). Every call throws Error(detail) on failure.

async function request(path, { method = 'GET', body } = {}) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    const detail = typeof data?.detail === 'string' ? data.detail : `Request failed (${res.status})`
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),
  resume: () => request('/resume'),
  profile: () => request('/profile'),
  runs: () => request('/runs'),
  run: (id) => request(`/runs/${id}`),
  startRun: (jdText, strict) => request('/runs', { method: 'POST', body: { jd_text: jdText, strict } }),
  decide: (id, proposalId, action, extra = {}) =>
    request(`/runs/${id}/proposals/${proposalId}`, { method: 'POST', body: { action, ...extra } }),
  acceptAll: (id) => request(`/runs/${id}/accept-all`, { method: 'POST' }),
  setSkillAdditions: (id, include) =>
    request(`/runs/${id}`, { method: 'PATCH', body: { include_skill_additions: include } }),
  finalize: (id) => request(`/runs/${id}/finalize`, { method: 'POST' }),
  abort: (id) => request(`/runs/${id}/abort`, { method: 'POST' }),
  pdfUrl: (id, version) => `/api/runs/${id}/pdf?v=${encodeURIComponent(version ?? '')}`,
  texUrl: (id) => `/api/runs/${id}/tex`,
}
