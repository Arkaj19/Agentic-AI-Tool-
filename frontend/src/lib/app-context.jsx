import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { api } from './api'

const AppCtx = createContext(null)

function readName() {
  try { return localStorage.getItem('amt.user') || 'Consultant' } catch { return 'Consultant' }
}

export function AppProvider({ children }) {
  const [status, setStatus] = useState(null)
  const [meta, setMeta] = useState({ steps: [] })
  const [pending, setPending] = useState(0)
  const [user, setUserState] = useState(readName)
  // Files picked in this session: the MARC extract and the mapping document.
  const [marcFile, setMarcFile] = useState(null)
  const [mappingDoc, setMappingDoc] = useState(null)
  const [mappingId, setMappingId] = useState(null)
  const [toasts, setToasts] = useState([])
  const idRef = useRef(0)

  const refreshPending = useCallback(async () => {
    try { setPending((await api.approvals()).pending) } catch { /* backend down */ }
  }, [])

  useEffect(() => {
    api.status().then(setStatus).catch((e) => setStatus({ error: e.message }))
    api.meta().then(setMeta).catch(() => {})
    refreshPending()
    const t = setInterval(refreshPending, 8000)
    return () => clearInterval(t)
  }, [refreshPending])

  const setUser = (name) => {
    setUserState(name)
    try { localStorage.setItem('amt.user', name) } catch { /* private mode */ }
  }

  const toast = useCallback((message, kind = 'info') => {
    const id = ++idRef.current
    setToasts((t) => [...t, { id, message, kind }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === 'error' ? 7000 : 3500)
  }, [])
  const dismiss = (id) => setToasts((t) => t.filter((x) => x.id !== id))

  return (
    <AppCtx.Provider value={{
      status, meta, pending, refreshPending, user, setUser, toast, toasts, dismiss,
      marcFile, setMarcFile, mappingDoc, setMappingDoc, mappingId, setMappingId,
    }}>
      {children}
    </AppCtx.Provider>
  )
}

export const useApp = () => useContext(AppCtx)
