import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CheckCircle2, Download, FileText, FolderOpen, Play, Sparkles } from 'lucide-react'
import { PageHeader } from '../components/Layout'
import DataTable from '../components/DataTable'
import FilePicker from '../components/FilePicker'
import DatabricksRulebook from '../components/DatabricksRulebook'
import { Card, Empty, ErrorBox, Loading, Segmented, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'
import { useApp } from '../lib/app-context'

function DocumentPanel({ doc, onFetch, onGenerate, generating }) {
  const q = useAsync(() => api.document(doc.path), [doc?.path], { enabled: !!doc })
  return (
    <Card title="Mapping document"
      actions={<button className="btn-outline btn-sm" onClick={onFetch}><FolderOpen className="h-3.5 w-3.5" />{doc ? 'Change' : 'Fetch'}</button>}>
      {!doc ? (
        <Empty icon={FileText} title="No document selected"
          action={<button className="btn-accent" onClick={onFetch}><FolderOpen className="h-4 w-4" />Fetch from SharePoint</button>}>
          Pick the mapping document from SharePoint.
        </Empty>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm">
            <FileText className="h-4 w-4 text-navy-700" />
            <span className="truncate font-semibold text-slate-900">{doc.name}</span>
          </div>
          <ErrorBox error={q.error} onRetry={q.reload} />
          {q.loading ? <Loading label="Reading the document…" /> : q.data && (
            <pre className="max-h-[52vh] overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-4 font-sans text-[13.5px] leading-relaxed text-slate-800 scroll-thin">{q.data.text}</pre>
          )}
          <button className="btn-primary w-full" disabled={generating || !q.data} onClick={onGenerate}>
            {generating ? <Spinner /> : <Sparkles className="h-4 w-4" />}{generating ? 'Generating rulebook…' : 'Generate rulebook'}
          </button>
        </div>
      )}
    </Card>
  )
}

// Columns shown by default; the downloaded file keeps the full template.
const MAIN_COLS = [2, 8, 9, 10, 11]

function RulebookPreview({ preview }) {
  const [all, setAll] = useState(false)
  const columns = useMemo(() => preview.columns.map((c, i) => ({
    i, key: c, label: c, sortable: false, render: (r) => r.cells[i],
    className: (r) => [
      '!whitespace-normal align-top',
      { 2: 'min-w-[150px] font-medium text-slate-800', 8: 'max-w-[110px] [overflow-wrap:anywhere]', 9: 'mono max-w-[110px] [overflow-wrap:anywhere] font-semibold text-navy-800',
        10: 'min-w-[100px]', 11: 'min-w-[260px]' }[i] || '',
      i === 11 && r.generated ? 'bg-[#FFF4D6]' : '',
    ].join(' '),
  })).filter((c) => all || MAIN_COLS.includes(c.i)), [preview, all])
  const rows = useMemo(() => preview.rows.filter((r) => all || r.cells.some((v, i) => v && MAIN_COLS.includes(i))), [preview, all])
  return (
    <div className="space-y-2">
      <div className="flex justify-end">
        <Segmented value={all ? 'all' : 'main'} onChange={(v) => setAll(v === 'all')}
          options={[{ value: 'main', label: 'Main columns' }, { value: 'all', label: 'All columns' }]} />
      </div>
      <DataTable columns={columns} rows={rows} maxHeight="56vh" rowKey={(r) => r.row} blank="" />
    </div>
  )
}

function ApproveBar({ meta }) {
  const { user, toast, marcFile, refreshPending } = useApp()
  const [busy, setBusy] = useState(false)
  const nav = useNavigate()
  const start = async () => {
    setBusy(true)
    try {
      const { runId } = await api.approveAndRun(meta.id, { file: marcFile.path, by: user })
      toast('Approved. Processing started.', 'success')
      refreshPending()
      nav(`/agents/${runId}`)
    } catch (e) { toast(e.message, 'error'); setBusy(false) }
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border-2 border-brand-500/70 bg-brand-50/60 px-4 py-3">
      <div className="text-sm">
        {marcFile ? <>ECC file: <b className="text-slate-900">{marcFile.name}</b></>
          : <>No ECC file selected. <Link to="/extraction" className="font-semibold text-brand-700 underline">Select it in Data Extraction</Link></>}
      </div>
      <button className="btn-accent" disabled={busy || !marcFile} onClick={start}>
        {busy ? <Spinner /> : <Play className="h-4 w-4" />}Approve and start
      </button>
    </div>
  )
}

export default function Rulebook() {
  const { mappingDoc, setMappingDoc, mappingId, setMappingId, status, toast } = useApp()
  const [picker, setPicker] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [pipeline, setPipeline] = useState('embedded')
  const mapQ = useAsync(() => api.mapping(mappingId), [mappingId], { enabled: !!mappingId })
  const meta = mapQ.data?.meta

  const generate = async () => {
    setGenerating(true)
    try {
      const m = await api.generate(mappingDoc.path)
      setMappingId(m.id)
    } catch (e) { toast(e.message, 'error') } finally { setGenerating(false) }
  }

  return (
    <>
      <PageHeader title="Rulebook" />
      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <DocumentPanel doc={mappingDoc} generating={generating} onFetch={() => setPicker(true)} onGenerate={generate} />

        <Card title={pipeline === 'databricks' ? 'Databricks rule book' : 'Rulebook'}
          actions={meta && <>
            <span className="text-xs font-medium text-slate-500">Run on</span>
            <Segmented value={pipeline} onChange={setPipeline} options={[
              { value: 'embedded', label: 'Embedded engine' }, { value: 'databricks', label: 'Databricks' }]} />
            {pipeline === 'embedded' && <a className="btn-outline btn-sm" href={api.mappingDownloadUrl(meta.id)}><Download className="h-3.5 w-3.5" />Download</a>}
          </>}>
          {meta && pipeline === 'databricks' ? <DatabricksRulebook /> : generating ? <Loading label="Creating the rulebook…" hint="The AI agent is reading the document." />
            : !mappingId ? (
              <Empty icon={Sparkles} title="Rulebook appears here">Fetch a mapping document and click Generate rulebook.</Empty>
            ) : mapQ.loading && !mapQ.data ? <Loading /> : mapQ.error ? <ErrorBox error={mapQ.error} onRetry={mapQ.reload} /> : meta && (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                  <span>From <b className="text-slate-700">{meta.sourceDoc.name}</b></span>
                  <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-sm bg-[#FFF4D6] ring-1 ring-amber-200" />Written from the document</span>
                  {meta.status === 'approved' && <span className="ml-auto flex items-center gap-1 font-semibold text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" />Approved</span>}
                </div>
                <RulebookPreview preview={mapQ.data} />
                <ApproveBar meta={meta} />
              </div>
            )}
        </Card>
      </div>

      <FilePicker open={picker} onClose={() => setPicker(false)} title="Select the mapping document"
        startPath={status?.mappingsFolder || ''} accept={['.pdf', '.docx', '.txt', '.md']}
        onPick={(f) => { setMappingDoc(f); setMappingId(null) }} />
    </>
  )
}
