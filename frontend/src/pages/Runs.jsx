import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, History } from 'lucide-react'
import { PageHeader } from '../components/Layout'
import { Card, Empty, ErrorBox, Loading, Pill } from '../components/ui'
import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'
import { dateTime, duration, num } from '../lib/format'

export default function Runs() {
  const q = useAsync(() => api.runs(), [])
  const runs = q.data?.runs || []
  useEffect(() => {
    if (!runs.some((r) => ['running', 'queued', 'waiting'].includes(r.status))) return
    const t = setInterval(q.reload, 4000)
    return () => clearInterval(t)
  }, [runs, q.reload])

  return (
    <>
      <PageHeader title="Runs" />
      <ErrorBox error={q.error} onRetry={q.reload} />
      <Card bodyClass="p-0">
        {q.loading && !q.data ? <Loading /> : runs.length === 0 ? (
          <Empty icon={History} title="No runs yet"
            action={<Link to="/rulebook" className="btn-accent">Go to Rulebook <ArrowRight className="h-4 w-4" /></Link>}>
            Every time a rulebook is approved, a run appears here.
          </Empty>
        ) : (
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs text-slate-600">
              <tr>
                <th className="px-5 py-2.5">Started</th><th className="px-3 py-2.5">Engine</th><th className="px-3 py-2.5">ECC file</th><th className="px-3 py-2.5">Rulebook</th>
                <th className="px-3 py-2.5">Status</th><th className="px-3 py-2.5">Validation</th>
                <th className="px-3 py-2.5 text-right">S/4 rows</th><th className="px-3 py-2.5">Duration</th><th className="px-5 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className="border-t border-slate-100 hover:bg-navy-50/50">
                  <td className="whitespace-nowrap px-5 py-3">{dateTime(r.created)}<div className="text-xs text-slate-500">{r.startedBy}</div></td>
                  <td className="px-3 py-3"><span className={`rounded-md px-2 py-0.5 text-xs font-semibold ${r.engine === 'databricks' ? 'bg-brand-100 text-brand-700' : 'bg-navy-50 text-navy-800'}`}>{r.engine === 'databricks' ? 'Databricks' : 'Embedded'}</span></td>
                  <td className="max-w-[220px] truncate px-3 py-3" title={r.file}>{r.file}</td>
                  <td className="max-w-[200px] truncate px-3 py-3" title={r.mappingDoc}>{r.mappingDoc}</td>
                  <td className="px-3 py-3"><Pill status={r.status} /></td>
                  <td className="px-3 py-3">{r.passed === undefined || r.passed === null ? <span className="text-slate-300">–</span>
                    : <Pill status={r.passed ? 'pass' : 'fail'}>{r.passed ? 'Passed' : 'Failed'}</Pill>}</td>
                  <td className="px-3 py-3 text-right font-semibold tabular-nums">{num(r.metrics?.loadRows)}</td>
                  <td className="px-3 py-3 tabular-nums text-slate-600">{duration(r.started, r.finished)}</td>
                  <td className="px-5 py-3">
                    <div className="flex justify-end gap-2">
                      <Link to={`/agents/${r.id}`} className="btn-ghost btn-sm">Open</Link>
                      {r.outputs > 0 && <Link to={`/reports/${r.id}`} className="btn-outline btn-sm">Reports</Link>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  )
}
