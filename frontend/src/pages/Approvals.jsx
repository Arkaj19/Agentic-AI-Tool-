import { Link } from 'react-router-dom'
import { CheckCircle2, Clock, ShieldCheck, XCircle } from 'lucide-react'
import { PageHeader } from '../components/Layout'
import { Card, Empty, ErrorBox, Loading, Pill } from '../components/ui'
import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'
import { dateTime } from '../lib/format'

export default function Approvals() {
  const q = useAsync(() => api.approvals(), [])
  const items = q.data?.items || []
  return (
    <>
      <PageHeader title="Approvals" />
      <ErrorBox error={q.error} onRetry={q.reload} />
      <Card bodyClass="p-0">
        {q.loading && !q.data ? <Loading /> : items.length === 0 ? (
          <Empty icon={ShieldCheck} title="No approvals yet">Approved rulebooks are listed here.</Empty>
        ) : (
          <ul className="divide-y divide-slate-100">
            {items.map((g, i) => {
              const Icon = g.status === 'approved' ? CheckCircle2 : g.status === 'rejected' ? XCircle : Clock
              const tone = g.status === 'approved' ? 'text-emerald-600' : g.status === 'rejected' ? 'text-red-600' : 'text-amber-600'
              return (
                <li key={`${g.runId}-${i}`} className={`flex flex-wrap items-center gap-4 px-5 py-3.5 ${g.status === 'pending' ? 'bg-amber-50/50' : ''}`}>
                  <Icon className={`h-5 w-5 shrink-0 ${tone}`} />
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold text-slate-900">{g.title}</div>
                    <div className="truncate text-xs text-slate-500">{g.mappingDoc} · {g.file}</div>
                  </div>
                  <div className="text-right text-xs text-slate-500">
                    {g.decidedAt ? <>{g.decidedBy}<div>{dateTime(g.decidedAt)}</div></> : <>Requested<div>{dateTime(g.requested)}</div></>}
                  </div>
                  <Pill status={g.status} />
                  <Link to={`/agents/${g.runId}`} className={g.status === 'pending' ? 'btn-accent btn-sm' : 'btn-ghost btn-sm'}>
                    {g.status === 'pending' ? 'Review' : 'Open'}
                  </Link>
                </li>
              )
            })}
          </ul>
        )}
      </Card>
    </>
  )
}
