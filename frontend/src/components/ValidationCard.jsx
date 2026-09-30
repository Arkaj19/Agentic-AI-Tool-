import { CheckCircle2, XCircle } from 'lucide-react'
import { Card, Pill } from './ui'

// Result of the plant check against the Databricks output.
export default function ValidationCard({ validation, plant }) {
  if (!validation) {
    return (
      <Card title={`Validation · plant ${plant || ''}`}>
        <p className="text-sm text-slate-500">The result appears here once validation has run.</p>
      </Card>
    )
  }
  const ok = validation.passed
  return (
    <Card title={`Validation · plant ${validation.plant}`} subtitle="Compared with the Databricks output"
      actions={<Pill status={ok ? 'pass' : 'fail'}>{ok ? 'Passed' : 'Failed'}</Pill>} bodyClass="p-0">
      <ul className="divide-y divide-slate-100">
        {validation.checks.map((c) => (
          <li key={c.id} className="flex items-start gap-3 px-5 py-3">
            {c.status === 'pass'
              ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              : <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />}
            <div className="min-w-0">
              <div className="text-sm font-medium text-slate-900">{c.name}</div>
              <div className="text-xs text-slate-500">{c.detail}</div>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}
