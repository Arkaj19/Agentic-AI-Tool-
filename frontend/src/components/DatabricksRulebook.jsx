import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CloudDownload, Play } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'
import { dateTime } from '../lib/format'
import { useApp } from '../lib/app-context'
import DataTable from './DataTable'
import { ErrorBox, Loading, Segmented, Spinner } from './ui'

// The rule book the Databricks pipeline generates its notebook from.
export default function DatabricksRulebook() {
  const { user, toast, marcFile, refreshPending, status } = useApp()
  const q = useAsync(() => api.databricksRulebook(), [])
  const [view, setView] = useState('transformation')
  const [busy, setBusy] = useState(false)
  const nav = useNavigate()
  const connected = status?.databricks?.connected

  const start = async () => {
    setBusy(true)
    try {
      const { runId } = await api.startDatabricks({ file: marcFile.path, by: user })
      toast('Approved. Databricks pipeline started.', 'success')
      refreshPending()
      nav(`/agents/${runId}`)
    } catch (e) { toast(e.message, 'error'); setBusy(false) }
  }

  if (q.loading) return <Loading label="Fetching the Databricks rule book from SharePoint…" />
  if (q.error) return <ErrorBox error={q.error} onRetry={q.reload} />
  const d = q.data
  const rows = d[view]
  const columns = [
    { key: 'rule_id', label: 'Rule', sortable: false, className: 'mono font-semibold text-navy-800 align-top' },
    { key: 'rule_text', label: view === 'transformation' ? 'Transformation' : 'Check', sortable: false,
      className: '!whitespace-normal min-w-[420px] align-top' },
  ]

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <CloudDownload className="h-4 w-4 text-navy-700" />
        {d.shared.found
          ? <span>Fetched from SharePoint: <b className="text-slate-700">{d.shared.path}</b> · {dateTime(d.shared.modified)}</span>
          : <span className="text-amber-700">Not found in SharePoint at <b>{d.shared.path}</b></span>}
        <span className="ml-auto">{d.silverTable} → {d.goldTable}</span>
      </div>
      <div className="flex justify-end">
        <Segmented value={view} onChange={setView} options={[
          { value: 'transformation', label: `Transformation (${d.transformation.length})` },
          { value: 'validation', label: `Validation (${d.validation.length})` }]} />
      </div>
      <DataTable columns={columns} rows={rows} rowKey={(r) => r.rule_id} maxHeight="52vh" blank="" />
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border-2 border-brand-500/70 bg-brand-50/60 px-4 py-3">
        <div className="text-sm">
          {!marcFile ? <>No ECC file selected. <Link to="/extraction" className="font-semibold text-brand-700 underline">Go to Data Extraction</Link></>
            : !connected ? <>Databricks is not connected ({status?.databricks?.detail || 'checking…'}).</>
              : <>ECC file: <b className="text-slate-900">{marcFile.name}</b> → Databricks</>}
        </div>
        <button className="btn-accent" disabled={busy || !marcFile || !connected} onClick={start}>
          {busy ? <Spinner /> : <Play className="h-4 w-4" />}Approve and start on Databricks
        </button>
      </div>
    </div>
  )
}
