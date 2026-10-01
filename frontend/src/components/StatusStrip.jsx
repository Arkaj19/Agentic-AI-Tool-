import { AlertCircle, Check, Loader2 } from 'lucide-react'
import { useApp } from '../lib/app-context'

function Tile({ ok, title, detail, loading }) {
  return (
    <div className="card flex min-w-0 items-start gap-2.5 px-4 py-3">
      <span className="mt-0.5">
        {loading ? <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
          : ok ? <Check className="h-4 w-4 text-emerald-600" strokeWidth={3} /> : <AlertCircle className="h-4 w-4 text-red-500" />}
      </span>
      <div className="min-w-0">
        <div className="text-[13px] font-semibold text-slate-900">{title}</div>
        <div className="truncate text-xs text-slate-500" title={detail}>{detail}</div>
      </div>
    </div>
  )
}

export default function StatusStrip({ run }) {
  const { status } = useApp()
  const loading = !status
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Tile loading={loading} ok={status?.sharepoint?.connected} title="SharePoint" detail={status?.sharepoint?.detail || ''} />
      <Tile loading={loading} ok title="ECC file" detail={run?.file || '—'} />
      {run?.engine === 'databricks'
        ? <Tile loading={loading} ok={status?.databricks?.connected} title="Databricks" detail={status?.databricks?.detail || ''} />
        : <Tile loading={loading} ok title="Rulebook" detail={run?.mappingDoc || '—'} />}
      <Tile loading={loading} ok={status?.llm?.configured} title="AI model" detail={status?.llm?.deployment || 'Not configured'} />
    </div>
  )
}
