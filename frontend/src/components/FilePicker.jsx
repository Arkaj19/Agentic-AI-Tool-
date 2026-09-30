import { useEffect, useState } from 'react'
import { ChevronRight, FileSpreadsheet, FileText, Folder, Home } from 'lucide-react'
import { api } from '../lib/api'
import { bytes, dateTime } from '../lib/format'
import { ErrorBox, Modal, Spinner } from './ui'

// Browse the SharePoint library and pick one file.
// accept: list of extensions that can be picked, e.g. ['.xlsx', '.csv']
export default function FilePicker({ open, onClose, onPick, accept, startPath = '', title = 'Select a file' }) {
  const [path, setPath] = useState(startPath)
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)

  useEffect(() => { if (open) { setPath(startPath); setSelected(null) } }, [open, startPath])
  useEffect(() => {
    if (!open) return
    let live = true
    setItems(null); setError(null)
    api.browse(path).then((d) => live && setItems(d.items)).catch((e) => live && setError(e))
    return () => { live = false }
  }, [open, path])

  const crumbs = path ? path.split('/') : []
  const ok = (it) => it.type === 'folder' || !accept || accept.includes(it.ext)

  return (
    <Modal open={open} onClose={onClose} title={title} wide
      footer={<>
        <button className="btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn-primary" disabled={!selected} onClick={() => { onPick(selected); onClose() }}>Select</button>
      </>}>
      <div className="mb-3 flex flex-wrap items-center gap-1 text-sm">
        <button className="btn-ghost btn-sm" onClick={() => setPath('')}><Home className="h-3.5 w-3.5" />SharePoint</button>
        {crumbs.map((c, i) => (
          <span key={i} className="flex items-center gap-1">
            <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
            <button className="btn-ghost btn-sm" onClick={() => setPath(crumbs.slice(0, i + 1).join('/'))}>{c}</button>
          </span>
        ))}
      </div>
      <ErrorBox error={error} />
      {!items && !error && <div className="flex justify-center py-10"><Spinner className="h-6 w-6 text-navy-700" /></div>}
      {items && (
        <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
          {items.length === 0 && <li className="px-4 py-8 text-center text-sm text-slate-500">This folder is empty</li>}
          {items.map((it) => {
            const Icon = it.type === 'folder' ? Folder : ['.pdf', '.docx', '.txt', '.md'].includes(it.ext) ? FileText : FileSpreadsheet
            const enabled = ok(it)
            const isSel = selected?.path === it.path
            return (
              <li key={it.path}>
                <button disabled={!enabled}
                  onClick={() => (it.type === 'folder' ? setPath(it.path) : setSelected(it))}
                  onDoubleClick={() => { if (it.type === 'file' && enabled) { onPick(it); onClose() } }}
                  className={`flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition
                    ${isSel ? 'bg-navy-50 ring-1 ring-inset ring-navy-600/40' : 'hover:bg-slate-50'} ${enabled ? '' : 'cursor-not-allowed opacity-40'}`}>
                  <Icon className={`h-4 w-4 shrink-0 ${it.type === 'folder' ? 'text-amber-500' : 'text-navy-700'}`} />
                  <span className="min-w-0 flex-1 truncate font-medium text-slate-800">{it.name}</span>
                  {it.type === 'file' && <span className="shrink-0 text-xs text-slate-500">{bytes(it.size)} · {dateTime(it.modified)}</span>}
                  {it.type === 'folder' && <ChevronRight className="h-4 w-4 text-slate-400" />}
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </Modal>
  )
}
