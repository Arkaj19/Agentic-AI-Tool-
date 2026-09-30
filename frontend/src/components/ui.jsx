import { useEffect } from 'react'
import { AlertTriangle, CheckCircle2, Info, Loader2, X, XCircle } from 'lucide-react'
import { useApp } from '../lib/app-context'

const PILL = {
  done: 'bg-navy-100 text-navy-800',
  completed: 'bg-emerald-100 text-emerald-800',
  pass: 'bg-emerald-100 text-emerald-800',
  approved: 'bg-emerald-100 text-emerald-800',
  running: 'bg-brand-100 text-brand-700',
  waiting: 'bg-amber-100 text-amber-800',
  pending: 'bg-amber-100 text-amber-800',
  draft: 'bg-amber-50 text-amber-800 ring-1 ring-amber-200',
  issue: 'bg-brand-100 text-brand-700',
  unmapped: 'bg-brand-100 text-brand-700',
  queued: 'bg-slate-100 text-slate-600',
  skipped: 'bg-slate-100 text-slate-500',
  accepted: 'bg-indigo-100 text-indigo-800',
  fail: 'bg-red-100 text-red-800',
  failed: 'bg-red-100 text-red-800',
  rejected: 'bg-red-100 text-red-800',
  info: 'bg-slate-100 text-slate-700',
}

const LABEL = {
  done: 'Done', completed: 'Completed', pass: 'Pass', approved: 'Approved', running: 'Running',
  waiting: 'Needs approval', pending: 'Pending', draft: 'Draft', issue: 'Issue', unmapped: 'No rule',
  queued: 'Queued', skipped: 'Skipped', accepted: 'Accepted', fail: 'Fail', failed: 'Failed', rejected: 'Rejected',
}

export function Pill({ status, children, className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${PILL[status] || PILL.info} ${className}`}>
      {status === 'running' && <span className="h-1.5 w-1.5 rounded-full bg-brand-500 animate-pulse" />}
      {children ?? LABEL[status] ?? status}
    </span>
  )
}

export function Card({ title, subtitle, actions, children, className = '', bodyClass = 'p-5' }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
          <div className="min-w-0">
            {title && <h2 className="section-title">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  )
}

export function Spinner({ className = 'h-4 w-4' }) {
  return <Loader2 className={`animate-spin ${className}`} />
}

export function Loading({ label = 'Loading…', hint }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-14 text-sm text-slate-500">
      <Spinner className="h-6 w-6 text-navy-700" />
      <span className="font-medium text-slate-700">{label}</span>
      {hint && <span className="max-w-md text-center text-xs">{hint}</span>}
    </div>
  )
}

export function Empty({ icon: Icon = Info, title, children, action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      <div className="rounded-full bg-navy-50 p-3 text-navy-700"><Icon className="h-6 w-6" /></div>
      <h3 className="mt-1 font-semibold text-slate-900">{title}</h3>
      {children && <p className="max-w-md text-sm text-slate-500">{children}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}

export function ErrorBox({ error, onRetry }) {
  if (!error) return null
  return (
    <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0 flex-1 break-words">{String(error.message || error)}</div>
      {onRetry && <button className="btn-ghost btn-sm text-red-800" onClick={onRetry}>Retry</button>}
    </div>
  )
}

export function Kpi({ label, value, sub, tone = 'default', icon: Icon }) {
  const tones = { default: 'text-slate-900', good: 'text-emerald-700', warn: 'text-brand-700', bad: 'text-red-700' }
  return (
    <div className="card px-4 py-3.5">
      <div className="flex items-center justify-between text-xs font-medium text-slate-500">
        <span>{label}</span>
        {Icon && <Icon className="h-4 w-4 text-slate-400" />}
      </div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${tones[tone]}`}>{value}</div>
      {sub && <div className="mt-0.5 truncate text-xs text-slate-500">{sub}</div>}
    </div>
  )
}

