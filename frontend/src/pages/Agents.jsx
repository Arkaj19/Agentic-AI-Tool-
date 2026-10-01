import { useEffect } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowRight, Bot, CheckCircle2, FileBarChart2, XCircle } from 'lucide-react'
import { PageHeader } from '../components/Layout'
import StatusStrip from '../components/StatusStrip'
import Stepper from '../components/Stepper'
import DecisionPanel from '../components/DecisionPanel'
import ValidationCard from '../components/ValidationCard'
import { Card, Empty, ErrorBox, Loading, Pill, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { useAsync, useRunStream } from '../lib/hooks'
import { dateTime, num } from '../lib/format'
import { useApp } from '../lib/app-context'

const WAITING_TEXT_DBX = {
  connect: 'Connects to the Databricks workspace.',
  silver: 'Loads the ECC file into the silver layer.',
  rulebook: 'Loads the Databricks rule book.',
  approve: 'Waits for approval.',
  codegen: 'The AI writes the PySpark notebook.',
  transform: 'Runs the notebook; fixes errors with the AI.',
  gold: 'Reads the result from the gold layer.',
  validate: 'Runs the rule book checks on the gold table.',
  report: 'Prepares the validation report.',
}

const WAITING_TEXT = {
  extract: 'Reads the ECC file from SharePoint.',
  mapping: 'Loads the approved rulebook.',
  approve: 'Waits for approval.',
  transform: 'Creates the S/4 rows.',
  validate: 'Checks the result against Databricks.',
  report: 'Prepares the S/4 file and report.',
}

function Attempts({ attempts }) {
  if (!attempts?.length) return null
  return (
    <ul className="mt-2 space-y-1 border-t border-slate-100 pt-2 text-xs">
      {attempts.map((a) => (
        <li key={a.attempt} className="flex flex-wrap items-center gap-1.5">
          <span className={`h-1.5 w-1.5 rounded-full ${a.status === 'succeeded' ? 'bg-emerald-500' : a.status === 'failed' ? 'bg-red-500' : 'bg-brand-500 animate-pulse'}`} />
          <span className="font-medium text-slate-700">Attempt {a.attempt}: {a.status}</span>
          {a.url && <a href={a.url} target="_blank" rel="noreferrer" className="text-navy-700 underline">job run</a>}
          {a.error && <span className="w-full truncate pl-3 text-slate-500" title={a.error}>{a.error}</span>}
          {a.fixed && <span className="w-full pl-3 font-medium text-brand-700">AI fixed the code → retrying</span>}
        </li>
      ))}
    </ul>
  )
}

function AgentCard({ step, st, engine, dbx }) {
  const status = st?.status || 'queued'
  const waiting = (engine === 'databricks' ? WAITING_TEXT_DBX : WAITING_TEXT)[step.id]
  return (
    <div className={`card px-4 py-3.5 ${status === 'running' ? 'border-brand-500/50' : status === 'waiting' ? 'border-amber-300'
      : status === 'failed' ? 'border-red-300' : ''}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="text-[15px] font-semibold text-slate-900">{step.agent}</div>
        <Pill status={status} />
      </div>
      <p className={`mt-2 text-[13px] leading-snug ${status === 'queued' ? 'text-slate-500' : 'text-slate-700'}`}>
        {st?.summary || waiting}
      </p>
      {engine === 'databricks' && step.id === 'transform' && <Attempts attempts={dbx?.attempts} />}
      {engine === 'databricks' && step.id === 'codegen' && dbx?.notebookPath && status === 'done' && (
        <p className="mt-1 truncate text-xs text-slate-500" title={dbx.notebookPath}>{dbx.notebookPath}</p>
      )}
    </div>
  )
}

function Outcome({ run }) {
  if (run.status === 'completed') {
    return (
      <section className="card animate-slidein border-2 border-emerald-300 p-5">
        <div className="flex items-center gap-2 text-[15px] font-bold text-emerald-700"><CheckCircle2 className="h-5 w-5" />Completed</div>
        <p className="mt-1 text-sm text-slate-600">
          {run.engine === 'databricks' ? <>{num(run.metrics?.loadRows)} rows in the gold layer ({run.dbx?.goldTable}).</>
            : <>{num(run.metrics?.loadRows)} rows are ready in the S/4 file.</>}
        </p>
        <Link to={`/reports/${run.id}`} className="btn-primary mt-3"><FileBarChart2 className="h-4 w-4" />Open reports</Link>
      </section>
    )
  }
  if (run.status === 'failed' || run.status === 'rejected') {
    return (
      <section className="card border-2 border-red-200 p-5">
        <div className="flex items-center gap-2 text-[15px] font-bold text-red-700"><XCircle className="h-5 w-5" />{run.status === 'failed' ? 'Failed' : 'Rejected'}</div>
        {run.error && <p className="mt-1 break-words text-sm text-slate-600">{run.error}</p>}
        <Link to="/rulebook" className="btn-outline mt-3">Back to Rulebook</Link>
      </section>
    )
  }
  if (run.status === 'waiting' && !run.active) return null
  return (
    <section className="card flex items-center gap-3 p-5">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-navy-900 text-white animate-pulsering"><Bot className="h-5 w-5" /></div>
      <div className="font-semibold text-slate-900">Processing…</div>
      <Spinner className="ml-auto h-5 w-5 text-brand-600" />
    </section>
  )
}

export default function Agents() {
  const { runId } = useParams()
  const nav = useNavigate()
  const { meta, status } = useApp()
  const runsQ = useAsync(() => api.runs(), [runId])
  useEffect(() => {
    if (!runId && runsQ.data?.runs?.length) nav(`/agents/${runsQ.data.runs[0].id}`, { replace: true })
  }, [runId, runsQ.data, nav])
  const { run, error, refresh } = useRunStream(runId)
  const steps = (run && meta.engines?.[run.engine || 'embedded']) || meta.steps || []

  if (!runId) {
    return (
      <>
        <PageHeader title="Agents" />
        {runsQ.loading ? <Card><Loading /></Card> : (
          <Card><Empty icon={Bot} title="Nothing running yet"
            action={<Link to="/rulebook" className="btn-accent">Go to Rulebook <ArrowRight className="h-4 w-4" /></Link>}>
            Approve a rulebook to start processing.
          </Empty></Card>
        )}
      </>
    )
  }

  return (
    <>
      <PageHeader title="Agents"
        actions={<>
          <select className="input !w-auto !py-1.5 text-xs" value={runId} onChange={(e) => nav(`/agents/${e.target.value}`)}>
            {(runsQ.data?.runs || []).map((r) => <option key={r.id} value={r.id}>{dateTime(r.created)} · {r.id === runId && run ? run.status : r.status}</option>)}
          </select>
          <Link to={`/reports/${runId}`} className="btn-outline">Reports</Link>
        </>}>
        <div className="mt-4"><StatusStrip run={run} /></div>
      </PageHeader>

      <ErrorBox error={error} onRetry={refresh} />
      {!run ? <Card><Loading /></Card> : (
        <div className="space-y-5">
          <Stepper steps={steps} state={run.steps} />
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
            <div className="grid grid-cols-1 content-start gap-3 sm:grid-cols-2">
              {steps.filter((s) => !s.gate).map((s) => (
                <AgentCard key={s.id} step={s} st={run.steps[s.id]} engine={run.engine} dbx={run.dbx} />
              ))}
            </div>
            <div className="space-y-5">
              <DecisionPanel run={run} onDone={refresh} />
              <Outcome run={run} />
              <ValidationCard validation={run.validation} plant={run.engine === 'databricks' ? null : status?.validationPlant} />
            </div>
          </div>
        </div>
      )}
    </>
  )
}
