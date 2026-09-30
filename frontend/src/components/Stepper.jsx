import { Check, ShieldCheck, X } from 'lucide-react'

// Horizontal pipeline stepper driven by run.steps.
export default function Stepper({ steps, state }) {
  const done = steps.filter((s) => ['done', 'skipped'].includes(state?.[s.id]?.status)).length
  const progress = Math.round((done / steps.length) * 100)
  return (
    <div className="card px-5 pb-3 pt-4">
      <div className="flex items-start justify-between gap-1">
        {steps.map((s, i) => {
          const st = state?.[s.id]?.status || 'queued'
          const ring = {
            done: 'bg-navy-900 text-white border-navy-900',
            skipped: 'bg-slate-200 text-slate-500 border-slate-200',
            running: 'bg-white text-brand-600 border-brand-500 animate-pulsering',
            waiting: 'bg-amber-50 text-amber-700 border-amber-500 animate-pulsering',
            failed: 'bg-red-600 text-white border-red-600',
            queued: 'bg-slate-100 text-slate-500 border-slate-100',
          }[st]
          return (
            <div key={s.id} className="relative flex min-w-0 flex-1 flex-col items-center gap-1.5 px-1">
              {i > 0 && <span className={`absolute right-1/2 top-[15px] h-0.5 w-full -translate-x-[16px] ${['done', 'skipped'].includes(st) || st === 'running' || st === 'waiting' ? 'bg-navy-900/70' : 'bg-slate-200'}`} style={{ width: 'calc(100% - 32px)' }} />}
              <span className={`relative z-[1] flex h-8 w-8 items-center justify-center rounded-full border-2 text-xs font-bold transition ${ring}`}>
                {st === 'done' ? <Check className="h-4 w-4" strokeWidth={3} /> : st === 'failed' ? <X className="h-4 w-4" strokeWidth={3} />
                  : s.gate ? <ShieldCheck className="h-4 w-4" /> : i + 1}
              </span>
              <span className={`truncate text-center text-[12px] leading-tight ${st === 'running' || st === 'waiting' ? 'font-semibold text-brand-700'
                : st === 'done' ? 'font-semibold text-slate-800' : 'text-slate-500'}`}>{s.label}</span>
            </div>
          )
        })}
      </div>
      <div className="mt-3 flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
          <div className="h-full rounded-full bg-gradient-to-r from-navy-800 to-brand-500 transition-all duration-700" style={{ width: `${progress}%` }} />
        </div>
        <span className="text-xs font-semibold tabular-nums text-slate-600">{progress}%</span>
      </div>
    </div>
  )
}