export function Tabs({ tabs, value, onChange, className = '' }) {
  return (
    <div className={`flex gap-1 border-b border-slate-200 ${className}`}>
      {tabs.map((t) => (
        <button key={t.id} onClick={() => onChange(t.id)}
          className={`-mb-px flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium transition ${value === t.id
            ? 'border-brand-600 text-navy-900' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>
          {t.label}
          {t.count !== undefined && (
            <span className={`rounded-full px-1.5 text-[11px] ${value === t.id ? 'bg-brand-100 text-brand-700' : 'bg-slate-100 text-slate-600'}`}>{t.count}</span>
          )}
        </button>
      ))}
    </div>
  )
}

export function Segmented({ options, value, onChange }) {
  return (
    <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5">
      {options.map((o) => (
        <button key={o.value} onClick={() => onChange(o.value)}
          className={`rounded-md px-2.5 py-1 text-xs font-semibold transition ${value === o.value ? 'bg-white text-navy-900 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Modal({ open, onClose, title, children, footer, wide }) {
  useEffect(() => {
    if (!open) return
    const k = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-950/40 p-4 backdrop-blur-[2px]" onMouseDown={onClose}>
      <div className={`card w-full animate-slidein ${wide ? 'max-w-3xl' : 'max-w-lg'}`} onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5">
          <h3 className="section-title">{title}</h3>
          <button className="btn-ghost btn-sm" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-5 py-4 scroll-thin">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-slate-100 px-5 py-3">{footer}</div>}
      </div>
    </div>
  )
}

export function Toasts() {
  const { toasts, dismiss } = useApp()
  const icon = { success: CheckCircle2, error: XCircle, warn: AlertTriangle, info: Info }
  const tone = { success: 'text-emerald-600', error: 'text-red-600', warn: 'text-amber-600', info: 'text-navy-700' }
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-80 flex-col gap-2">
      {toasts.map((t) => {
        const I = icon[t.kind] || Info
        return (
          <div key={t.id} className="card pointer-events-auto flex animate-slidein items-start gap-3 px-4 py-3 text-sm">
            <I className={`mt-0.5 h-4 w-4 shrink-0 ${tone[t.kind]}`} />
            <div className="min-w-0 flex-1 break-words text-slate-700">{t.message}</div>
            <button onClick={() => dismiss(t.id)} className="text-slate-400 hover:text-slate-700"><X className="h-3.5 w-3.5" /></button>
          </div>
        )
      })}
    </div>
  )
}

export function Bar({ value, max, tone = 'navy' }) {
  const w = max ? Math.max(2, Math.round((value / max) * 100)) : 0
  const c = { navy: 'bg-navy-700', brand: 'bg-brand-500', green: 'bg-emerald-500', slate: 'bg-slate-400' }[tone]
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
      <div className={`h-full rounded-full ${c}`} style={{ width: `${w}%` }} />
    </div>
  )
}

export function Pager({ offset, limit, total, onChange }) {
  const page = Math.floor(offset / limit) + 1
  const pages = Math.max(1, Math.ceil(total / limit))
  return (
    <div className="flex items-center justify-between gap-3 text-xs text-slate-500">
      <span className="tabular-nums">
        {total ? `${(offset + 1).toLocaleString()}–${Math.min(offset + limit, total).toLocaleString()} of ${total.toLocaleString()}` : '0 rows'}
      </span>
      <div className="flex items-center gap-1">
        <button className="btn-ghost btn-sm" disabled={page <= 1} onClick={() => onChange(0)}>First</button>
        <button className="btn-ghost btn-sm" disabled={page <= 1} onClick={() => onChange(offset - limit)}>Prev</button>
        <span className="px-2 tabular-nums">Page {page} / {pages.toLocaleString()}</span>
        <button className="btn-ghost btn-sm" disabled={page >= pages} onClick={() => onChange(offset + limit)}>Next</button>
        <button className="btn-ghost btn-sm" disabled={page >= pages} onClick={() => onChange((pages - 1) * limit)}>Last</button>
      </div>
    </div>
  )
}
