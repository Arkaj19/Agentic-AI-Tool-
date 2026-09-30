import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Download, FileBarChart2, FileSpreadsheet, Table2 } from 'lucide-react'
import { PageHeader } from '../components/Layout'
import ValidationCard from '../components/ValidationCard'
import { Card, Empty, ErrorBox, Kpi, Loading } from '../components/ui'
import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'
import { bytes, dateTime, num } from '../lib/format'

const KIND = {
  s4: { tone: 'bg-emerald-50 text-emerald-700', icon: FileSpreadsheet },
  report: { tone: 'bg-navy-50 text-navy-800', icon: FileBarChart2 },
  mapping: { tone: 'bg-amber-50 text-amber-800', icon: Table2 },
}

export default function Reports() {
  const { runId } = useParams()
  const nav = useNavigate()
  const runsQ = useAsync(() => api.runs(), [])
  const done = (runsQ.data?.runs || []).filter((r) => r.outputs > 0)
  useEffect(() => { if (!runId && done[0]) nav(`/reports/${done[0].id}`, { replace: true }) }, [runId, done, nav])
  const runQ = useAsync(() => api.run(runId), [runId], { enabled: !!runId })
  const run = runQ.data
  const inProgress = run && ['running', 'queued', 'waiting'].includes(run.status)
  useEffect(() => {
    if (!inProgress) return
    const t = setInterval(runQ.reload, 4000)
    return () => clearInterval(t)
  }, [inProgress, runQ.reload])
  const v = run?.validation

  return (
    <>
      <PageHeader title="Reports"
        actions={done.length > 0 && runId && (
          <select className="input !w-auto !py-1.5 text-xs" value={runId} onChange={(e) => nav(`/reports/${e.target.value}`)}>
            {done.map((r) => <option key={r.id} value={r.id}>{dateTime(r.created)} · {r.file}</option>)}
          </select>
        )} />
      {!runId ? (runsQ.loading ? <Card><Loading /></Card> : (
        <Card><Empty icon={FileBarChart2} title="No reports yet">Reports appear here when processing finishes.</Empty></Card>
      )) : runQ.loading && !run ? <Card><Loading /></Card> : runQ.error ? <ErrorBox error={runQ.error} onRetry={runQ.reload} /> : run && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Kpi label="ECC rows" value={num(run.metrics?.eccRows)} />
            <Kpi label="S/4 rows" value={num(run.metrics?.loadRows)} tone="good" />
            <Kpi label={`Plant ${v?.plant || ''} match with Databricks`} value={v ? `${v.metrics.foundPct}%` : '–'} />
            <Kpi label="Validation" value={v ? (v.passed ? 'Passed' : 'Failed') : '–'} tone={v?.passed ? 'good' : v ? 'bad' : 'default'} />
          </div>
          <div className="grid gap-5 xl:grid-cols-2">
            <Card title="Files" bodyClass="p-0">
              {run.outputs.length === 0 ? <Empty icon={FileSpreadsheet} title="Files are being prepared" /> : (
                <ul className="divide-y divide-slate-100">
                  {run.outputs.map((o) => {
                    const k = KIND[o.kind] || KIND.report
                    const I = k.icon
                    return (
                      <li key={o.name} className="flex items-center gap-4 px-5 py-3.5">
                        <div className={`rounded-lg p-2 ${k.tone}`}><I className="h-5 w-5" /></div>
                        <div className="min-w-0 flex-1">
                          <div className="font-semibold text-slate-900">{o.label}</div>
                          <div className="truncate text-xs text-slate-500">{o.name} · {bytes(o.size)}</div>
                        </div>
                        <a className="btn-primary btn-sm" href={api.outputUrl(run.id, o.name)}><Download className="h-3.5 w-3.5" />Download</a>
                      </li>
                    )
                  })}
                </ul>
              )}
            </Card>
            <ValidationCard validation={v} />
          </div>
        </div>
      )}
    </>
  )
}
