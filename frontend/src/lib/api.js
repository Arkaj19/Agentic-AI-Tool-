// Thin client for the FastAPI backend (proxied at /api by Vite).

async function request(method, path, body) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const text = await res.text()
  let data = null
  try { data = text ? JSON.parse(text) : null } catch { data = text }
  if (!res.ok) {
    const detail = (data && data.detail) || res.statusText || 'Request failed'
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return data
}

const enc = encodeURIComponent
const qs = (o) => new URLSearchParams(o).toString()

export const api = {
  status: () => request('GET', '/status'),
  meta: () => request('GET', '/meta'),

  browse: (path = '') => request('GET', `/files?${qs({ path })}`),
  table: (path, params) => request('GET', `/files/table?${qs({ path, ...params })}`),
  document: (path) => request('GET', `/files/document?${qs({ path })}`),

  generate: (path) => request('POST', '/mappings/generate', { path }),
  mapping: (id) => request('GET', `/mappings/${enc(id)}`),
  mappingDownloadUrl: (id) => `/api/mappings/${enc(id)}/download`,
  approveAndRun: (id, body) => request('POST', `/mappings/${enc(id)}/approve-and-run`, body),

  runs: () => request('GET', '/runs'),
  run: (id) => request('GET', `/runs/${enc(id)}`),
  decide: (id, gate, body) => request('POST', `/runs/${enc(id)}/gates/${gate}/decision`, body),
  outputUrl: (id, name) => `/api/runs/${enc(id)}/outputs/${enc(name)}`,

  approvals: () => request('GET', '/approvals'),
}

// Server-Sent Events for a run's progress. Returns a close() function.
export function streamRun(runId, onEvent, onEnd) {
  const es = new EventSource(`/api/runs/${enc(runId)}/events`)
  es.onmessage = (m) => { try { onEvent(JSON.parse(m.data)) } catch { /* ignore */ } }
  es.addEventListener('end', () => { es.close(); onEnd && onEnd() })
  return () => es.close()
}
