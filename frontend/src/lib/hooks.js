import { useCallback, useEffect, useRef, useState } from 'react'
import { api, streamRun } from './api'

// Runs an async loader and tracks data / loading / error. Re-runs when deps change.
export function useAsync(fn, deps = [], { enabled = true } = {}) {
  const [state, setState] = useState({ data: null, loading: enabled, error: null })
  const seq = useRef(0)
  const load = useCallback(async () => {
    const id = ++seq.current
    setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const data = await fn()
      if (id === seq.current) setState({ data, loading: false, error: null })
      return data
    } catch (error) {
      if (id === seq.current) setState((s) => ({ ...s, loading: false, error }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(() => { if (enabled) load() }, [load, enabled])
  return { ...state, reload: load, setData: (d) => setState((s) => ({ ...s, data: d })) }
}

// Live view of one run: the run record, refreshed whenever the backend reports progress (SSE).
export function useRunStream(runId) {
  const [run, setRun] = useState(null)
  const [error, setError] = useState(null)
  const timer = useRef(null)

  const refresh = useCallback(async () => {
    if (!runId) return
    try { setRun(await api.run(runId)); setError(null) } catch (e) { setError(e) }
  }, [runId])

  useEffect(() => {
    setRun(null); setError(null)
    if (!runId) return
    refresh()
    const close = streamRun(runId, () => {
      clearTimeout(timer.current)
      timer.current = setTimeout(refresh, 250)
    }, refresh)
    const poll = setInterval(refresh, 10000) // safety net if the stream drops
    return () => { close(); clearInterval(poll); clearTimeout(timer.current) }
  }, [runId, refresh])

  return { run, error, refresh }
}
