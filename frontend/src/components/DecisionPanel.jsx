import { useState } from 'react'
import { api } from '../lib/api'
import { useApp } from '../lib/app-context'
import { Spinner } from './ui'

// Approval card, shown only while the run is waiting for a decision.
export default function DecisionPanel({ run, onDone }) {
  const { user, toast, refreshPending } = useApp()
  const [busy, setBusy] = useState('')
  const gate = run?.gates?.find((g) => g.status === 'pending')
  if (!gate || run.active) return null
  const decide = async (action) => {
    setBusy(action)
    try {
      await api.decide(run.id, gate.id, { action, by: user })
      toast(action === 'approve' ? 'Approved' : 'Rejected', action === 'approve' ? 'success' : 'warn')
      refreshPending(); onDone()
    } catch (e) { toast(e.message, 'error') } finally { setBusy('') }
  }
  return (
    <section className="card animate-slidein border-2 border-brand-500/80 p-5">
      <div className="text-[15px] font-bold text-brand-700">Needs your approval</div>
      <p className="mt-1 text-sm text-slate-700">{gate.description || 'Approve the rulebook to continue.'}</p>
      {gate.proposal?.lines?.length > 0 && (
        <ul className="mt-3 space-y-1 rounded-lg bg-slate-50 p-3">
          {gate.proposal.lines.map((l) => <li key={l} className="text-sm text-slate-800">{l}</li>)}
        </ul>
      )}
      <div className="mt-4 flex gap-2">
        <button className="btn-primary" disabled={!!busy} onClick={() => decide('approve')}>{busy === 'approve' && <Spinner />}Approve</button>
        <button className="btn-danger" disabled={!!busy} onClick={() => decide('reject')}>{busy === 'reject' && <Spinner />}Reject</button>
      </div>
    </section>
  )
}
